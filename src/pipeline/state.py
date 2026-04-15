"""LangGraph TypedDict state for the FinSight ETL pipeline."""

import operator
from typing import Annotated, TypedDict


class PipelineState(TypedDict):
    """Shared state passed between every node in the LangGraph pipeline.

    The parallel fan-out (extract_quantitative + extract_qualitative) means
    both branches run concurrently and write back to the shared state in the
    same step.  LangGraph raises InvalidUpdateError if two branches write to
    the same plain key simultaneously.

    Resolution:
      - `errors` is declared as an Annotated reducer (operator.add) so both
        branches can append to it and LangGraph merges the lists automatically.
      - Each branch writes ONLY its own output key(s):
          extract_quantitative  →  quantitative_data
          extract_qualitative   →  qualitative_data
        …so all other plain keys are safe (single writer per step).
    """

    # Input
    pdf_path: str

    # After parse_pdf
    markdown_text: str

    # After route_content — sub-strings fed to each branch
    table_markdown: str
    narrative_markdown: str

    # After extraction branches (each branch writes only its own key)
    quantitative_data: dict   # written exclusively by extract_quantitative
    qualitative_data: dict    # written exclusively by extract_qualitative

    # After merge_and_validate
    validated_payload: dict   # final FinancialReportPayload as dict

    # Cross-cutting — reducer allows both parallel branches to append safely
    errors: Annotated[list[str], operator.add]
    metadata: dict            # ticker, fiscal_year, report_period, source_pdf
