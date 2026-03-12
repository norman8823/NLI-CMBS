#!/bin/bash
# =============================================================================
# NLI-CMBS Day 2 Build — ABS-EE XML Parsing + Loan Data Persistence
# =============================================================================
#
# USAGE:
#   Fully autonomous (no permission prompts):
#     ./nli-cmbs-day2.sh --auto
#
#   Single phase only:
#     ./nli-cmbs-day2.sh --phase 2
#
# PREREQUISITES:
#   1. Day 1 complete: docker-compose up, alembic upgrade head, cli scan works
#   2. Claude Code installed and authenticated
#   3. Ralph Wiggum plugin installed
#   4. Docker running with PostgreSQL
#
# =============================================================================

set -euo pipefail

PROJECT_DIR="${NLI_CMBS_DIR:-$(pwd)}"
LOG_DIR="$PROJECT_DIR/.claude/build-logs"
MODE="auto"
SINGLE_PHASE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --auto)    MODE="auto"; shift ;;
        --remote)  MODE="remote"; shift ;;
        --phase)   SINGLE_PHASE="$2"; shift 2 ;;
        --dir)     PROJECT_DIR="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--auto|--remote] [--phase N] [--dir /path/to/project]"
            echo "  --auto    Fully autonomous (default)"
            echo "  --remote  Starts Remote Control session"
            echo "  --phase N Run only phase N (1-4)"
            echo "  --dir     Project directory (default: current directory)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARNING:${NC} $1"; }
fail() { echo -e "${RED}[$(date +%H:%M:%S)] FAILED:${NC} $1"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "Running pre-flight checks..."

if ! docker compose ps --status running 2>/dev/null | grep -q postgres; then
    warn "PostgreSQL container not running. Attempting to start..."
    docker compose up -d
    sleep 5
fi

if ! docker compose ps --status running 2>/dev/null | grep -q postgres; then
    fail "PostgreSQL is not running. Run 'docker compose up -d' first."
    exit 1
fi

log "Pre-flight checks passed."

# ---------------------------------------------------------------------------
# Remote Control mode
# ---------------------------------------------------------------------------
if [[ "$MODE" == "remote" ]]; then
    log "Starting Remote Control session..."
    claude remote-control "NLI-CMBS Day 2 Build"
    exit 0
fi

# =============================================================================
# PHASE 1: XML Reconnaissance
# =============================================================================

read -r -d '' PHASE1_PROMPT << 'PHASE1_EOF' || true
/ralph-loop:ralph-loop "In the nli-cmbs project, before building the XML parser we need to understand the ACTUAL structure of ABS-EE EX-102 XML files. Different issuers produce slightly different XML, so we must inspect real samples before writing any parsing code.

TASK:
1. Use the existing cli scan pipeline to download the EX-102 XML for TWO different deals:
   - 'BMARK 2024-V6' (JPMorgan depositor)
   - 'BANK5 2024-5YR9' (Morgan Stanley depositor) — if this fails, try 'WFCM 2024-C64' or any other shelf that works

   If these specific tickers fail to resolve, pick ANY two deals from different depositors that successfully resolve.

2. Save the downloaded XML files to tests/fixtures/:
   - tests/fixtures/ex102_bmark_2024_v6.xml (or whatever deal you got)
   - tests/fixtures/ex102_second_deal.xml

3. Create a reconnaissance report at docs/ex102_xml_structure.md documenting:
   a. ROOT ELEMENT: root tag and namespace declarations
   b. LOAN CONTAINER: element wrapping each individual loan/asset
   c. FIELD MAPPING: For each target field, the EXACT XML element name and XPath:
      - Loan identity: prospectus_loan_id, asset_number, originator, original_amount, origination_date
      - Property: property_name, property_city, property_state, property_type
      - Borrower: borrower_name / obligor_name
      - Current status: reporting_period dates, beginning/ending balance, current_rate, delinquency_status, interest_paid_through_date, servicer_advanced_amount
      - Maturity: maturity_date, original_term, original_amort_term, original_rate
      - Payment: scheduled_interest, scheduled_principal, actual_interest, actual_principal, actual_other
   d. NAMESPACE HANDLING: are elements namespaced? prefix/URI?
   e. DATA TYPES: numeric format, date format, null representation
   f. DIFFERENCES between the two issuer XMLs
   g. TOTAL LOAN COUNT in each file

4. Create scripts/inspect_xml.py that loads an EX-102 XML, prints root tag, namespaces, first 3 loan elements with all child names and sample values, and total loan count.

IMPORTANT: Do NOT write the actual parser yet. Reconnaissance only. Do NOT guess element names — only document what you actually see.

VERIFICATION:
1. At least ONE real EX-102 XML file exists in tests/fixtures/ (>100KB, valid XML)
2. docs/ex102_xml_structure.md exists with actual element names from real XML
3. Field mapping has actual XPath expressions, not guesses
4. scripts/inspect_xml.py runs successfully and prints loan data

When ALL checks pass, output <promise>PHASE1_DONE</promise>.
If stuck after 10 iterations, write blockers to BLOCKERS.md and output <promise>PHASE1_DONE</promise>." --max-iterations 12 --completion-promise "PHASE1_DONE"
PHASE1_EOF


# =============================================================================
# PHASE 2: EX-102 XML Parser
# =============================================================================

read -r -d '' PHASE2_PROMPT << 'PHASE2_EOF' || true
/ralph-loop:ralph-loop "In the nli-cmbs project, build the XML parser at nli_cmbs/edgar/xml_parser.py.

CRITICAL: Before writing ANY parsing code, read docs/ex102_xml_structure.md from the previous phase. Use the ACTUAL element names and namespaces documented there. If that file is incomplete, run 'python scripts/inspect_xml.py' on the fixture XML files first.

IMPLEMENTATION:

1. Create Pydantic models at nli_cmbs/schemas/parsed_loan.py:
   - ParsedLoan: prospectus_loan_id (str), asset_number (int|None), originator_name, original_loan_amount (Decimal|None), origination_date (date|None), property_name, property_city, property_state, property_type, borrower_name, maturity_date, original_term_months, original_amortization_term_months, original_interest_rate (all nullable except prospectus_loan_id)
   - ParsedLoanSnapshot: reporting_period_begin_date (date), reporting_period_end_date (date), beginning_balance (Decimal), ending_balance (Decimal), current_interest_rate, scheduled_interest_amount, scheduled_principal_amount, actual_interest_collected, actual_principal_collected, actual_other_collected, servicer_advanced_amount, delinquency_status, interest_paid_through_date, next_payment_amount_due (nullable decimals/dates)
   - ParsedFiling: loans (list[ParsedLoan]), snapshots (dict keyed by prospectus_loan_id), reporting_period_start/end, total_loan_count, parse_errors (list[str])

2. Implement Ex102Parser class:
   - parse(xml_bytes) -> ParsedFiling — parses complete file
   - _parse_loan_element(element) -> tuple[ParsedLoan, ParsedLoanSnapshot] | None
   - _parse_decimal, _parse_date, _parse_int — safe type converters
   - _get_text(parent, tag) — get child element text handling namespaces
   - NEVER raise for a single malformed loan — log it, skip it, continue
   - Collect non-fatal errors in ParsedFiling.parse_errors
   - Only raise Ex102ParseError if XML is fundamentally unparseable

3. Tests in tests/test_xml_parser.py using the REAL fixture XML files:
   - Assert total loan count matches recon report
   - Assert first loan has non-null prospectus_loan_id, original_loan_amount, maturity_date
   - Assert snapshots have non-null beginning_balance, ending_balance
   - Assert property_name, property_city, borrower_name populated for some loans
   - Assert malformed XML input raises Ex102ParseError
   - Assert single malformed loan within valid XML does not abort parse

4. CLI command: 'python -m nli_cmbs.cli parse-xml <filepath>' outputs total loans, parse errors, and first 5 loans in a rich table.

VERIFICATION:
1. Ex102Parser exists at nli_cmbs/edgar/xml_parser.py
2. Parser correctly extracts loans from real fixture XML
3. Property and borrower fields are populated
4. 'python -m nli_cmbs.cli parse-xml tests/fixtures/<file>.xml' outputs a loan table
5. Tests pass: pytest tests/test_xml_parser.py -v
6. ruff check . passes
7. No field values are hardcoded

When ALL checks pass, output <promise>PHASE2_DONE</promise>.
If stuck after 12 iterations, write blockers to BLOCKERS.md and output <promise>PHASE2_DONE</promise>." --max-iterations 15 --completion-promise "PHASE2_DONE"
PHASE2_EOF


# =============================================================================
# PHASE 3: Loan Data Persistence
# =============================================================================

read -r -d '' PHASE3_PROMPT << 'PHASE3_EOF' || true
/ralph-loop:ralph-loop "In the nli-cmbs project, build the service that persists parsed XML data to PostgreSQL.

Prerequisite check: verify docker is running and PostgreSQL is accessible before starting.

IMPLEMENTATION:

1. Create nli_cmbs/services/ingest_service.py:
   - IngestService class with async ingest_filing(deal, filing, xml_bytes) -> IngestResult
   - Steps: parse XML with Ex102Parser -> upsert Loan records -> create LoanSnapshot records -> update Deal stats
   - Upsert loans on (deal_id, prospectus_loan_id) — same loan appears in every monthly filing
   - Create LoanSnapshot per loan per filing period — unique on (loan_id, filing_id)
   - Update Filing: set reporting_period_start/end, mark parsed=True
   - Update Deal: set loan_count, original_balance from parsed data
   - IngestResult model: deal_ticker, filing_accession, reporting_period, loans_created, loans_updated, snapshots_created, parse_errors, errors list

2. Add scan_deal method to deal_service.py:
   - Full pipeline: resolve CIK -> fetch filing -> download XML -> parse -> persist
   - Returns IngestResult

3. Update CLI scan command to:
   - Run full pipeline via deal_service.scan_deal()
   - Print IngestResult stats
   - Query DB and print summary: total loans, total UPB, delinquency counts, top 5 loans by balance with property_name and borrower_name
   - Use rich tables

4. Idempotency:
   - Running scan twice for same deal/filing must NOT create duplicates
   - Use Filing.parsed flag and unique constraints
   - Second run should show 'already parsed' or 'no new data'

5. Tests in tests/test_ingest_service.py:
   - Ingest a parsed filing, verify Loan and LoanSnapshot records created
   - Ingest same filing again, verify no duplicates
   - Verify IngestResult stats are accurate

VERIFICATION:
1. docker-compose up -d (PostgreSQL running)
2. alembic upgrade head succeeds
3. python -m nli_cmbs.cli scan 'BMARK 2024-V6' prints IngestResult stats and loan table with property_name and borrower_name
4. Run scan a SECOND time — no duplicates created
5. Verify in PostgreSQL: SELECT count(*) FROM loans; SELECT count(*) FROM loan_snapshots;
6. Tests pass: pytest tests/test_ingest_service.py -v
7. ruff check . passes

When ALL checks pass, output <promise>PHASE3_DONE</promise>.
If stuck after 12 iterations, write blockers to BLOCKERS.md and output <promise>PHASE3_DONE</promise>." --max-iterations 15 --completion-promise "PHASE3_DONE"
PHASE3_EOF


# =============================================================================
# PHASE 4: Multi-Deal Validation + API Endpoints
# =============================================================================

read -r -d '' PHASE4_PROMPT << 'PHASE4_EOF' || true
/ralph-loop:ralph-loop "In the nli-cmbs project, validate the parser against multiple deals and wire up API endpoints.

TASK A — MULTI-DEAL VALIDATION:
1. Run scan for at least 3 deals from different shelves (try in order, skip failures):
   - 'BMARK 2024-V6', 'BANK5 2024-5YR9', 'GSMS 2023-GC15', 'WFCM 2024-C64', 'COMM 2024-CALI'
2. For each successful deal, record in docs/parser_validation.md:
   - Ticker, CIK, filing date, total loans, parse errors
   - Sample of 3 loans with loan_id, property_name, city, state, balance, rate, delinquency
   - Fields that came back NULL that should not be (parser gaps)
3. Fix parser for any issuer-specific XML differences (namespaces, element names, date formats)
4. Get at least 2 deals working. Document failures in BLOCKERS.md.

TASK B — API ENDPOINTS:
1. Wire up endpoints to serve real data from PostgreSQL:
   - GET /deals -> list all deals with ticker, trust_name, loan_count, total_upb, delinquency_rate, last_filing_date
   - GET /deals/{ticker} -> deal detail with metrics: total_upb, wa_coupon, wa_remaining_term, delinquency rates by tier, loan_count
   - GET /deals/{ticker}/loans -> all loans with latest snapshot. Support ?delinquent=true, ?sort_by=ending_balance, ?limit=50
   - GET /loans/search -> make it return real data now (property/borrower fields populated)

2. Implement metrics in nli_cmbs/services/metrics.py:
   - total_upb, wa_coupon, delinquency_rate (by status), wa_remaining_term, loan_count

3. Update Pydantic response schemas to match.

VERIFICATION:
1. At least 2 deals ingested into PostgreSQL
2. docs/parser_validation.md documents results
3. FastAPI on port 8000
4. GET /deals returns deals with non-null metrics
5. GET /deals/BMARK%202024-V6 returns calculated metrics
6. GET /deals/BMARK%202024-V6/loans returns loans with snapshot data
7. GET /loans/search?state=NY returns results (or try another state that has data)
8. Metrics are reasonable (UPB in millions, rates 0-15%)
9. ruff check . passes

When ALL checks pass, output <promise>PHASE4_DONE</promise>.
If stuck after 12 iterations, write blockers to BLOCKERS.md and output <promise>PHASE4_DONE</promise>." --max-iterations 15 --completion-promise "PHASE4_DONE"
PHASE4_EOF


# =============================================================================
# EXECUTION
# =============================================================================

declare -a PHASE_NAMES=(
    ""
    "XML Reconnaissance"
    "EX-102 XML Parser"
    "Loan Data Persistence"
    "Multi-Deal Validation + API"
)

declare -a PHASE_PROMPTS=(
    ""
    "$PHASE1_PROMPT"
    "$PHASE2_PROMPT"
    "$PHASE3_PROMPT"
    "$PHASE4_PROMPT"
)

declare -a PHASE_ITERS=(0 12 15 15 15)

run_phases() {
    local start=${1:-1}
    local end=${2:-4}

    for i in $(seq "$start" "$end"); do
        log ""
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "  STARTING PHASE $i of 4: ${PHASE_NAMES[$i]}"
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log ""

        local logfile="$LOG_DIR/day2_phase${i}_${TIMESTAMP}.log"

        if claude --dangerously-skip-permissions -p "${PHASE_PROMPTS[$i]}" 2>&1 | tee "$logfile"; then
            log "✓ Phase $i (${PHASE_NAMES[$i]}) complete."
        else
            fail "Phase $i (${PHASE_NAMES[$i]}) exited with error."
            fail "Check log: $logfile"

            if [[ -f BLOCKERS.md ]]; then
                warn "Blockers documented in BLOCKERS.md:"
                cat BLOCKERS.md
            fi

            warn "Continuing to next phase anyway..."
        fi

        # Pause between phases for EDGAR rate limits
        log "Pausing 15 seconds between phases..."
        sleep 15
    done
}

log "NLI-CMBS Day 2 Build — XML Parsing + Persistence"
log "Mode: $MODE"
log "Project dir: $PROJECT_DIR"
log "Logs: $LOG_DIR"
log ""

if [[ -n "$SINGLE_PHASE" ]]; then
    if [[ "$SINGLE_PHASE" -lt 1 || "$SINGLE_PHASE" -gt 4 ]]; then
        fail "Phase must be 1-4, got: $SINGLE_PHASE"
        exit 1
    fi
    run_phases "$SINGLE_PHASE" "$SINGLE_PHASE"
else
    run_phases 1 4
fi

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "  DAY 2 BUILD COMPLETE"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "Verify results:"
log "  1. python -m nli_cmbs.cli scan 'BMARK 2024-V6'"
log "  2. curl http://localhost:8000/deals"
log "  3. curl http://localhost:8000/deals/BMARK%202024-V6/loans"
log "  4. curl 'http://localhost:8000/loans/search?state=CA'"
log "  5. Check docs/parser_validation.md for multi-deal results"
log "  6. Check BLOCKERS.md for any issues"
log ""
log "Build logs saved to: $LOG_DIR"
