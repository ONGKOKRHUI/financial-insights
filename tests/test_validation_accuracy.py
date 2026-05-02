import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from validation.validate_extraction_accuracy import (
    GroundTruthRecord,
    ValidationResult,
    compare_value,
    summarize_results,
)


def test_compare_value_uses_absolute_tolerance():
    assert compare_value(10.0, 10.04, 0.05) is True
    assert compare_value(10.0, 10.06, 0.05) is False
    assert compare_value(10.0, None, 0.05) is False


def test_ground_truth_record_shape_matches_mock_schema():
    record = GroundTruthRecord(
        ticker="MAYBANK",
        fiscal_year=2024,
        report_period="FY",
        statement="income_statement",
        field="revenue_bln",
        expected_value=47.7,
        tolerance_abs=0.05,
    )

    assert record.ticker == "MAYBANK"
    assert record.statement == "income_statement"


def test_summarize_results_counts_accuracy_and_missing_values():
    results = [
        ValidationResult(
            ticker="MAYBANK",
            fiscal_year=2024,
            report_period="FY",
            statement="income_statement",
            field="revenue_bln",
            expected_value=47.7,
            actual_value=47.7,
            tolerance_abs=0.05,
            passed=True,
        ),
        ValidationResult(
            ticker="CIMB",
            fiscal_year=2024,
            report_period="FY",
            statement="income_statement",
            field="net_income_bln",
            expected_value=6.1,
            actual_value=None,
            tolerance_abs=0.05,
            passed=False,
        ),
    ]

    assert summarize_results(results) == {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "missing": 1,
        "accuracy": 0.5,
    }
