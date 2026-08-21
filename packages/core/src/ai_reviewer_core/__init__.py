"""Shared code for the janus review job and the feedback collector.

See ``README.md`` in this package for why it exists and why it stays small.
"""

from ai_reviewer_core.marker import (
    MARKER_PREFIX,
    MARKER_VERSION,
    Marker,
    MarkerError,
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

__all__ = [
    "MARKER_PREFIX",
    "MARKER_VERSION",
    "Finding",
    "LineKind",
    "Marker",
    "MarkerError",
    "MarkerFormatError",
    "MarkerVersionError",
    "Review",
    "append_marker",
    "finding_fid",
    "marker_for_finding",
    "marker_for_summary",
    "parse_marker",
    "render_marker",
]
