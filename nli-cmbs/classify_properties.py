import re

# Keywords → (type_code, full_name, base_confidence)
# Order matters — first match wins, so put more specific patterns first
RULES = [
    # === HEALTHCARE (must be before PLAZA rule) ===
    (r'\bMEDICAL (?:OFFICE|CENTER|PLAZA)\b', 'HC', 'Healthcare', 0.90),
    (r'\bHEARTLAND DENTAL\b', 'HC', 'Healthcare', 0.95),
    (r'\bFRESENIUS\b', 'HC', 'Healthcare', 0.90),
    (r'\bQUEST DIAGNOSTICS\b', 'HC', 'Healthcare', 0.85),
    (r'\bSUNNYVALE MEDICAL\b', 'HC', 'Healthcare', 0.85),
    (r'\bOAK LAWN MEDICAL\b', 'HC', 'Healthcare', 0.85),
    (r'\bMEDICAL\b', 'HC', 'Healthcare', 0.80),
    (r'\bHOSPITAL\b', 'HC', 'Healthcare', 0.85),
    (r'\bPHARMA\b', 'HC', 'Healthcare', 0.75),
    (r'\bDENTAL\b', 'HC', 'Healthcare', 0.85),
    (r'\bTUTOR TIME\b', 'OT', 'Other', 0.60),
    (r'\bVATTEROTT COLLEGE\b', 'OT', 'Other', 0.60),

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
    (r'\bTOWNEPLACE SUITES\b', 'LO', 'Lodging', 0.95),
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
    (r'\bINN\b(?!.*\b(?:STORAGE|INDUSTRIAL|SHOPPING|PLAZA))', 'LO', 'Lodging', 0.70),
    (r'\bLODGE\b', 'LO', 'Lodging', 0.70),
    (r'\bSUITES\b(?!.*\b(?:OFFICE|MEDICAL))', 'LO', 'Lodging', 0.75),
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

    # === SELF STORAGE ===
    (r'\bSELF STORAGE\b', 'SS', 'Self Storage', 0.95),
    (r'\bMINI STORAGE\b', 'SS', 'Self Storage', 0.95),
    (r'\bSTORAGE\b(?!.*\b(?:DATA|DISTRIBUTION))', 'SS', 'Self Storage', 0.80),
    (r'\bCUBESMART\b', 'SS', 'Self Storage', 0.95),
    (r'\bSTORE IT\b', 'SS', 'Self Storage', 0.90),
    (r'\bSTORAMRT\b', 'SS', 'Self Storage', 0.90),

    # === MULTIFAMILY / RESIDENTIAL ===
    (r'\bAPARTMENTS?\b', 'MF', 'Multifamily', 0.95),
    (r'\bTOWNHOMES?\b', 'MF', 'Multifamily', 0.90),
    (r'\bTOWNHOUSES?\b', 'MF', 'Multifamily', 0.90),
    (r'\bRENTAL TOWNHOMES\b', 'MF', 'Multifamily', 0.95),
    (r'\bLOFTS\b', 'MF', 'Multifamily', 0.80),
    (r'\bVILLAS\b', 'MF', 'Multifamily', 0.75),
    (r'\bRESIDENCES\b', 'MF', 'Multifamily', 0.80),
    (r'\bFLATS\b', 'MF', 'Multifamily', 0.80),
    (r'\bGARDEN APARTMENTS\b', 'MF', 'Multifamily', 0.95),
    (r'\bYORKSHIRE TOWER', 'MF', 'Multifamily', 0.80),
    (r'\bLEXINGTON TOWERS\b', 'MF', 'Multifamily', 0.75),

    # === MOBILE HOME ===
    (r'\bMHC\b', 'MH', 'Mobile Home', 0.90),
    (r'\bMHP\b', 'MH', 'Mobile Home', 0.90),
    (r'\bMOBILE HOME\b', 'MH', 'Mobile Home', 0.95),
    (r'\bRV PARK\b', 'MH', 'Mobile Home', 0.80),

    # === RETAIL ===
    (r'\bSHOPPING CENTER\b', 'RT', 'Retail', 0.95),
    (r'\bSHOPPING CENTRE\b', 'RT', 'Retail', 0.95),
    (r'\bRETAIL CENTER\b', 'RT', 'Retail', 0.95),
    (r'\bRETAIL CENTRE\b', 'RT', 'Retail', 0.95),
    (r'\bRETAIL CONDO\b', 'RT', 'Retail', 0.90),
    (r'\bRETAIL\b', 'RT', 'Retail', 0.80),
    (r'\bTOWN CENTER\b', 'RT', 'Retail', 0.85),
    (r'\bTOWN CENTRE\b', 'RT', 'Retail', 0.85),
    (r'\bTOWNE CENTER\b', 'RT', 'Retail', 0.85),
    (r'\bMARKETPLACE\b', 'RT', 'Retail', 0.85),
    (r'\bSHOPPES\b', 'RT', 'Retail', 0.90),
    (r'\bVILLAGE CENTER\b', 'RT', 'Retail', 0.80),
    (r'\bOUTLET\b', 'RT', 'Retail', 0.85),
    (r'\bMALL\b', 'RT', 'Retail', 0.90),
    (r'\bPLAZA\b(?!.*\b(?:HOTEL|APARTMENT|OFFICE))', 'RT', 'Retail', 0.65),
    (r'\bWALGREENS\b', 'RT', 'Retail', 0.95),
    (r'\bCVS\b', 'RT', 'Retail', 0.90),
    (r'\bRITE AID\b', 'RT', 'Retail', 0.90),
    (r'\bDOLLAR GENERAL\b', 'RT', 'Retail', 0.90),
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
    (r'\bVASA FITNESS\b', 'RT', 'Retail', 0.80),
    (r'\bGYMBOREE\b(?!.*DISTRIBUTION)', 'RT', 'Retail', 0.70),

    # === OFFICE ===
    (r'\bOFFICE PARK\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE CENTER\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE BUILDING\b', 'OF', 'Office', 0.95),
    (r'\bOFFICE\b', 'OF', 'Office', 0.80),
    (r'\bCORPORATE CENTER\b', 'OF', 'Office', 0.90),
    (r'\bCORPORATE CAMPUS\b', 'OF', 'Office', 0.90),
    (r'\bEXECUTIVE CENTER\b', 'OF', 'Office', 0.85),
    (r'\bEXECUTIVE CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bEXECUTIVE PARK\b', 'OF', 'Office', 0.85),
    (r'\bFINANCIAL CENTER\b', 'OF', 'Office', 0.85),
    (r'\bFINANCIAL PLAZA\b', 'OF', 'Office', 0.85),
    (r'\bBUSINESS CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bBUSINESS CENTER\b', 'OF', 'Office', 0.80),
    (r'\bTECHNOLOGY CENTER\b', 'OF', 'Office', 0.80),
    (r'\bTECHNOLOGY CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bINNOVATION CAMPUS\b', 'OF', 'Office', 0.80),
    (r'\b(?:REGIONAL )?HQ\b', 'OF', 'Office', 0.90),
    (r'\bHEADQUARTERS?\b', 'OF', 'Office', 0.90),
    (r'\bOPERATIONS CENTER\b', 'OF', 'Office', 0.85),
    (r'\bCALL CENTER\b', 'OF', 'Office', 0.85),
    (r'\bDREAMWORKS CAMPUS\b', 'OF', 'Office', 0.85),
    (r'\bMEDIA STUDIOS\b', 'OF', 'Office', 0.70),

    # (Healthcare rules moved to top of RULES list)

    # === INDUSTRIAL / WAREHOUSE ===
    (r'\bDISTRIBUTION CENTER\b', 'IN', 'Industrial', 0.95),
    (r'\bDISTRIBUTION HUB\b', 'IN', 'Industrial', 0.90),
    (r'\bDISTRIBUTION\b', 'IN', 'Industrial', 0.85),
    (r'\bINDUSTRIAL PARK\b', 'IN', 'Industrial', 0.95),
    (r'\bINDUSTRIAL\b', 'IN', 'Industrial', 0.85),
    (r'\bWAREHOUSE\b', 'WH', 'Warehouse', 0.90),
    (r'\bMANUFACTUR', 'IN', 'Industrial', 0.90),
    (r'\bBUSINESS PARK\b', 'IN', 'Industrial', 0.75),
    (r'\bLOGISTICS CENTER\b', 'IN', 'Industrial', 0.90),
    (r'\bFEDEX\b', 'IN', 'Industrial', 0.85),
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

    # === DATA CENTER ===
    (r'\bDATA CENTER\b', 'IN', 'Industrial', 0.85),

    # === MIXED USE ===
    (r'\bMIXED USE\b', 'MU', 'Mixed Use', 0.90),

    # === SINGLE-TENANT (company name — split by likely use) ===
    # Tech / financial / services → Office
    (r'^(?:APPLE|NVIDIA|COMCAST|WESTERN DIGITAL|SYNCHRONY|T-MOBILE|GODADDY|ALLIANCE DATA|STATE FARM|GSK|CHRISTUS|WELLS FARGO)\b', 'OF', 'Office', 0.65),
    # Pharma / biotech → Healthcare/Industrial
    (r'^(?:NOVO NORDISK|PFIZER|BAXALTA|ALVOGEN)\b', 'HC', 'Healthcare', 0.65),
    # Defense / aerospace / manufacturing → Industrial
    (r'^(?:BAE|CAMERON|CARRIER|HARMAN|HITACHI|TYCO|TE CONNECTIVITY|ACE HARDWARE|VARSITY BRANDS|ALFA LAVAL|FCA|CATERPILLAR)\b', 'IN', 'Industrial', 0.65),
    (r'\bPLANT\b', 'IN', 'Industrial', 0.80),
    (r'\bFACILITY\b', 'IN', 'Industrial', 0.70),

    # === GROCERY (GVS = Grocery Venture Stores) ===
    (r'^GVS\b', 'RT', 'Retail', 0.85),
]

def classify(name: str):
    upper = name.upper().strip()
    for pattern, code, type_name, conf in RULES:
        if re.search(pattern, upper):
            return code, type_name, conf
    return None, None, None

def main():
    import csv

    # Load location data (pipe-delimited: name|address|city|state|ticker)
    locations = {}
    with open('/tmp/prop_locations.txt') as f:
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

    with open('/Users/norman/main/CMBS/nli-cmbs/missing_type_names.txt') as f:
        lines = f.readlines()

    # Skip header line
    names = [l.strip() for l in lines[1:] if l.strip()]

    out_lines = []
    classified = 0
    flagged = 0
    unknown = 0

    hdr = f"{'PROPERTY NAME':<55} {'ADDRESS':<40} {'CITY':<20} {'ST':<5} {'DEAL':<18} {'BEST GUESS':<20} {'PROB':>5}  {'FLAG'}"
    out_lines.append(hdr)
    out_lines.append("-" * len(hdr))

    for name in names:
        loc = locations.get(name.upper().strip(), {})
        addr = loc.get('address', '')[:38]
        city = loc.get('city', '')[:18]
        state = loc.get('state', '')[:4]
        ticker = loc.get('ticker', '')[:16]

        code, type_name, conf = classify(name)
        if code is None:
            flag = "UNKNOWN"
            out_lines.append(f"{name:<55} {addr:<40} {city:<20} {state:<5} {ticker:<18} {'?':<20} {'?':>5}  {flag}")
            unknown += 1
        elif conf < 0.75:
            flag = "LOW CONFIDENCE"
            out_lines.append(f"{name:<55} {addr:<40} {city:<20} {state:<5} {ticker:<18} {type_name + ' (' + code + ')':<20} {conf:>5.0%}  {flag}")
            flagged += 1
        else:
            flag = ""
            if conf < 0.85:
                flag = "REVIEW"
                flagged += 1
            out_lines.append(f"{name:<55} {addr:<40} {city:<20} {state:<5} {ticker:<18} {type_name + ' (' + code + ')':<20} {conf:>5.0%}  {flag}")
            classified += 1

    # Summary at top
    summary = [
        f"PROPERTY TYPE CLASSIFICATION — {len(names)} distinct names",
        f"  Classified (>=75%): {classified}",
        f"  Flagged (review):   {flagged}",
        f"  Unknown:            {unknown}",
        "",
    ]

    with open('/Users/norman/main/CMBS/nli-cmbs/missing_type_classifications.txt', 'w') as f:
        f.write('\n'.join(summary + out_lines) + '\n')

    print(f"Done: {classified} classified, {flagged} flagged, {unknown} unknown out of {len(names)}")

if __name__ == '__main__':
    main()
