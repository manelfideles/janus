"""The HTML-comment JSON marker, writer and parser.

This module is the reason ``core`` exists. The review job writes a marker into every
comment it posts; the feedback collector parses those markers back out. Ticket 04
records why they must not be two implementations: a drift between them silently breaks
feedback attribution -- rows simply stop matching, with no error anywhere.

The format, from ticket 03::

    <!-- ai-reviewer:{"v":1,"review_id":"…","persona":"fast","head_sha":"…",
                      "category":"…","fid":"…"} -->

(all on one line in a real comment; wrapped here to fit)

GitLab Flavored Markdown documents this exact use: HTML comments are invisible in
rendered output, and "add metadata or processing instructions" is a listed purpose.

**Treat this as a wire format, not an internal struct.** It has two readers that are
deployed separately and are upgraded at different times, which is what the ``v`` field
is for. So:

- Unknown fields are ignored, never an error. A newer writer may add one.
- A version this code does not know raises :class:`MarkerVersionError`. Guessing at an
  unknown layout is worse than stopping.
- A missing marker is not an error -- :func:`parse_marker` returns ``None``. Ticket 03
  makes that the fail-safe path: no marker means no last-reviewed SHA, so the job does a
  full review, which costs tokens and nothing else.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Final

from janus_core.models import Finding, Review

__all__ = [
    "MARKER_PREFIX",
    "MARKER_VERSION",
    "Marker",
    "MarkerError",
    "MarkerFormatError",
    "MarkerVersionError",
    "append_marker",
    "finding_fid",
    "marker_for_finding",
    "marker_for_summary",
    "parse_marker",
    "render_marker",
]

MARKER_PREFIX: Final = "ai-reviewer"
"""Namespace inside the HTML comment. Distinguishes our markers from anyone else's."""

MARKER_VERSION: Final = 1
"""The only payload version this code can read or write."""

FID_LENGTH: Final = 12
"""Hex characters of the finding fingerprint kept, per ticket 12."""

# The payload cannot contain `<` or `>`: `render_marker` escapes both. So a body that
# itself contains `-->` -- ordinary prose, or a Markdown code block quoting a marker --
# cannot truncate a real marker, and the terminator here is unambiguous.
_MARKER_RE: Final = re.compile(rf"<!--\s*{re.escape(MARKER_PREFIX)}:(?P<payload>[^<>]*?)\s*-->")

# Written in ticket 03's field order so a marker on a merge request reads the way the
# ticket documents it. Absent optional fields are omitted rather than sent as null.
_FIELD_ORDER: Final = ("v", "review_id", "persona", "head_sha", "category", "fid")


class MarkerError(Exception):
    """A marker was found but could not be trusted."""


class MarkerVersionError(MarkerError):
    """The marker declares a payload version this code does not know."""

    def __init__(self, version: object) -> None:
        super().__init__(
            f"unsupported marker version {version!r}; this build understands v{MARKER_VERSION} only"
        )
        self.version = version


class MarkerFormatError(MarkerError):
    """A marker of a known version is missing a required field, or has the wrong type."""


@dataclass(frozen=True, slots=True)
class Marker:
    """The machine-readable payload carried by every comment the bot posts.

    ``category`` and ``fid`` are set on an inline finding comment and absent on a summary
    comment. Ticket 12: summary comments are keyed by ``review_id`` and are never
    deduplicated, because idea.md §9 requires a fresh summary every review.
    """

    review_id: str
    persona: str
    head_sha: str
    category: str | None = None
    fid: str | None = None
    version: int = MARKER_VERSION

    @property
    def dedup_key(self) -> str | None:
        """Ticket 12's idempotency key -- the ``fid`` alone -- or ``None`` for a summary.

        ``review_id`` cannot do this job: a crashed job's re-run is a new process and
        mints a new id, so nothing would match and every comment would be posted twice.

        **``head_sha`` is deliberately not part of it.** It used to be, and that was the
        bug: every push mints a new head, so the key never matched across reviews and a
        re-review re-posted every finding. It also bought nothing, because the
        discrimination it looked like it provided is already in the ``fid`` --
        :func:`finding_fid` hashes the diff line's text, so a finding whose line really
        changed gets a different ``fid`` and correctly re-posts, while a finding on
        untouched code keeps its ``fid`` and is correctly suppressed. Keying on the
        commit could only add re-posts, never remove one.

        The marker still *carries* ``head_sha``: that is ticket 03's last-reviewed-commit
        channel, and it is a separate job from deduplication.
        """
        return self.fid


def finding_fid(finding: Finding) -> str:
    """Ticket 12's fingerprint of a finding: what makes a re-review idempotent.

    A sha256 over ``new_path``, ``old_path``, ``line_kind``, ``line_text`` and
    ``category``, truncated to 12 hex characters. ``line_text`` is stripped of leading
    and trailing whitespace first, and the fields are framed by :func:`_digest` rather
    than simply joined.

    Every input is produced by code, never by the model: the diff walk supplies the
    paths, the kind and the line text, and ticket 01 established that code owns the
    category.

    **Two different kinds of text, and only one of them is here.** The *model's* prose --
    ``finding.body`` -- is excluded, because the model is not deterministic and a re-run
    may word the same finding differently, so a prose-derived fingerprint would fail to
    match and re-post every comment. The *diff's* text -- ``finding.line_text`` -- is
    included, because the diff is deterministic: the same commit walked twice yields the
    same line, character for character. A future reader who collapses these two into
    "text is excluded" will reintroduce the bug this function was written to fix.

    **The line number is not an input.** It was, and it was wrong: an insertion anywhere
    above a finding moves its line number while leaving the code it is about untouched,
    so the fingerprint changed and the comment was posted a second time. Line text
    survives such an insertion; a line number does not. ``line_number`` stays on
    :class:`~janus_core.models.Finding` because the posting code needs it to place the
    comment -- it just no longer decides identity.

    **Whitespace is stripped at the ends, and left alone inside.** Leading and trailing
    whitespace is what mechanical reformatting churns -- a re-indent, a tab-to-space
    migration, an editor trimming line ends -- and none of it changes what a review
    comment was about, so a fid that moved with it would re-post a whole file's findings
    after a formatter run. Interior whitespace is kept exactly: normalising it would need
    to know the language, which ``core`` deliberately does not, and would fold together
    lines a reader sees as different. The accepted cost is that in an
    indentation-sensitive language a line moved into another block keeps its fid and its
    comment is suppressed; that costs one missing re-post on a thread GitLab still
    renders against the right code, which is cheaper than the churn.

    The accepted collision: two findings on the same line in the same category collapse
    to one ``fid``, and the second is suppressed as a duplicate. One comment per line per
    category is a reasonable noise ceiling. Keying on line text rather than line number
    widens that collision slightly -- two *identical* lines in one file now collapse too,
    so a file with the same ``except Exception: pass`` twice gets one comment for the
    category rather than two. That is the same noise ceiling reasoned about the code
    instead of its position, and it is the price of surviving an insertion.

    Note for the wire format: ``fid`` is an opaque string to :func:`parse_marker`, so
    changing this function is not a payload change and does not need a
    ``MARKER_VERSION`` bump. It does mean fids written by an older build never match
    fids computed by this one, so merge requests already reviewed pay one round of
    re-posts.
    """
    parts = (
        finding.new_path,
        finding.old_path,
        finding.line_kind.value,
        finding.line_text.strip(),
        finding.category,
    )
    return _digest(parts)[:FID_LENGTH]


def _digest(parts: tuple[str, ...]) -> str:
    """Hash a field tuple so that no field's content can imitate the field boundary.

    Each part is length-prefixed rather than merely joined by a separator. One of the
    parts is now free-form source text, and a ``|`` in it would otherwise let two
    different tuples -- ``("a|b", "c")`` and ``("a", "b|c")`` -- hash identically.
    """
    framed = "".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(framed.encode("utf-8")).hexdigest()


def marker_for_finding(review: Review, finding: Finding) -> Marker:
    """The marker for the inline comment carrying ``finding``."""
    return Marker(
        review_id=review.review_id,
        persona=review.persona,
        head_sha=review.head_sha,
        category=finding.category,
        fid=finding_fid(finding),
    )


def marker_for_summary(review: Review) -> Marker:
    """The marker for a review's summary comment. No ``category``, no ``fid``."""
    return Marker(
        review_id=review.review_id,
        persona=review.persona,
        head_sha=review.head_sha,
    )


def render_marker(marker: Marker) -> str:
    """Render a marker as the HTML comment to embed in a note body.

    ``<`` and ``>`` are escaped as ``\\u003c`` and ``\\u003e``, so no field value can
    ever produce a ``-->`` inside the payload and cut the marker short. JSON decodes
    those escapes back to the original characters, so this costs nothing on the way in.
    """
    payload: dict[str, Any] = {
        "v": marker.version,
        "review_id": marker.review_id,
        "persona": marker.persona,
        "head_sha": marker.head_sha,
    }
    if marker.category is not None:
        payload["category"] = marker.category
    if marker.fid is not None:
        payload["fid"] = marker.fid

    ordered = {key: payload[key] for key in _FIELD_ORDER if key in payload}
    encoded = json.dumps(ordered, ensure_ascii=True, separators=(",", ":"))
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<!-- {MARKER_PREFIX}:{encoded} -->"


def append_marker(body: str, marker: Marker) -> str:
    """Attach ``marker`` to the end of a comment body.

    Last, and on its own line, for two reasons: GitLab renders nothing for it either way,
    and :func:`parse_marker` resolves a body holding more than one marker-shaped string
    by taking the last -- so a reviewer who quotes a marker in their own words cannot
    shadow the real one.
    """
    rendered = render_marker(marker)
    if not body:
        return rendered
    return f"{body.rstrip()}\n\n{rendered}"


def parse_marker(text: str) -> Marker | None:
    """Read the marker out of a note body.

    Returns ``None`` when the body carries no marker at all -- ticket 03's fail-safe
    path, and the common case for a human's comment.

    Where a body holds several marker-shaped strings, the **last** one wins:
    :func:`append_marker` always writes at the end, so anything earlier is quoted prose
    rather than the bot's own metadata. Candidates whose payload is not a JSON object,
    or which carry no integer ``v``, are not markers this code wrote and are skipped
    rather than raised on.

    Raises:
        MarkerVersionError: the last real marker declares a version this build does not
            know. Better to stop than to guess at an unknown layout.
        MarkerFormatError: the marker's version is known but a required field is missing
            or has the wrong type. Attribution would be silently wrong, so this is loud.
    """
    for match in reversed(list(_MARKER_RE.finditer(text))):
        try:
            payload = json.loads(match.group("payload"))
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        version = payload.get("v")
        # `bool` is an `int` in Python, and `{"v": true}` is not a version.
        if not isinstance(version, int) or isinstance(version, bool):
            continue
        if version != MARKER_VERSION:
            raise MarkerVersionError(version)
        return _marker_from_payload(payload, version)
    return None


def _marker_from_payload(payload: dict[str, Any], version: int) -> Marker:
    """Build a v1 marker. Fields this build does not know are ignored, not an error."""
    return Marker(
        review_id=_required_str(payload, "review_id"),
        persona=_required_str(payload, "persona"),
        head_sha=_required_str(payload, "head_sha"),
        category=_optional_str(payload, "category"),
        fid=_optional_str(payload, "fid"),
        version=version,
    )


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise MarkerFormatError(
            f"marker field {key!r} must be a string, got {type(value).__name__}"
        )
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if not isinstance(value, str):
        raise MarkerFormatError(
            f"marker field {key!r} must be a string or absent, got {type(value).__name__}"
        )
    return value
