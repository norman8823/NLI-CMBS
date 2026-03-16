"""Tests for surveillance report prompt templates."""

from nli_cmbs.ai.prompts import (
    build_surveillance_prompt,
    format_currency,
    format_delinquency_status,
    format_maturity_schedule,
)

# --- Delinquency mapping ---


def test_delinquency_current():
    assert format_delinquency_status("0") == "Current"


def test_delinquency_30_day():
    assert format_delinquency_status("A") == "30-59 Days"


def test_delinquency_60_day():
    assert format_delinquency_status("B") == "60-89 Days"


def test_delinquency_90_plus():
    assert format_delinquency_status("1") == "90+ Days"


def test_delinquency_foreclosure():
    assert format_delinquency_status("2") == "Foreclosure"


def test_delinquency_reo():
    assert format_delinquency_status("3") == "REO"


def test_delinquency_defeased():
    assert format_delinquency_status("4") == "Defeased"


def test_delinquency_unknown_passthrough():
    assert format_delinquency_status("X") == "X"


# --- Currency formatting ---


def test_format_currency_billions():
    assert format_currency(1_500_000_000) == "$1.50B"


def test_format_currency_one_billion():
    assert format_currency(1_000_000_000) == "$1.00B"


def test_format_currency_millions():
    assert format_currency(75_000_000) == "$75.0M"


def test_format_currency_one_million():
    assert format_currency(1_000_000) == "$1.0M"


def test_format_currency_thousands():
    assert format_currency(500_000) == "$500,000"


def test_format_currency_small():
    assert format_currency(1_234) == "$1,234"


# --- Maturity schedule formatting ---


def test_format_maturity_schedule():
    schedule = [
        {"year": 2026, "loan_count": 5, "total_balance": 120_000_000},
        {"year": 2027, "loan_count": 12, "total_balance": 1_800_000_000},
    ]
    result = format_maturity_schedule(schedule)
    assert "2026: 5 loans, $120.0M" in result
    assert "2027: 12 loans, $1.80B" in result


# --- Prompt construction ---


SAMPLE_DEAL_SUMMARY = {
    "deal_name": "BANK5 2023-BNK45",
    "current_upb": 950_000_000,
    "original_upb": 1_000_000_000,
    "loan_count": 45,
    "wa_coupon": 5.2,
    "wa_dscr": 1.85,
    "wa_ltv": 58.3,
    "wa_occupancy": 94.1,
}

SAMPLE_TOP_LOANS = [
    {
        "property_name": "One Manhattan West",
        "city": "New York",
        "state": "NY",
        "current_upb": 120_000_000,
        "dscr": 2.1,
        "occupancy": 98.0,
        "maturity_date": "January 2028",
    },
    {
        "property_name": "Riverpark Tower",
        "city": "Chicago",
        "state": "IL",
        "current_upb": 85_000_000,
        "dscr": 1.45,
        "occupancy": 91.0,
        "maturity_date": "March 2027",
    },
]

SAMPLE_DELINQUENT = [
    {
        "property_name": "Sunset Mall",
        "city": "Phoenix",
        "state": "AZ",
        "current_upb": 25_000_000,
        "delinquency_code": "A",
    },
]

SAMPLE_SPECIALLY_SERVICED = [
    {
        "property_name": "Harbor Office Park",
        "city": "Baltimore",
        "state": "MD",
        "current_upb": 18_000_000,
    },
]

SAMPLE_MATURITY = [
    {"year": 2026, "loan_count": 3, "total_balance": 80_000_000},
    {"year": 2027, "loan_count": 10, "total_balance": 350_000_000},
    {"year": 2028, "loan_count": 20, "total_balance": 520_000_000},
]

SAMPLE_FILING = {
    "filing_date": "February 2026",
    "accession_number": "0001234567-26-000123",
    "edgar_url": "https://www.sec.gov/Archives/edgar/data/12345/0001234567-26-000123.txt",
}


def test_prompt_contains_all_sections():
    prompt = build_surveillance_prompt(
        deal_summary=SAMPLE_DEAL_SUMMARY,
        top_loans=SAMPLE_TOP_LOANS,
        delinquent_loans=SAMPLE_DELINQUENT,
        specially_serviced_loans=SAMPLE_SPECIALLY_SERVICED,
        maturity_schedule=SAMPLE_MATURITY,
        filing_metadata=SAMPLE_FILING,
    )
    # Section instructions are split between system prompt and user prompt.
    # User prompt references key sections; system prompt has the full list.
    assert "Executive Summary" in prompt
    assert "Top Loans" in prompt
    assert "Maturity & Refinancing Risk" in prompt

    # System prompt contains all 6 section headers
    from nli_cmbs.ai.prompts import SURVEILLANCE_SYSTEM_PROMPT

    for section in [
        "Executive Summary",
        "Deal Performance Overview",
        "Delinquency & Special Servicing",
        "Maturity & Refinancing Risk",
        "Top Loans",
        "Outlook",
    ]:
        assert section in SURVEILLANCE_SYSTEM_PROMPT, f"Missing section in system prompt: {section}"


def test_prompt_contains_deal_data():
    prompt = build_surveillance_prompt(
        deal_summary=SAMPLE_DEAL_SUMMARY,
        top_loans=SAMPLE_TOP_LOANS,
        delinquent_loans=SAMPLE_DELINQUENT,
        specially_serviced_loans=SAMPLE_SPECIALLY_SERVICED,
        maturity_schedule=SAMPLE_MATURITY,
        filing_metadata=SAMPLE_FILING,
    )
    assert "BANK5 2023-BNK45" in prompt
    assert "$950.0M" in prompt
    assert "$1.00B" in prompt


def test_prompt_contains_filing_metadata():
    prompt = build_surveillance_prompt(
        deal_summary=SAMPLE_DEAL_SUMMARY,
        top_loans=SAMPLE_TOP_LOANS,
        delinquent_loans=SAMPLE_DELINQUENT,
        specially_serviced_loans=SAMPLE_SPECIALLY_SERVICED,
        maturity_schedule=SAMPLE_MATURITY,
        filing_metadata=SAMPLE_FILING,
    )
    assert "February 2026" in prompt
    assert "0001234567-26-000123" in prompt
    assert "sec.gov" in prompt


def test_prompt_contains_delinquent_loans():
    prompt = build_surveillance_prompt(
        deal_summary=SAMPLE_DEAL_SUMMARY,
        top_loans=SAMPLE_TOP_LOANS,
        delinquent_loans=SAMPLE_DELINQUENT,
        specially_serviced_loans=SAMPLE_SPECIALLY_SERVICED,
        maturity_schedule=SAMPLE_MATURITY,
        filing_metadata=SAMPLE_FILING,
    )
    assert "Sunset Mall" in prompt
    assert "30-59 Days" in prompt


def test_prompt_contains_specially_serviced():
    prompt = build_surveillance_prompt(
        deal_summary=SAMPLE_DEAL_SUMMARY,
        top_loans=SAMPLE_TOP_LOANS,
        delinquent_loans=SAMPLE_DELINQUENT,
        specially_serviced_loans=SAMPLE_SPECIALLY_SERVICED,
        maturity_schedule=SAMPLE_MATURITY,
        filing_metadata=SAMPLE_FILING,
    )
    assert "Harbor Office Park" in prompt


def test_prompt_no_delinquencies():
    prompt = build_surveillance_prompt(
        deal_summary=SAMPLE_DEAL_SUMMARY,
        top_loans=SAMPLE_TOP_LOANS,
        delinquent_loans=[],
        specially_serviced_loans=[],
        maturity_schedule=SAMPLE_MATURITY,
        filing_metadata=SAMPLE_FILING,
    )
    assert "all loans are current" in prompt


def test_prompt_returns_string():
    prompt = build_surveillance_prompt(
        deal_summary=SAMPLE_DEAL_SUMMARY,
        top_loans=SAMPLE_TOP_LOANS,
        delinquent_loans=SAMPLE_DELINQUENT,
        specially_serviced_loans=SAMPLE_SPECIALLY_SERVICED,
        maturity_schedule=SAMPLE_MATURITY,
        filing_metadata=SAMPLE_FILING,
    )
    assert isinstance(prompt, str)
    assert len(prompt) > 100
