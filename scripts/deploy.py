"""TIDE Master Deploy Script.

Executes SQL DDL, seeds data, deploys Snowpark procedures,
creates the Cortex Agent, and deploys the Streamlit app.

Usage:
    python scripts/deploy.py --connection tide
"""

import argparse
import subprocess
import sys
import zipfile
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

    print("\n=== 3. Procedures & Agents ===")

    # The decision engine has to reach Snowflake as an importable module.
    # Snowflake resolves a procedure's IMPORTS at CREATE time, so the zip must
    # be on the stage before sql/procedures/*.sql runs — which is exactly why
    # those files are not in the sql/*.sql glob above.
    engine_zip = root_dir / "build" / "tide_decision.zip"
    engine_zip.parent.mkdir(exist_ok=True)

    print(f"\nPackaging tide_decision -> {engine_zip.name}...")
    with zipfile.ZipFile(engine_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for module in sorted((root_dir / "tide_decision").glob("*.py")):
            z.write(module, f"tide_decision/{module.name}")
            print(f"  + tide_decision/{module.name}")

    print("\nUploading engine to @TIDE.DECISION.CODE_STAGE...")
    put_path = engine_zip.as_posix()
    run_command([
        "snow", "sql",
        "--connection", connection,
        "--query",
        f"PUT 'file://{put_path}' @TIDE.DECISION.CODE_STAGE"
        " AUTO_COMPRESS = FALSE OVERWRITE = TRUE",
    ])

    proc_dir = sql_dir / "procedures"
    proc_files = sorted(proc_dir.glob("*.sql")) if proc_dir.is_dir() else []
    if not proc_files:
        print("No procedure files found. Skipping.")
    for proc_file in proc_files:
        tolerated = is_tolerated(proc_file)
        print(f"\nExecuting procedures/{proc_file.name}...")
        result = run_command([
            "snow", "sql",
            "--connection", connection,
            "--filename", str(proc_file),
        ], check=not tolerated)
        if tolerated and result.returncode != 0:
            blocked_failures.append(f"procedures/{proc_file.name}")
            print(f"TOLERATED: {proc_file.name} failed and carries the"
                  f" '{BLOCKED_MARKER}' marker. Continuing.")

    # TODO: WS-C — create the Cortex Agent from agents/investigator.yaml
    print("\nCortex Agent creation still pending (TASKS.md C-1).")

    print("\n=== 4. Streamlit App ===")
    # Deployed from streamlit/snowflake.yml via the CLI rather than hand-rolled
    # DDL, so the stage upload and CREATE STREAMLIT stay in step with whatever
    # files are actually in streamlit/. --replace makes a re-deploy idempotent.
    streamlit_dir = root_dir / "streamlit"
    if not (streamlit_dir / "snowflake.yml").is_file():
        print("No streamlit/snowflake.yml found. Skipping app deployment.")
    else:
        run_command([
            "snow", "streamlit", "deploy",
            "--connection", connection,
            "--replace",
            "--project", str(streamlit_dir),
        ])

        # The app object cannot be granted before it exists, so 14_demo_access
        # skipped its grants on the pass above. Re-run it now that it does.
        # The file guards on the app's existence, so this is safe either way.
        access_file = sql_dir / "14_demo_access.sql"
        if access_file.is_file():
            print("\nRe-applying app grants (14_demo_access.sql)...")
            run_command([
                "snow", "sql",
                "--connection", connection,
                "--filename", str(access_file),
                "--role", "ACCOUNTADMIN",
            ])

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

    print("\nOK: Deployment pipeline completed.")
    print("    Streamlit app: TIDE.TRIAGE.TIDE_APP")
    print("    Open it from Snowsight > Streamlit, or `snow streamlit get-url TIDE.TRIAGE.TIDE_APP`.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy TIDE to Snowflake")
    parser.add_argument(
        "--connection",
        default="tide",
        help="Snowflake connection name from config"
    )
    args = parser.parse_args()
    deploy(args.connection)
