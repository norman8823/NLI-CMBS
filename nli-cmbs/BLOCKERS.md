# Blockers

## CIK Resolution Failures (3 of 5 deals)

**Affected deals:** GSMS 2023-GC15, WFCM 2024-C64, COMM 2024-CALI

**Root cause:** The 3-strategy CIK resolver cannot find these deals because:
1. No DB cache entry exists (Strategy 1 miss)
2. EDGAR full-text search returns no ABS-EE matches for these trust names (Strategy 2 miss)
3. Seed data depositor CIKs don't have filings matching these deal series (Strategy 3 miss)

**Likely fix:** These deals may use different depositor entities or CIKs not in our seed data. Manual CIK lookup on EDGAR EFTS or expanding seed_data.py with additional depositor CIKs would resolve this.

## Missing Fields

- **borrower_name**: Not present in EX-102 CMBS XML schema. Would need to be sourced from prospectus (EX-99.1) or other filing exhibits.
- **delinquency_status**: NULL for ~15% of BANK5 loans — some asset types may not report this field.
