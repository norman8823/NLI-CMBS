"""
Fix data quality issues directly in the database:
1. "NA" property names stored as literal strings -> set to null
2. A/B note loans missing parent-child linking -> link via prospectus_loan_id pattern
"""

import asyncio
import re
import sys

from sqlalchemy import text

sys.path.insert(0, ".")

from nli_cmbs.db.session import async_session_factory  # noqa: E402

AB_PATTERN = re.compile(r"^(\d+)([A-Za-z]+)$")


async def main():
    async with async_session_factory() as session:
        # Fix 1: NULL out "NA" property names
        result = await session.execute(text(
            "UPDATE loans SET property_name = NULL "
            "WHERE property_name IN ('NA', 'N/A', 'None', 'NONE', 'n/a', '')"
        ))
        na_fixed = result.rowcount
        print(f"Fix 1: Set {na_fixed} 'NA' property_name values to NULL")

        # Also fix properties table
        result = await session.execute(text(
            "UPDATE properties SET property_name = NULL "
            "WHERE property_name IN ('NA', 'N/A', 'None', 'NONE', 'n/a', '')"
        ))
        na_props_fixed = result.rowcount
        if na_props_fixed:
            print(f"  Also fixed {na_props_fixed} property records")

        # Fix 2: Link A/B notes to parents
        # Get all loans with A/B-style IDs that have no parent
        result = await session.execute(text("""
            SELECT l.id, l.deal_id, l.prospectus_loan_id
            FROM loans l
            WHERE l.prospectus_loan_id ~ '^[0-9]+[A-Za-z]+$'
              AND l.parent_loan_id IS NULL
        """))
        orphans = result.fetchall()
        print(f"\nFix 2: Found {len(orphans)} orphaned A/B notes to link")

        # Group by deal for efficient parent lookup
        by_deal: dict[str, list[tuple]] = {}
        for row in orphans:
            deal_id = str(row[1])
            by_deal.setdefault(deal_id, []).append(row)

        linked = 0
        for deal_id, deal_orphans in by_deal.items():
            # Get all loans for this deal to find parents
            result = await session.execute(text(
                "SELECT id, prospectus_loan_id FROM loans WHERE deal_id = :did"
            ), {"did": deal_id})
            loan_map = {row[1]: row[0] for row in result.fetchall()}

            for loan_id, _, pid in deal_orphans:
                match = AB_PATTERN.match(pid)
                if match:
                    parent_pid = match.group(1)
                    parent_id = loan_map.get(parent_pid)
                    if parent_id and parent_id != loan_id:
                        await session.execute(text(
                            "UPDATE loans SET parent_loan_id = :pid "
                            "WHERE id = :lid"
                        ), {"pid": parent_id, "lid": loan_id})
                        linked += 1

        print(f"  Linked {linked} A/B notes to parent loans")

        await session.commit()

        # Verify
        na_count = (await session.execute(
            text("SELECT COUNT(*) FROM loans WHERE property_name IN ('NA', 'N/A', 'None', '')")
        )).scalar()
        orphan_count = (await session.execute(text(
            "SELECT COUNT(*) FROM loans "
            "WHERE prospectus_loan_id ~ '^[0-9]+[A-Za-z]+$' "
            "AND parent_loan_id IS NULL"
        ))).scalar()
        print("\nVerification:")
        print(f"  Remaining 'NA' property names: {na_count}")
        print(f"  Remaining orphaned A/B notes:  {orphan_count}")

        # Show BMO 2024-5C3 specifically
        result = await session.execute(text("""
            SELECT l.prospectus_loan_id, l.property_name, l.parent_loan_id
            FROM loans l JOIN deals d ON l.deal_id = d.id
            WHERE d.ticker = 'BMO 2024-5C3'
              AND l.prospectus_loan_id IN ('4', '4A', '4B')
            ORDER BY l.prospectus_loan_id
        """))
        rows = result.fetchall()
        if rows:
            print("\nBMO 2024-5C3 verification (loans 4, 4A, 4B):")
            for row in rows:
                parent = f"-> {row[2]}" if row[2] else "no parent"
                print(f"  {row[0]}: name={row[1]}, {parent}")


if __name__ == "__main__":
    asyncio.run(main())
