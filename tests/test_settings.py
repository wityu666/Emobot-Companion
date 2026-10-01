from dataclasses import replace

import pytest

from emobot.settings import Settings


def test_secret_config_permissions_and_environment(settings, tmp_path, monkeypatch):
    target = tmp_path / "private.json"
    replace(settings, api_key="test-key").save(target)
    assert target.stat().st_mode & 0o777 == 0o600
    monkeypatch.setenv("EMOBOT_LANGUAGE", "en")
    monkeypatch.setenv("EMOBOT_MEMORY_ENABLED", "false")
    loaded = Settings.load(target)
    assert loaded.language == "en" and loaded.memory_enabled is False
    assert loaded.api_key == "test-key"
    assert not target.with_suffix(".tmp").exists()


@pytest.mark.parametrize("url", ["http://remote.example", "file:///tmp/x", "https://key:secret@example.com", "https://example.com?key=secret", "https://example.com#fragment"])
def test_unsafe_api_urls_rejected(settings, url):
    with pytest.raises(ValueError):
        replace(settings, api_url=url).validate()
