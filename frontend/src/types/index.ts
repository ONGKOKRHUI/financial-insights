export interface CompanySummary {
  ticker: string;
  name: string;
  sector: string;
  market_cap_bln: number;
  currency: string;
}

export interface CompanyDetail {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  description: string;
  market_cap_bln: number;
  employees: number;
  founded: number;
  headquarters: string;
  website: string;
  currency: string;
  exchange: string;
}

export interface KPISummary {
  ticker: string;
  revenue_bln: number;
  net_income_bln: number;
  eps: number;
  pe_ratio: number | null;
  roe_pct: number;
  debt_to_equity: number;
  dividend_yield_pct: number | null;
  fiscal_year: number;
}

export interface IncomeStatementEntry {
  fiscal_year: number;
  revenue_bln: number | null;
  gross_profit_bln: number | null;
  operating_income_bln: number | null;
  net_income_bln: number | null;
  eps: number | null;
  gross_margin_pct: number | null;
  operating_margin_pct: number | null;
  net_margin_pct: number | null;
}

export interface IncomeStatementResponse {
  ticker: string;
  name: string;
  currency: string;
  data: IncomeStatementEntry[];
}

export interface LiveSearchResult {
  rank: number;
  title: string;
  snippet: string;
  source_path: string;
  source_uri: string | null;
  score: number;
  doc_type: string;
  domain: string;
  ticker: string | null;
}

export interface LiveSearchResponse {
  query: string;
  hits: LiveSearchResult[];
  total: number;
}
