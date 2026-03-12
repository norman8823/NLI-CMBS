# EX-102 Parser Validation Report

**Date:** 2026-03-12

## Summary

| Ticker | CIK | Filing Date | Loans | Parse Errors | Status |
|--------|-----|-------------|-------|-------------|--------|
| BMARK 2024-V6 | 0001888524 | 2026-02-26 | 37 | 0 | OK |
| BANK5 2024-5YR9 | 0001888524 | 2026-02-26 | 60 | 0 | OK |
| GSMS 2023-GC15 | — | — | — | — | CIK resolution failed |
| WFCM 2024-C64 | — | — | — | — | CIK resolution failed |
| COMM 2024-CALI | — | — | — | — | CIK resolution failed |

**Result: 2 of 5 deals successfully ingested.**

## Deal: BMARK 2024-V6

- **Filing:** 0001888524-26-002583
- **Reporting Period:** 2026-01-13 to 2026-02-11
- **Total Loans:** 37
- **Total UPB:** $1,090,060,000.00
- **Parse Errors:** 0

### Sample Loans

| Loan ID | Property Name | City | State | Ending Balance | Rate | Delinquency |
|---------|--------------|------|-------|----------------|------|-------------|
| 1 | Prime Storage - Hudson Valley Portfolio | New Windsor | NY | $80,000,000 | 6.23% | Current (0) |
| 2 | Warwick Melrose & Allerton | Dallas | TX | $78,000,000 | 8.14% | Current (0) |
| 3 | Panorama Tower | Charlotte | NC | $71,500,000 | 7.37% | Current (0) |

### NULL Field Analysis

- **borrower_name:** NULL for all 37 loans — NOT a parser gap, field is not present in EX-102 CMBS XML schema
- **property_type:** Populated for all 37 loans (SS, LO, MU, OF, RT, etc.)
- **property_city/state:** Populated for all 37 loans
- **origination_date:** Populated for all 37 loans

## Deal: BANK5 2024-5YR9

- **Filing:** 0001888524-26-002812
- **Reporting Period:** 2026-01-13 to 2026-02-11
- **Total Loans:** 60
- **Total UPB:** $907,421,747.10
- **Parse Errors:** 0

### Sample Loans

| Loan ID | Property Name | City | State | Ending Balance | Rate | Delinquency |
|---------|--------------|------|-------|----------------|------|-------------|
| 1 | THE PIAZZA | Philadelphia | PA | $75,000,000 | 5.91% | Current (0) |
| 3 | POTOMAC TOWER | Arlington | VA | $70,000,000 | 7.60% | Current (0) |
| 2 | BAYBROOK MALL | Friendswood | TX | $59,142,381 | 6.82% | Current (0) |

### NULL Field Analysis

- **borrower_name:** NULL for all 60 loans — field not in EX-102 XML schema
- **property_type:** NULL for 13 loans — some portfolio/multi-property loans lack type codes
- **property_city/state:** NULL for ~15 loans — portfolio loans without single-property geography
- **origination_date:** NULL for 15 loans — some loans missing origination date
- **delinquency_status:** NULL for 15 loans — some assets lack paymentStatusLoanCode

## Failures

### GSMS 2023-GC15
- All 3 CIK resolution strategies failed
- GSMS seed data has only 1 depositor CIK, and EDGAR search returned no matches

### WFCM 2024-C64
- All 3 CIK resolution strategies failed
- WFCM seed data has only 1 depositor CIK

### COMM 2024-CALI
- All 3 CIK resolution strategies failed
- COMM seed data has only 1 depositor CIK

## Parser Quality Assessment

The parser correctly handles both BMARK and BANK5 XML formats without modification. Key observations:

1. **Namespace handling:** Works correctly — both deals use the same `absee/cmbs/assetdata` namespace
2. **Date parsing:** MM-DD-YYYY format handled correctly for both shelves
3. **Decimal/financial amounts:** Parsed accurately (UPB figures in correct ranges)
4. **Property nesting:** `property/propertyName`, `property/propertyCity`, etc. work as expected
5. **Missing fields:** `borrower_name` is not part of the EX-102 CMBS XML schema — this is expected, not a parser gap
6. **Portfolio loans:** Some multi-property/portfolio loans have NULL city/state/type which is correct behavior
