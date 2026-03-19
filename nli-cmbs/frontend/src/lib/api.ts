import axios from "axios";
import type { DealListItem, DealDetail, Loan, MaturityBucket, Report, PropertyHistory } from "./types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
});

export async function fetchDeals(): Promise<DealListItem[]> {
  const { data } = await api.get<DealListItem[]>("/deals/");
  return data;
}

export async function fetchDeal(ticker: string): Promise<DealDetail> {
  const { data } = await api.get<DealDetail>(`/deals/${ticker}`);
  return data;
}

export async function fetchLoans(ticker: string): Promise<Loan[]> {
  const { data } = await api.get<Loan[]>(`/deals/${ticker}/loans`, {
    params: { limit: 500, sort_by: "ending_balance" },
  });
  return data;
}

export async function fetchMaturityWall(
  ticker: string
): Promise<MaturityBucket[]> {
  const { data } = await api.get<MaturityBucket[]>(
    `/deals/${ticker}/maturity-wall`
  );
  return data;
}

export async function fetchReport(
  ticker: string,
  regenerate = false
): Promise<Report> {
  const { data } = await api.get<Report>(`/deals/${ticker}/report`, {
    params: regenerate ? { regenerate: true } : undefined,
  });
  return data;
}

export async function fetchPropertyHistory(
  propertyId: string
): Promise<PropertyHistory> {
  const { data } = await api.get<PropertyHistory>(
    `/properties/${propertyId}/history`
  );
  return data;
}

export async function fetchLoanBlurb(
  loanId: string
): Promise<{ blurb: string }> {
  const { data } = await api.get(`/loans/${loanId}/blurb`);
  return data;
}
