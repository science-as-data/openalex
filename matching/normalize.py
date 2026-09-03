"""Normalization of ISSNs, journal titles and publisher names.

Shared by every matching tier so that both sides (OpenAlex and Scopus) are
transformed identically. Two title representations are produced:

* ``title_keys(t)``  - a set of deterministic keys for exact matching:
  diacritics stripped, casefolded, medium qualifiers "(Online)" dropped,
  "Title, The" un-inverted, parallel titles "A = B" / "A / B" split, section
  markers normalized ("Part II" -> "2"), unambiguous abbreviations expanded,
  leading articles stripped in EN/FR/DE/ES/IT/PT.
* ``fuzzy_forms(t)`` - token lists for fuzzy scoring: same pipeline but articles
  kept and section markers kept as distinct ``§x`` tokens, because "Physical
  Review A" vs "B" must NOT match.

Run ``python normalize.py --test`` to execute the built-in test cases.
"""
from __future__ import annotations

import re
import sys
import unicodedata

# ---------------------------------------------------------------- ISSN ------

_ISSN_JUNK = re.compile(r"[^0-9X]")


def norm_issn(s: str | None, validate: bool = True) -> str | None:
    """Return the 8-character ISSN (no hyphen, uppercase X) or None.

    With ``validate`` the mod-11 check digit must be correct; invalid ISSNs
    are a known source of spurious matches, so the matcher drops them.
    """
    if not s:
        return None
    v = _ISSN_JUNK.sub("", str(s).upper())
    if len(v) == 7:            # leading zero lost (common in spreadsheets)
        v = "0" + v
    if len(v) != 8 or not v[:7].isdigit():
        return None
    if validate:
        total = sum((8 - i) * int(c) for i, c in enumerate(v[:7]))
        check = (11 - total % 11) % 11
        if v[7] != ("X" if check == 10 else str(check)):
            return None
    return v


def hyphen_issn(v: str) -> str:
    return f"{v[:4]}-{v[4:]}"


# --------------------------------------------------------------- titles -----

MEDIUM_PAREN = re.compile(
    r"\((?:[^()]*\b(?:online|print|internet|cd-?rom|electronic|digital|web|"
    r"microform|microfiche|e-?journal)\b[^()]*)\)", re.I)
TRAILING_ARTICLE = re.compile(
    r",\s*(?:the|a|an|le|la|les|l'|der|die|das|el|los|las|il|lo|gli)\s*$", re.I)
SECTION_WORD = re.compile(
    r"\b(?:part|section|sect|series|ser|teil|serie|série|parte|sezione)\.?\s+"
    r"([A-Za-z]|\d{1,2}|[IVXivx]{1,4})\b(?![-\w])", re.I)
# A lone capital A-H preceded by a space and followed by a separator or the
# end: "Physical Review B", "Journal of Physics A: Mathematical ...".
SECTION_LETTER = re.compile(r"(?<=\s)([A-H])(?=\s*(?:[:.\-–—(/,;]|$))")
ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6",
         "vii": "7", "viii": "8", "ix": "9", "x": "10"}

ARTICLES = {"the", "a", "an", "le", "la", "les", "l", "der", "die", "das",
            "el", "los", "las", "il", "lo", "gli", "o", "os", "as", "un",
            "une", "una", "um", "uma"}

# Only expansions that are unambiguous. NOT: rev (review/revista/revue),
# ann (annals/annalen/annales), phys, chem, biol, sci, med - handled by
# prefix alignment in linkage.title_similarity instead.
ABBR = {
    "j": "journal", "jour": "journal", "jnl": "journal",
    "trans": "transactions", "proc": "proceedings",
    "int": "international", "intl": "international",
    "z": "zeitschrift", "natl": "national", "assoc": "association",
    "soc": "society", "acad": "academy", "univ": "university",
    "q": "quarterly", "bull": "bulletin", "suppl": "supplement",
    "conf": "conference", "symp": "symposium", "amer": "american",
    "eur": "european", "res": "research",
}
# Single-letter abbreviations expand only at position 0 or when dotted.
_SINGLE = {k for k in ABBR if len(k) == 1}

CHARS = {"&": " and ", "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
         "ø": "o", "Ø": "o", "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ð": "d",
         "þ": "th", "ı": "i"}
CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
       "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
       "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
       "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
       "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
       "є": "ye", "і": "i", "ї": "yi", "ґ": "g"}

SUBTITLE_SEP = re.compile(r":\s|\s[-–—]\s")
_NON_TOKEN = re.compile(r"[^a-z0-9§¦]+")


def to_ascii(s: str) -> str:
    """Lowercase ASCII: ligatures, Cyrillic transliteration, NFKD, no marks."""
    for k, v in CHARS.items():
        s = s.replace(k, v)
    s = "".join(CYR.get(c, c) for c in s.lower())
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def _mark_sections(s: str) -> str:
    def word(m):
        x = m.group(1).lower()
        if x in ROMAN and len(x) > 1 or x in {"i", "v", "x"}:
            x = ROMAN[x]
        return f" §{x} "
    s = SECTION_WORD.sub(word, s)
    s = SECTION_LETTER.sub(lambda m: f" §{m.group(1).lower()} ", s)
    return s


def _tokens(part: str) -> list[str]:
    s = MEDIUM_PAREN.sub(" ", part)
    s = TRAILING_ARTICLE.sub("", s)
    s = SUBTITLE_SEP.sub(" ¦ ", s, count=1)     # subtitle marker, down-weighted in fuzzy scoring
    s = re.sub(r"\(([^()]*)\)", r" ¦ \1 ", s)    # qualifiers "(Switzerland)", "(London)" likewise
    acronyms = {a.lower() for a in re.findall(r"\b[A-Z]{2,}\b", s)}
    dotted = {d.lower() for d in re.findall(r"\b([A-Za-z]{1,6})\.", s)}
    s = _mark_sections(s)
    toks = _NON_TOKEN.sub(" ", to_ascii(s)).split()
    out = []
    for i, t in enumerate(toks):
        if t in ABBR and t not in acronyms and (t not in _SINGLE or i == 0 or t in dotted):
            t = ABBR[t]
        out.append(t)
    return out


def split_parallel(title: str) -> list[str]:
    """'A = B' and 'A/B' parallel titles -> [A, B]; otherwise [title]."""
    if " = " in title:
        ps = [p for p in re.split(r"\s+=\s+", title) if p.strip()]
        if all(len(p.split()) >= 2 for p in ps):
            return ps
    if "/" in title:
        ps = [p for p in re.split(r"\s*/\s*", title) if p.strip()]
        if len(ps) > 1 and len({p.casefold() for p in ps}) == 1:
            return [ps[0]]                      # "Gewina/GeWina"
        if len(ps) > 1 and all(len(p.split()) >= 3 for p in ps):
            return ps
    if ". " in title:                           # "English title. Titre parallèle"
        ps = [p for p in re.split(r"(?<=[a-z\u00e0-\u024f])\.\s+(?=[A-Z])", title) if p.strip()]
        if len(ps) > 1 and all(len(p.split()) >= 3 for p in ps):
            return ps
    return [title]


def strip_articles(toks: list[str]) -> list[str]:
    while len(toks) > 1 and toks[0] in ARTICLES:
        toks = toks[1:]
    return toks


def title_keys(title: str | None, with_head: bool = True) -> set[str]:
    """Exact-match keys. With ``with_head`` also the part before the first
    subtitle separator (': ' or ' - ') when it has >= 3 tokens; head keys
    generate candidates only, the score decides."""
    if not title:
        return set()
    keys = set()
    parts = split_parallel(title)
    if with_head:
        for p in list(parts):
            head = re.split(r":\s|\s[-–—]\s", p, maxsplit=1)[0]
            if head != p and len(head.split()) >= 3:
                parts.append(head)
    for p in parts:
        toks = strip_articles([t.lstrip("§") for t in _tokens(p) if t != "¦"])
        if toks:
            keys.add(" ".join(toks))
    return keys


def fuzzy_forms(title: str | None) -> list[list[str]]:
    """Token lists for fuzzy scoring: leading articles stripped, sections kept
    as ``§x`` tokens, the first subtitle separator kept as ``¦``."""
    if not title:
        return []
    return [t for t in (strip_articles(_tokens(p)) for p in split_parallel(title)) if t]


def search_string(title: str | None) -> str | None:
    """What to send to the Serial Title API ``title=`` substring search:
    original casing and punctuation, medium qualifiers removed, ', The'
    un-inverted, leading article dropped, first parallel part only."""
    if not title:
        return None
    s = split_parallel(title)[0]
    s = MEDIUM_PAREN.sub(" ", s)
    s = TRAILING_ARTICLE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;")
    first, _, rest = s.partition(" ")
    if first.lower() in ARTICLES and rest:
        s = rest
    return s or None


GENERIC_HEADS = {"bulletin", "proceedings", "annals", "journal", "review",
                 "reviews", "transactions", "revista", "zeitschrift", "acta",
                 "archives", "letters", "reports", "studies", "papers",
                 "notes", "revue", "annales", "boletin", "anales", "cahiers",
                 "quarterly", "magazine", "newsletter", "yearbook"}


def is_generic(title: str | None) -> bool:
    """Titles too short/generic for a substring search (costs quota, returns junk)."""
    if not title:
        return True
    toks = strip_articles([t.lstrip("§") for t in _tokens(split_parallel(title)[0]) if t != "¦"])
    content = [t for t in toks if t not in {"of", "the", "and", "de", "der", "des", "di", "du"}]
    return len(content) <= 1 or (len(content) <= 2 and content[0] in GENERIC_HEADS)


# ------------------------------------------------------------- publisher ----

_PUB_DROP = {"ltd", "inc", "gmbh", "bv", "b", "v", "sa", "llc", "plc", "co",
             "kg", "ag", "publishing", "publishers", "publications",
             "publisher", "verlag", "press", "group", "limited", "corporation",
             "corp", "the", "of", "and", "company", "srl", "spa", "pvt", "pty"}
_PUB_ALIAS = [
    (("elsevier", "cell", "sciencedirect"), "elsevier"),
    (("springer", "nature", "biomed", "bmc"), "springer nature"),
    (("wiley", "blackwell"), "wiley"),
    (("taylor", "francis", "routledge", "informa"), "taylor francis"),
    (("sage",), "sage"),
    (("oxford",), "oxford university"),
    (("cambridge",), "cambridge university"),
    (("de", "gruyter"), "de gruyter"),
    (("emerald",), "emerald"),
    (("mdpi", "multidisciplinary digital"), "mdpi"),
    (("frontiers",), "frontiers"),
    (("ieee",), "ieee"),
    (("lippincott", "wolters", "kluwer", "ovid"), "wolters kluwer"),
    (("karger",), "karger"),
    (("thieme",), "thieme"),
    (("hindawi",), "hindawi"),
    (("inderscience",), "inderscience"),
    (("iop",), "iop"),
    (("acs", "american chemical society"), "american chemical society"),
]


def publisher_key(s: str | None) -> str:
    if not s:
        return ""
    toks = [t for t in _NON_TOKEN.sub(" ", to_ascii(s)).split() if t not in _PUB_DROP]
    joined = " ".join(toks)
    for needles, canon in _PUB_ALIAS:
        if any(n in toks or (" " in n and n in joined) for n in needles):
            return canon
    return joined


# ----------------------------------------------------------- discriminators --

CONTENT_TOKENS = {"letters", "supplement", "supplements", "abstracts",
                  "reviews", "proceedings", "bulletin", "newsletter",
                  "communications", "transactions", "reports", "express",
                  "rapid", "open", "plus", "one", "x", "advances", "annual",
                  "yearbook", "digest", "cases", "case", "education",
                  "practice", "methods", "protocols", "perspectives", "trends",
                  "series", "conference", "symposium", "workshop"}
SCOPE_TOKENS = {"international", "european", "american", "british", "national",
                "world", "asian", "african", "indian", "chinese", "japanese",
                "russian", "canadian", "australian", "german", "french",
                "italian", "spanish", "brazilian", "latin", "global", "new",
                "pacific", "nordic", "scandinavian", "korean", "turkish",
                "iranian", "polish", "mexican", "egyptian"}


def discriminators(toks: list[str]) -> dict[str, set[str]]:
    toks = [t for t in toks if t != "¦"]
    return {
        "section": {t for t in toks if t.startswith("§")},
        "content": {t for t in toks if t in CONTENT_TOKENS},
        "scope": {t for t in toks if t in SCOPE_TOKENS},
    }


# ----------------------------------------------------------------- tests ----

KEY_CASES = [
    ("The Lancet", {"lancet"}),
    ("Lancet, The", {"lancet"}),
    ("SHILAP Revista de lepidopterología", {"shilap revista de lepidopterologia"}),
    ("Proceedings of SPIE, the International Society for Optical Engineering/Proceedings of SPIE",
     {"proceedings of spie the international society for optical engineering", "proceedings of spie"}),
    ("Proceedings of SPIE - The International Society for Optical Engineering",
     {"proceedings of spie the international society for optical engineering", "proceedings of spie"}),
    ("ChemInform (Weinheim. Print)", {"cheminform"}),
    ("Chemischer Informationsdienst (CD-ROM)", {"chemischer informationsdienst"}),
    ("Bulletin of miscellaneous Information, Kew", {"bulletin of miscellaneous information kew"}),
    ("Physical Review B", {"physical review b"}),
    ("Physical Review, Section B", {"physical review b"}),
    ("Nature Reviews. Molecular Cell Biology", {"nature reviews molecular cell biology"}),
    ("Zeitschrift für Naturforschung A", {"zeitschrift fur naturforschung a"}),
    ("Z. Naturforsch. A", {"zeitschrift naturforsch a"}),
    ("IEEE Trans. on Pattern Analysis & Machine Intelligence",
     {"ieee transactions on pattern analysis and machine intelligence"}),
    ("Revista Brasileira de Zootecnia = Brazilian Journal of Animal Science",
     {"revista brasileira de zootecnia", "brazilian journal of animal science"}),
    ("Journal of Physics: Conference Series",
     {"journal of physics conference series", "journal of physics"}),
    ("Comptes Rendus. Mathématique", {"comptes rendus mathematique"}),
    ("Annals of Surgery (Online)", {"annals of surgery"}),
    ("Journal of Physiology (London)", {"journal of physiology london"}),
    ("Les Cahiers de Droit", {"cahiers de droit"}),
    ("J. Am. Chem. Soc.", {"journal am chem society"}),
    ("Advances in Mathematics, Part II", {"advances in mathematics 2"}),
    ("Œuvres & Critiques", {"oeuvres and critiques"}),
    ("Журнал физической химии", {"zhurnal fizicheskoi khimii"}),
    ("Journal of Physics A: Mathematical and Theoretical",
     {"journal of physics a mathematical and theoretical", "journal of physics a"}),
]

ISSN_CASES = [("0378-5955", "03785955"), ("0140-6736", "01406736"),
              ("1474-547x", "1474547X"), ("2950631X", "2950631X"),
              ("0378-5956", None), ("123", None), (None, None),
              ("3090566", "03090566")]


def _run_tests() -> int:
    fails = 0
    for inp, want in KEY_CASES:
        got = title_keys(inp)
        if got != want:
            fails += 1
            print(f"FAIL key  {inp!r}\n   want {sorted(want)}\n   got  {sorted(got)}")
    for inp, want in ISSN_CASES:
        got = norm_issn(inp)
        if got != want:
            fails += 1
            print(f"FAIL issn {inp!r}: want {want!r} got {got!r}")
    print(f"{len(KEY_CASES) + len(ISSN_CASES) - fails} passed, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(_run_tests())
    for arg in sys.argv[1:]:
        print(arg, "->", sorted(title_keys(arg)), fuzzy_forms(arg))
