"""
Mock financial data for 8 Malaysian Blue-Chip companies (KLSE).
All monetary values in MYR billions unless noted otherwise.
Figures are illustrative and based on approximate public data.
"""

COMPANIES: dict = {
    "MAYBANK": {
        "ticker": "MAYBANK", # manual mapping
        "name": "Malayan Banking Berhad", # manual mapping
        "sector": "Financials", # manual mapping
        "industry": "Banking", # manual mapping
        "description": (
            "Maybank is Malaysia's largest bank and one of the leading financial services "
            "groups in ASEAN. It offers a comprehensive range of financial products and "
            "services including commercial banking, investment banking, insurance, and "
            "Islamic finance across 20 countries."
        ),
        # Source: External Market API (Requires live stock price. CANNOT get from financial report)
        "market_cap_bln": 102.4, 
        "employees": 43000, # can get from financial report for updates
        "founded": 1960, # manual mapping
        "headquarters": "Kuala Lumpur, Malaysia", # manual mapping   
        "website": "https://www.maybank.com", # manual mapping
        "currency": "MYR", # manual mapping
        "exchange": "KLSE", # manual mapping
    },
    "CIMB": {
        "ticker": "CIMB",
        "name": "CIMB Group Holdings Berhad",
        "sector": "Financials",
        "industry": "Banking",
        "description": (
            "CIMB Group is one of ASEAN's leading universal banking groups, offering "
            "consumer banking, commercial banking, investment banking, and asset management "
            "services across 18 countries with over 34,000 employees."
        ),
        "market_cap_bln": 62.1,
        "employees": 34000,
        "founded": 1924,
        "headquarters": "Kuala Lumpur, Malaysia",
        "website": "https://www.cimb.com",
        "currency": "MYR",
        "exchange": "KLSE",
    },
    "TNB": {
        "ticker": "TNB",
        "name": "Tenaga Nasional Berhad",
        "sector": "Utilities",
        "industry": "Electric Utilities",
        "description": (
            "Tenaga Nasional Berhad is Malaysia's largest electricity utility company and "
            "one of the largest in Southeast Asia. TNB is involved in the generation, "
            "transmission, and distribution of electricity throughout Peninsular Malaysia."
        ),
        "market_cap_bln": 78.3,
        "employees": 35000,
        "founded": 1990,
        "headquarters": "Kuala Lumpur, Malaysia",
        "website": "https://www.tnb.com.my",
        "currency": "MYR",
        "exchange": "KLSE",
    },
    "PETRONAS": {
        "ticker": "PETRONAS",
        "name": "Petroliam Nasional Berhad",
        "sector": "Energy",
        "industry": "Integrated Oil & Gas",
        "description": (
            "PETRONAS is Malaysia's national oil company, wholly owned by the Malaysian "
            "government. It is engaged in the exploration, development, and production of "
            "oil and natural gas resources globally, as well as downstream chemicals and "
            "retail fuel operations."
        ),
        "market_cap_bln": 320.0,
        "employees": 51000,
        "founded": 1974,
        "headquarters": "Kuala Lumpur, Malaysia",
        "website": "https://www.petronas.com",
        "currency": "MYR",
        "exchange": "Private",
    },
    "MAXIS": {
        "ticker": "MAXIS",
        "name": "Maxis Berhad",
        "sector": "Communication Services",
        "industry": "Telecommunications",
        "description": (
            "Maxis is Malaysia's leading telecommunications company, providing mobile, "
            "fixed-line, broadband, and enterprise solutions. It serves millions of "
            "individual and business customers across Malaysia with a focus on 5G and "
            "digital services."
        ),
        "market_cap_bln": 36.2,
        "employees": 5000,
        "founded": 1993,
        "headquarters": "Kuala Lumpur, Malaysia",
        "website": "https://www.maxis.com.my",
        "currency": "MYR",
        "exchange": "KLSE",
    },
    "TM": {
        "ticker": "TM",
        "name": "Telekom Malaysia Berhad",
        "sector": "Communication Services",
        "industry": "Integrated Telecommunications",
        "description": (
            "Telekom Malaysia is Malaysia's incumbent telecommunications company and the "
            "country's largest fixed-line operator. TM provides broadband, voice, data, "
            "and managed services to consumers and enterprises, operating the national "
            "fibre broadband infrastructure."
        ),
        "market_cap_bln": 24.8,
        "employees": 21000,
        "founded": 1984,
        "headquarters": "Kuala Lumpur, Malaysia",
        "website": "https://www.tm.com.my",
        "currency": "MYR",
        "exchange": "KLSE",
    },
    "GENTING": {
        "ticker": "GENTING",
        "name": "Genting Berhad",
        "sector": "Consumer Discretionary",
        "industry": "Casinos & Gaming",
        "description": (
            "Genting Berhad is a global leisure and hospitality corporation with businesses "
            "in leisure and hospitality, power generation, oil and gas, and plantations. "
            "It operates resorts and casinos across Malaysia, Singapore, the US, and UK "
            "through its listed subsidiaries."
        ),
        "market_cap_bln": 22.6,
        "employees": 60000,
        "founded": 1965,
        "headquarters": "Kuala Lumpur, Malaysia",
        "website": "https://www.genting.com",
        "currency": "MYR",
        "exchange": "KLSE",
    },
    "SUNWAY": {
        "ticker": "SUNWAY",
        "name": "Sunway Berhad",
        "sector": "Real Estate",
        "industry": "Diversified Real Estate",
        "description": (
            "Sunway Berhad is one of Malaysia's largest conglomerates with diversified "
            "businesses in property development, construction, hospitality, retail, "
            "education, and healthcare. It is known for developing integrated townships "
            "including the Sunway City township in Selangor."
        ),
        "market_cap_bln": 18.4,
        "employees": 16000,
        "founded": 1974,
        "headquarters": "Petaling Jaya, Malaysia",
        "website": "https://www.sunway.com.my",
        "currency": "MYR",
        "exchange": "KLSE",
    },
}

KPI_SUMMARIES: dict = {
    "MAYBANK": {
        "ticker": "MAYBANK", # Source: Internal mapping
        "revenue_bln": 30.2, # Source: Financial Report (Income Statement)
        "net_income_bln": 9.1, # Source: Financial Report (Income Statement - PAT)
        "eps": 0.86, # Source: Financial Report (Income Statement)
        # Source: Derived (External Market Price / EPS). Needs separate ETL.
        "pe_ratio": 12.4, 
        "roe_pct": 10.8, # Source: Derived (Net Income / Total Equity from Balance Sheet)
        # Added: Source: Financial Report (Performance Review/Derived). 
        "roace_pct": 8.2,  
        "debt_to_equity": 0.92, # Source: Derived (Total Debt / Total Equity from Balance Sheet).
        # Source: Derived (Annual Dividend Per Share / External Stock Price). Needs separate ETL.
        "dividend_yield_pct": 5.8, 
        "fiscal_year": 2024, # Source: Financial Report (Cover Page)
    },
    "CIMB": {
        "ticker": "CIMB",
        "revenue_bln": 22.4,
        "net_income_bln": 6.3,
        "eps": 0.62,
        "pe_ratio": 10.2,
        "roe_pct": 11.2,
        "roace_pct": 10.0,
        "debt_to_equity": 1.05,
        "dividend_yield_pct": 5.1,
        "fiscal_year": 2024,
    },
    "TNB": {
        "ticker": "TNB",
        "revenue_bln": 58.7,
        "net_income_bln": 3.8,
        "eps": 0.67,
        "pe_ratio": 18.6,
        "roe_pct": 6.4,
        "roace_pct": 10.0,
        "debt_to_equity": 1.42,
        "dividend_yield_pct": 3.2,
        "fiscal_year": 2024,
    },
    "PETRONAS": {
        "ticker": "PETRONAS",
        "revenue_bln": 320.0,
        "net_income_bln": 55.0,
        "eps": 6.22,
        "pe_ratio": None,
        "roe_pct": 14.5,
        "roace_pct": 10.0,
        "debt_to_equity": 0.28,
        "dividend_yield_pct": None,
        "fiscal_year": 2024,
    },
    "MAXIS": {
        "ticker": "MAXIS",
        "revenue_bln": 9.8,
        "net_income_bln": 1.6,
        "eps": 0.20,
        "pe_ratio": 22.1,
        "roe_pct": 31.4,
        "roace_pct": 10.0,
        "debt_to_equity": 2.18,
        "dividend_yield_pct": 3.7,
        "fiscal_year": 2024,
    },
    "TM": {
        "ticker": "TM",
        "revenue_bln": 12.3,
        "net_income_bln": 1.1,
        "eps": 0.29,
        "pe_ratio": 14.8,
        "roe_pct": 8.9,
        "roace_pct": 10.0,
        "debt_to_equity": 1.12,
        "dividend_yield_pct": 4.2,
        "fiscal_year": 2024,
    },
    "GENTING": {
        "ticker": "GENTING",
        "revenue_bln": 21.4,
        "net_income_bln": 1.9,
        "eps": 0.52,
        "pe_ratio": 11.6,
        "roe_pct": 5.8,
        "roace_pct": 10.0,
        "debt_to_equity": 0.76,
        "dividend_yield_pct": 2.1,
        "fiscal_year": 2024,
    },
    "SUNWAY": {
        "ticker": "SUNWAY",
        "revenue_bln": 8.6,
        "net_income_bln": 1.0,
        "eps": 0.47,
        "pe_ratio": 13.4,
        "roe_pct": 9.3,
        "roace_pct": 10.0,
        "debt_to_equity": 0.58,
        "dividend_yield_pct": 3.6,
        "fiscal_year": 2024,
    },
}

INCOME_STATEMENTS: dict = {
    "MAYBANK": [
        {
            "fiscal_year": 2020, #Source: Financial Report Date
            "revenue_bln": 24.8, # Source: Financial Report (Income Statement)
            "gross_profit_bln": 16.2, # Source: Financial Report (Income Statement)
            "operating_income_bln": 10.1, # Source: Financial Report (Income Statement)
            "net_income_bln": 6.5, # Source: Financial Report (Income Statement - PAT)
            "eps": 0.62, # Source: Financial Report (Income Statement)
            "gross_margin_pct": 65.3, # Source: Derived (Gross Profit / Revenue)
            "operating_margin_pct": 40.7, # Source: Derived (Operating Income / Revenue)
            "net_margin_pct": 26.2, # Source: Derived (Net Income / Revenue)
        },
        {"fiscal_year": 2021, "revenue_bln": 25.6, "gross_profit_bln": 17.0, "operating_income_bln": 10.8, "net_income_bln": 7.2, "eps": 0.68, "gross_margin_pct": 66.4, "operating_margin_pct": 42.2, "net_margin_pct": 28.1},
        {"fiscal_year": 2022, "revenue_bln": 27.4, "gross_profit_bln": 18.3, "operating_income_bln": 11.6, "net_income_bln": 7.9, "eps": 0.75, "gross_margin_pct": 66.8, "operating_margin_pct": 42.3, "net_margin_pct": 28.8},
        {"fiscal_year": 2023, "revenue_bln": 29.1, "gross_profit_bln": 19.8, "operating_income_bln": 12.4, "net_income_bln": 8.6, "eps": 0.81, "gross_margin_pct": 68.0, "operating_margin_pct": 42.6, "net_margin_pct": 29.6},
        {"fiscal_year": 2024, "revenue_bln": 31.2, "gross_profit_bln": 20.6, "operating_income_bln": 13.1, "net_income_bln": 9.1, "eps": 0.86, "gross_margin_pct": 68.2, "operating_margin_pct": 43.4, "net_margin_pct": 30.1},
    ],
    "CIMB": [
        {"fiscal_year": 2020, "revenue_bln": 17.2, "gross_profit_bln": 10.8, "operating_income_bln": 5.8, "net_income_bln": 3.1, "eps": 0.31, "gross_margin_pct": 62.8, "operating_margin_pct": 33.7, "net_margin_pct": 18.0},
        {"fiscal_year": 2021, "revenue_bln": 18.6, "gross_profit_bln": 11.9, "operating_income_bln": 6.6, "net_income_bln": 4.3, "eps": 0.43, "gross_margin_pct": 64.0, "operating_margin_pct": 35.5, "net_margin_pct": 23.1},
        {"fiscal_year": 2022, "revenue_bln": 20.1, "gross_profit_bln": 13.0, "operating_income_bln": 7.4, "net_income_bln": 5.2, "eps": 0.51, "gross_margin_pct": 64.7, "operating_margin_pct": 36.8, "net_margin_pct": 25.9},
        {"fiscal_year": 2023, "revenue_bln": 21.5, "gross_profit_bln": 13.9, "operating_income_bln": 8.1, "net_income_bln": 5.9, "eps": 0.58, "gross_margin_pct": 64.7, "operating_margin_pct": 37.7, "net_margin_pct": 27.4},
        {"fiscal_year": 2024, "revenue_bln": 22.4, "gross_profit_bln": 14.6, "operating_income_bln": 8.8, "net_income_bln": 6.3, "eps": 0.62, "gross_margin_pct": 65.2, "operating_margin_pct": 39.3, "net_margin_pct": 28.1},
    ],
    "TNB": [
        {"fiscal_year": 2020, "revenue_bln": 46.3, "gross_profit_bln": 14.2, "operating_income_bln": 7.1, "net_income_bln": 2.8, "eps": 0.49, "gross_margin_pct": 30.7, "operating_margin_pct": 15.3, "net_margin_pct": 6.0},
        {"fiscal_year": 2021, "revenue_bln": 50.1, "gross_profit_bln": 15.4, "operating_income_bln": 7.8, "net_income_bln": 3.1, "eps": 0.55, "gross_margin_pct": 30.7, "operating_margin_pct": 15.6, "net_margin_pct": 6.2},
        {"fiscal_year": 2022, "revenue_bln": 54.2, "gross_profit_bln": 16.1, "operating_income_bln": 8.2, "net_income_bln": 3.4, "eps": 0.60, "gross_margin_pct": 29.7, "operating_margin_pct": 15.1, "net_margin_pct": 6.3},
        {"fiscal_year": 2023, "revenue_bln": 56.8, "gross_profit_bln": 16.9, "operating_income_bln": 8.6, "net_income_bln": 3.6, "eps": 0.64, "gross_margin_pct": 29.8, "operating_margin_pct": 15.1, "net_margin_pct": 6.3},
        {"fiscal_year": 2024, "revenue_bln": 58.7, "gross_profit_bln": 17.8, "operating_income_bln": 9.1, "net_income_bln": 3.8, "eps": 0.67, "gross_margin_pct": 30.3, "operating_margin_pct": 15.5, "net_margin_pct": 6.5},
    ],
    "PETRONAS": [
        {"fiscal_year": 2020, "revenue_bln": 198.0, "gross_profit_bln": 62.4, "operating_income_bln": 28.1, "net_income_bln": 15.2, "eps": 1.72, "gross_margin_pct": 31.5, "operating_margin_pct": 14.2, "net_margin_pct": 7.7},
        {"fiscal_year": 2021, "revenue_bln": 245.0, "gross_profit_bln": 82.0, "operating_income_bln": 42.0, "net_income_bln": 30.0, "eps": 3.39, "gross_margin_pct": 33.5, "operating_margin_pct": 17.1, "net_margin_pct": 12.2},
        {"fiscal_year": 2022, "revenue_bln": 332.0, "gross_profit_bln": 124.0, "operating_income_bln": 78.0, "net_income_bln": 60.0, "eps": 6.78, "gross_margin_pct": 37.3, "operating_margin_pct": 23.5, "net_margin_pct": 18.1},
        {"fiscal_year": 2023, "revenue_bln": 296.0, "gross_profit_bln": 104.0, "operating_income_bln": 63.0, "net_income_bln": 49.0, "eps": 5.54, "gross_margin_pct": 35.1, "operating_margin_pct": 21.3, "net_margin_pct": 16.6},
        {"fiscal_year": 2024, "revenue_bln": 320.0, "gross_profit_bln": 112.0, "operating_income_bln": 70.0, "net_income_bln": 55.0, "eps": 6.22, "gross_margin_pct": 35.0, "operating_margin_pct": 21.9, "net_margin_pct": 17.2},
    ],
    "MAXIS": [
        {"fiscal_year": 2020, "revenue_bln": 8.4, "gross_profit_bln": 4.8, "operating_income_bln": 2.1, "net_income_bln": 1.2, "eps": 0.15, "gross_margin_pct": 57.1, "operating_margin_pct": 25.0, "net_margin_pct": 14.3},
        {"fiscal_year": 2021, "revenue_bln": 8.7, "gross_profit_bln": 5.0, "operating_income_bln": 2.2, "net_income_bln": 1.3, "eps": 0.16, "gross_margin_pct": 57.5, "operating_margin_pct": 25.3, "net_margin_pct": 14.9},
        {"fiscal_year": 2022, "revenue_bln": 9.1, "gross_profit_bln": 5.3, "operating_income_bln": 2.4, "net_income_bln": 1.4, "eps": 0.18, "gross_margin_pct": 58.2, "operating_margin_pct": 26.4, "net_margin_pct": 15.4},
        {"fiscal_year": 2023, "revenue_bln": 9.5, "gross_profit_bln": 5.6, "operating_income_bln": 2.6, "net_income_bln": 1.5, "eps": 0.19, "gross_margin_pct": 58.9, "operating_margin_pct": 27.4, "net_margin_pct": 15.8},
        {"fiscal_year": 2024, "revenue_bln": 9.8, "gross_profit_bln": 5.9, "operating_income_bln": 2.8, "net_income_bln": 1.6, "eps": 0.20, "gross_margin_pct": 60.2, "operating_margin_pct": 28.6, "net_margin_pct": 16.3},
    ],
    "TM": [
        {"fiscal_year": 2020, "revenue_bln": 10.8, "gross_profit_bln": 4.3, "operating_income_bln": 1.6, "net_income_bln": 0.7, "eps": 0.19, "gross_margin_pct": 39.8, "operating_margin_pct": 14.8, "net_margin_pct": 6.5},
        {"fiscal_year": 2021, "revenue_bln": 11.2, "gross_profit_bln": 4.6, "operating_income_bln": 1.8, "net_income_bln": 0.8, "eps": 0.21, "gross_margin_pct": 41.1, "operating_margin_pct": 16.1, "net_margin_pct": 7.1},
        {"fiscal_year": 2022, "revenue_bln": 11.7, "gross_profit_bln": 5.0, "operating_income_bln": 2.0, "net_income_bln": 0.9, "eps": 0.24, "gross_margin_pct": 42.7, "operating_margin_pct": 17.1, "net_margin_pct": 7.7},
        {"fiscal_year": 2023, "revenue_bln": 12.0, "gross_profit_bln": 5.2, "operating_income_bln": 2.1, "net_income_bln": 1.0, "eps": 0.26, "gross_margin_pct": 43.3, "operating_margin_pct": 17.5, "net_margin_pct": 8.3},
        {"fiscal_year": 2024, "revenue_bln": 12.3, "gross_profit_bln": 5.5, "operating_income_bln": 2.3, "net_income_bln": 1.1, "eps": 0.29, "gross_margin_pct": 44.7, "operating_margin_pct": 18.7, "net_margin_pct": 8.9},
    ],
    "GENTING": [
        {"fiscal_year": 2020, "revenue_bln": 10.1, "gross_profit_bln": 2.4, "operating_income_bln": 0.4, "net_income_bln": -1.2, "eps": -0.33, "gross_margin_pct": 23.8, "operating_margin_pct": 4.0, "net_margin_pct": -11.9},
        {"fiscal_year": 2021, "revenue_bln": 12.6, "gross_profit_bln": 3.8, "operating_income_bln": 1.2, "net_income_bln": 0.2, "eps": 0.05, "gross_margin_pct": 30.2, "operating_margin_pct": 9.5, "net_margin_pct": 1.6},
        {"fiscal_year": 2022, "revenue_bln": 17.8, "gross_profit_bln": 6.2, "operating_income_bln": 2.6, "net_income_bln": 1.2, "eps": 0.33, "gross_margin_pct": 34.8, "operating_margin_pct": 14.6, "net_margin_pct": 6.7},
        {"fiscal_year": 2023, "revenue_bln": 20.1, "gross_profit_bln": 7.4, "operating_income_bln": 3.1, "net_income_bln": 1.6, "eps": 0.44, "gross_margin_pct": 36.8, "operating_margin_pct": 15.4, "net_margin_pct": 8.0},
        {"fiscal_year": 2024, "revenue_bln": 21.4, "gross_profit_bln": 8.0, "operating_income_bln": 3.5, "net_income_bln": 1.9, "eps": 0.52, "gross_margin_pct": 37.4, "operating_margin_pct": 16.4, "net_margin_pct": 8.9},
    ],
    "SUNWAY": [
        {"fiscal_year": 2020, "revenue_bln": 5.8, "gross_profit_bln": 1.4, "operating_income_bln": 0.5, "net_income_bln": 0.3, "eps": 0.14, "gross_margin_pct": 24.1, "operating_margin_pct": 8.6, "net_margin_pct": 5.2},
        {"fiscal_year": 2021, "revenue_bln": 6.4, "gross_profit_bln": 1.7, "operating_income_bln": 0.7, "net_income_bln": 0.5, "eps": 0.23, "gross_margin_pct": 26.6, "operating_margin_pct": 10.9, "net_margin_pct": 7.8},
        {"fiscal_year": 2022, "revenue_bln": 7.3, "gross_profit_bln": 2.1, "operating_income_bln": 0.9, "net_income_bln": 0.7, "eps": 0.33, "gross_margin_pct": 28.8, "operating_margin_pct": 12.3, "net_margin_pct": 9.6},
        {"fiscal_year": 2023, "revenue_bln": 8.0, "gross_profit_bln": 2.4, "operating_income_bln": 1.1, "net_income_bln": 0.9, "eps": 0.42, "gross_margin_pct": 30.0, "operating_margin_pct": 13.8, "net_margin_pct": 11.3},
        {"fiscal_year": 2024, "revenue_bln": 8.6, "gross_profit_bln": 2.7, "operating_income_bln": 1.2, "net_income_bln": 1.0, "eps": 0.47, "gross_margin_pct": 31.4, "operating_margin_pct": 14.0, "net_margin_pct": 11.6},
    ],
}

# --- BALANCE SHEETS (FY2020-FY2024) ---
# Fields: total_assets_bln, total_liabilities_bln, total_equity_bln derived from
#   ROE and D/E ratios in KPI_SUMMARIES for FY2024. Historical years scaled proportionally.
# Source notes per field match PETRONAS template below.

BALANCE_SHEETS: dict = {
    "MAYBANK": [
        # FY2024: equity = net_income(9.1) / ROE(10.8%) = 84.3B; debt = equity * D/E(0.92) = 77.6B
        {
            "fiscal_year": 2020,  #Source: Financial Report Date
            "total_assets_bln": 780.0, #Source: Financial Report (Statement of Financial Position)
            "total_liabilities_bln": 714.0, #Source: Financial Report (Statement of Financial Position)
            "total_equity_bln": 66.0, #Source: Financial Report (Statement of Financial Position)
            "cash_and_equivalents_bln": 140.0, #Source: Financial Report (Statement of Financial Position)
            "total_debt_bln": 60.7#Source: Financial Report (Notes - Borrowings: Non-Current + Current)
            },  # Source: Financial Report (Statement of Financial Position)
        {"fiscal_year": 2021, "total_assets_bln": 820.0, "total_liabilities_bln": 749.6, "total_equity_bln": 70.4, "cash_and_equivalents_bln": 152.0, "total_debt_bln": 64.8},
        {"fiscal_year": 2022, "total_assets_bln": 862.0, "total_liabilities_bln": 787.1, "total_equity_bln": 74.9, "cash_and_equivalents_bln": 162.0, "total_debt_bln": 68.9},
        {"fiscal_year": 2023, "total_assets_bln": 906.0, "total_liabilities_bln": 826.3, "total_equity_bln": 79.7, "cash_and_equivalents_bln": 172.0, "total_debt_bln": 73.3},
        {"fiscal_year": 2024, "total_assets_bln": 950.0, "total_liabilities_bln": 865.7, "total_equity_bln": 84.3, "cash_and_equivalents_bln": 180.0, "total_debt_bln": 77.6},  # Source: Derived from KPI ROE + D/E; total assets consistent with ASEAN-5 bank scale
    ],
    "CIMB": [
        # FY2024: equity = net_income(6.3) / ROE(11.2%) = 56.3B; debt = equity * D/E(1.05) = 59.1B
        {"fiscal_year": 2020, "total_assets_bln": 542.0, "total_liabilities_bln": 503.0, "total_equity_bln": 39.0, "cash_and_equivalents_bln": 86.0, "total_debt_bln": 40.9},  # Source: Financial Report (Statement of Financial Position)
        {"fiscal_year": 2021, "total_assets_bln": 574.0, "total_liabilities_bln": 531.1, "total_equity_bln": 42.9, "cash_and_equivalents_bln": 96.0, "total_debt_bln": 45.0},
        {"fiscal_year": 2022, "total_assets_bln": 610.0, "total_liabilities_bln": 561.2, "total_equity_bln": 48.8, "cash_and_equivalents_bln": 104.0, "total_debt_bln": 51.2},
        {"fiscal_year": 2023, "total_assets_bln": 646.0, "total_liabilities_bln": 592.2, "total_equity_bln": 53.8, "cash_and_equivalents_bln": 112.0, "total_debt_bln": 56.5},
        {"fiscal_year": 2024, "total_assets_bln": 680.0, "total_liabilities_bln": 623.7, "total_equity_bln": 56.3, "cash_and_equivalents_bln": 122.0, "total_debt_bln": 59.1},
    ],
    "TNB": [
        # FY2024: equity = net_income(3.8) / ROE(6.4%) = 59.4B; debt = equity * D/E(1.42) = 84.3B
        {"fiscal_year": 2020, "total_assets_bln": 192.0, "total_liabilities_bln": 141.9, "total_equity_bln": 50.1, "cash_and_equivalents_bln": 6.8, "total_debt_bln": 71.1},  # Source: Financial Report (Statement of Financial Position)
        {"fiscal_year": 2021, "total_assets_bln": 199.0, "total_liabilities_bln": 146.4, "total_equity_bln": 52.6, "cash_and_equivalents_bln": 7.1, "total_debt_bln": 74.7},
        {"fiscal_year": 2022, "total_assets_bln": 206.0, "total_liabilities_bln": 151.0, "total_equity_bln": 55.0, "cash_and_equivalents_bln": 7.5, "total_debt_bln": 78.1},
        {"fiscal_year": 2023, "total_assets_bln": 213.0, "total_liabilities_bln": 155.7, "total_equity_bln": 57.3, "cash_and_equivalents_bln": 8.0, "total_debt_bln": 81.3},
        {"fiscal_year": 2024, "total_assets_bln": 220.0, "total_liabilities_bln": 160.6, "total_equity_bln": 59.4, "cash_and_equivalents_bln": 8.5, "total_debt_bln": 84.3},
    ],
    "PETRONAS": [
        # FY2024: equity = net_income(55.0) / ROE(14.5%) = 379.3B; debt = equity * D/E(0.28) = 106.2B
        {"fiscal_year": 2020, "total_assets_bln": 430.0, "total_liabilities_bln": 220.0, "total_equity_bln": 210.0, "cash_and_equivalents_bln": 65.0, "total_debt_bln": 58.8},  # Source: Financial Report (Statement of Financial Position); COVID oil-price impact
        {"fiscal_year": 2021, "total_assets_bln": 490.0, "total_liabilities_bln": 225.0, "total_equity_bln": 265.0, "cash_and_equivalents_bln": 80.0, "total_debt_bln": 74.2},
        {"fiscal_year": 2022, "total_assets_bln": 560.0, "total_liabilities_bln": 240.0, "total_equity_bln": 320.0, "cash_and_equivalents_bln": 112.0, "total_debt_bln": 89.6},  # High-price commodity supercycle
        {"fiscal_year": 2023, "total_assets_bln": 610.0, "total_liabilities_bln": 255.0, "total_equity_bln": 355.0, "cash_and_equivalents_bln": 138.0, "total_debt_bln": 99.4},
        {"fiscal_year": 2024, "total_assets_bln": 650.0, "total_liabilities_bln": 270.7, "total_equity_bln": 379.3, "cash_and_equivalents_bln": 158.0, "total_debt_bln": 106.2},
        # FY2025 data sourced directly from PETRONAS Annual Report (Statement of Financial Position)
        {"fiscal_year": 2025, "total_assets_bln": 774.9, "total_liabilities_bln": 272.8, "total_equity_bln": 502.1, "cash_and_equivalents_bln": 204.4, "total_debt_bln": 121.6},
    ],
    "MAXIS": [
        # FY2024: equity = net_income(1.6) / ROE(31.4%) = 5.1B; debt = equity * D/E(2.18) = 11.1B
        {"fiscal_year": 2020, "total_assets_bln": 26.5, "total_liabilities_bln": 22.4, "total_equity_bln": 4.1, "cash_and_equivalents_bln": 1.8, "total_debt_bln": 8.9},  # Source: Financial Report (Statement of Financial Position)
        {"fiscal_year": 2021, "total_assets_bln": 27.2, "total_liabilities_bln": 22.9, "total_equity_bln": 4.3, "cash_and_equivalents_bln": 2.0, "total_debt_bln": 9.4},
        {"fiscal_year": 2022, "total_assets_bln": 28.0, "total_liabilities_bln": 23.5, "total_equity_bln": 4.5, "cash_and_equivalents_bln": 2.2, "total_debt_bln": 9.8},
        {"fiscal_year": 2023, "total_assets_bln": 29.0, "total_liabilities_bln": 24.2, "total_equity_bln": 4.8, "cash_and_equivalents_bln": 2.4, "total_debt_bln": 10.5},
        {"fiscal_year": 2024, "total_assets_bln": 30.0, "total_liabilities_bln": 24.9, "total_equity_bln": 5.1, "cash_and_equivalents_bln": 2.5, "total_debt_bln": 11.1},
    ],
    "TM": [
        # FY2024: equity = net_income(1.1) / ROE(8.9%) = 12.4B; debt = equity * D/E(1.12) = 13.9B
        {"fiscal_year": 2020, "total_assets_bln": 34.4, "total_liabilities_bln": 24.1, "total_equity_bln": 10.3, "cash_and_equivalents_bln": 2.4, "total_debt_bln": 11.5},  # Source: Financial Report (Statement of Financial Position)
        {"fiscal_year": 2021, "total_assets_bln": 35.8, "total_liabilities_bln": 24.9, "total_equity_bln": 10.9, "cash_and_equivalents_bln": 2.6, "total_debt_bln": 12.2},
        {"fiscal_year": 2022, "total_assets_bln": 37.2, "total_liabilities_bln": 25.8, "total_equity_bln": 11.4, "cash_and_equivalents_bln": 2.8, "total_debt_bln": 12.8},
        {"fiscal_year": 2023, "total_assets_bln": 38.6, "total_liabilities_bln": 26.7, "total_equity_bln": 11.9, "cash_and_equivalents_bln": 3.0, "total_debt_bln": 13.3},
        {"fiscal_year": 2024, "total_assets_bln": 40.0, "total_liabilities_bln": 27.6, "total_equity_bln": 12.4, "cash_and_equivalents_bln": 3.2, "total_debt_bln": 13.9},
    ],
    "GENTING": [
        # FY2024: equity = net_income(1.9) / ROE(5.8%) = 32.8B; debt = equity * D/E(0.76) = 24.9B
        {"fiscal_year": 2020, "total_assets_bln": 74.0, "total_liabilities_bln": 49.8, "total_equity_bln": 24.2, "cash_and_equivalents_bln": 7.5, "total_debt_bln": 17.6},  # Source: Financial Report (Statement of Financial Position); COVID impact on liquidity
        {"fiscal_year": 2021, "total_assets_bln": 77.5, "total_liabilities_bln": 51.3, "total_equity_bln": 26.2, "cash_and_equivalents_bln": 8.5, "total_debt_bln": 19.0},
        {"fiscal_year": 2022, "total_assets_bln": 82.0, "total_liabilities_bln": 53.1, "total_equity_bln": 28.9, "cash_and_equivalents_bln": 9.8, "total_debt_bln": 21.0},
        {"fiscal_year": 2023, "total_assets_bln": 86.0, "total_liabilities_bln": 55.2, "total_equity_bln": 30.8, "cash_and_equivalents_bln": 10.9, "total_debt_bln": 22.9},
        {"fiscal_year": 2024, "total_assets_bln": 90.0, "total_liabilities_bln": 57.2, "total_equity_bln": 32.8, "cash_and_equivalents_bln": 12.0, "total_debt_bln": 24.9},
    ],
    "SUNWAY": [
        # FY2024: equity = net_income(1.0) / ROE(9.3%) = 10.8B; debt = equity * D/E(0.58) = 6.3B
        {"fiscal_year": 2020, "total_assets_bln": 20.5, "total_liabilities_bln": 13.2, "total_equity_bln": 7.3, "cash_and_equivalents_bln": 1.5, "total_debt_bln": 4.2},  # Source: Financial Report (Statement of Financial Position)
        {"fiscal_year": 2021, "total_assets_bln": 22.0, "total_liabilities_bln": 13.9, "total_equity_bln": 8.1, "cash_and_equivalents_bln": 1.8, "total_debt_bln": 4.7},
        {"fiscal_year": 2022, "total_assets_bln": 24.0, "total_liabilities_bln": 14.9, "total_equity_bln": 9.1, "cash_and_equivalents_bln": 2.1, "total_debt_bln": 5.3},
        {"fiscal_year": 2023, "total_assets_bln": 26.0, "total_liabilities_bln": 15.9, "total_equity_bln": 10.1, "cash_and_equivalents_bln": 2.5, "total_debt_bln": 5.9},
        {"fiscal_year": 2024, "total_assets_bln": 28.0, "total_liabilities_bln": 17.2, "total_equity_bln": 10.8, "cash_and_equivalents_bln": 2.8, "total_debt_bln": 6.3},
    ],
}

# --- CASH FLOWS (FY2020-FY2024) ---
# free_cash_flow_bln = operating_cash_flow_bln - capital_expenditure_bln  # Source: Derived
# dividends_paid_bln approximated from dividend_yield_pct * market_cap for FY2024;
#   historical years scaled with revenue growth.

CASH_FLOWS: dict = {
    "MAYBANK": [
        {
            "fiscal_year": 2020, #Source: Financial Report Date
            "operating_cash_flow_bln": 10.2, #Source: Financial Report (Statement of Cash Flows)
            "capital_expenditure_bln": 1.0, #Source: Financial Report (Statement of Cash Flows / Performance Review)
            "free_cash_flow_bln": 9.2, #Source: Derived (Operating Cash Flow - Capital Expenditure). Crucial metric for dashboards.
            "dividends_paid_bln": 3.8 ## Added - Source: Financial Report (Statement of Cash Flows)
            },   # Source: Financial Report (Statement of Cash Flows)
        {"fiscal_year": 2021, "operating_cash_flow_bln": 11.5, "capital_expenditure_bln": 1.0, "free_cash_flow_bln": 10.5, "dividends_paid_bln": 4.3},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 12.4, "capital_expenditure_bln": 1.1, "free_cash_flow_bln": 11.3, "dividends_paid_bln": 4.8},
        {"fiscal_year": 2023, "operating_cash_flow_bln": 13.2, "capital_expenditure_bln": 1.1, "free_cash_flow_bln": 12.1, "dividends_paid_bln": 5.4},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 14.0, "capital_expenditure_bln": 1.2, "free_cash_flow_bln": 12.8, "dividends_paid_bln": 5.9},   # Dividends: DY(5.8%) * mktcap(102.4B) ≈ 5.9B
    ],
    "CIMB": [
        {"fiscal_year": 2020, "operating_cash_flow_bln": 5.4, "capital_expenditure_bln": 0.7, "free_cash_flow_bln": 4.7, "dividends_paid_bln": 1.5},
        {"fiscal_year": 2021, "operating_cash_flow_bln": 6.5, "capital_expenditure_bln": 0.7, "free_cash_flow_bln": 5.8, "dividends_paid_bln": 1.9},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 7.6, "capital_expenditure_bln": 0.8, "free_cash_flow_bln": 6.8, "dividends_paid_bln": 2.4},
        {"fiscal_year": 2023, "operating_cash_flow_bln": 8.3, "capital_expenditure_bln": 0.8, "free_cash_flow_bln": 7.5, "dividends_paid_bln": 2.8},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 9.0, "capital_expenditure_bln": 0.9, "free_cash_flow_bln": 8.1, "dividends_paid_bln": 3.2},   # Dividends: DY(5.1%) * mktcap(62.1B) ≈ 3.2B
    ],
    "TNB": [
        {"fiscal_year": 2020, "operating_cash_flow_bln": 9.8, "capital_expenditure_bln": 7.2, "free_cash_flow_bln": 2.6, "dividends_paid_bln": 1.8},   # Source: Financial Report (Statement of Cash Flows); high CapEx for grid infra
        {"fiscal_year": 2021, "operating_cash_flow_bln": 10.6, "capital_expenditure_bln": 7.5, "free_cash_flow_bln": 3.1, "dividends_paid_bln": 2.0},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 11.2, "capital_expenditure_bln": 7.9, "free_cash_flow_bln": 3.3, "dividends_paid_bln": 2.2},
        {"fiscal_year": 2023, "operating_cash_flow_bln": 11.8, "capital_expenditure_bln": 8.3, "free_cash_flow_bln": 3.5, "dividends_paid_bln": 2.4},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 12.5, "capital_expenditure_bln": 8.8, "free_cash_flow_bln": 3.7, "dividends_paid_bln": 2.5},
    ],
    "PETRONAS": [
        {"fiscal_year": 2020, "operating_cash_flow_bln": 35.0, "capital_expenditure_bln": 30.0, "free_cash_flow_bln": 5.0, "dividends_paid_bln": 12.0},  # Source: Financial Report (Statement of Cash Flows); COVID-depressed oil prices
        {"fiscal_year": 2021, "operating_cash_flow_bln": 52.0, "capital_expenditure_bln": 32.0, "free_cash_flow_bln": 20.0, "dividends_paid_bln": 20.0},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 88.0, "capital_expenditure_bln": 38.5, "free_cash_flow_bln": 49.5, "dividends_paid_bln": 36.0},  # Commodity supercycle peak
        {"fiscal_year": 2023, "operating_cash_flow_bln": 68.0, "capital_expenditure_bln": 35.5, "free_cash_flow_bln": 32.5, "dividends_paid_bln": 28.0},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 75.0, "capital_expenditure_bln": 38.0, "free_cash_flow_bln": 37.0, "dividends_paid_bln": 30.0},
        # FY2025 data sourced directly from PETRONAS Annual Report (Statement of Cash Flows)
        {"fiscal_year": 2025, "operating_cash_flow_bln": 85.2, "capital_expenditure_bln": 41.6, "free_cash_flow_bln": 43.6, "dividends_paid_bln": 32.0},
    ],
    "MAXIS": [
        {"fiscal_year": 2020, "operating_cash_flow_bln": 2.6, "capital_expenditure_bln": 1.4, "free_cash_flow_bln": 1.2, "dividends_paid_bln": 1.0},
        {"fiscal_year": 2021, "operating_cash_flow_bln": 2.7, "capital_expenditure_bln": 1.4, "free_cash_flow_bln": 1.3, "dividends_paid_bln": 1.1},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 2.8, "capital_expenditure_bln": 1.5, "free_cash_flow_bln": 1.3, "dividends_paid_bln": 1.1},
        {"fiscal_year": 2023, "operating_cash_flow_bln": 2.9, "capital_expenditure_bln": 1.6, "free_cash_flow_bln": 1.3, "dividends_paid_bln": 1.2},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 3.0, "capital_expenditure_bln": 1.6, "free_cash_flow_bln": 1.4, "dividends_paid_bln": 1.3},   # Dividends: DY(3.7%) * mktcap(36.2B) ≈ 1.3B
    ],
    "TM": [
        {"fiscal_year": 2020, "operating_cash_flow_bln": 2.0, "capital_expenditure_bln": 1.5, "free_cash_flow_bln": 0.5, "dividends_paid_bln": 0.6},   # Source: Financial Report (Statement of Cash Flows); high CapEx for JENDELA fibre
        {"fiscal_year": 2021, "operating_cash_flow_bln": 2.2, "capital_expenditure_bln": 1.6, "free_cash_flow_bln": 0.6, "dividends_paid_bln": 0.7},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 2.4, "capital_expenditure_bln": 1.7, "free_cash_flow_bln": 0.7, "dividends_paid_bln": 0.8},
        {"fiscal_year": 2023, "operating_cash_flow_bln": 2.5, "capital_expenditure_bln": 1.8, "free_cash_flow_bln": 0.7, "dividends_paid_bln": 0.9},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 2.6, "capital_expenditure_bln": 1.9, "free_cash_flow_bln": 0.7, "dividends_paid_bln": 1.0},
    ],
    "GENTING": [
        {"fiscal_year": 2020, "operating_cash_flow_bln": 0.8, "capital_expenditure_bln": 1.5, "free_cash_flow_bln": -0.7, "dividends_paid_bln": 0.1},  # Source: Financial Report (Statement of Cash Flows); COVID-impacted, negative FCF
        {"fiscal_year": 2021, "operating_cash_flow_bln": 1.5, "capital_expenditure_bln": 1.2, "free_cash_flow_bln": 0.3, "dividends_paid_bln": 0.1},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 3.6, "capital_expenditure_bln": 1.8, "free_cash_flow_bln": 1.8, "dividends_paid_bln": 0.3},
        {"fiscal_year": 2023, "operating_cash_flow_bln": 4.3, "capital_expenditure_bln": 2.0, "free_cash_flow_bln": 2.3, "dividends_paid_bln": 0.4},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 4.8, "capital_expenditure_bln": 2.3, "free_cash_flow_bln": 2.5, "dividends_paid_bln": 0.5},
    ],
    "SUNWAY": [
        {"fiscal_year": 2020, "operating_cash_flow_bln": 0.9, "capital_expenditure_bln": 0.6, "free_cash_flow_bln": 0.3, "dividends_paid_bln": 0.2},
        {"fiscal_year": 2021, "operating_cash_flow_bln": 1.2, "capital_expenditure_bln": 0.7, "free_cash_flow_bln": 0.5, "dividends_paid_bln": 0.3},
        {"fiscal_year": 2022, "operating_cash_flow_bln": 1.5, "capital_expenditure_bln": 0.8, "free_cash_flow_bln": 0.7, "dividends_paid_bln": 0.5},
        {"fiscal_year": 2023, "operating_cash_flow_bln": 1.7, "capital_expenditure_bln": 0.9, "free_cash_flow_bln": 0.8, "dividends_paid_bln": 0.6},
        {"fiscal_year": 2024, "operating_cash_flow_bln": 1.9, "capital_expenditure_bln": 1.0, "free_cash_flow_bln": 0.9, "dividends_paid_bln": 0.7},
    ],
}


# --- QUALITATIVE INSIGHTS (FY2024) ---
# future_outlook: Source: Financial Report (Management Discussion & Analysis / Commentary on Prospects)
# key_strategic_events: Source: Financial Report (Significant Events / Notes to Accounts)

QUALITATIVE_INSIGHTS: dict = {
    "MAYBANK": {
        "fiscal_year": 2024, # Source: Financial Report Date 
        "future_outlook": ( # Source: Financial Report (Commentary on Prospects B1) 
            "Maybank's M25+ strategy focuses on becoming the digital financial services leader in ASEAN. "
            "The group targets double-digit ROE and growth of its sustainable finance portfolio to RM80 billion, "
            "supported by continued investment in digital infrastructure, Islamic finance, and regional expansion."
        ),
        "key_strategic_events": [ # Source: Financial Report (Significant Events A6) 
            "Launched MAE Super App revamp with AI-powered financial advisory and wealth management features.",
            "M-Islamic banking segment crossed 30% contribution to group net profit for the first time.",
            "Signed MoU with EPF to expand retirement and wealth solutions for Malaysian depositors.",
        ],
    },
    "CIMB": {
        "fiscal_year": 2024,
        "future_outlook": (
            "CIMB's Forward23+ strategy targets ROE of 12-13% through operational efficiency, "
            "digital transformation, and deepening ASEAN connectivity. The bank is investing in AI-driven "
            "credit underwriting and data analytics platforms to enhance customer acquisition and retention."
        ),
        "key_strategic_events": [
            "Completed integration of PT Bank CIMB Niaga digital platforms across Indonesia.",
            "Launched CIMB Clicks 2.0 with enhanced biometric authentication and digital wealth management.",
            "Divested non-core business units in Thailand to sharpen ASEAN banking focus.",
        ],
    },
    "TNB": {
        "fiscal_year": 2024,
        "future_outlook": (
            "TNB is accelerating its energy transition under the National Energy Transition Roadmap (NETR), "
            "targeting 8,000 MW of renewable energy capacity. International investments via TNB International "
            "are expanding into renewable energy assets across ASEAN and South Asia."
        ),
        "key_strategic_events": [
            "Commissioned 500 MW solar farm under the Large Scale Solar (LSS4) programme.",
            "TNB International acquired a 49% stake in a 200 MW wind energy project in India.",
            "Launched GridBeyond AI-powered grid management pilot for industrial and commercial customers.",
        ],
    },
    "PETRONAS": {
        "fiscal_year": 2024, 
        "future_outlook": (
            "PETRONAS continues to navigate energy transition while sustaining upstream excellence. "
            "The company targets scaling value-accretive energy investments and lower-carbon solutions, "
            "including LNG, hydrogen, and carbon capture and storage (CCS), amid heightened market volatility."
        ),
        "key_strategic_events": [
            "Established joint venture with ENI for deepwater exploration in Sarawak.",
            "Divestment of 20% interest in North Montney Joint Venture to optimise portfolio.",
            "Inaugurated Pengerang Integrated Complex (PIC) downstream expansion, Malaysia's largest integrated refinery.",
        ],
    },
    "MAXIS": {
        "fiscal_year": 2024,
        "future_outlook": (
            "Maxis is positioned as Malaysia's 5G network partner of choice, targeting enterprise digitalisation "
            "and smart city solutions. The company is expanding its B2B digital services portfolio including cloud, "
            "IoT, and cybersecurity while driving consumer ARPU growth through premium 5G propositions."
        ),
        "key_strategic_events": [
            "Achieved 5G network coverage exceeding 80% of populated areas ahead of the national target.",
            "Launched Maxis Business Hub, a one-stop digital services platform for SMEs.",
            "Signed strategic partnership with AWS to deliver cloud-first enterprise solutions across Malaysia.",
        ],
    },
    "TM": {
        "fiscal_year": 2024,
        "future_outlook": (
            "Telekom Malaysia is executing the JENDELA national broadband plan, targeting delivery of "
            "high-speed fibre to 7.5 million premises by 2025. TM's pivot to HyperScale data centre services "
            "and cloud connectivity positions it as a critical national digital infrastructure provider."
        ),
        "key_strategic_events": [
            "Surpassed 4 million Unifi broadband subscribers, cementing fixed broadband market leadership.",
            "Broke ground on TM's second HyperScale data centre in Iskandar Puteri, Johor.",
            "Signed strategic partnership with Google Cloud for data centre co-location and cloud services.",
        ],
    },
    "GENTING": {
        "fiscal_year": 2024,
        "future_outlook": (
            "Genting is executing a post-COVID recovery strategy, strengthening the Resorts World brand globally. "
            "The group is investing in non-gaming revenue streams including MICE, entertainment, and premium "
            "hospitality while pursuing ESG-aligned sustainable gaming practices."
        ),
        "key_strategic_events": [
            "Resorts World Las Vegas achieved monthly profitability milestone in Q3 2024, two years after opening.",
            "Genting Singapore delivered record gaming revenue exceeding SGD 2.5 billion for the year.",
            "Genting Malaysia announced MYR 4 billion masterplan expansion of Resorts World Genting highland resort.",
        ],
    },
    "SUNWAY": {
        "fiscal_year": 2024,
        "future_outlook": (
            "Sunway is leveraging its Integrated Township model to drive long-term growth, with a strong pipeline "
            "of developments in Selangor, Johor, and Penang. The healthcare and education segments are targeted to "
            "contribute 30% of group profits by 2027, reducing reliance on property development cycles."
        ),
        "key_strategic_events": [
            "Launched Sunway City Iskandar Puteri, a new 1,000-acre integrated township development in Johor.",
            "Sunway Medical Centres expanded capacity with a new 450-bed hospital tower in Sunway City.",
            "Completed acquisition of a retail mall in Vietnam, marking Sunway's first international retail asset.",
        ],
    },
}

# Generic Segment Data structure to handle different industries dynamically - this one on hold for now
# SEGMENT_DATA: dict = {
#     "MAYBANK": [
#         {
#             "fiscal_year": 2025,                  # Source: Financial Report Date
#             "segments": [                         # Source: Financial Report (Notes - Operating Segments).
#                 {"name": "Community Financial Services", "revenue_bln": 15.1, "profit_bln": 4.5},
#                 {"name": "Global Banking", "revenue_bln": 10.2, "profit_bln": 3.8},
#                 {"name": "Insurance & Takaful", "revenue_bln": 4.9, "profit_bln": 0.8}
#             ]
#         }
#     ],
#     "PETRONAS": [
#         {
#             "fiscal_year": 2025,                  # Source: Financial Report Date
#             "segments": [                         # Source: Financial Report (Notes - Operating Segments A13)
#                 {"name": "Upstream", "revenue_bln": 111.9, "profit_bln": 26.2},
#                 {"name": "Gas & Maritime", "revenue_bln": 119.9, "profit_bln": 20.9},
#                 {"name": "Downstream", "revenue_bln": 120.0, "profit_bln": -1.9}
#             ]
#         }
#     ]
# }