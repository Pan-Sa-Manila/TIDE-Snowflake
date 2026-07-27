"""Pre-commit hook to guard against destructive SQL.

Enforces rules from AGENTS.md §2:
- No UPDATE or DELETE on TRIAGE.CASES, TRIAGE.CASE_EVENTS, TRIAGE.CHAT
- Tables are append-only.
"""

import re
import sys
from pathlib import Path


BANNED_PATTERNS = [
    re.compile(r"UPDATE\s+(?:TIDE\.)?(?:TRIAGE\.)?(?:CASES|CASE_EVENTS|CHAT)", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM\s+(?:TIDE\.)?(?:TRIAGE\.)?(?:CASES|CASE_EVENTS|CHAT)", re.IGNORECASE),
]

def check_file(path: Path) -> list[str]:
    violations = []
    content = path.read_text(encoding="utf-8")
    for i, line in enumerate(content.splitlines(), 1):
        for pattern in BANNED_PATTERNS:
            if pattern.search(line):
                violations.append(f"{path.name}:{i} -> {line.strip()}")
    return violations

def main():
    repo_root = Path(__file__).parent.parent
    sql_files = list(repo_root.rglob("*.sql"))
    
    all_violations = []
    for f in sql_files:
        if f.name == "demo_reset.sql":
            # Allowed exception for demo reset
            continue
        all_violations.extend(check_file(f))
        
    if all_violations:
        print("❌ Destructive SQL detected on append-only tables:")
        for v in all_violations:
            print(f"  {v}")
        print("See AGENTS.md §2. Commit rejected.")
        sys.exit(1)
        
    print("✅ SQL guard check passed.")

if __name__ == "__main__":
    main()
