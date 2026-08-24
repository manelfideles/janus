"""Domain types shared by the review job and the feedback collector.

Ticket 01 settled the shape: the model is a pure function that returns findings as
data, and code owns everything else -- the GitLab ``position`` payload, the comment
markers, and the finding category. So these types describe what code holds, not what
the model is asked to emit.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["Finding", "LineKind", "Review"]


class LineKind(StrEnum):
    """Which of GitLab's three diff line kinds a finding sits on.

    Closed on purpose. Ticket 02 found that GitLab infers the kind purely from which
    line numbers are present in the ``position`` hash, and that getting it wrong is a
    hard 400 rather than a comment in the wrong place:

    ==================  ==========  ==========
    Line kind           ``old_line``  ``new_line``
    ==================  ==========  ==========
    ``ADDED``           omit        set
    ``REMOVED``         set         omit
    ``CONTEXT``         set         set
    ==================  ==========  ==========

    "Omit" means omit -- not ``null``, not ``0``. There is no fourth kind to model, and
    a fourth value would have no valid ``position`` payload, so the enum is the type
    that stops one being invented.
    """

    ADDED = "added"
    REMOVED = "removed"
    CONTEXT = "context"


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the reviewer wants to say about one line of the diff.

    ``new_path`` and ``old_path`` are both always required, for every line kind
    (ticket 02) -- for a file that was not renamed they are the same string.

    ``line_number`` is the line number on the side named by ``line_kind``: the new-side
    number for ``ADDED``, the old-side number for ``REMOVED``, and the new-side number
    for ``CONTEXT`` (a context line exists on both sides). A ``CONTEXT`` finding
    therefore needs its old-side number recovered from the diff walk before it can be
    positioned; that belongs to the reviewer package, which is a later slice.

    ``line_text`` is that line's text as the diff carries it, without the leading ``+``,
    ``-`` or space marker and without the line ending. It comes from the same diff walk
    as the paths, the kind and the number -- **not** from the model. It is what
    :func:`janus_core.marker.finding_fid` fingerprints, so that a finding keeps its
    identity when an unrelated insertion moves it down the file. An empty string is
    legitimate: a diff line may be blank.

    ``category`` derives from the persona's ``review_focus`` bullets (ticket 01), which
    idea.md §3 keeps as free text -- so it is a plain string, not an enum.

    ``severity`` is a plain string for now. Its vocabulary is not fixed by any closed
    ticket; ``blockers_only`` in idea.md §3 implies one exists, and ticket 08 (prompt
    and persona draft) is where it gets settled. Left open rather than invented.
    """

    new_path: str
    old_path: str
    line_kind: LineKind
    line_number: int
    line_text: str
    category: str
    severity: str
    body: str

    def __post_init__(self) -> None:
        if not self.new_path:
            raise ValueError("new_path must not be empty")
        if not self.old_path:
            raise ValueError("old_path must not be empty")
        if self.line_number < 1:
            raise ValueError(f"line_number must be 1 or greater, got {self.line_number}")
        if not self.category:
            raise ValueError("category must not be empty")


def _diff_order(finding: Finding) -> tuple[str, int, str]:
    """Sort key for the stable diff order the posting loop uses: path, then line."""
    return (finding.new_path, finding.line_number, finding.category)


@dataclass(frozen=True, slots=True)
class Review:
    """One run of one persona against one commit.

    ``review_id`` groups a review's comments for the feedback store (ticket 07's natural
    key). It does **not** identify a finding and cannot deduplicate one: a crashed job's
    re-run is a new process that mints a new id. That job belongs to
    :func:`janus_core.marker.finding_fid`.
    """

    review_id: str
    persona: str
    head_sha: str
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.review_id:
            raise ValueError("review_id must not be empty")
        if not self.persona:
            raise ValueError("persona must not be empty")
        if not self.head_sha:
            raise ValueError("head_sha must not be empty")

    @classmethod
    def of(
        cls,
        review_id: str,
        persona: str,
        head_sha: str,
        findings: Iterable[Finding] = (),
    ) -> Review:
        """Build a review from any iterable of findings."""
        return cls(
            review_id=review_id,
            persona=persona,
            head_sha=head_sha,
            findings=tuple(findings),
        )

    def in_diff_order(self) -> Sequence[Finding]:
        """The findings in the order the posting loop must use.

        Ticket 12 fixed it as stable diff order -- path, then line -- so that a crashed
        run and its re-run walk the findings the same way.
        """
        return sorted(self.findings, key=_diff_order)
