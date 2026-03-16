"""Surveillance report prompt templates for CMBS deal analysis."""

SURVEILLANCE_SYSTEM_PROMPT = (
    "You are a junior credit analyst on the CMBS surveillance desk at a "
    "top-tier institutional asset manager. You write quarterly surveillance "
    "memos that go to senior PMs and the investment committee.\n"
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
    "DATA INTEGRITY:\n"
    "- Only reference data explicitly provided in the prompt. "
    "Never fabricate property names, loan amounts, borrower names, or metrics.\n"
    "- If data is missing or insufficient, state \"Data not available\" rather "
    "than inventing details.\n"
    "- Every claim must be traceable to the provided data.\n"
    "- Do not speculate about market conditions or make predictions not "
    "supported by the deal data.\n"
    "\n"
    "STRUCTURE:\n"
    "- Use exactly these 6 section headers in this order, formatted as "
    "markdown ## headers:\n"
    "  ## Executive Summary\n"
    "  ## Deal Performance Overview\n"
    "  ## Delinquency & Special Servicing\n"
    "  ## Maturity & Refinancing Risk\n"
    "  ## Top Loans\n"
    "  ## Outlook\n"
    "- Executive Summary must be exactly 3-4 sentences.\n"
    "- End with a --- divider followed by the Data Source footer.\n"
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

    # --- Top loans block ---
    top_lines = ["TOP LOANS BY BALANCE"]
    for i, loan in enumerate(top_loans[:10], 1):
        top_lines.append(
            f"  {i}. {loan.get('property_name', 'N/A')} — "
            f"{loan.get('city', 'N/A')}, {loan.get('state', 'N/A')} — "
            f"UPB: {format_currency(loan.get('current_upb', 0))} — "
            f"DSCR: {loan.get('dscr', 'N/A')} — "
            f"Occupancy: {loan.get('occupancy', 'N/A')}% — "
            f"Maturity: {loan.get('maturity_date', 'N/A')}"
        )
    top_block = "\n".join(top_lines)

    # --- Delinquent loans block ---
    delq_lines = ["DELINQUENT LOANS"]
    if delinquent_loans:
        for loan in delinquent_loans:
            status = format_delinquency_status(str(loan.get("delinquency_code", "")))
            delq_lines.append(
                f"  - {loan.get('property_name', 'N/A')} — "
                f"{loan.get('city', 'N/A')}, {loan.get('state', 'N/A')} — "
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
                f"  - {loan.get('property_name', 'N/A')} — "
                f"{loan.get('city', 'N/A')}, {loan.get('state', 'N/A')} — "
                f"UPB: {format_currency(loan.get('current_upb', 0))}"
            )
    else:
        ss_lines.append("  None.")
    ss_block = "\n".join(ss_lines)

    # --- Maturity schedule block ---
    mat_block = "MATURITY SCHEDULE\n" + format_maturity_schedule(maturity_schedule)

    # --- Filing metadata ---
    filing_date = filing_metadata.get("filing_date", "N/A")
    accession_number = filing_metadata.get("accession_number", "N/A")
    edgar_url = filing_metadata.get("edgar_url", "N/A")

    # --- Instruction block ---
    instructions = (
        "Write a surveillance memo using the deal data above. "
        "Follow the section structure and formatting rules "
        "from your system instructions exactly.\n"
        "\n"
        "For the Executive Summary: state deal name, current UPB, "
        "key credit metrics (WA DSCR, delinquency rate), and the "
        "single most important risk factor — in exactly 3-4 sentences.\n"
        "\n"
        "For Top Loans: profile the top 5 by UPB. For each loan "
        "state property name, city/state, UPB, DSCR, occupancy, "
        "and maturity date. Flag any with DSCR below 1.25x or "
        "maturity within 24 months.\n"
        "\n"
        "For Maturity & Refinancing Risk: reference specific years "
        "and dollar amounts from the maturity schedule. "
        "Identify concentration risk."
    )

    footer = (
        f"Data Source: ABS-EE filing dated {filing_date}, "
        f"Accession No. {accession_number}\n"
        f"SEC EDGAR: {edgar_url}"
    )

    # --- Assemble prompt ---
    prompt = (
        f"{deal_block}\n\n"
        f"{top_block}\n\n"
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
