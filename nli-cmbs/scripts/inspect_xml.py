"""Inspect an EX-102 XML file and print its structure.

Usage: python scripts/inspect_xml.py <path_to_xml>
       python scripts/inspect_xml.py tests/fixtures/ex102_bmark_2024_v6.xml
"""

import sys
from pathlib import Path

from lxml import etree

NS = "http://www.sec.gov/edgar/document/absee/cmbs/assetdata"
NSP = f"{{{NS}}}"


def inspect(xml_path: str) -> None:
    tree = etree.parse(xml_path)
    root = tree.getroot()

    # Root tag and namespaces
    print(f"File: {xml_path}")
    print(f"File size: {Path(xml_path).stat().st_size:,} bytes")
    print(f"Root tag: {root.tag}")
    print(f"Namespaces: {root.nsmap}")
    print()

    # Find all loan/asset elements
    assets = root.findall(f"{NSP}assets")
    print(f"Total loan count: {len(assets)}")
    print()

    # Show first 3 loans
    for i, asset in enumerate(assets[:3]):
        print(f"{'='*60}")
        print(f"LOAN {i+1}")
        print(f"{'='*60}")

        for child in asset:
            tag = child.tag.replace(f"{{{NS}}}", "")

            if tag == "property":
                print("  [property]")
                for prop_child in child:
                    ptag = prop_child.tag.replace(f"{{{NS}}}", "")
                    print(f"    {ptag}: {prop_child.text}")
            else:
                print(f"  {tag}: {child.text}")

        print()

    # Collect all unique element names across entire file
    all_asset_tags = set()
    all_property_tags = set()
    for asset in assets:
        for child in asset:
            tag = child.tag.replace(f"{{{NS}}}", "")
            all_asset_tags.add(tag)
            if tag == "property":
                for prop_child in child:
                    ptag = prop_child.tag.replace(f"{{{NS}}}", "")
                    all_property_tags.add(ptag)

    print(f"{'='*60}")
    print("ALL UNIQUE ELEMENT NAMES")
    print(f"{'='*60}")
    print(f"\nAsset-level ({len(all_asset_tags)} unique):")
    for tag in sorted(all_asset_tags):
        print(f"  {tag}")

    print(f"\nProperty-level ({len(all_property_tags)} unique):")
    for tag in sorted(all_property_tags):
        print(f"  {tag}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_ex102_xml>")
        print(f"Example: {sys.argv[0]} tests/fixtures/ex102_bmark_2024_v6.xml")
        sys.exit(1)

    inspect(sys.argv[1])
