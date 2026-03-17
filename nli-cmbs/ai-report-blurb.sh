#!/bin/bash
# =============================================================================
# NLI-CMBS AI Report & Blurb Implementation — Ralph Loop Script
# =============================================================================
#
# USAGE:
#   chmod +x ai-report-blurb.sh
#   ./ai-report-blurb.sh
#
# This script runs with --dangerously-skip-permissions to avoid approval prompts.
# =============================================================================

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="ai-report-blurb-${TIMESTAMP}.log"

echo "Starting AI Report & Blurb implementation at $(date)"
echo "Logging to: $LOG_FILE"

# =============================================================================
# COMBINED PROMPT — Report + Blurb + Quality Control
# =============================================================================

read -r -d '' FULL_PROMPT << 'PROMPT_EOF' || true
Implement AI-powered surveillance reports and loan-level blurbs for NLI-CMBS.
This is a two-part implementation with quality control verification.

═══════════════════════════════════════════════════════════════════════════════
PART 1: UPDATE DEAL-LEVEL SURVEILLANCE REPORT
═══════════════════════════════════════════════════════════════════════════════

Location: nli_cmbs/services/report_service.py (or wherever the Claude API 
prompt for report generation lives)

SECTION STRUCTURE (keep unchanged):
1. Executive Summary (3-4 sentences)
2. Deal Performance Overview
3. Delinquency & Special Servicing
4. Maturity & Refinancing Risk
5. Outlook

REMOVE: "Top 5 Loans" or "Loan Highlights" section entirely.

UPDATE THE SYSTEM PROMPT TO:

---

"You are a senior CMBS credit analyst writing a quarterly surveillance memo. Your 
tone is professional, precise, and analytical. You write like a top analyst at a 
major investment bank, not like an AI summarizing a spreadsheet.

The difference between a chatbot summary and an analyst memo is INFERENCE AND JUDGMENT:

1. **Identify patterns across the loan pool**
   Look for correlations in the data you're given:
   - Are delinquent loans concentrated in a single property type or geography?
   - Do maturing loans share common risk characteristics (low DSCR, high LTV, specific vintage)?
   - Is special servicing concentrated or dispersed?
   
   Example: 'Three of the four specially serviced loans are anchored retail properties, 
   consistent with ongoing tenant distress in that sector.'

2. **Connect dots across sections**
   Link findings together to surface compounding risks:
   
   Example: 'The near-term maturity wall (45% of UPB maturing within 18 months) is 
   compounded by below-1.0x DSCR on several of those loans, suggesting refinancing 
   may require sponsor equity or maturity extensions.'

3. **Note anomalies and what they might signal**
   Flag data patterns that warrant attention:
   
   Example: 'No servicer advances despite two 60+ day delinquencies suggests the 
   servicer expects near-term resolution or the loans have alternative recovery paths.'
   
   Example: 'DSCR unavailable for 30% of loans limits full portfolio risk assessment.'

4. **Apply domain knowledge to tenant credit (where identifiable)**
   If you recognize a tenant name from your training data (e.g., a Fortune 500 company,
   a publicly traded retailer), you may note their credit quality or public company status. 
   This is factual information, not market speculation.
   
   Example: 'The largest tenant is an investment-grade diagnostics company traded on NYSE.'

5. **Be precise about data limitations**
   - You have TWO data points per property: securitization and most recent
   - You do NOT have a time series — do not claim 'stable' or 'maintained' performance
   - Correct: 'Occupancy is 95%, down from 98% at the March 2020 securitization'
   - Wrong: 'Occupancy has remained stable since securitization'

WHAT NOT TO DO:

- Do NOT cite specific market vacancy rates or rent trends (no CoStar data available)
- Do NOT compare to 'conduit averages' or 'sector benchmarks' (no benchmark data available)
- Do NOT fabricate statistics — if you don't have the data, don't invent it
- Do NOT restate metrics without adding interpretation — that's a spreadsheet, not analysis
- Do NOT make predictions without data support — use conditional language ('may,' 'could,' 
  'warrants monitoring')

CITATION:
- Reference specific loan IDs when discussing examples
- Note the filing date and accession number as the data source
- If data is missing or unavailable for certain loans, say so explicitly

OUTPUT FORMAT:
- Use standard section headers (Executive Summary, Deal Performance, etc.)
- Dollar amounts: $1,234,567 format, or $X.XM / $X.XB for large figures
- Percentages: one decimal place (4.5%, not 4.523%)
- Dates: Month YYYY (e.g., 'March 2024')
- Use proper CMBS terminology: UPB, DSCR, specially serviced, NCF, balloon maturity"

---

USER PROMPT TEMPLATE (update accordingly):

"Generate a quarterly surveillance report for {deal_ticker} based on the following 
data from the {filing_date} ABS-EE filing (Accession No. {accession_number}).

DEAL SUMMARY:
{deal_summary_json}

LOAN-LEVEL DATA:
{loans_json}

DELINQUENT/SPECIALLY SERVICED LOANS:
{delinquent_loans_json}

MATURITY SCHEDULE (next 24 months):
{maturity_schedule_json}

Note: Property-level metrics (occupancy, NOI) represent TWO data points only: 
at securitization and most recent. Do not characterize performance as 'stable' 
or 'maintained' — you cannot know what happened between these two snapshots."

---

═══════════════════════════════════════════════════════════════════════════════
PART 2: ADD LOAN-LEVEL BLURB FOR PROPERTY MODAL
═══════════════════════════════════════════════════════════════════════════════

## 2A. Schema change

Create alembic migration to add to loans table:
- ai_blurb (TEXT, nullable)
- ai_blurb_generated_at (TIMESTAMP WITH TIME ZONE, nullable)

Run: alembic revision -m "add ai_blurb to loans"
Then update the migration file and run: alembic upgrade head

## 2B. API endpoint

Add GET /loans/{loan_id}/blurb endpoint in nli_cmbs/api/endpoints/loans.py:

1. Look up loan by UUID
2. Check if ai_blurb exists and ai_blurb_generated_at < 30 days ago
3. If cached and fresh, return: { "blurb": ai_blurb, "generated_at": ai_blurb_generated_at }
4. If not, call Claude API to generate blurb, save to DB, return it

## 2C. Blurb generation service

Create nli_cmbs/services/blurb_service.py with generate_loan_blurb() function.

SYSTEM PROMPT:
"You are a CMBS credit analyst writing a 2-3 sentence summary for a loan detail view. 
Focus on what's notable — do not restate metrics the user already sees on screen."

USER PROMPT TEMPLATE:
"Generate a brief credit note for this loan.

LOAN: {prospectus_loan_id}
DEAL: {deal_ticker}
SECURITIZATION DATE: {securitization_date}  # Use valuation_securitization_date or deal.issuance_year
PROPERTY COUNT: {property_count}
BALANCE: ${ending_balance}
RATE: {current_interest_rate}%
MATURITY: {maturity_date}
DSCR: {dscr_noi}
DELINQUENCY: {delinquency_status}

PROPERTIES:
{for each property}
- {property_name}, {property_city}, {property_state}
  Type: {property_type}
  Year Built: {year_built}
  Sq Ft: {net_rentable_sq_ft}
  Occupancy at securitization: {occupancy_securitization}%
  Occupancy most recent: {occupancy_most_recent}%
  NOI at securitization: ${noi_securitization}
  NOI most recent: ${noi_most_recent}
  Largest Tenant: {largest_tenant}
{end for}

GUIDELINES:

1. DO NOT restate balance, rate, maturity, DSCR — the user sees these already.

2. OCCUPANCY/NOI: You have exactly TWO data points — securitization and most recent.
   - Correct: 'Occupancy is 87%, down from 100% at the {securitization_date} securitization'
   - Correct: 'NOI declined 29% since the {securitization_date} securitization, from $21.6M to $15.3M'
   - Wrong: 'Occupancy has been stable' or 'maintained 100%' or 'NOI declined' (without date context)
   - If both values are the same, say 'unchanged since the {securitization_date} securitization'
   - ALWAYS include the securitization date when discussing changes

3. SINGLE-TENANT PROPERTIES: 100% occupancy is trivial for single-tenant assets — 
   the tenant is either there or gone. Note this if relevant:
   'As a single-tenant property, occupancy is binary — the tenant remains in place.'

4. DATA ANOMALIES: Flag suspicious patterns that warrant attention:
   - If occupancy unchanged but NOI dropped significantly: 'NOI declined 29% since the 
     {securitization_date} securitization despite unchanged occupancy — may reflect rent 
     reductions, concessions, or expense increases'
   - If NOI is null for some properties: 'NOI unavailable for X of Y properties'

5. TENANT CREDIT: If you recognize a tenant from your training data, note their credit 
   quality or public status. Only do this for tenants you're confident about.

6. MULTI-PROPERTY CONCENTRATION: For portfolio loans, note geographic or property type 
   concentration if notable:
   '8 of 12 properties are in Texas, creating geographic concentration risk'

7. MATURITY CONTEXT: If maturity is within 18 months and DSCR is below 1.25x, flag 
   refinancing risk. If maturity is 5+ years out, note the runway.

8. LENGTH: 2-3 sentences maximum. Be direct."

## 2D. Update API response

Update GET /deals/{ticker}/loans to include ai_blurb field on each loan 
(null if not generated yet).

Update LoanOut schema in nli_cmbs/schemas/loan.py to include:
- ai_blurb: str | None
- ai_blurb_generated_at: datetime | None

## 2E. Frontend

In frontend/src/components/dashboard/PropertyModal.tsx:

1. Add state: blurb (string | null), blurbLoading (boolean), blurbError (boolean)
2. On modal open, if loan has ai_blurb already, display it
3. If not, call GET /loans/{loan_id}/blurb
4. Display blurb at TOP of modal body, before the properties table
5. Style: bg-slate-50 dark:bg-slate-800, text-sm, rounded-md, p-3, mb-4
6. Show subtle loading skeleton while fetching (not a spinner)
7. If blurb fails to generate, hide the blurb section silently (don't crash modal)

Update frontend/src/lib/types.ts to add:
- ai_blurb: string | null to Loan interface
- ai_blurb_generated_at: string | null to Loan interface

Add to frontend/src/lib/api.ts:
export async function fetchLoanBlurb(loanId: string): Promise<{ blurb: string }> {
  const { data } = await api.get(`/loans/${loanId}/blurb`);
  return data;
}

═══════════════════════════════════════════════════════════════════════════════
PART 3: QUALITY CONTROL VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

After implementation, run these verification steps:

## 3A. Generate a test report and evaluate

Run this command to generate a report for MSBAM 2015-C22:
curl -s "http://localhost:8000/deals/MSBAM%202015-C22/report?regenerate=true" | python -m json.tool > test_report.json

Then evaluate the report_text field against these criteria:

REPORT QUALITY CHECKLIST:
[ ] Does NOT contain any specific market vacancy rates (e.g., "Houston office vacancy is 24%")
[ ] Does NOT compare to "conduit average" or "sector benchmark"
[ ] Does NOT say "stable" or "maintained" for occupancy/NOI (only 2 data points)
[ ] DOES reference specific loan IDs when discussing examples
[ ] DOES include the filing date and accession number
[ ] DOES identify at least one pattern (property type concentration, geography, maturity clustering)
[ ] DOES use proper CMBS terminology (UPB, DSCR, specially serviced, NCF)
[ ] Reads like an analyst memo, not a metric dump

Print the report and flag any violations of the above criteria.

## 3B. Generate test blurbs and evaluate

Generate blurbs for 3 test loans:

# Loan 1 - multi-property portfolio (should flag NOI changes)
curl -s "http://localhost:8000/loans/{loan_1_uuid}/blurb" | python -m json.tool > test_blurb_1.json

# Loan 1A - A/B note (should reference parent loan properties)  
curl -s "http://localhost:8000/loans/{loan_1a_uuid}/blurb" | python -m json.tool > test_blurb_1a.json

# Single property loan
curl -s "http://localhost:8000/loans/{loan_2_uuid}/blurb" | python -m json.tool > test_blurb_2.json

Get the loan UUIDs first:
curl -s "http://localhost:8000/deals/MSBAM%202015-C22/loans?limit=10" | python -c "
import json, sys
data = json.load(sys.stdin)
for loan in data[:5]:
    print(f\"{loan['prospectus_loan_id']}: {loan['id']}\")
"

BLURB QUALITY CHECKLIST (for each blurb):
[ ] Does NOT say "stable" or "maintained" 
[ ] Does NOT say "declined" without "since securitization" and the date
[ ] DOES include securitization date when discussing changes
[ ] DOES flag anomalies (e.g., NOI down but occupancy unchanged)
[ ] DOES NOT restate balance, rate, maturity, DSCR
[ ] Is 2-3 sentences, not longer
[ ] Notes single-tenant status if applicable

Print each blurb and flag any violations.

## 3C. Database verification

Verify the migration ran correctly:
docker-compose exec postgres psql -U nli -d nli_cmbs -c "\d loans" | grep ai_blurb

Should show:
ai_blurb                | text
ai_blurb_generated_at   | timestamp with time zone

## 3D. Frontend verification

Rebuild frontend and verify modal works:
cd frontend && npm run build

Then manually test (or use curl to verify API):
- GET /deals/MSBAM%202015-C22/loans should include ai_blurb field (null initially)
- After calling /loans/{id}/blurb, the ai_blurb should be populated
- Second call to /loans/{id}/blurb should return cached version (check timestamps)

═══════════════════════════════════════════════════════════════════════════════
SUCCESS CRITERIA
═══════════════════════════════════════════════════════════════════════════════

The implementation is complete when ALL of the following pass:

1. [ ] alembic upgrade head runs successfully with new ai_blurb columns
2. [ ] GET /deals/{ticker}/report returns a report that passes the quality checklist
3. [ ] GET /loans/{id}/blurb returns a blurb that passes the quality checklist
4. [ ] Blurbs are cached in DB (second call returns same blurb without new generation)
5. [ ] Frontend PropertyModal displays blurb above property table
6. [ ] ruff check . passes
7. [ ] npm run build succeeds in frontend/

When ALL checks pass, output: <promise>AI_REPORT_BLURB_DONE</promise>

If stuck after 20 iterations, document blockers in BLOCKERS.md and output the promise anyway.
PROMPT_EOF

# =============================================================================
# EXECUTION
# =============================================================================

echo "Running Claude Code with Ralph loop..."
echo "This will take several iterations. Check $LOG_FILE for progress."
echo ""

claude --dangerously-skip-permissions -p "$FULL_PROMPT" 2>&1 | tee "$LOG_FILE"

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "  SCRIPT COMPLETE"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "Log file: $LOG_FILE"
echo ""
echo "Next steps:"
echo "  1. Review test_report.json for report quality"
echo "  2. Review test_blurb_*.json for blurb quality"
echo "  3. Open http://localhost:5173 and test the modal UI"
echo "  4. Check BLOCKERS.md if any issues were documented"