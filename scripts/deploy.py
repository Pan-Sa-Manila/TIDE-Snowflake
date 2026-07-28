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


BLOCKED_MARKER = "BLOCKED: cortex-trial"


def is_tolerated(sql_path: Path) -> bool:
    """True if this file is marked as expected to fail until Cortex unblocks.

    Marked files are still attempted on every deploy. Skipping them would mean
    nobody notices the day entitlements change.
    """
    try:
        return BLOCKED_MARKER in sql_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


ACCOUNTADMIN_MARKER = "REQUIRES: ACCOUNTADMIN"


def needs_accountadmin(sql_path: Path) -> bool:
    """True if this file contains account-level DDL that TIDE_ADMIN cannot run.

    Warehouses and roles are account-level objects, so the bootstrap file needs
    ACCOUNTADMIN. Everything else runs under the connection's own role so that
    TIDE_ADMIN owns the schema objects, per ARCHITECTURE.md section 4.
    """
    try:
        return ACCOUNTADMIN_MARKER in sql_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


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

    blocked_failures: list[str] = []

    print("=== 1. SQL DDL ===")
    sql_files = sorted(sql_dir.glob("*.sql"))
    for sql_file in sql_files:
        tolerated = is_tolerated(sql_file)
        print(f"\nExecuting {sql_file.name}...")
        cmd = [
            "snow", "sql",
            "--connection", connection,
            "--filename", str(sql_file)
        ]
        if needs_accountadmin(sql_file):
            cmd += ["--role", "ACCOUNTADMIN"]
            print("  (running as ACCOUNTADMIN: account-level DDL)")
        # An unmarked file still fails hard and immediately.
        result = run_command(cmd, check=not tolerated)
        if tolerated and result.returncode != 0:
            blocked_failures.append(sql_file.name)
            print(f"TOLERATED: {sql_file.name} failed and carries the"
                  f" '{BLOCKED_MARKER}' marker. Continuing.")

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

    if blocked_failures:
        print("\n" + "=" * 74)
        print("BLOCKED BY CORTEX ENTITLEMENTS")
        print("=" * 74)
        for name in blocked_failures:
            print(f"  - {name}")
        print("")
        print("These files are expected to fail until Cortex entitlements change.")
        print("Everything else deployed and the database is seeded and usable.")
        print("They are attempted on every deploy on purpose: the day the block")
        print("lifts they simply start succeeding, with no change needed here.")
        print("See docs/CAPABILITIES.md section C for the current matrix.")
        print("=" * 74)
        sys.exit(3)

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
