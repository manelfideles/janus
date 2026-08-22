"""The 12-factor environment reader.

idea.md §12 fixes the mechanism: one code path everywhere, and only env-driven
configuration differs between local and production. So configuration is read once, at
start-up, into a frozen object -- nothing later in the program reads ``os.environ``.

**This is deliberately a short list.** The full production variable set is not settled
yet. Only variables fixed by a closed ticket or a settled report live here; anything
still under discussion is left out on purpose, so that this file never becomes the place
a value was quietly invented. Adding one is a field plus a line in :func:`load_config`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "DEFAULT_GLOBAL_DIFF_CAP_TOKENS",
    "Config",
    "ConfigError",
    "ModelProvider",
    "load_config",
]

DEFAULT_GLOBAL_DIFF_CAP_TOKENS: Final = 60_000
"""Ticket 10's global diff cap, in tokens.

Chosen because it lands just inside GitLab's own 5,000-changed-line collapse threshold
(roughly 56k-90k tokens), caps one review at about $0.50 on the most expensive candidate
model, and still fits inside the context window of every current model -- so a model swap
cannot break it. A persona may lower this value and may never raise it.
"""


class ModelProvider(StrEnum):
    """Which :class:`ModelClient` implementation to build.

    idea.md §12 names both the variable and its values: production talks to Amazon
    Bedrock, local development talks to the Anthropic API with a personal key. The
    interface behind them is a later slice.
    """

    BEDROCK = "bedrock"
    ANTHROPIC_API = "anthropic_api"


class ConfigError(Exception):
    """The environment does not describe a runnable configuration.

    Carries every problem found, not just the first: an operator fixing a deployment
    should not have to re-run to discover the second broken variable.
    """

    def __init__(self, problems: list[str]) -> None:
        joined = "\n".join(f"  - {problem}" for problem in problems)
        super().__init__(f"invalid configuration:\n{joined}")
        self.problems = tuple(problems)


@dataclass(frozen=True, slots=True)
class Config:
    """Everything the program is allowed to learn from the environment."""

    model_provider: ModelProvider
    global_diff_cap_tokens: int


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Read the configuration, or raise :class:`ConfigError` listing every problem.

    ``env`` defaults to the real process environment; pass a mapping to test.

    ``MODEL_PROVIDER`` has no default. Production and local development want different
    values and neither is safer to assume, so an unset variable is an error rather than a
    silent pick.
    """
    source = os.environ if env is None else env
    problems: list[str] = []

    provider = _read_enum(source, "MODEL_PROVIDER", ModelProvider, problems)
    cap = _read_positive_int(
        source, "GLOBAL_DIFF_CAP_TOKENS", DEFAULT_GLOBAL_DIFF_CAP_TOKENS, problems
    )

    if problems:
        raise ConfigError(problems)

    # Unreachable: an unusable MODEL_PROVIDER is always one of the problems above.
    assert provider is not None
    return Config(model_provider=provider, global_diff_cap_tokens=cap)


def _read_enum[E: StrEnum](
    env: Mapping[str, str],
    name: str,
    enum: type[E],
    problems: list[str],
) -> E | None:
    raw = env.get(name, "").strip()
    allowed = ", ".join(member.value for member in enum)
    if not raw:
        problems.append(f"{name} is required; set one of: {allowed}")
        return None
    try:
        return enum(raw)
    except ValueError:
        problems.append(f"{name}={raw!r} is not recognised; expected one of: {allowed}")
        return None


def _read_positive_int(
    env: Mapping[str, str],
    name: str,
    default: int,
    problems: list[str],
) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        problems.append(f"{name}={raw!r} is not a whole number")
        return default
    if value < 1:
        problems.append(f"{name}={value} must be 1 or greater")
        return default
    return value
