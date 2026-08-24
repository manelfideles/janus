"""Tests for the domain types."""

import pytest

from janus_core.models import Finding, LineKind, Review


def a_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "new_path": "src/app.py",
        "old_path": "src/app.py",
        "line_kind": LineKind.ADDED,
        "line_number": 12,
        "line_text": "    session.rollback()",
        "category": "data_integrity",
        "severity": "blocker",
        "body": "This drops the transaction.",
    }
    return Finding(**{**defaults, **overrides})  # ty: ignore[invalid-argument-type]


def test_line_kind_is_closed_to_gitlabs_three_kinds() -> None:
    # Ticket 02: GitLab infers the kind from which line numbers are present, and there
    # is no fourth kind that has a valid `position` payload.
    assert [kind.value for kind in LineKind] == ["added", "removed", "context"]


def test_line_kind_rejects_anything_else() -> None:
    with pytest.raises(ValueError, match="unchanged"):
        LineKind("unchanged")


def test_finding_is_frozen() -> None:
    finding = a_finding()
    with pytest.raises(AttributeError):
        finding.line_number = 13  # ty: ignore[invalid-assignment]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"new_path": ""}, "new_path"),
        ({"old_path": ""}, "old_path"),
        ({"line_number": 0}, "line_number"),
        ({"line_number": -1}, "line_number"),
        ({"category": ""}, "category"),
    ],
)
def test_finding_rejects_unusable_values(overrides: dict[str, object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        a_finding(**overrides)


def test_finding_allows_a_blank_line() -> None:
    # A diff line may be blank, so empty line text is legitimate, not a missing value.
    assert a_finding(line_text="").line_text == ""


def test_finding_allows_a_rename() -> None:
    finding = a_finding(new_path="src/new.py", old_path="src/old.py")
    assert (finding.old_path, finding.new_path) == ("src/old.py", "src/new.py")


def test_review_requires_its_identifying_fields() -> None:
    for field, message in [
        ("review_id", "review_id"),
        ("persona", "persona"),
        ("head_sha", "head_sha"),
    ]:
        kwargs = {"review_id": "r1", "persona": "fast", "head_sha": "abc123", field: ""}
        with pytest.raises(ValueError, match=message):
            Review(**kwargs)  # ty: ignore[invalid-argument-type]


def test_review_defaults_to_no_findings() -> None:
    # The `fast` persona is built to return nothing on a clean merge request.
    review = Review(review_id="r1", persona="fast", head_sha="abc123")
    assert review.findings == ()
    assert list(review.in_diff_order()) == []


def test_review_of_accepts_any_iterable() -> None:
    review = Review.of("r1", "backend", "abc123", iter([a_finding()]))
    assert len(review.findings) == 1


def test_findings_are_ordered_by_path_then_line() -> None:
    # Ticket 12 posts inline comments in stable diff order, so a crashed run and its
    # re-run walk the findings identically.
    findings = [
        a_finding(new_path="src/b.py", line_number=3),
        a_finding(new_path="src/a.py", line_number=90),
        a_finding(new_path="src/a.py", line_number=9),
    ]
    review = Review.of("r1", "backend", "abc123", findings)
    assert [(f.new_path, f.line_number) for f in review.in_diff_order()] == [
        ("src/a.py", 9),
        ("src/a.py", 90),
        ("src/b.py", 3),
    ]
