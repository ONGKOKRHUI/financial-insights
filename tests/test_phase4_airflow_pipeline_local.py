"""Local Airflow ETL smoke test runner.

This script validates that the local Airflow pipeline can start and execute
the `finsight_etl` DAG end-to-end using `airflow dags test`.

Usage:
    python scripts/test_airflow_pipeline_local.py
    python scripts/test_airflow_pipeline_local.py --pipeline-engine dify
    python scripts/test_airflow_pipeline_local.py --max-pdfs 1

Prerequisites:
    - Docker Desktop running
    - .env configured
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd or REPO_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test local Airflow ETL DAG")
    parser.add_argument(
        "--pipeline-engine",
        choices=["langgraph", "dify"],
        default=None,
        help="Temporarily override PIPELINE_ENGINE for this test run.",
    )
    parser.add_argument(
        "--execution-date",
        default=dt.date.today().isoformat(),
        help="Execution date for `airflow dags test` (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--max-pdfs",
        type=int,
        default=1,
        help=(
            "Max unprocessed PDFs to process during this test run via "
            "FINSIGHT_MAX_PDFS_PER_RUN (default: 1 for fast validation). "
            "Set 0 to disable the cap."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Start the main stack so local Airflow can reach the finsight database.
    run(["docker", "compose", "up", "-d"])

    # Start local Airflow stack (build custom image with pipeline dependencies).
    run(["docker", "compose", "-f", "docker-compose.airflow.yml", "up", "-d", "--build"])

    # Basic DAG visibility check.
    run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.airflow.yml",
            "exec",
            "-T",
            "airflow-webserver",
            "airflow",
            "dags",
            "list",
        ]
    )

    # Run DAG in test mode; this executes all tasks in sequence in one process.
    test_cmd = [
        "docker",
        "compose",
        "-f",
        "docker-compose.airflow.yml",
        "exec",
        "-T",
        "airflow-webserver",
        "env",
        f"FINSIGHT_MAX_PDFS_PER_RUN={max(args.max_pdfs, 0)}",
    ]
    if args.pipeline_engine:
        test_cmd.append(f"PIPELINE_ENGINE={args.pipeline_engine}")
    test_cmd.extend(["airflow", "dags", "test", "finsight_etl", args.execution_date])
    run(test_cmd)

    print("\nAirflow DAG smoke test completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed with exit code {exc.returncode}.", file=sys.stderr)
        raise SystemExit(exc.returncode)
