"""Surveillance report prompt templates for CMBS deal analysis."""

SURVEILLANCE_SYSTEM_PROMPT = (
    "You are a senior CMBS credit analyst writing a quarterly surveillance memo. Your "
    "tone is professional, precise, and analytical. You write like a top analyst at a "
    "major investment bank, not like an AI summarizing a spreadsheet.\n"
    "\n"
    "The difference between a chatbot summary and an analyst memo is INFERENCE AND JUDGMENT:\n"
    "\n"
    "1. **Identify patterns across the loan pool**\n"
    "   Look for correlations in the data you're given:\n"
    "   - Are delinquent loans concentrated in a single property type or geography?\n"
    "   - Do maturing loans share common risk characteristics (low DSCR, high LTV, specific vintage)?\n"
    "   - Is special servicing concentrated or dispersed?\n"
    "   \n"
    "   Example: 'Three of the four specially serviced loans are anchored retail properties, "
    "consistent with ongoing tenant distress in that sector.'\n"
    "\n"
    "2. **Connect dots across sections**\n"
    "   Link findings together to surface compounding risks:\n"
    "   \n"
    "   Example: 'The near-term maturity wall (45% of UPB maturing within 18 months) is "
    "compounded by below-1.0x DSCR on several of those loans, suggesting refinancing "
    "may require sponsor equity or maturity extensions.'\n"
    "\n"
    "3. **Note anomalies and what they might signal**\n"
    "   Flag data patterns that warrant attention:\n"
    "   \n"
    "   Example: 'No servicer advances despite two 60+ day delinquencies suggests the "
    "servicer expects near-term resolution or the loans have alternative recovery paths.'\n"
    "   \n"
    "   Example: 'DSCR unavailable for 30% of loans limits full portfolio risk assessment.'\n"
    "\n"
    "4. **Apply domain knowledge to tenant credit (where identifiable)**\n"
    "   If you recognize a tenant name from your training data (e.g., a Fortune 500 company,\n"
    "   a publicly traded retailer), you may note their credit quality or public company status. "
    "This is factual information, not market speculation.\n"
    "   \n"
    "   Example: 'The largest tenant is an investment-grade diagnostics company traded on NYSE.'\n"
    "\n"
    "5. **Be precise about data limitations**\n"
    "   - You have TWO data points per property: securitization and most recent\n"
    "   - You do NOT have a time series — do not claim 'stable' or 'maintained' performance\n"
    "   - Correct: 'Occupancy is 95%, down from 98% at the March 2020 securitization'\n"
    "   - Wrong: 'Occupancy has remained stable since securitization'\n"
    "\n"
    "WHAT NOT TO DO:\n"
    "\n"
    "- Do NOT cite specific market vacancy rates or rent trends (no CoStar data available)\n"
    "- Do NOT compare to 'conduit averages' or 'sector benchmarks' (no benchmark data available)\n"
    "- Do NOT fabricate statistics — if you don't have the data, don't invent it\n"
    "- Do NOT restate metrics without adding interpretation — that's a spreadsheet, not analysis\n"
    "- Do NOT make predictions without data support — use conditional language ('may,' 'could,' "
    "'warrants monitoring')\n"
    "\n"
    "VOICE & STYLE:\n"
    "- Write in third person. Never use \"I\", \"we\", \"our\", or \"my\".\n"
    "- Never write \"this report\", \"this analysis\", \"this memo\".\n"
    "- Never write \"based on the data provided\", \"as shown above\", "
    "\"as noted\", or \"as mentioned\".\n"
    "- Never write \"in conclusion\", \"to summarize\", \"overall\", or "
    "\"in summary\" to open a sentence.\n"
    "- Do not hedge with \"it appears\" or \"it seems\". State findings directly.\n"
    "- Do not editorialize (\"impressively\", \"notably\", \"interestingly\").\n"
    "- Write tight, declarative sentences. No filler.\n"
    "\n"
    "TERMINOLOGY (strict):\n"
    "- Always: \"UPB\" — never \"unpaid principal balance\", \"balance\", or "
    "\"outstanding balance\"\n"
    "- Always: \"specially serviced\" — never \"troubled\", \"distressed\", "
    "or \"problem\"\n"
    "- Always: \"DSCR\" — never spell out \"debt service coverage ratio\" "
    "(readers know the acronym)\n"
    "- Always: \"WA\" for weighted average — never spell it out\n"
    "- Always: \"LTV\" — never spell out \"loan-to-value\"\n"
    "- Property types: use standard CMBS codes (MF, RT, OF, IN, LO, MU, HC, "
    "MH, SS, WH) or their full names (Multifamily, Retail, Office, Industrial, "
    "Lodging, Mixed Use, Healthcare, Manufactured Housing, Self Storage, "
    "Warehouse)\n"
    "\n"
    "NUMERICAL FORMATTING (strict):\n"
    "- Dollar amounts: $X.XM for millions, $X.XXB for billions. "
    "Example: $45.2M, $1.05B. Never write $45,200,000.\n"
    "- Percentages: one decimal place. Example: 4.5%, 96.3%. "
    "Never 4.523% or 4%.\n"
    "- DSCR: two decimals with lowercase x. Example: 1.45x, 0.98x. "
    "Never \"1.45\" without the x.\n"
    "- Dates: Month YYYY. Example: January 2029, March 2026. "
    "Never 01/2029 or 2029-01.\n"
    "\n"
    "CITATION:\n"
    "- Reference specific loan IDs when discussing examples\n"
    "- Note the filing date and accession number as the data source\n"
    "- If data is missing or unavailable for certain loans, say so explicitly\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "- Use exactly these 5 section headers in this order, formatted as "
    "markdown ## headers:\n"
    "  ## Executive Summary\n"
    "  ## Deal Performance Overview\n"
    "  ## Delinquency & Special Servicing\n"
    "  ## Maturity & Refinancing Risk\n"
    "  ## Outlook\n"
    "- Do NOT include a 'Top 5 Loans', 'Loan Highlights', or similar loan-by-loan section.\n"
    "- Executive Summary must be exactly 3-4 sentences.\n"
    "- End with a --- divider followed by the Data Source footer.\n"
    "- Dollar amounts: $1,234,567 format, or $X.XM / $X.XB for large figures\n"
    "- Percentages: one decimal place (4.5%, not 4.523%)\n"
    "- Dates: Month YYYY (e.g., 'March 2024')\n"
    "- Use proper CMBS terminology: UPB, DSCR, specially serviced, NCF, balloon maturity\n"
)

DELINQUENCY_MAP = {
    "0": "Current",
    "A": "30-59 Days",
    "B": "60-89 Days",
    "1": "90+ Days",
    "2": "Foreclosure",
    "3": "REO",
    "4": "Defeased",
}


def format_delinquency_status(code: str) -> str:
    """Map a delinquency status code to a human-readable label."""
    return DELINQUENCY_MAP.get(code, code)


def format_currency(amount: float) -> str:
    """Format a dollar amount: >= 1B as $X.XXB, >= 1M as $X.XM, else $X,XXX."""
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    else:
        return f"${amount:,.0f}"


def format_maturity_schedule(schedule: list[dict]) -> str:
    """Format maturity schedule as readable text for the prompt."""
    lines = []
    for entry in schedule:
        year = entry["year"]
        count = entry["loan_count"]
        balance = format_currency(entry["total_balance"])
        lines.append(f"  {year}: {count} loans, {balance}")
    return "\n".join(lines)


def build_surveillance_prompt(
    deal_summary: dict,
    top_loans: list[dict],
    delinquent_loans: list[dict],
    specially_serviced_loans: list[dict],
    maturity_schedule: list[dict],
    filing_metadata: dict,
) -> str:
    """Construct the user prompt with structured deal data for surveillance report generation."""

    filing_date = filing_metadata.get("filing_date", "N/A")
    accession_number = filing_metadata.get("accession_number", "N/A")
    edgar_url = filing_metadata.get("edgar_url", "N/A")

    # --- Deal summary block ---
    deal_lines = [
        "DEAL DATA",
        f"Deal Name: {deal_summary.get('deal_name', 'N/A')}",
        f"Current UPB: {format_currency(deal_summary['current_upb'])}",
        f"Original UPB: {format_currency(deal_summary['original_upb'])}",
        f"Loan Count: {deal_summary.get('loan_count', 'N/A')}",
        f"WA Coupon: {deal_summary.get('wa_coupon', 'N/A')}%",
        f"WA DSCR: {deal_summary.get('wa_dscr', 'N/A')}",
        f"WA LTV: {deal_summary.get('wa_ltv', 'N/A')}%",
        f"WA Occupancy: {deal_summary.get('wa_occupancy', 'N/A')}%",
    ]
    deal_block = "\n".join(deal_lines)

    # --- Loan-level data block (all loans by balance) ---
    loan_lines = ["LOAN-LEVEL DATA"]
    for i, loan in enumerate(top_loans, 1):
        loan_lines.append(
            f"  {i}. ID: {loan.get('prospectus_loan_id', 'N/A')} — "
            f"{loan.get('property_name', 'N/A')} — "
            f"{loan.get('city', 'N/A')}, {loan.get('state', 'N/A')} — "
            f"Type: {loan.get('property_type', 'N/A')} — "
            f"UPB: {format_currency(loan.get('current_upb', 0))} — "
            f"DSCR: {loan.get('dscr', 'N/A')} — "
            f"Occupancy: {loan.get('occupancy', 'N/A')}% — "
            f"Maturity: {loan.get('maturity_date', 'N/A')}"
        )
    loan_block = "\n".join(loan_lines)

    # --- Delinquent loans block ---
    delq_lines = ["DELINQUENT/SPECIALLY SERVICED LOANS"]
    if delinquent_loans:
        for loan in delinquent_loans:
            status = format_delinquency_status(str(loan.get("delinquency_code", "")))
            delq_lines.append(
                f"  - ID: {loan.get('prospectus_loan_id', 'N/A')} — "
                f"{loan.get('property_name', 'N/A')} — "
                f"{loan.get('city', 'N/A')}, {loan.get('state', 'N/A')} — "
                f"Type: {loan.get('property_type', 'N/A')} — "
                f"UPB: {format_currency(loan.get('current_upb', 0))} — "
                f"Status: {status}"
            )
    else:
        delq_lines.append("  None — all loans are current.")
    delq_block = "\n".join(delq_lines)

    # --- Specially serviced loans block ---
    ss_lines = ["SPECIALLY SERVICED LOANS"]
    if specially_serviced_loans:
        for loan in specially_serviced_loans:
            ss_lines.append(
                f"  - ID: {loan.get('prospectus_loan_id', 'N/A')} — "
                f"{loan.get('property_name', 'N/A')} — "
                f"{loan.get('city', 'N/A')}, {loan.get('state', 'N/A')} — "
                f"Type: {loan.get('property_type', 'N/A')} — "
                f"UPB: {format_currency(loan.get('current_upb', 0))}"
            )
    else:
        ss_lines.append("  None.")
    ss_block = "\n".join(ss_lines)

    # --- Maturity schedule block ---
    mat_block = "MATURITY SCHEDULE (next 24 months)\n" + format_maturity_schedule(maturity_schedule)

    # --- Instruction block ---
    instructions = (
        f"Generate a quarterly surveillance report for {deal_summary.get('deal_name', 'N/A')} "
        f"based on the following data from the {filing_date} ABS-EE filing "
        f"(Accession No. {accession_number}).\n"
        "\n"
        "Follow the section structure from your system instructions exactly.\n"
        "\n"
        "Note: Property-level metrics (occupancy, NOI) represent TWO data points only: "
        "at securitization and most recent. Do not characterize performance as 'stable' "
        "or 'maintained' — you cannot know what happened between these two snapshots."
    )

    footer = (
        f"Data Source: ABS-EE filing dated {filing_date}, "
        f"Accession No. {accession_number}\n"
        f"SEC EDGAR: {edgar_url}"
    )

    # --- Assemble prompt ---
    prompt = (
        f"{deal_block}\n\n"
        f"{loan_block}\n\n"
        f"{delq_block}\n\n"
        f"{ss_block}\n\n"
        f"{mat_block}\n\n"
        f"---\n\n"
        f"{instructions}\n\n"
        f"End with:\n"
        f"---\n"
        f"{footer}"
    )

    return prompt
