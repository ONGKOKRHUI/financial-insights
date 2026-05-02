"""LangGraph state machine for the FinSight ETL pipeline.

Supports two engine modes controlled by the PIPELINE_ENGINE env var:
  - "langgraph" (default): Native LangGraph nodes with Gemini + Langfuse
  - "dify": Bypasses LangGraph nodes; routes parsed markdown to a Dify
            Workflow endpoint and uses its structured JSON output.

CLI entry point:
    python -m pipeline.graph --pdf path/to/report.pdf
"""

import argparse
import json
import logging
import os
import sys

from dotenv import load_dotenv

# load_dotenv()
load_dotenv(override=True) # ensures .env is loaded and overrides any existing environment variables

logger = logging.getLogger(__name__)

PIPELINE_ENGINE = os.getenv("PIPELINE_ENGINE", "langgraph").lower()


# ── LangGraph imports (only needed for langgraph engine) ──────────────────────

def _build_langgraph():
    """Construct and compile the LangGraph state machine."""
    from langgraph.graph import END, START, StateGraph  # type: ignore

    from pipeline.nodes.merger import merge_and_validate
    from pipeline.nodes.parser import parse_pdf
    from pipeline.nodes.qualitative import extract_qualitative
    from pipeline.nodes.quantitative import extract_quantitative
    from pipeline.nodes.router import route_content
    from pipeline.state import PipelineState

    graph = StateGraph(PipelineState)

    graph.add_node("parse_pdf", parse_pdf)
    graph.add_node("route_content", route_content)
    graph.add_node("extract_quantitative", extract_quantitative)
    graph.add_node("extract_qualitative", extract_qualitative)
    graph.add_node("merge_and_validate", merge_and_validate)

    # Sequential backbone with parallel fan-out after routing
    graph.add_edge(START, "parse_pdf")
    graph.add_edge("parse_pdf", "route_content")
    # Parallel branches: both are triggered from route_content
    graph.add_edge("route_content", "extract_quantitative")
    graph.add_edge("route_content", "extract_qualitative")
    # Fan-in: merge_and_validate runs after both branches complete
    graph.add_edge("extract_quantitative", "merge_and_validate")
    graph.add_edge("extract_qualitative", "merge_and_validate")
    graph.add_edge("merge_and_validate", END)

    return graph.compile()


def _run_dify_engine(pdf_path: str) -> dict:
    """Run the Dify engine: parse PDF → send to Dify → return payload dict."""
    from pipeline.nodes.parser import parse_pdf, _extract_metadata_from_path
    from pipeline.dify_client import run_dify_workflow

    metadata = _extract_metadata_from_path(pdf_path)
    initial_state = {
        "pdf_path": pdf_path,
        "markdown_text": "",
        "table_markdown": "",
        "narrative_markdown": "",
        "quantitative_data": {},
        "qualitative_data": {},
        "validated_payload": {},
        "errors": [],
        "metadata": metadata,
    }

    # Only run the parser node; skip LangGraph routing/extraction
    parsed_state = parse_pdf(initial_state)
    markdown_text = parsed_state.get("markdown_text", "")
    errors = parsed_state.get("errors", [])

    if not markdown_text:
        return {"errors": errors, "validated_payload": {}}

    try:
        payload = run_dify_workflow(markdown_text, parsed_state["metadata"])
    except Exception as exc:
        errors.append(f"Dify workflow error: {exc}")
        logger.error("Dify workflow failed: %s", exc)
        payload = {}

    return {
        "validated_payload": payload,
        "errors": errors,
        "metadata": parsed_state["metadata"],
    }


def run_pipeline(pdf_path: str) -> dict:
    """Run the full ETL pipeline for a single PDF.

    Returns:
        dict with keys: validated_payload (dict), errors (list), metadata (dict)
    """
    logger.info("Starting pipeline [engine=%s] for: %s", PIPELINE_ENGINE, pdf_path)

    if PIPELINE_ENGINE == "dify":
        return _run_dify_engine(pdf_path)

    # Default: LangGraph engine
    compiled = _build_langgraph()

    from pipeline.nodes.parser import _extract_metadata_from_path

    metadata = _extract_metadata_from_path(pdf_path)
    initial_state = {
        "pdf_path": pdf_path,
        "markdown_text": "",
        "table_markdown": "",
        "narrative_markdown": "",
        "quantitative_data": {},
        "qualitative_data": {},
        "validated_payload": {},
        "errors": [],
        "metadata": metadata,
    }

    final_state = compiled.invoke(initial_state)

    return {
        "validated_payload": final_state.get("validated_payload", {}),
        "errors": final_state.get("errors", []),
        "metadata": final_state.get("metadata", {}),
    }


def build_graph():
    """Public helper for smoke-testing the LangGraph construction."""
    return _build_langgraph()


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="FinSight ETL pipeline CLI")
    parser.add_argument("--pdf", required=True, help="Path to the PDF to process")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the JSON output (default: stdout)",
    )
    args = parser.parse_args()

    result = run_pipeline(args.pdf)

    output_json = json.dumps(result, indent=2, default=str)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"Output written to {args.output}")
    else:
        print(output_json)

    if result.get("errors"):
        sys.exit(1)
