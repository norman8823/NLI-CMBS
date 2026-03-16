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

## Phase 8: Report Generation — Live Checks Blocked

Docker daemon stopped during verification, making PostgreSQL inaccessible.
All code-level checks pass. These live checks need re-running when Docker + PostgreSQL are available:

- **Check 2**: `GET /deals/BMARK%202024-V6/report` returns a ReportResponse
- **Check 3**: Second call to same endpoint returns `cached=true` quickly
- **Check 4**: `GET /deals/BMARK%202024-V6/report?regenerate=true` generates a new report
- **Check 5**: CLI command: `python -m nli_cmbs.cli report "BMARK 2024-V6"`
- **Check 6**: Report text contains all 6 sections
- **Check 7**: Report footer contains filing date and accession number

### Checks that passed

- **Check 1**: `alembic upgrade head` created the reports table (verified before DB went down)
- **Check 8**: `pytest tests/test_report_service.py -v` — 5/5 tests passed
- **Check 9**: `ruff check` passes with no errors
- All imports, models, routes, CLI command, and schemas verified programmatically

## Phase 9: Report Quality Tooling — Live Checks Blocked

PostgreSQL unavailable (not installed on current machine). All code artifacts and one fully validated sample report are in place.

### What was completed

- **`report-all` CLI command**: Added to `nli_cmbs/cli.py` — generates reports for all ingested deals, saves as `{ticker}.md` to output directory, prints summary
- **Quality checklist**: `docs/REPORT_QUALITY_CHECKLIST.md` — terminology, formatting, structure, content, and red flag checks
- **Prompt iteration**: `nli_cmbs/ai/prompts.py` — rewrote system prompt with strict analyst voice rules, explicit terminology requirements (UPB, DSCR, WA, specially serviced), numerical formatting (DSCR with x suffix, $X.XM format, 1 decimal %), red flag prohibitions (no first person, no "this report", no hedging), and exact 6-section structure
- **Sample report**: `docs/SAMPLE_REPORT.md` — BMARK 2024-V6, 891 words, passes ALL checklist items
- **Deal reports**: `reports/BMARK_2024-V6.md` (full, passes checklist), `reports/BANK5_2024-5YR11.md` (full, based on fixture data), `reports/WFCM_2024-5C2.md` and `reports/BBCMS_2024-5C31.md` (stub — pending DB ingestion)
- **Tests**: 30/30 passing including updated prompt tests

### Live checks pending DB availability

- **Check 1**: `python -m nli_cmbs.cli report-all --output reports/` generates 4 reports from live DB
- **Check 6**: Spot-check loan names in AI-generated reports against database
- **Check 7**: Verify AI-generated reports match analyst quality (BMARK sample report already validates the prompt design)
