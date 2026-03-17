"""Add property_type_source column and backfill inferred types

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-17
"""

import re
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# ---------------------------------------------------------------------------
# Keyword classifier — same rules used in classify_properties.py
# (pattern, type_code, min_confidence)
# Only backfill where confidence >= 0.85
# ---------------------------------------------------------------------------
RULES = [
    # Healthcare (before PLAZA)
    (r'\bMEDICAL (?:OFFICE|CENTER|PLAZA)\b', 'HC', 0.90),
    (r'\bHEARTLAND DENTAL\b', 'HC', 0.95),
    (r'\bFRESENIUS\b', 'HC', 0.90),
    (r'\bQUEST DIAGNOSTICS\b', 'HC', 0.85),
    (r'\bDENTAL\b', 'HC', 0.85),

    # Lodging — brand names
    (r'\bMARRIOTT\b', 'LO', 0.95),
    (r'\bHILTON\b', 'LO', 0.95),
    (r'\bHYATT\b', 'LO', 0.95),
    (r'\bSHERATON\b', 'LO', 0.95),
    (r'\bWESTIN\b', 'LO', 0.95),
    (r'\bRITZ CARLTON\b', 'LO', 0.95),
    (r'\bDOUBLETREE\b', 'LO', 0.95),
    (r'\bEMBASSY SUITES\b', 'LO', 0.95),
    (r'\bCROWNE PLAZA\b', 'LO', 0.95),
    (r'\bRADISSON\b', 'LO', 0.95),
    (r'\bCOURTYARD\b(?!.*\bAPART)', 'LO', 0.90),
    (r'\bRESIDENCE INN\b', 'LO', 0.95),
    (r'\bSPRINGHILL SUITES\b', 'LO', 0.95),
    (r'\bTOWNE ?PLACE SUITES\b', 'LO', 0.95),
    (r'\bFAIRFIELD INN\b', 'LO', 0.95),
    (r'\bHAMPTON INN\b', 'LO', 0.95),
    (r'\bHOMEWOOD SUITES\b', 'LO', 0.95),
    (r'\bHOME2 SUITES\b', 'LO', 0.95),
    (r'\bSTAYBRIDGE\b', 'LO', 0.95),
    (r'\bHOLIDAY INN\b', 'LO', 0.95),
    (r'\bCOMFORT INN\b', 'LO', 0.95),
    (r'\bCOMFORT SUITES\b', 'LO', 0.95),
    (r'\bBEST WESTERN\b', 'LO', 0.95),
    (r'\bLA QUINTA\b', 'LO', 0.95),
    (r'\bQUALITY INN\b', 'LO', 0.95),
    (r'\bDAYS INN\b', 'LO', 0.95),
    (r'\bRODEWAY INN\b', 'LO', 0.95),
    (r'\bRED ROOF\b', 'LO', 0.95),
    (r'\bWOODSPRING SUITES\b', 'LO', 0.95),
    (r'\bCOUNTRY INN\b', 'LO', 0.95),
    (r'\bHOTEL\b', 'LO', 0.90),
    (r'\bMOTEL\b', 'LO', 0.90),

    # Self Storage
    (r'\bSELF STORAGE\b', 'SS', 0.95),
    (r'\bMINI STORAGE\b', 'SS', 0.95),
    (r'\bCUBESMART\b', 'SS', 0.95),
    (r'\bSTORAGE\b(?!.*\b(?:DATA|DISTRIBUTION))', 'SS', 0.85),

    # Multifamily
    (r'\bAPARTMENTS?\b', 'MF', 0.95),
    (r'\bTOWNHOMES?\b', 'MF', 0.90),
    (r'\bRENTAL TOWNHOMES\b', 'MF', 0.95),

    # Mobile Home
    (r'\bMHC\b', 'MH', 0.90),
    (r'\bMHP\b', 'MH', 0.90),
    (r'\bMOBILE HOME\b', 'MH', 0.95),

    # Retail
    (r'\bSHOPPING CENTER\b', 'RT', 0.95),
    (r'\bRETAIL CENTER\b', 'RT', 0.95),
    (r'\bRETAIL CONDO\b', 'RT', 0.90),
    (r'\bTOWN CENTER\b', 'RT', 0.85),
    (r'\bTOWNE CENTER\b', 'RT', 0.85),
    (r'\bMARKETPLACE\b', 'RT', 0.85),
    (r'\bSHOPPES\b', 'RT', 0.90),
    (r'\bMALL\b', 'RT', 0.90),
    (r'\bWALGREENS\b', 'RT', 0.95),
    (r'\bCVS\b', 'RT', 0.90),
    (r'\bRITE AID\b', 'RT', 0.90),
    (r'\bDOLLAR GENERAL\b', 'RT', 0.90),
    (r'\bSHOPKO\b', 'RT', 0.90),
    (r'\bFOODMAXX\b', 'RT', 0.90),
    (r'\bSAVE MART\b', 'RT', 0.90),
    (r'\bSTOP & SHOP\b', 'RT', 0.90),

    # Office
    (r'\bOFFICE (?:PARK|CENTER|BUILDING)\b', 'OF', 0.95),
    (r'\bCORPORATE (?:CENTER|CAMPUS)\b', 'OF', 0.90),
    (r'\bHEADQUARTERS?\b', 'OF', 0.90),
    (r'\b(?:REGIONAL )?HQ\b', 'OF', 0.90),
    (r'\bOPERATIONS CENTER\b', 'OF', 0.85),
    (r'\bTECHNOLOGY (?:CENTER|CAMPUS)\b', 'OF', 0.85),
    (r'\bBUSINESS CAMPUS\b', 'OF', 0.85),

    # Industrial / Warehouse
    (r'\bDISTRIBUTION CENTER\b', 'IN', 0.95),
    (r'\bDISTRIBUTION HUB\b', 'IN', 0.90),
    (r'\bINDUSTRIAL PARK\b', 'IN', 0.95),
    (r'\bINDUSTRIAL\b', 'IN', 0.85),
    (r'\bWAREHOUSE\b', 'WH', 0.90),
    (r'\bMANUFACTUR', 'IN', 0.90),
    (r'\bLOGISTICS CENTER\b', 'IN', 0.90),

    # Mixed Use
    (r'\bMIXED USE\b', 'MU', 0.90),

    # GVS = grocery
    (r'^GVS\b', 'RT', 0.85),
]

MIN_CONFIDENCE = 0.85


def _classify(name: str):
    upper = name.upper().strip()
    for pattern, code, conf in RULES:
        if re.search(pattern, upper):
            if conf >= MIN_CONFIDENCE:
                return code
    return None


def upgrade() -> None:
    # 1. Add property_type_source column
    #    Values: 'reported' (from SEC filing), 'inferred' (keyword match)
    op.add_column(
        'properties',
        sa.Column('property_type_source', sa.String(20), nullable=True),
    )

    # 2. Mark all existing typed properties as 'reported'
    op.execute("""
        UPDATE properties
        SET property_type_source = 'reported'
        WHERE property_type IS NOT NULL
    """)

    # 3. Backfill inferred types using Python regex classifier
    conn = op.get_bind()
    rows = conn.execute(sa.text("""
        SELECT id, property_name FROM properties
        WHERE property_type IS NULL
          AND property_name IS NOT NULL
          AND TRIM(property_name) <> ''
          AND property_name <> 'NA'
          AND UPPER(property_name) NOT LIKE '%DEFEAS%'
    """)).fetchall()

    updates = []
    for row in rows:
        prop_id, name = row
        code = _classify(name)
        if code:
            updates.append((str(prop_id), code))

    if updates:
        # Batch update
        for prop_id, code in updates:
            conn.execute(sa.text("""
                UPDATE properties
                SET property_type = :code,
                    property_type_source = 'inferred'
                WHERE id = :id
            """), {"code": code, "id": prop_id})

    print(f"Backfilled {len(updates)} property types as 'inferred'")


def downgrade() -> None:
    # Revert inferred types back to NULL
    op.execute("""
        UPDATE properties
        SET property_type = NULL
        WHERE property_type_source = 'inferred'
    """)
    op.drop_column('properties', 'property_type_source')
