#!/usr/bin/env python3
"""
Property Type Classifier v2.0
Enhanced version with:
- More comprehensive regex patterns
- Manual override lookup for researched properties
- Better confidence scoring
- Fuzzy matching for location data joins (optional)

Property Type Codes:
- MF: Multifamily
- RT: Retail
- OF: Office
- IN: Industrial
- WH: Warehouse
- LO: Lodging
- HC: Healthcare
- SS: Self Storage
- MH: Mobile Home
- MU: Mixed Use
- OT: Other
"""

import re
from typing import Optional, Tuple

# ============================================================================
# MANUAL OVERRIDES - Researched properties that can't be auto-classified
# These take precedence over regex rules
# ============================================================================
MANUAL_OVERRIDES = {
    # NYC Properties (researched)
    "1049 5TH AVENUE": ("MF", "Multifamily", 0.95, "Condo - 66 units UES"),
    "130 BOWERY": ("OT", "Other", 0.90, "Event venue/special use"),
    "120 SPRING STREET": ("RT", "Retail", 0.90, "SoHo commercial retail"),
    "10 JAVA STREET": ("IN", "Industrial", 0.85, "Industrial/warehouse Brooklyn"),
    "106 BEDFORD AVENUE": ("MF", "Multifamily", 0.85, "Residential Williamsburg"),
    "1384 FIRST AVENUE": ("RT", "Retail", 0.85, "UES retail"),
    
    # Dallas Properties
    "1500 DRAGON": ("IN", "Industrial", 0.90, "Flex-industrial Design District"),
    "1201 OAK LAWN": ("RT", "Retail", 0.85, "Mixed retail/showroom"),
    
    # Charlotte/NC Properties (DBGS 2018-C1 concentration)
    "10023 NORTH TRYON STREET": ("RT", "Retail", 0.80, "Retail corridor"),
    "10806 PROVIDENCE ROAD": ("RT", "Retail", 0.80, "Retail corridor"),
    "11208 EAST INDEPENDENCE BOULEVARD": ("RT", "Retail", 0.80, "Retail corridor"),
    "12710 SOUTH TRYON STREET": ("RT", "Retail", 0.80, "Retail corridor"),
    "1120 WEST SUGAR CREEK ROAD": ("RT", "Retail", 0.75, "Retail"),
    
    # Denver area (UBSCM 2017-C1 Grant Street cluster - likely same development)
    "1149 GRANT STREET": ("MF", "Multifamily", 0.75, "Denver residential area"),
    "1150 GRANT STREET": ("MF", "Multifamily", 0.75, "Denver residential area"),
    "1156 GRANT STREET": ("MF", "Multifamily", 0.75, "Denver residential area"),
    "1163 GRANT STREET": ("MF", "Multifamily", 0.75, "Denver residential area"),
    "1176 GRANT STREET": ("MF", "Multifamily", 0.75, "Denver residential area"),
    "1179 GRANT STREET": ("MF", "Multifamily", 0.75, "Denver residential area"),
    "1205 MAPLE STREET": ("MF", "Multifamily", 0.75, "Denver residential area"),
    
    # Chicago area
    "1101-1109 WEST RANDOLPH STREET": ("MU", "Mixed Use", 0.80, "West Loop mixed use"),
    "1421 WEST SHURE DRIVE": ("IN", "Industrial", 0.80, "Arlington Heights industrial"),
    "1422 E. 68TH STREET": ("IN", "Industrial", 0.75, "South Chicago industrial"),
    
    # Generic names that need context
    "WHISPERING WINDS": ("MF", "Multifamily", 0.70, "Generic MF name - verify"),
    "WHISPERING WOODS": ("MF", "Multifamily", 0.70, "Generic MF name - verify"),
    "WOODGLEN VILLAGE": ("RT", "Retail", 0.70, "Likely retail - verify"),
    "WESTPARK HUDSON": ("OF", "Office", 0.70, "Likely office park - verify"),
    "WINDMILL LAKES CENTER": ("RT", "Retail", 0.75, "Likely retail center"),
    
    # Special cases
    "121 EAST MARYLAND STREET PARKING GARAGE": ("OT", "Other", 0.95, "Parking garage"),
    "WEST 34TH": ("RT", "Retail", 0.70, "Manhattan retail - verify address"),
}

# ============================================================================
# REGEX RULES - Order matters! First match wins.
# Format: (pattern, type_code, type_name, confidence)
# ============================================================================
RULES = [
    # === PARKING (before other patterns) ===
    (r'\bPARKING\s*(?:GARAGE|DECK|LOT|STRUCTURE)\b', 'OT', 'Other', 0.95),
    (r'\bGARAGE\b(?=.*\b(?:PARKING|LEVEL|SPACE))', 'OT', 'Other', 0.85),
    
    # === HEALTHCARE (must be before PLAZA rule) ===
    (r'\bMEDICAL (?:OFFICE|CENTER|PLAZA|BUILDING)\b', 'HC', 'Healthcare', 0.90),
    (r'\bHEARTLAND DENTAL\b', 'HC', 'Healthcare', 0.95),
    (r'\bFRESENIUS\b', 'HC', 'Healthcare', 0.90),
    (r'\bDAVITA\b', 'HC', 'Healthcare', 0.90),
    (r'\bQUEST DIAGNOSTICS\b', 'HC', 'Healthcare', 0.85),
    (r'\bLABCORP\b', 'HC', 'Healthcare', 0.85),
    (r'\bSUNNYVALE MEDICAL\b', 'HC', 'Healthcare', 0.85),
    (r'\bOAK LAWN MEDICAL\b', 'HC', 'Healthcare', 0.85),
    (r'\bMEDICAL\b', 'HC', 'Healthcare', 0.80),
    (r'\bHOSPITAL\b', 'HC', 'Healthcare', 0.85),
    (r'\bPHARMA\b', 'HC', 'Healthcare', 0.75),
    (r'\bDENTAL\b(?!.*\bOFFICE\b)', 'HC', 'Healthcare', 0.85),
    (r'\bURGENT CARE\b', 'HC', 'Healthcare', 0.90),
    (r'\bSURGERY CENTER\b', 'HC', 'Healthcare', 0.90),
    (r'\bDIALYSIS\b', 'HC', 'Healthcare', 0.90),
    (r'\bCLINIC\b', 'HC', 'Healthcare', 0.75),
    
    # === EDUCATION (to Other) ===
    (r'\bTUTOR TIME\b', 'OT', 'Other', 0.60),
    (r'\bVATTEROTT COLLEGE\b', 'OT', 'Other', 0.60),
    (r'\bUNIVERSITY\b', 'OT', 'Other', 0.80),
    (r'\bCOLLEGE\b(?!.*PARK)', 'OT', 'Other', 0.75),
    (r'\bSCHOOL\b', 'OT', 'Other', 0.70),

    # === HOSPITALITY / LODGING (very distinctive names) ===
    (r'\bMARRIOTT\b', 'LO', 'Lodging', 0.95),
    (r'\bHILTON\b', 'LO', 'Lodging', 0.95),
    (r'\bHYATT\b', 'LO', 'Lodging', 0.95),
    (r'\bSHERATON\b', 'LO', 'Lodging', 0.95),
    (r'\bWESTIN\b', 'LO', 'Lodging', 0.95),
    (r'\bRITZ CARLTON\b', 'LO', 'Lodging', 0.95),
    (r'\bDOUBLETREE\b', 'LO', 'Lodging', 0.95),
    (r'\bEMBASSY SUITES\b', 'LO', 'Lodging', 0.95),
    (r'\bCROWNE PLAZA\b', 'LO', 'Lodging', 0.95),
    (r'\bRADISSON\b', 'LO', 'Lodging', 0.95),
    (r'\bRENAISSANCE\b.*\bHOTEL\b', 'LO', 'Lodging', 0.95),
    (r'\bFOUR POINTS\b.*\bSHERATON\b', 'LO', 'Lodging', 0.95),
    (r'\bCOURTYARD\b(?!.*\bAPART)', 'LO', 'Lodging', 0.90),
    (r'\bRESIDENCE INN\b', 'LO', 'Lodging', 0.95),
    (r'\bSPRINGHILL SUITES\b', 'LO', 'Lodging', 0.95),
    (r'\bTOWNE ?PLACE SUITES\b', 'LO', 'Lodging', 0.95),
    (r'\bFAIRFIELD INN\b', 'LO', 'Lodging', 0.95),
    (r'\bHAMPTON INN\b', 'LO', 'Lodging', 0.95),
    (r'\bHOMEWOOD SUITES\b', 'LO', 'Lodging', 0.95),
    (r'\bHOME2 SUITES\b', 'LO', 'Lodging', 0.95),
    (r'\bSTAYBRIDGE\b', 'LO', 'Lodging', 0.95),
    (r'\bHOLIDAY INN\b', 'LO', 'Lodging', 0.95),
    (r'\bCOMFORT INN\b', 'LO', 'Lodging', 0.95),
    (r'\bCOMFORT SUITES\b', 'LO', 'Lodging', 0.95),
    (r'\bBEST WESTERN\b', 'LO', 'Lodging', 0.95),
    (r'\bLA QUINTA\b', 'LO', 'Lodging', 0.95),
    (r'\bQUALITY INN\b', 'LO', 'Lodging', 0.95),
    (r'\bDAYS INN\b', 'LO', 'Lodging', 0.95),
    (r'\bRODEWAY INN\b', 'LO', 'Lodging', 0.95),
    (r'\bRED ROOF\b', 'LO', 'Lodging', 0.95),
    (r'\bWOODSPRING SUITES\b', 'LO', 'Lodging', 0.95),
    (r'\bVALUE PLACE\b', 'LO', 'Lodging', 0.90),
    (r'\bWINGATE\b', 'LO', 'Lodging', 0.90),
    (r'\bCOUNTRY INN\b', 'LO', 'Lodging', 0.95),
    (r'\bHOTEL\b', 'LO', 'Lodging', 0.90),
    (r'\bMOTEL\b', 'LO', 'Lodging', 0.90),
    (r'\bHOSPITALITY\b', 'LO', 'Lodging', 0.85),
    (r'\bEB HOTEL\b', 'LO', 'Lodging', 0.90),
    (r'\bSOHO (?:BEACH )?HOUSE\b', 'LO', 'Lodging', 0.85),
    (r'\bCHATEAU MARMONT\b', 'LO', 'Lodging', 0.95),
    (r'\bBRAZILIAN COURT\b', 'LO', 'Lodging', 0.90),
    (r'\bGODFREY HOTEL\b', 'LO', 'Lodging', 0.95),
    (r'\bLUXE RODEO\b', 'LO', 'Lodging', 0.90),
    (r'\bMELA TIMES SQUARE\b', 'LO', 'Lodging', 0.90),
    (r'\bPALOMAR\b', 'LO', 'Lodging', 0.85),
    (r'\bPARTRIDGE INN\b', 'LO', 'Lodging', 0.90),
    (r'\bSIRTAJ HOTEL\b', 'LO', 'Lodging', 0.90),
    (r'\bMELROSE MANSION\b', 'LO', 'Lodging', 0.80),
    (r'\bCRYSTAL SPRINGS RESORT\b', 'LO', 'Lodging', 0.90),
    (r'\bFLORIDA HOTEL\b', 'LO', 'Lodging', 0.90),
    (r'\bBIDE-A-WEE INN\b', 'LO', 'Lodging', 0.95),
    (r'\bSEA BREEZE INN\b', 'LO', 'Lodging', 0.90),
    (r'\bPIONEER LODGE\b', 'LO', 'Lodging', 0.80),
    (r'\bUNION HOTEL\b', 'LO', 'Lodging', 0.85),
    (r'\bMEZZ 42\b', 'LO', 'Lodging', 0.60),
    (r'\bSNOWMASS VILLAGE\b', 'LO', 'Lodging', 0.60),
    (r'\bFOUR POINTS\b', 'LO', 'Lodging', 0.85),
    (r'\bESA\b.*(?:CLEVELAND|BROOKLYN)', 'LO', 'Lodging', 0.85),
    (r'\bALOFT\b', 'LO', 'Lodging', 0.95),
    (r'\bW HOTEL\b', 'LO', 'Lodging', 0.95),
    (r'\bACE HOTEL\b', 'LO', 'Lodging', 0.95),
    (r'\bINN\b(?!.*\b(?:STORAGE|INDUSTRIAL|SHOPPING|PLAZA|TWIN))', 'LO', 'Lodging', 0.70),
    (r'\bLODGE\b(?!.*\b(?:STORAGE|INDUSTRIAL))', 'LO', 'Lodging', 0.70),
    (r'\bSUITES\b(?!.*\b(?:OFFICE|MEDICAL|EXECUTIVE))', 'LO', 'Lodging', 0.75),
    (r'\bRESORTS?\b', 'LO', 'Lodging', 0.85),

    # === SELF STORAGE ===
    (r'\bSELF STORAGE\b', 'SS', 'Self Storage', 0.95),
    (r'\bMINI STORAGE\b', 'SS', 'Self Storage', 0.95),
    (r'\bEXTRA SPACE\b', 'SS', 'Self Storage', 0.95),
    (r'\bPUBLIC STORAGE\b', 'SS', 'Self Storage', 0.95),
    (r'\bLIFE STORAGE\b', 'SS', 'Self Storage', 0.95),
    (r'\bCUBESMART\b', 'SS', 'Self Storage', 0.95),
    (r'\bSTORAGE\b(?!.*\b(?:DATA|DISTRIBUTION|COLD))', 'SS', 'Self Storage', 0.80),
    (r'\bSTORE IT\b', 'SS', 'Self Storage', 0.90),
    (r'\bSTORAMRT\b', 'SS', 'Self Storage', 0.90),

    # === MULTIFAMILY / RESIDENTIAL ===
    (r'\bAPARTMENTS?\b', 'MF', 'Multifamily', 0.95),
    (r'\bTOWNHOMES?\b', 'MF', 'Multifamily', 0.90),
    (r'\bTOWNHOUSES?\b', 'MF', 'Multifamily', 0.90),
    (r'\bRENTAL TOWNHOMES\b', 'MF', 'Multifamily', 0.95),
    (r'\bLOFTS\b', 'MF', 'Multifamily', 0.80),
    (r'\bVILLAS\b', 'MF', 'Multifamily', 0.75),
    (r'\bRESIDENCES\b(?!.*\bINN\b)', 'MF', 'Multifamily', 0.80),
    (r'\bFLATS\b', 'MF', 'Multifamily', 0.80),
    (r'\bGARDEN APARTMENTS\b', 'MF', 'Multifamily', 0.95),
    (r'\bYORKSHIRE TOWER', 'MF', 'Multifamily', 0.80),
    (r'\bLEXINGTON TOWERS\b', 'MF', 'Multifamily', 0.75),
    (r'\bCONDOS?\b', 'MF', 'Multifamily', 0.85),
    (r'\bCONDOMINIUM\b', 'MF', 'Multifamily', 0.85),
    (r'\bSENIOR (?:LIVING|HOUSING)\b', 'MF', 'Multifamily', 0.90),
    (r'\bASSSISTED LIVING\b', 'MF', 'Multifamily', 0.90),
    (r'\bSTUDENT HOUSING\b', 'MF', 'Multifamily', 0.90),

    # === MOBILE HOME ===
    (r'\bMHC\b', 'MH', 'Mobile Home', 0.90),
    (r'\bMHP\b', 'MH', 'Mobile Home', 0.90),
    (r'\bMOBILE HOME\b', 'MH', 'Mobile Home', 0.95),
    (r'\bMANUFACTURED HOUSING\b', 'MH', 'Mobile Home', 0.90),
    (r'\bRV PARK\b', 'MH', 'Mobile Home', 0.80),

    # === RETAIL ===
    (r'\bSHOPPING CENTER\b', 'RT', 'Retail', 0.95),
    (r'\bSHOPPING CENTRE\b', 'RT', 'Retail', 0.95),
    (r'\bRETAIL CENTER\b', 'RT', 'Retail', 0.95),
    (r'\bRETAIL CENTRE\b', 'RT', 'Retail', 0.95),
    (r'\bRETAIL CONDO\b', 'RT', 'Retail', 0.90),
    (r'\bSTRIP CENTER\b', 'RT', 'Retail', 0.95),
    (r'\bPOWER CENTER\b', 'RT', 'Retail', 0.90),
    (r'\bANCHORED CENTER\b', 'RT', 'Retail', 0.90),
    (r'\bRETAIL\b', 'RT', 'Retail', 0.80),
    (r'\bTOWN CENTER\b', 'RT', 'Retail', 0.85),
    (r'\bTOWN CENTRE\b', 'RT', 'Retail', 0.85),
    (r'\bTOWNE CENTER\b', 'RT', 'Retail', 0.85),
    (r'\bMARKETPLACE\b', 'RT', 'Retail', 0.85),
    (r'\bSHOPPES\b', 'RT', 'Retail', 0.90),
    (r'\bVILLAGE CENTER\b', 'RT', 'Retail', 0.80),
    (r'\bOUTLET\b', 'RT', 'Retail', 0.85),
    (r'\bMALL\b', 'RT', 'Retail', 0.90),
    (r'\bWALGREENS\b', 'RT', 'Retail', 0.95),
    (r'\bCVS\b', 'RT', 'Retail', 0.90),
    (r'\bRITE AID\b', 'RT', 'Retail', 0.90),
    (r'\bDOLLAR GENERAL\b', 'RT', 'Retail', 0.90),
    (r'\bDOLLAR TREE\b', 'RT', 'Retail', 0.90),
    (r'\bFAMILY DOLLAR\b', 'RT', 'Retail', 0.90),
    (r'\bSHOPKO\b', 'RT', 'Retail', 0.90),
    (r'\bDICKS SPORTING\b', 'RT', 'Retail', 0.90),
    (r'\bFLOOR & DECOR\b', 'RT', 'Retail', 0.90),
    (r'\bRESTORATION HARDWARE\b(?!.*DISTRIBUTION)', 'RT', 'Retail', 0.85),
    (r'\bBASS?ETT FURNITURE\b', 'RT', 'Retail', 0.85),
    (r'\bFOODMAXX\b', 'RT', 'Retail', 0.90),
    (r'\bSAVE MART\b', 'RT', 'Retail', 0.90),
    (r'\bS-MART\b', 'RT', 'Retail', 0.90),
    (r'\bLUCKY\b(?!.*STORAGE)', 'RT', 'Retail', 0.80),
    (r'\bSTOP & SHOP\b', 'RT', 'Retail', 0.90),
    (r'\bGARDEN FRESH MARKET\b', 'RT', 'Retail', 0.90),
    (r'\bCIRCLE K\b', 'RT', 'Retail', 0.90),
    (r'\bKOHLS\b', 'RT', 'Retail', 0.85),
    (r'\bNATIONAL TIRE\b', 'RT', 'Retail', 0.85),
    (r'\bDRIVE TIME\b', 'RT', 'Retail', 0.75),
    (r'\bREGAL CINEMAS\b', 'RT', 'Retail', 0.90),
    (r'\bAMC THEATRE\b', 'RT', 'Retail', 0.90),
    (r'\bVASA FITNESS\b', 'RT', 'Retail', 0.80),
    (r'\bGYMBOREE\b(?!.*DISTRIBUTION)', 'RT', 'Retail', 0.70),
    (r'\bTARGET\b', 'RT', 'Retail', 0.90),
    (r'\bWALMART\b', 'RT', 'Retail', 0.90),
    (r'\bKROGER\b', 'RT', 'Retail', 0.90),
    (r'\bSAFEWAY\b', 'RT', 'Retail', 0.90),
    (r'\bWHOLE FOODS\b', 'RT', 'Retail', 0.90),
    (r'\bTRADER JOE', 'RT', 'Retail', 0.90),
    (r'\bCOSTCO\b', 'RT', 'Retail', 0.90),
    (r'\bSAM\'?S CLUB\b', 'RT', 'Retail', 0.90),
    (r'\bBJ\'?S\b.*(?:WHOLESALE|CLUB)', 'RT', 'Retail', 0.90),
    (r'\bPLAZA\b(?!.*\b(?:HOTEL|APARTMENT|OFFICE|MEDICAL|CROWNE))', 'RT', 'Retail', 0.65),

    # === OFFICE ===
    (r'\bOFFICE PARK\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE CENTER\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE BUILDING\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE TOWER\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE COMPLEX\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE\b', 'OF', 'Office', 0.80),
    (r'\bCORPORATE CENTER\b', 'OF', 'Office', 0.90),
    (r'\bCORPORATE CAMPUS\b', 'OF', 'Office', 0.90),
    (r'\bCORPORATE PARK\b', 'OF', 'Office', 0.90),
    (r'\bEXECUTIVE CENTER\b', 'OF', 'Office', 0.85),
    (r'\bEXECUTIVE CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bEXECUTIVE PARK\b', 'OF', 'Office', 0.85),
    (r'\bFINANCIAL CENTER\b', 'OF', 'Office', 0.85),
    (r'\bFINANCIAL PLAZA\b', 'OF', 'Office', 0.85),
    (r'\bBUSINESS CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bBUSINESS CENTER\b', 'OF', 'Office', 0.80),
    (r'\bTECHNOLOGY CENTER\b', 'OF', 'Office', 0.80),
    (r'\bTECHNOLOGY CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bTECH CENTER\b', 'OF', 'Office', 0.80),
    (r'\bINNOVATION CAMPUS\b', 'OF', 'Office', 0.80),
    (r'\b(?:REGIONAL )?HQ\b', 'OF', 'Office', 0.90),
    (r'\bHEADQUARTERS?\b', 'OF', 'Office', 0.90),
    (r'\bOPERATIONS CENTER\b', 'OF', 'Office', 0.85),
    (r'\bCALL CENTER\b', 'OF', 'Office', 0.85),
    (r'\bDREAMWORKS CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bMEDIA STUDIOS\b', 'OF', 'Office', 0.70),
    (r'\bNETWORK CENTRE\b', 'OF', 'Office', 0.80),

    # === INDUSTRIAL / WAREHOUSE ===
    (r'\bDISTRIBUTION CENTER\b', 'IN', 'Industrial', 0.95),
    (r'\bDISTRIBUTION HUB\b', 'IN', 'Industrial', 0.90),
    (r'\bFULFILLMENT CENTER\b', 'IN', 'Industrial', 0.95),
    (r'\bDISTRIBUTION\b', 'IN', 'Industrial', 0.85),
    (r'\bINDUSTRIAL PARK\b', 'IN', 'Industrial', 0.95),
    (r'\bINDUSTRIAL\b', 'IN', 'Industrial', 0.85),
    (r'\bWAREHOUSE\b', 'WH', 'Warehouse', 0.90),
    (r'\bMANUFACTUR', 'IN', 'Industrial', 0.90),
    (r'\bBUSINESS PARK\b', 'IN', 'Industrial', 0.75),
    (r'\bCOMMERCE PARK\b', 'IN', 'Industrial', 0.80),
    (r'\bCOMMERCE CENTER\b', 'IN', 'Industrial', 0.80),
    (r'\bLOGISTICS CENTER\b', 'IN', 'Industrial', 0.90),
    (r'\bLOGISTICS PARK\b', 'IN', 'Industrial', 0.90),
    (r'\bFLEX\b', 'IN', 'Industrial', 0.75),
    (r'\bFEDEX\b', 'IN', 'Industrial', 0.85),
    (r'\bUPS\b.*(?:HUB|CENTER|FACILITY)', 'IN', 'Industrial', 0.85),
    (r'\bAMAZON\b.*(?:FC|FULFILLMENT|WAREHOUSE)', 'IN', 'Industrial', 0.90),
    (r'\bLKQ\b', 'IN', 'Industrial', 0.80),
    (r'\bH&E EQUIPMENT\b', 'IN', 'Industrial', 0.80),
    (r'\bGM LOGISTICS\b', 'IN', 'Industrial', 0.90),
    (r'\bSIKORSKY\b', 'IN', 'Industrial', 0.85),
    (r'\bFAUREC', 'IN', 'Industrial', 0.85),
    (r'\bGE AVIATION\b', 'IN', 'Industrial', 0.85),
    (r'\b3PL\b', 'IN', 'Industrial', 0.85),
    (r'\bFLOWSERVE\b', 'IN', 'Industrial', 0.80),
    (r'\bDURAVANT\b', 'IN', 'Industrial', 0.80),
    (r'\bGERDAU\b', 'IN', 'Industrial', 0.80),
    (r'\bGRINNELL WATER WORKS\b', 'IN', 'Industrial', 0.75),
    (r'\bKIRLIN\b', 'IN', 'Industrial', 0.70),
    (r'\bQUAD ?PACKAGING\b', 'IN', 'Industrial', 0.85),
    (r'\bRESTORATION HARDWARE DISTRIBUTION\b', 'IN', 'Industrial', 0.90),
    (r'\bGYMBOREE DISTRIBUTION\b', 'IN', 'Industrial', 0.90),
    (r'\bMATTRESS DISTRIBUTION\b', 'IN', 'Industrial', 0.85),
    (r'\bSAINT-GOBAIN\b', 'IN', 'Industrial', 0.80),
    (r'\bCOLD STORAGE\b', 'IN', 'Industrial', 0.90),

    # === DATA CENTER ===
    (r'\bDATA CENTER\b', 'IN', 'Industrial', 0.85),
    (r'\bDATA CENTRE\b', 'IN', 'Industrial', 0.85),

    # === MIXED USE ===
    (r'\bMIXED USE\b', 'MU', 'Mixed Use', 0.90),
    (r'\bMIXED-USE\b', 'MU', 'Mixed Use', 0.90),

    # === SINGLE-TENANT (company name — split by likely use) ===
    # Tech / financial / services → Office
    (r'^(?:APPLE|NVIDIA|COMCAST|WESTERN DIGITAL|SYNCHRONY|T-MOBILE|GODADDY|ALLIANCE DATA|STATE FARM|GSK|CHRISTUS|WELLS FARGO)\b', 'OF', 'Office', 0.65),
    (r'^(?:MICROSOFT|GOOGLE|FACEBOOK|META|TWITTER|SALESFORCE|ORACLE|IBM|CISCO)\b', 'OF', 'Office', 0.70),
    # Pharma / biotech → Healthcare/Industrial
    (r'^(?:NOVO NORDISK|PFIZER|BAXALTA|ALVOGEN|MERCK|JOHNSON & JOHNSON|ABBOTT)\b', 'HC', 'Healthcare', 0.65),
    # Defense / aerospace / manufacturing → Industrial
    (r'^(?:BAE|CAMERON|CARRIER|HARMAN|HITACHI|TYCO|TE CONNECTIVITY|ACE HARDWARE|VARSITY BRANDS|ALFA LAVAL|FCA|CATERPILLAR)\b', 'IN', 'Industrial', 0.65),
    (r'^(?:BOEING|LOCKHEED|RAYTHEON|NORTHROP|GENERAL DYNAMICS)\b', 'IN', 'Industrial', 0.70),
    (r'\bPLANT\b', 'IN', 'Industrial', 0.80),
    (r'\bFACILITY\b', 'IN', 'Industrial', 0.70),
    (r'\bFACTORY\b', 'IN', 'Industrial', 0.85),

    # === GROCERY (GVS = Grocery Venture Stores) ===
    (r'^GVS\b', 'RT', 'Retail', 0.85),
]


def classify(name: str) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[str]]:
    """
    Classify a property by name.
    
    Returns:
        Tuple of (type_code, type_name, confidence, notes)
        Returns (None, None, None, None) if no classification found
    """
    upper = name.upper().strip()
    
    # Check manual overrides first
    if upper in MANUAL_OVERRIDES:
        code, type_name, conf, notes = MANUAL_OVERRIDES[upper]
        return code, type_name, conf, notes
    
    # Fall back to regex rules
    for pattern, code, type_name, conf in RULES:
        if re.search(pattern, upper):
            return code, type_name, conf, None
    
    return None, None, None, None


def main():
    import csv
    import sys
    
    # Configuration - update paths as needed
    locations_file = '/tmp/prop_locations.txt'
    input_file = sys.argv[1] if len(sys.argv) > 1 else '/tmp/missing_type_names.txt'
    output_file = sys.argv[2] if len(sys.argv) > 2 else '/tmp/classified_output.txt'
    
    # Load location data (pipe-delimited: name|address|city|state|ticker)
    locations = {}
    try:
        with open(locations_file) as f:
            reader = csv.reader(f, delimiter='|')
            for row in reader:
                if len(row) >= 5:
                    uname = row[0].upper().strip()
                    locations[uname] = {
                        'address': row[1] or '',
                        'city': row[2] or '',
                        'state': row[3] or '',
                        'ticker': row[4] or '',
                    }
    except FileNotFoundError:
        print(f"Warning: Location file not found: {locations_file}", file=sys.stderr)

    # Load property names
    try:
        with open(input_file) as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Skip header line if present
    if lines and lines[0].strip().upper().startswith('PROPERTY'):
        lines = lines[1:]
    
    names = [l.strip() for l in lines if l.strip()]

    out_lines = []
    stats = {'classified': 0, 'high_conf': 0, 'low_conf': 0, 'unknown': 0, 'override': 0}

    hdr = f"{'PROPERTY NAME':<55} {'ADDRESS':<35} {'CITY':<18} {'ST':<4} {'DEAL':<16} {'TYPE':<18} {'PROB':>5}  {'FLAG':<15} {'NOTES'}"
    out_lines.append(hdr)
    out_lines.append("-" * 180)

    for name in names:
        loc = locations.get(name.upper().strip(), {})
        addr = loc.get('address', '')[:33]
        city = loc.get('city', '')[:16]
        state = loc.get('state', '')[:3]
        ticker = loc.get('ticker', '')[:14]

        code, type_name, conf, notes = classify(name)
        notes = notes or ''
        
        if code is None:
            flag = "UNKNOWN"
            out_lines.append(f"{name:<55} {addr:<35} {city:<18} {state:<4} {ticker:<16} {'?':<18} {'?':>5}  {flag:<15} {notes}")
            stats['unknown'] += 1
        else:
            # Check if from manual override
            is_override = name.upper().strip() in MANUAL_OVERRIDES
            
            if conf < 0.75:
                flag = "LOW CONFIDENCE"
                stats['low_conf'] += 1
            elif conf < 0.85:
                flag = "REVIEW"
                stats['low_conf'] += 1
            else:
                flag = "OVERRIDE" if is_override else ""
                stats['high_conf'] += 1
                
            if is_override:
                stats['override'] += 1
                
            stats['classified'] += 1
            type_display = f"{type_name} ({code})"
            out_lines.append(f"{name:<55} {addr:<35} {city:<18} {state:<4} {ticker:<16} {type_display:<18} {conf:>5.0%}  {flag:<15} {notes}")

    # Summary
    total = len(names)
    summary = [
        f"PROPERTY TYPE CLASSIFICATION v2.0 — {total} distinct names",
        f"",
        f"  High confidence (>=85%):  {stats['high_conf']:>4} ({stats['high_conf']/total*100:.1f}%)",
        f"  Low confidence / Review:  {stats['low_conf']:>4} ({stats['low_conf']/total*100:.1f}%)",
        f"  Unknown (no match):       {stats['unknown']:>4} ({stats['unknown']/total*100:.1f}%)",
        f"  ────────────────────────────────",
        f"  Manual overrides used:    {stats['override']:>4}",
        f"",
    ]

    # Write output
    with open(output_file, 'w') as f:
        f.write('\n'.join(summary + out_lines) + '\n')

    print(f"Done: {stats['classified']} classified, {stats['unknown']} unknown out of {total}")
    print(f"Output written to: {output_file}")


if __name__ == '__main__':
    main()
