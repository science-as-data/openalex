"""Pairwise scoring for OpenAlex <-> Scopus journal candidates.

One additive log-odds-style score combines ISSN agreement, title similarity,
publisher agreement, coverage-year overlap and country, with hard penalties
for the classic false-positive traps (Physical Review A vs B, Journal vs
Journal Letters, supplements, reused ISSNs). Weights in ``W`` and thresholds
in ``THRESH`` are starting points; refit them on a coded gold set
(``match.py eval-sample`` / ``eval-score``).

Title similarity is an IDF-weighted soft Jaccard over normalized tokens
(``normalize.fuzzy_forms``): tokens align when identical, when normalized
Levenshtein >= 0.85 on tokens of 5+ letters (typos, inflections), or when one is a 3-5 letter prefix
abbreviation of the other ("surg" ~ "surgery"). Rare tokens dominate, so
"journal of" contributes little and "medical" vs "dental" decides.

Run ``python linkage.py --test`` for the must-not-match cases.
"""
from __future__ import annotations

import math
import sys

from rapidfuzz import fuzz
from rapidfuzz.distance import LCSseq, Levenshtein

from normalize import discriminators, fuzzy_forms, publisher_key

W = {
    "issn_1": 4.0,            # exactly one shared ISSN
    "issn_2": 6.0,            # two or more shared ISSNs
    "issn_conflict": -2.0,    # both sides have ISSNs, none shared
    "title_slope": 5.0,       # 0 at title_floor, +title_slope at 1.0
    "title_floor": 0.85,
    "title_mid": 0.60,        # [mid, floor): neutral
    "title_low": -2.0,        # below mid
    "pub_strong": 1.5,        # publisher keys agree (>= 0.9)
    "pub_weak": 0.5,          # 0.7-0.9
    "pub_conflict": -1.0,     # both present and clearly different
    "year_overlap": 1.0,
    "year_conflict": -2.0,    # both ranges known, no overlap
    "country": 0.5,
    "issn_reuse": -2.0,       # shared ISSN but no year overlap and dissimilar title
}
THRESH = {
    "review": 2.0,            # store pairs at or above this
    "accept_issn": 3.5,       # issn_l / issn_any: one ISSN needs title >= 0.6 or publisher
    "accept_title": 5.0,      # title_exact / title_fuzzy: needs publisher + years, no ISSN conflict
    "fuzzy_block": 75,        # token_sort_ratio cutoff for candidate blocking
    "fuzzy_topk": 10,
}
DEFAULT_IDF = 2.0
TYPO_SIM = 0.85        # normalized Levenshtein for aligning near-identical tokens
ORDER_WEIGHT = 0.2     # share of the title score that depends on token order
SUBTITLE_WEIGHT = 0.3
_PREFIX_OK3 = {"sci", "med", "rev", "ann", "bul", "ind", "eng", "soc", "env",
               "geo", "bio", "psy", "ecol", "eco", "mat", "app", "com", "hum"}


# --------------------------------------------------------------- IDF --------

def build_idf(token_lists) -> dict[str, float]:
    df: dict[str, int] = {}
    n = 0
    for toks in token_lists:
        n += 1
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    return {t: max(0.1, math.log((n + 1) / (c + 1))) for t, c in df.items()}


# --------------------------------------------------------- title sim --------

def _aligned(a: str, b: str) -> bool:
    if a == b:
        return True
    if a.startswith("§") or b.startswith("§") or a.isdigit() or b.isdigit():
        return False
    if len(a) >= 5 and len(b) >= 5 and Levenshtein.normalized_similarity(a, b) >= TYPO_SIM:
        return True
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    return (l.startswith(s) and len(l) >= len(s) + 2
            and (4 <= len(s) <= 5 or s in _PREFIX_OK3))


def _weighted(toks: list[str], idf: dict[str, float]) -> list[tuple[str, float]]:
    """(token, weight) pairs; tokens after the subtitle marker weigh 0.3x."""
    out, mult = [], 1.0
    for t in toks:
        if t == "¦":
            mult = SUBTITLE_WEIGHT
            continue
        out.append((t, idf.get(t, DEFAULT_IDF) * mult))
    return out


def title_similarity(a: list[str], b: list[str], idf: dict[str, float]) -> float:
    """IDF-weighted soft Jaccard in [0, 1] with discriminator penalties."""
    wa, wb = _weighted(a, idf), _weighted(b, idf)
    if not wa or not wb:
        return 0.0
    used_a: set[int] = set()
    used_b: set[int] = set()
    aligned = 0.0
    # pass 1: identical tokens; pass 2: fuzzy alignment on the leftovers
    for exact in (True, False):
        for i, (t, wt) in enumerate(wa):
            if i in used_a:
                continue
            for j, (u, wu) in enumerate(wb):
                if j in used_b:
                    continue
                if (t == u) if exact else _aligned(t, u):
                    used_a.add(i)
                    used_b.add(j)
                    aligned += (wt + wu) / 2
                    break
    denom = sum(w for _, w in wa) + sum(w for _, w in wb) - aligned
    sim = aligned / denom if denom > 0 else 0.0
    # token order: "Journal of Education Science" is not "Journal of Science Education"
    ta, tb = [t for t in a if t != "¦"], [t for t in b if t != "¦"]
    order = LCSseq.similarity(ta, tb) / min(len(ta), len(tb))
    sim *= (1 - ORDER_WEIGHT) + ORDER_WEIGHT * order
    da, db = discriminators(a), discriminators(b)
    if da["section"] and db["section"] and da["section"] != db["section"]:
        return 0.0
    if bool(da["section"]) != bool(db["section"]):
        sim *= 0.5
    for cls in ("content", "scope"):
        if da[cls] ^ db[cls]:
            sim *= 0.6
    return sim


def best_title_similarity(oa_forms: list[list[str]], sc_forms: list[list[str]],
                          idf: dict[str, float]) -> tuple[float, int]:
    best, best_i = 0.0, -1
    for i, f in enumerate(oa_forms):
        for g in sc_forms:
            s = title_similarity(f, g, idf)
            if s > best:
                best, best_i = s, i
    return best, best_i


# ------------------------------------------------------------ scoring -------

def year_overlap(oa_first, oa_last, sc_start, sc_end) -> int | None:
    """Years of overlap between the two ranges; None when either is unknown."""
    if oa_first is None or sc_start is None:
        return None
    lo = max(oa_first, sc_start)
    hi = min(oa_last if oa_last is not None else 9999,
             sc_end if sc_end is not None else 9999)
    return hi - lo + 1


def score_pair(oa: dict, sc: dict, tsim: float) -> tuple[float, dict]:
    """``oa``/``sc`` are the prepared dicts built in match.py (keys: issns set,
    pub key, first/last or coverage_start/end, country)."""
    ev: dict = {}
    s = 0.0
    shared = sorted(oa["issns"] & sc["issns"])
    ev["shared_issns"] = shared
    if len(shared) >= 2:
        s += W["issn_2"]
    elif len(shared) == 1:
        s += W["issn_1"]
    elif oa["issns"] and sc["issns"]:
        s += W["issn_conflict"]
        ev["issn_conflict"] = True

    ev["title_sim"] = round(tsim, 3)
    if tsim >= W["title_floor"]:
        s += W["title_slope"] * (tsim - W["title_floor"]) / (1 - W["title_floor"])
    elif tsim < W["title_mid"]:
        s += W["title_low"]

    if oa["pub"] and sc["pub"]:
        p = fuzz.token_set_ratio(oa["pub"], sc["pub"]) / 100
        ev["pub_sim"] = round(p, 2)
        if p >= 0.9:
            s += W["pub_strong"]
        elif p >= 0.7:
            s += W["pub_weak"]
        else:
            s += W["pub_conflict"]

    ov = year_overlap(oa.get("first"), oa.get("last"), sc.get("coverage_start"), sc.get("coverage_end"))
    ev["year_overlap"] = ov
    if ov is not None:
        s += W["year_overlap"] if ov > 0 else W["year_conflict"]
        if shared and ov <= 0 and tsim < W["title_mid"]:
            s += W["issn_reuse"]
            ev["issn_reuse_suspect"] = True

    if oa.get("country") and sc.get("country") and oa["country"] == sc["country"]:
        s += W["country"]
    return round(s, 3), ev


def assign_tier(method: str, score: float, shared_issn: bool) -> int | None:
    """1 accept, 2 review, None = do not store."""
    accept = THRESH["accept_issn"] if method.startswith("issn") else THRESH["accept_title"]
    if score >= accept:
        return 1
    if score >= THRESH["review"] or shared_issn:
        return 2
    return None


def probability(score: float) -> float:
    """Sigmoid of the score for reporting only; decisions use thresholds."""
    return 1 / (1 + math.exp(-(score - 3.0)))


# ---------------------------------------------------------------- tests -----

_CORPUS = [
    "Physical Review A", "Physical Review B", "Physical Review E", "Physical Review Letters",
    "Physical Review", "Journal of Physics A: Mathematical and Theoretical", "Journal of Physics D",
    "Journal of Physics: Conference Series", "European Journal of Cancer", "Journal of Cancer",
    "Nature Cell Biology", "Nature Reviews Molecular Cell Biology", "Revista Brasileira de Zootecnia",
    "Revista Brasileira de Zoologia", "Journal of the American Medical Association",
    "Journal of the American Dental Association", "ChemInform", "Chemischer Informationsdienst",
    "Annals of Surgery", "Annals of Surgical Oncology", "Zeitschrift für Naturforschung A",
    "Zeitschrift fur Naturforschung - Section A Journal of Physical Sciences",
    "Zeitschrift für Naturforschung B", "The Lancet", "Lancet, The", "Journal of Biological Chemistry",
    "Journal of Chemical Physics", "Journal of Applied Physics", "American Journal of Medicine",
    "British Journal of Surgery", "Journal of Surgical Research", "International Journal of Cancer",
    "Cancer Research", "Journal of Clinical Oncology", "Revista de Biologia Tropical",
    "Journal of the American Chemical Society", "Journal of Dental Research", "Nature", "Science",
    "Cell", "Nature Medicine", "Journal of Physics B", "Journal of Physics C", "Physical Review C",
    "Physical Review D", "Zeitschrift für Physik", "Journal of Molecular Biology", "Molecular Cell",
    "Brazilian Journal of Medical and Biological Research", "Journal of Animal Science",
    "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "IEEE Trans. on Pattern Analysis & Machine Intelligence",
]
MUST_MATCH = [
    ("The Lancet", "Lancet, The"),
    ("Physical Review B", "Physical Review, Section B"),
    ("IEEE Trans. on Pattern Analysis & Machine Intelligence",
     "IEEE Transactions on Pattern Analysis and Machine Intelligence"),
    ("SHILAP Revista de lepidopterología", "SHILAP Revista de Lepidopterologia"),
    ("Zeitschrift für Naturforschung A",
     "Zeitschrift fur Naturforschung - Section A Journal of Physical Sciences"),
    ("Sustainability", "Sustainability (Switzerland)"),
    ("Philippine Journal of Internal Medicine", "Phillippine Journal of Internal Medicine"),
    ("South African dental journal",
     "South African dental journal. Suid Afrikaanse tandheelkundige tydskrif"),
]
MUST_NOT = [
    ("Physical Review B", "Physical Review E"),
    ("Physical Review", "Physical Review Letters"),
    ("Journal of Physics A", "Journal of Physics D"),
    ("Journal of Physics: Conference Series", "Journal of Physics A"),
    ("European Journal of Cancer", "Journal of Cancer"),
    ("Nature Cell Biology", "Nature Reviews Molecular Cell Biology"),
    ("Revista Brasileira de Zootecnia", "Revista Brasileira de Zoologia"),
    ("Journal of the American Medical Association", "Journal of the American Dental Association"),
    ("ChemInform", "Chemischer Informationsdienst"),
    ("Annals of Surgery", "Annals of Surgical Oncology"),
    ("Zeitschrift für Naturforschung A", "Zeitschrift für Naturforschung B"),
    ("Journal of Hydroecology", "Journal of Hydrology"),
    ("Journal of Neuroparasitology", "Journal of Neurophysiology"),
    ("Biomics", "Biomimetics"),
    ("Pontica", "Phonetica"),
    ("epiDEMES", "Epidemics"),
]
ORDER_SENSITIVE = [   # bag-of-words says 1.0; must land below 0.97 so title alone cannot accept
    ("Journal of Education Science", "Journal of Science Education"),
    ("Journal of Food and Nutrition Sciences", "Journal of Food Science and Nutrition"),
]


def _run_tests() -> int:
    idf = build_idf(f for t in _CORPUS for f in fuzzy_forms(t))
    fails = 0
    for a, b in MUST_MATCH:
        s, _ = best_title_similarity(fuzzy_forms(a), fuzzy_forms(b), idf)
        ok = s >= 0.70
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} match     {s:.2f}  {a!r} ~ {b!r}")
    for a, b in MUST_NOT:
        s, _ = best_title_similarity(fuzzy_forms(a), fuzzy_forms(b), idf)
        ok = s < 0.70
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} not-match {s:.2f}  {a!r} ~ {b!r}")
    for a, b in ORDER_SENSITIVE:
        s, _ = best_title_similarity(fuzzy_forms(a), fuzzy_forms(b), idf)
        ok = s < 0.97
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} order     {s:.2f}  {a!r} ~ {b!r}")
    print(f"{fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_run_tests() if "--test" in sys.argv else 0)
