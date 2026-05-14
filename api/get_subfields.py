"""Retrieve the subfields associated with an OpenAlex field.

Usage:
    python get_subfields.py "Computer Science"
    python get_subfields.py 17              # field ID number
    python get_subfields.py --list          # list all fields
"""

import argparse
import sys
import requests

BASE_URL = "https://api.openalex.org"


def list_fields():
    """Print all available fields."""
    resp = requests.get(f"{BASE_URL}/fields", params={"per_page": 50})
    resp.raise_for_status()
    fields = resp.json()["results"]
    print(f"{'ID':<6} {'Field':<45} {'Domain'}")
    print("-" * 80)
    for f in sorted(fields, key=lambda x: x["display_name"]):
        fid = f["id"].split("/")[-1]
        print(f"{fid:<6} {f['display_name']:<45} {f['domain']['display_name']}")


def resolve_field(query):
    """Resolve a field by numeric ID or search string. Returns the field object."""
    if query.isdigit():
        resp = requests.get(f"{BASE_URL}/fields/{query}")
        if resp.status_code == 404:
            sys.exit(f"No field found with ID {query}")
        resp.raise_for_status()
        return resp.json()

    resp = requests.get(f"{BASE_URL}/fields", params={"search": query})
    resp.raise_for_status()
    results = resp.json()["results"]
    if not results:
        sys.exit(f"No field found matching '{query}'")
    return results[0]


def get_subfields(field):
    """Fetch subfields for a field, including topic counts."""
    field_id = field["id"].split("/")[-1]
    resp = requests.get(
        f"{BASE_URL}/subfields",
        params={"filter": f"field.id:{field_id}", "per_page": 50},
    )
    resp.raise_for_status()
    return resp.json()["results"]


def main():
    parser = argparse.ArgumentParser(description="Get subfields for an OpenAlex field")
    parser.add_argument("field", nargs="?", help="Field name (search) or numeric ID")
    parser.add_argument("--list", action="store_true", help="List all available fields")
    args = parser.parse_args()

    if args.list:
        list_fields()
        return

    if not args.field:
        parser.print_help()
        sys.exit(1)

    field = resolve_field(args.field)
    print(f"\nField: {field['display_name']}")
    print(f"Domain: {field['domain']['display_name']}\n")

    subfields = get_subfields(field)
    print(f"{'ID':<6} {'Subfield':<50} {'Topics':>8}  {'Works':>12}")
    print("-" * 80)
    for sf in sorted(subfields, key=lambda x: x["works_count"], reverse=True):
        sfid = sf["id"].split("/")[-1]
        n_topics = len(sf.get("topics", []))
        print(f"{sfid:<6} {sf['display_name']:<50} {n_topics:>8}  {sf['works_count']:>12,}")

    print(f"\nTotal: {len(subfields)} subfields")


if __name__ == "__main__":
    main()
