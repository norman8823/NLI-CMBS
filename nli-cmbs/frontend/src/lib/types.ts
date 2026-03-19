/** GET /deals list item */
export interface DealListItem {
  id: string;
  ticker: string;
  trust_name: string;
  depositor_cik: string;
  trust_cik: string | null;
  issuer_shelf: string;
  issuance_year: number;
  original_balance: number | null;
  loan_count: number | null;
  total_upb: number | null;
  delinquency_rate: number | null;
  last_filing_date: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /deals/{ticker} detail */
export interface DealDetail {
  id: string;
  ticker: string;
  trust_name: string;
  depositor_cik: string;
  trust_cik: string | null;
  issuer_shelf: string;
  issuance_year: number;
  original_balance: number | null;
  loan_count: number | null;
  total_upb: number | null;
  wa_coupon: number | null;
  wa_remaining_term: number | null;
  delinquency_rate: number | null;
  delinquency_by_status: Record<string, number> | null;
  wa_dscr: number | null;
  wa_occupancy: number | null;
  wa_ltv: number | null;
  pct_interest_only: number | null;
  pct_balloon: number | null;
  has_current_financials: boolean;
  last_filing_date: string | null;
  last_filing_accession: string | null;
  created_at: string;
  updated_at: string;
}

/** Nested snapshot data from latest filing */
export interface LoanSnapshot {
  ending_balance: number | null;
  beginning_balance: number | null;
  current_interest_rate: number | null;
  delinquency_status: string | null;
  dscr_noi: number | null;
  dscr_ncf: number | null;
  noi: number | null;
  ncf: number | null;
  occupancy: number | null;
  revenue: number | null;
  operating_expenses: number | null;
  debt_service: number | null;
  appraised_value: number | null;
  dscr_noi_at_securitization: number | null;
  dscr_ncf_at_securitization: number | null;
  noi_at_securitization: number | null;
  ncf_at_securitization: number | null;
  occupancy_at_securitization: number | null;
  appraised_value_at_securitization: number | null;
  reporting_period_end_date: string | null;
}

/** Property detail for modal */
export interface LoanProperty {
  id: string | null;
  property_name: string | null;
  property_city: string | null;
  property_state: string | null;
  property_type: string | null;
  property_type_source: string | null; // 'reported' | 'inferred'
  net_rentable_sq_ft: number | null;
  year_built: number | null;
  valuation_securitization: number | null;
  occupancy_most_recent: number | null;
  noi_most_recent: number | null;
  largest_tenant: string | null;
}

/** GET /deals/{ticker}/loans item */
export interface Loan {
  id: string;
  deal_id: string;
  prospectus_loan_id: string;
  asset_number: number;
  originator_name: string | null;
  original_loan_amount: number;
  origination_date: string | null;
  maturity_date: string | null;
  original_term_months: number | null;
  original_amortization_term_months: number | null;
  original_interest_rate: number | null;
  property_type: string | null;
  property_name: string | null;
  property_city: string | null;
  property_state: string | null;
  borrower_name: string | null;
  interest_only_indicator: boolean | null;
  balloon_indicator: boolean | null;
  lien_position: string | null;
  property_count: number;
  parent_loan_id: string | null;
  parent_prospectus_loan_id: string | null;
  properties: LoanProperty[];
  parent_properties: LoanProperty[];
  created_at: string;
  latest_snapshot: LoanSnapshot | null;
  ai_blurb: string | null;
  ai_blurb_generated_at: string | null;
}

/** GET /properties/{id}/history */
export interface PropertySnapshot {
  reporting_period_end: string;
  occupancy: number | null;
  noi: number | null;
  ncf: number | null;
  dscr_noi: number | null;
  dscr_ncf: number | null;
  valuation_amount: number | null;
}

export interface PropertyHistory {
  property_id: string;
  property_name: string | null;
  snapshot_count: number;
  snapshots: PropertySnapshot[];
}

export interface MaturityBucket {
  year: number;
  loan_count: number;
  total_balance: number;
}

export interface Report {
  report_text: string;
  generated_at: string;
  model_used: string;
  filing_date: string;
  accession_number: string;
}
