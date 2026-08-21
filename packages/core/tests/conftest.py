"""Shared test settings for the core package."""

from hypothesis import HealthCheck, settings

# The functions under test are pure and fast, but a loaded CI runner can still blow a
# per-example deadline. Correctness is what these properties check, not latency.
settings.register_profile(
    "core",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("core")
