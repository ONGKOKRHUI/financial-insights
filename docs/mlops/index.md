# MLOps

This section documents FinSight's machine learning operations — feature
engineering, model training on financial datasets, experiment tracking with
MLflow, and production deployment pipelines.

## Feature store

The **`predictive_features`** PostgreSQL table is the primary training feature
store.  It is populated weekly by the [ML Features ETL pipeline](../data-engineering/ml-features-etl.md)
and holds 21 schema columns per `(ticker, fiscal_year, fiscal_quarter)` —
**19 populated** by the current five-phase pipeline (metrics 19–20 reserved for
future PDF-based extraction).

Query the feature matrix:

```sql
SELECT pf.*, c.sector, c.industry
FROM predictive_features pf
JOIN companies c ON c.ticker = pf.ticker
ORDER BY pf.ticker, pf.fiscal_year, pf.fiscal_quarter;
```

See [Database Schema](../backend/database-schema.md#predictive_features) for the
full column reference.

## Documentation map

| Topic | Page |
|-------|------|
| Feature engineering pipeline | [ML Features ETL](../data-engineering/ml-features-etl.md) |
| Model training workflow | [Model Training](model-training.md) |
| Experiment tracking | [Experiment Tracking](experiment-tracking.md) |
| Production deployment | [Deployment](deployment.md) |
