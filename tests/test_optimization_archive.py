from dataclasses import replace

import pytest
from sqlalchemy import event, insert, select, update
from sqlalchemy.exc import IntegrityError

from emobot.archive import Archive
from emobot.protocol import Action


def test_bulk_writes_keep_order_and_bound_database_calls(archive, tmp_path):
    document = tmp_path / "large.md"
    document.write_text("robot knowledge " * 5625)
    calls = []
    event.listen(archive.engine, "before_cursor_execute", lambda _c, _u, sql, *_args: calls.append(sql))
    assert archive.import_markdown([document]) == 1
    assert sum(sql.startswith("INSERT") for sql in calls) == 2
    with archive.engine.connect() as connection:
        rows = connection.execute(select(archive.chunks).order_by(archive.chunks.c.position)).mappings().all()
    assert len(rows) == 100
    assert [row["position"] for row in rows] == list(range(100))
    calls.clear()
    session = archive.start_session()
    archive.save_turn(session, "question", "answer")
    archive.record_actions(session, [Action("head_nod"), Action("eye_happy")], "sent")
    assert sum(sql.startswith("INSERT") for sql in calls) == 3
    assert archive.history(session) == [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
    ]


def test_top_results_preserve_ties_hybrid_ranking_and_user_scope(settings, archive, tmp_path):
    ids = [archive.remember(value) for value in ("robot cats", "robot dogs", "music cats")]
    with archive.engine.begin() as connection:
        for identity, vector in zip(ids, ([1, 0, 0], [0, 1, 0], [1, 0, 0])):
            connection.execute(
                update(archive.memories).where(archive.memories.c.id == identity).values(vector=vector)
            )
        connection.execute(
            insert(archive.memories).values(
                id="other", user_id="friend", content="robot cats", vector=[1, 0, 0]
            )
        )
    assert [row["id"] for row in archive.search("robot", limit=2)] == ids[:2]
    assert [row["id"] for row in archive.search("robot", vector=[1, 0, 0], limit=2)] == [ids[0], ids[2]]
    assert archive.search("robot", include_memories=False) == []
    assert len(archive.search("remember me", limit=1)) == 1
    assert archive.search("robot", limit=0) == []


def test_keyword_search_does_not_fetch_vectors(archive):
    archive.remember("robot preference")
    selects = []
    event.listen(archive.engine, "before_cursor_execute", lambda _c, _u, sql, *_args: selects.append(sql))
    assert archive.search("robot")
    assert all(".vector" not in sql for sql in selects)


def test_index_does_not_count_or_restore_concurrently_edited_memory(archive):
    identity = archive.remember("old preference")

    class EditingEmbedder:
        def embed(self, _content):
            archive.edit_memory(identity, "new preference")
            return [1, 0, 0]

    assert archive.index(EditingEmbedder()) == 0
    assert archive.list_memories()[0]["content"] == "new preference"
    assert archive.list_memories()[0]["vector"] is None


def test_failed_bulk_replacement_rolls_back_document_and_chunks(archive, tmp_path, monkeypatch):
    document = tmp_path / "guide.md"
    document.write_text("original robot guide")
    archive.import_markdown([document])
    document.write_text("new guide " * 200)
    monkeypatch.setattr("emobot.archive.uid", lambda: "duplicate")
    with pytest.raises(IntegrityError):
        archive.import_markdown([document])
    assert archive.search("original")[0]["content"] == "original robot guide"
    assert not archive.search("new")


def test_scoped_streaming_search_on_shared_file(settings, tmp_path):
    url = f"sqlite:///{tmp_path / 'shared.db'}"
    owner, friend = Archive(settings, url), Archive(replace(settings, user="friend"), url)
    try:
        owner.remember("robot owner")
        friend.remember("robot friend")
        assert [row["content"] for row in friend.search("robot")] == ["robot friend"]
    finally:
        owner.close()
        friend.close()
