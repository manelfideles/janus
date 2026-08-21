"""Tests for the 12-factor environment reader."""

import pytest

from ai_reviewer_core.config import (
    DEFAULT_GLOBAL_DIFF_CAP_TOKENS,
    Config,
    ConfigError,
    ModelProvider,
    load_config,
)


def test_the_minimal_environment_is_the_provider_alone() -> None:
    config = load_config({"MODEL_PROVIDER": "bedrock"})
    assert config == Config(
        model_provider=ModelProvider.BEDROCK,
        global_diff_cap_tokens=DEFAULT_GLOBAL_DIFF_CAP_TOKENS,
    )


def test_the_default_diff_cap_is_ticket_10s_number() -> None:
    assert DEFAULT_GLOBAL_DIFF_CAP_TOKENS == 60_000


@pytest.mark.parametrize("value", ["bedrock", "anthropic_api"])
def test_both_providers_from_section_12_are_accepted(value: str) -> None:
    assert load_config({"MODEL_PROVIDER": value}).model_provider == ModelProvider(value)


def test_provider_is_required_because_neither_value_is_safe_to_assume() -> None:
    with pytest.raises(ConfigError, match="MODEL_PROVIDER is required"):
        load_config({})


@pytest.mark.parametrize("value", ["", "   ", "Bedrock", "openai", "anthropic"])
def test_an_unrecognised_provider_is_rejected(value: str) -> None:
    with pytest.raises(ConfigError, match="MODEL_PROVIDER"):
        load_config({"MODEL_PROVIDER": value})


def test_the_diff_cap_can_be_overridden() -> None:
    config = load_config({"MODEL_PROVIDER": "bedrock", "GLOBAL_DIFF_CAP_TOKENS": " 30000 "})
    assert config.global_diff_cap_tokens == 30_000


@pytest.mark.parametrize("value", ["sixty thousand", "60_000.5", "0", "-1"])
def test_an_unusable_diff_cap_is_rejected(value: str) -> None:
    with pytest.raises(ConfigError, match="GLOBAL_DIFF_CAP_TOKENS"):
        load_config({"MODEL_PROVIDER": "bedrock", "GLOBAL_DIFF_CAP_TOKENS": value})


def test_an_empty_diff_cap_falls_back_to_the_default() -> None:
    config = load_config({"MODEL_PROVIDER": "bedrock", "GLOBAL_DIFF_CAP_TOKENS": ""})
    assert config.global_diff_cap_tokens == DEFAULT_GLOBAL_DIFF_CAP_TOKENS


def test_every_problem_is_reported_at_once() -> None:
    """An operator fixing a deployment should not re-run to find the second fault."""
    with pytest.raises(ConfigError) as caught:
        load_config({"MODEL_PROVIDER": "openai", "GLOBAL_DIFF_CAP_TOKENS": "lots"})
    assert len(caught.value.problems) == 2
    assert "MODEL_PROVIDER" in str(caught.value)
    assert "GLOBAL_DIFF_CAP_TOKENS" in str(caught.value)


def test_config_is_frozen() -> None:
    config = load_config({"MODEL_PROVIDER": "bedrock"})
    with pytest.raises(AttributeError):
        config.global_diff_cap_tokens = 1  # type: ignore[misc]


def test_the_real_environment_is_read_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic_api")
    monkeypatch.delenv("GLOBAL_DIFF_CAP_TOKENS", raising=False)
    assert load_config().model_provider == ModelProvider.ANTHROPIC_API
