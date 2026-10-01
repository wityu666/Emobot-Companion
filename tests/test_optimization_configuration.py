import json
import os
import subprocess
import sys
from dataclasses import replace

import httpx
import pytest
from test_cloud import cloud_with

from emobot.providers import ProviderError
from emobot.settings import Settings


@pytest.mark.parametrize("name", ["MEMORY_ENABLED", "SAVE_HISTORY", "VOICE_ENABLED"])
def test_boolean_environment_typo_is_reported(name, tmp_path, monkeypatch):
    monkeypatch.setenv("EMOBOT_" + name, "treu")
    with pytest.raises(ValueError, match=name):
        Settings.load(tmp_path / "missing.json")


@pytest.mark.parametrize("value,expected", [(" YES ", True), (" off ", False)])
def test_boolean_environment_accepts_explicit_trimmed_values(value, expected, tmp_path, monkeypatch):
    monkeypatch.setenv("EMOBOT_SAVE_HISTORY", value)
    assert Settings.load(tmp_path / "missing.json").save_history is expected


def test_private_configuration_round_trips_in_ascii_locale(tmp_path):
    script = r"""
import json, locale, sys
from pathlib import Path
from emobot.settings import Settings
target = Path(sys.argv[1])
Settings(persona="\u4f60\u597d", embedding_dimensions=3).save(target)
assert Settings.load(target).persona == "\u4f60\u597d"
assert json.loads(target.read_bytes().decode("utf-8"))["persona"] == "\u4f60\u597d"
print(locale.getpreferredencoding(False))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "settings.json")],
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C"},
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("payload", [[], {"code": 3000, "data": ""}])
def test_malformed_volcano_reply_is_a_provider_error(settings, payload):
    cloud = cloud_with(
        replace(settings, speech_provider="volcano", volcano_token="test-only"),
        lambda _request: httpx.Response(200, json=payload),
    )
    try:
        with pytest.raises(ProviderError):
            cloud.synthesize("hello")
    finally:
        cloud.close()


@pytest.mark.parametrize(
    "response", [httpx.Response(200, content=b""), httpx.Response(200, json={"error": "private-data"})]
)
def test_invalid_speech_body_fails_before_audio_playback(settings, response):
    cloud = cloud_with(settings, lambda _request: response)
    try:
        with pytest.raises(ProviderError) as error:
            cloud.synthesize("hello")
        assert "private-data" not in str(error.value)
    finally:
        cloud.close()


@pytest.mark.parametrize("vector", [[1.0], [float("nan"), 0, 0], [10**400, 0, 0]])
def test_invalid_embedding_contract_is_normalized_at_provider_boundary(settings, vector):
    cloud = cloud_with(
        replace(settings, embedding_model="synthetic"),
        lambda _request: httpx.Response(200, content=json.dumps({"data": [{"embedding": vector}]}).encode()),
    )
    try:
        with pytest.raises(ProviderError):
            cloud.embed("hello")
    finally:
        cloud.close()
