import pytest

from emobot.archive import Archive
from emobot.settings import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("EMOBOT_HOME", str(tmp_path / "state"))
    return Settings(embedding_dimensions=3)


@pytest.fixture
def archive(settings):
    database = Archive(settings, "sqlite:///:memory:")
    yield database
    database.close()
