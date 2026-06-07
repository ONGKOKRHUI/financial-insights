# Data Engineering

This section covers how FinSight acquires, parses, and transforms raw financial
report PDFs into structured, queryable data stored in PostgreSQL — including
the **ML Features ETL** pipeline that computes predictive metrics (19 of 21
schema columns populated) for model training.

## Pipelines

| Pipeline | Doc | Output |
|----------|-----|--------|
| PDF scraper | [Scraping System](scraping-system.md) | `src/scraper/data/raw/*.pdf` |
| Financial ETL | [ETL Pipeline](etl-pipeline.md) | `income_statements`, `kpi_summaries`, … |
| ML features ETL | [ML Features ETL](ml-features-etl.md) | `predictive_features` (21 schema cols, 19 populated) |
