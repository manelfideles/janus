"""Tests for the comment marker: the wire format with two independent readers.

The round-trip properties are the point of this file. The reviewer writes markers and
the collector parses them, and they are deployed separately, so anything the writer can
emit the parser must accept. A parser that breaks on a comment body containing `-->` is
a real bug, not a curiosity.
"""

import hashlib
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_reviewer_core.marker import (
    MARKER_PREFIX,
    MARKER_VERSION,
    Marker,
    MarkerFormatError,
    MarkerVersionError,
    append_marker,
    finding_fid,
    marker_for_finding,
    marker_for_summary,
    parse_marker,
    render_marker,
)
from ai_reviewer_core.models import Finding, LineKind, Review

# ---------------------------------------------------------------- fixtures

AWKWARD_TEXT = [
    "plain",
    "closes an HTML comment --> right here",
    "opens one <!-- and never closes it",
    'a whole fake marker: <!-- ai-reviewer:{"v":1,"review_id":"fake"} -->',
    'a fake marker from the future: <!-- ai-reviewer:{"v":99} -->',
    'quotes "double" and \'single\' and a backslash \\ and \\"escaped\\"',
    "line one\nline two\r\nline three\n\n",
    "unicode: café 日本語 🚀   ​",  # noqa: RUF001 -- awkward whitespace on purpose
    'a markdown fence:\n```\n<!-- ai-reviewer:{"v":1} -->\n```\n',
    "angle brackets <script>alert(1)</script> and an entity &amp;",
    "\t leading and trailing whitespace \t ",
    "null-ish \x00 control \x1f characters",
]


def a_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "new_path": "src/app.py",
        "old_path": "src/app.py",
        "line_kind": LineKind.ADDED,
        "line_number": 12,
        "category": "data_integrity",
        "severity": "blocker",
        "body": "This drops the transaction.",
    }
    return Finding(**{**defaults, **overrides})  # type: ignore[arg-type]


def a_review(**overrides: object) -> Review:
    defaults: dict[str, object] = {
        "review_id": "01JBX0Y6QK",
        "persona": "backend",
        "head_sha": "9f8e7d6c5b4a39281706",
    }
    return Review(**{**defaults, **overrides})  # type: ignore[arg-type]


field_text = st.text(max_size=40)
markers = st.builds(
    Marker,
    review_id=field_text,
    persona=field_text,
    head_sha=field_text,
    category=st.none() | field_text,
    fid=st.none() | field_text,
)

# ---------------------------------------------------------------- format shape


def test_rendered_marker_matches_ticket_03s_documented_form() -> None:
    marker = Marker(
        review_id="01JBX0Y6QK",
        persona="fast",
        head_sha="9f8e7d",
        category="security",
        fid="0123456789ab",
    )
    assert render_marker(marker) == (
        '<!-- ai-reviewer:{"v":1,"review_id":"01JBX0Y6QK","persona":"fast",'
        '"head_sha":"9f8e7d","category":"security","fid":"0123456789ab"} -->'
    )


def test_summary_marker_omits_category_and_fid() -> None:
    # Ticket 12: summary comments are keyed by review_id and never deduplicated.
    rendered = render_marker(marker_for_summary(a_review()))
    assert "category" not in rendered
    assert "fid" not in rendered
    assert marker_for_summary(a_review()).dedup_key is None


def test_finding_marker_carries_the_dedup_key() -> None:
    review, finding = a_review(), a_finding()
    marker = marker_for_finding(review, finding)
    assert marker.dedup_key == (review.head_sha, finding_fid(finding))


# ---------------------------------------------------------------- round trips


@pytest.mark.parametrize("value", AWKWARD_TEXT)
def test_awkward_body_round_trips(value: str) -> None:
    """A comment body may contain anything, including something shaped like a marker."""
    marker = marker_for_finding(a_review(), a_finding())
    body = append_marker(value, marker)
    assert parse_marker(body) == marker


@pytest.mark.parametrize("value", AWKWARD_TEXT)
def test_awkward_field_values_round_trip(value: str) -> None:
    """The marker's own fields are code-owned, but the format must still survive them."""
    marker = Marker(review_id=value, persona=value, head_sha=value, category=value, fid=value)
    assert parse_marker(render_marker(marker)) == marker


@given(markers)
def test_render_then_parse_is_identity(marker: Marker) -> None:
    assert parse_marker(render_marker(marker)) == marker


@given(st.text(), markers)
def test_append_then_parse_is_identity(body: str, marker: Marker) -> None:
    assert parse_marker(append_marker(body, marker)) == marker


@given(markers)
def test_rendering_is_stable(marker: Marker) -> None:
    """Two writers on the same inputs must produce the same bytes."""
    assert render_marker(marker) == render_marker(marker)
    assert render_marker(parse_marker(render_marker(marker)) or marker) == render_marker(marker)


@given(markers)
def test_a_rendered_marker_never_contains_an_early_terminator(marker: Marker) -> None:
    """This is what keeps a `-->` in a field value from cutting the marker short."""
    rendered = render_marker(marker)
    assert rendered.count("-->") == 1
    assert rendered.endswith("-->")
    payload = rendered.removeprefix(f"<!-- {MARKER_PREFIX}:").removesuffix(" -->")
    assert "<" not in payload
    assert ">" not in payload


def test_angle_brackets_are_escaped_and_decoded_back() -> None:
    marker = Marker(review_id="a-->b", persona="p", head_sha="s")
    rendered = render_marker(marker)
    assert "\\u003e" in rendered
    parsed = parse_marker(rendered)
    assert parsed is not None
    assert parsed.review_id == "a-->b"


# ---------------------------------------------------------------- parsing rules


def test_no_marker_is_not_an_error() -> None:
    # Ticket 03's fail-safe path: no marker means no last-reviewed SHA, so the job does
    # a full review. Costs tokens and nothing else.
    assert parse_marker("A human wrote this comment.") is None
    assert parse_marker("") is None


def test_a_different_namespace_is_not_our_marker() -> None:
    assert parse_marker('<!-- some-other-bot:{"v":1,"review_id":"x"} -->') is None


def test_unclosed_marker_is_not_a_marker() -> None:
    assert parse_marker('<!-- ai-reviewer:{"v":1,"review_id":"x"}') is None


def test_the_last_marker_wins() -> None:
    """append_marker always writes last, so anything earlier is quoted prose."""
    quoted = render_marker(Marker(review_id="quoted", persona="fast", head_sha="old"))
    real = marker_for_summary(a_review())
    parsed = parse_marker(append_marker(f"See this marker: {quoted}", real))
    assert parsed == real


def test_a_quoted_future_marker_does_not_shadow_the_real_one() -> None:
    body = 'Someone pasted <!-- ai-reviewer:{"v":99,"review_id":"x"} --> into a comment.'
    real = marker_for_summary(a_review())
    assert parse_marker(append_marker(body, real)) == real


def test_unknown_fields_are_ignored() -> None:
    """A newer writer may add a field. That must not stop an older reader."""
    payload = json.dumps(
        {
            "v": MARKER_VERSION,
            "review_id": "r1",
            "persona": "fast",
            "head_sha": "abc",
            "fid": "0123456789ab",
            "confidence": 0.7,
            "labels": ["a", "b"],
            "nested": {"k": "v"},
        }
    )
    parsed = parse_marker(f"<!-- {MARKER_PREFIX}:{payload} -->")
    assert parsed == Marker(
        review_id="r1", persona="fast", head_sha="abc", category=None, fid="0123456789ab"
    )


def test_explicit_null_optional_fields_are_absent() -> None:
    payload = json.dumps(
        {
            "v": MARKER_VERSION,
            "review_id": "r1",
            "persona": "fast",
            "head_sha": "abc",
            "category": None,
            "fid": None,
        }
    )
    parsed = parse_marker(f"<!-- {MARKER_PREFIX}:{payload} -->")
    assert parsed is not None
    assert (parsed.category, parsed.fid) == (None, None)


def test_an_unknown_version_fails_loudly() -> None:
    with pytest.raises(MarkerVersionError, match="unsupported marker version 2"):
        parse_marker('<!-- ai-reviewer:{"v":2,"review_id":"r1"} -->')


@pytest.mark.parametrize(
    "payload",
    [
        "not json at all",
        "{}",
        '{"review_id":"r1"}',
        '{"v":"1","review_id":"r1"}',
        '{"v":true,"review_id":"r1"}',
        '{"v":1.5,"review_id":"r1"}',
        "[1,2,3]",
        '"just a string"',
    ],
)
def test_a_payload_we_did_not_write_is_not_a_marker(payload: str) -> None:
    """Skipped, not raised. Humans quote things in comments."""
    assert parse_marker(f"<!-- {MARKER_PREFIX}:{payload} -->") is None


@pytest.mark.parametrize(
    "payload",
    [
        '{"v":1,"persona":"fast","head_sha":"abc"}',
        '{"v":1,"review_id":"r1","head_sha":"abc"}',
        '{"v":1,"review_id":"r1","persona":"fast"}',
        '{"v":1,"review_id":7,"persona":"fast","head_sha":"abc"}',
    ],
)
def test_a_v1_marker_missing_a_required_field_fails_loudly(payload: str) -> None:
    """A known version we cannot read means attribution would be silently wrong."""
    with pytest.raises(MarkerFormatError):
        parse_marker(f"<!-- {MARKER_PREFIX}:{payload} -->")


def test_a_v1_marker_with_a_bad_optional_field_fails_loudly() -> None:
    payload = '{"v":1,"review_id":"r1","persona":"fast","head_sha":"abc","fid":12}'
    with pytest.raises(MarkerFormatError, match="fid"):
        parse_marker(f"<!-- {MARKER_PREFIX}:{payload} -->")


@pytest.mark.parametrize(
    "text",
    [
        '<!--ai-reviewer:{"v":1,"review_id":"r","persona":"p","head_sha":"s"}-->',
        '<!--   ai-reviewer:{"v":1,"review_id":"r","persona":"p","head_sha":"s"}   -->',
    ],
)
def test_whitespace_around_the_payload_is_tolerated(text: str) -> None:
    parsed = parse_marker(text)
    assert parsed is not None
    assert parsed.review_id == "r"


def test_append_marker_puts_the_marker_last_on_its_own_line() -> None:
    body = append_marker("Findings above.", marker_for_summary(a_review()))
    assert body.startswith("Findings above.\n\n<!-- ai-reviewer:")


def test_append_marker_to_an_empty_body_adds_no_blank_lines() -> None:
    marker = marker_for_summary(a_review())
    assert append_marker("", marker) == render_marker(marker)


# ---------------------------------------------------------------- fid


def test_fid_is_twelve_hex_characters() -> None:
    fid = finding_fid(a_finding())
    assert len(fid) == 12
    assert set(fid) <= set("0123456789abcdef")


def test_fid_ignores_the_findings_words() -> None:
    """The model is not deterministic. A text-derived fid would re-post everything."""
    first = finding_fid(a_finding(body="This drops the transaction."))
    second = finding_fid(a_finding(body="The transaction is never committed here."))
    assert first == second


def test_fid_ignores_severity() -> None:
    # Severity is not one of ticket 12's five inputs.
    assert finding_fid(a_finding(severity="blocker")) == finding_fid(a_finding(severity="minor"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"new_path": "src/other.py"},
        {"old_path": "src/other.py"},
        {"line_kind": LineKind.CONTEXT},
        {"line_number": 13},
        {"category": "performance"},
    ],
)
def test_fid_changes_with_each_of_its_five_inputs(overrides: dict[str, object]) -> None:
    assert finding_fid(a_finding(**overrides)) != finding_fid(a_finding())


def test_fid_matches_the_specified_derivation() -> None:
    """Pinned against ticket 12's formula, computed independently of the module."""
    finding = a_finding()
    expected = hashlib.sha256(b"src/app.py|src/app.py|added|12|data_integrity").hexdigest()
    assert finding_fid(finding) == expected[:12]


def test_two_findings_on_one_line_in_one_category_collapse() -> None:
    """The accepted collision from ticket 12: one comment per line per category."""
    first = a_finding(body="first thing")
    second = a_finding(body="second thing")
    assert finding_fid(first) == finding_fid(second)


def test_the_dedup_key_survives_a_write_and_read() -> None:
    """This is the whole reason `core` owns both halves of the format."""
    review, finding = a_review(), a_finding()
    posted = append_marker(finding.body, marker_for_finding(review, finding))

    # The collector, a separate deployment, reads it back.
    parsed = parse_marker(posted)
    assert parsed is not None
    assert parsed.dedup_key == (review.head_sha, finding_fid(finding))


def test_the_dedup_key_discriminates_on_head_sha() -> None:
    finding = a_finding()
    old = marker_for_finding(a_review(head_sha="aaaa"), finding)
    new = marker_for_finding(a_review(head_sha="bbbb"), finding)
    assert old.fid == new.fid
    assert old.dedup_key != new.dedup_key
