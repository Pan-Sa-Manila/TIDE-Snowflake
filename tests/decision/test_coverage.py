"""Path-coverage gate — DETAILS.md §13.

"Every one has a pytest test; the coverage test fails if any id here lacks one."

Coverage is measured from *assertions*, not mentions: only `path_id == "X-NN"`
counts, so a path id appearing in a docstring or a negative assertion cannot
make an untested path look covered.
"""

import re
from pathlib import Path

from tide_decision.types import ALL_PATH_IDS, GUARDRAIL_PATH_IDS, ROUTING_PATH_IDS

# Matches the positive assertion form used throughout the suite:
#   assert decision.path_id == "R-07"
PATH_ASSERTION = re.compile(r"""path_id\s*==\s*["']([GR]-\d{2})["']""")


def _asserted_path_ids() -> set[str]:
    tests_dir = Path(__file__).parent
    found: set[str] = set()
    for test_file in tests_dir.glob("test_*.py"):
        if test_file.name == Path(__file__).name:
            continue
        found.update(PATH_ASSERTION.findall(test_file.read_text(encoding="utf-8")))
    return found


def test_path_enumeration_matches_details_md():
    """63 terminal paths: 10 guardrail + 53 routing, no duplicates."""
    assert len(GUARDRAIL_PATH_IDS) == 10
    assert len(ROUTING_PATH_IDS) == 53
    assert len(ALL_PATH_IDS) == 63
    assert len(set(ALL_PATH_IDS)) == 63


def test_all_paths_covered():
    """Fail if any of the 63 path IDs lacks an asserting test."""
    missing = sorted(set(ALL_PATH_IDS) - _asserted_path_ids())

    assert not missing, (
        f"{len(missing)} of {len(ALL_PATH_IDS)} BRL paths have no test: {missing}"
    )


def test_no_tests_assert_unknown_paths():
    """A test asserting R-54 would be testing a path the BRL does not define."""
    unknown = sorted(_asserted_path_ids() - set(ALL_PATH_IDS))

    assert not unknown, f"Tests assert path ids that DETAILS.md §13 does not define: {unknown}"
