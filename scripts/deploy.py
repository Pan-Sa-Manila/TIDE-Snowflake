"""TIDE Master Deploy Script.

Executes SQL DDL, seeds data, deploys Snowpark procedures,
creates the Cortex Agent, and deploys the Streamlit app.

Usage:
    python scripts/deploy.py --connection tide
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and print its output."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result


def deploy(connection: str):
    """Run the deployment pipeline."""
    root_dir = Path(__file__).parent.parent
    sql_dir = root_dir / "sql"

    print("=== 1. SQL DDL ===")
    sql_files = sorted(sql_dir.glob("*.sql"))
    for sql_file in sql_files:
        print(f"\nExecuting {sql_file.name}...")
        cmd = [
            "snow", "sql",
            "--connection", connection,
            "--filename", str(sql_file)
        ]
        run_command(cmd)

    print("\n=== 2. Seed Data ===")
    seed_dir = sql_dir / "seed"
    seed_files = sorted(seed_dir.glob("*.sql"))
    if not seed_files:
        print("No seed files found. Skipping.")
    for seed_file in seed_files:
        print(f"\nExecuting {seed_file.name}...")
        cmd = [
            "snow", "sql",
            "--connection", connection,
            "--filename", str(seed_file)
        ]
        run_command(cmd)

    # TODO: WS-C — deploy procedures and agent
    print("\n=== 3. Procedures & Agents (Stub) ===")
    print("Skipping procedure and agent deployment until WS-C.")

    # TODO: WS-D — deploy Streamlit app
    print("\n=== 4. Streamlit App (Stub) ===")
    print("Skipping Streamlit deployment until WS-D.")

    print("\nOK: Deployment pipeline completed (stubs).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy TIDE to Snowflake")
    parser.add_argument(
        "--connection",
        default="tide",
        help="Snowflake connection name from config"
    )
    args = parser.parse_args()
    deploy(args.connection)
