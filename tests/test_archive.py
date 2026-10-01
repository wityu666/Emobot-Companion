from dataclasses import replace

import pytest
from sqlalchemy import select

from emobot.archive import Archive, cosine


class Embedder:
    def embed(self, _text):
        return [1.0, 0.0, 0.0]


def test_embedding_invalidation_and_scoped_edit(settings, archive):
    identity = archive.remember("I like cats")
    assert archive.index(Embedder()) == 1
    assert archive.list_memories()[0]["vector"] == [1.0, 0.0, 0.0]
    archive.edit_memory(identity, "I prefer dogs")
    assert archive.list_memories()[0]["vector"] is None
    with pytest.raises(KeyError):
        archive.edit_memory("missing", "valid content")


def test_idempotent_import_and_replacement(settings, archive, tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# WiFi\n连接无线网络\n# USB\n串口连接")
    assert archive.import_markdown([path]) == 1
    assert archive.import_markdown([path]) == 0
    assert archive.search("无线网络")
    path.write_text("# BLE\nBluetooth connection")
    assert archive.import_markdown([path]) == 1
    assert not archive.search("无线网络")
    assert archive.search("Bluetooth")


def test_database_user_isolation(settings, tmp_path):
    url = f"sqlite:///{tmp_path / 'shared.db'}"
    first = Archive(settings, url)
    second = Archive(replace(settings, user="friend"), url)
    try:
        identity = first.remember("I like music")
        assert not second.list_memories()
        with pytest.raises(KeyError):
            second.edit_memory(identity, "stolen content")
        second.forget(identity)
        assert first.list_memories()
    finally:
        first.close()
        second.close()


def test_forget_removes_source_and_answer(archive):
    session = archive.start_session()
    source = archive.save_turn(session, "I like cats", "You like cats; remembered")
    memory = archive.remember("I like cats", source=source)
    archive.forget(memory)
    assert archive.history(session) == []
    assert not archive.list_memories()


def test_forget_all_removes_personal_data_but_preserves_docs(archive, tmp_path):
    session = archive.start_session()
    archive.save_turn(session, "private", "reply")
    archive.remember("private preference")
    document = tmp_path / "firmware.md"
    document.write_text("Firmware installation")
    archive.import_markdown([document])
    archive.forget()
    assert not archive.list_memories() and not archive.history(session)
    assert archive.search("firmware")
    with archive.engine.connect() as connection:
        assert not connection.execute(select(archive.sessions)).all()


def test_wrong_dimensions_or_nonfinite_not_indexed(archive):
    class Wrong:
        def embed(self, _text):
            return [float("nan")] * 3

    archive.remember("I like cats")
    with pytest.raises(ValueError):
        archive.index(Wrong())
    assert archive.list_memories()[0]["vector"] is None
    assert cosine([1, 0], [0, 1]) == 0


def test_edited_memory_is_reindexed(archive):
    identity = archive.remember("I like cats")
    assert archive.index(Embedder()) == 1
    archive.edit_memory(identity, "I like dogs")
    assert archive.index(Embedder()) == 1
    assert archive.list_memories()[0]["vector"] == [1.0, 0.0, 0.0]
