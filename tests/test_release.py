import os

import pytest
from test_conversation import ScriptedCloud, envelope

from emobot.archive import Archive
from emobot.companion import Companion
from emobot.providers import DemoCloud


def test_memory_recall_without_repeating_preference(settings, archive):
    archive.remember("I like cats")
    reply = Companion(settings, archive, ScriptedCloud([envelope("You like cats")])).ask(
        "What do you remember about me?"
    )
    assert reply.references[0]["content"] == "I like cats"
    assert reply.route == "retrieval"


def test_query_vector_and_stored_pgvector_array(settings, archive):
    np = pytest.importorskip("numpy")
    from emobot.archive import cosine

    assert cosine([1.0, 0.0, 0.0], np.array([1.0, 0.0, 0.0])) == 1.0


@pytest.mark.skipif(
    not os.environ.get("EMOBOT_TEST_POSTGRES"), reason="Requires isolated PostgreSQL/pgvector service"
)
def test_postgres_vector_crud_and_user_scope(settings, tmp_path):
    from dataclasses import replace
    from uuid import uuid4

    from sqlalchemy import delete, select

    from emobot.protocol import Action

    database = Archive(replace(settings, user="test-" + uuid4().hex), os.environ["EMOBOT_TEST_POSTGRES"])
    friend = Archive(replace(settings, user="friend-" + uuid4().hex), os.environ["EMOBOT_TEST_POSTGRES"])
    try:
        identity = database.remember("I like cats")
        friend_identity = friend.remember("I like cats")
        assert all(row["id"] != friend_identity for row in database.search("cats"))

        class Embedder:
            def embed(self, _text):
                return [1.0, 0.0, 0.0]

        assert database.index(Embedder()) == 1
        assert database.search("cats", [1.0, 0.0, 0.0])[0]["id"] == identity
        database.edit_memory(identity, "I like dogs")
        assert database.list_memories()[0]["vector"] is None
        document = tmp_path / "robot.md"
        document.write_text("robot manual " * 200)
        assert database.import_markdown([document]) == 1
        assert database.import_markdown([document]) == 0
        assert database.index(Embedder()) == 4  # Edited memory and three new chunks.
        results = database.search("robot", [1, 0, 0], include_memories=False)
        assert len(results) == 3 and all(row["source"] == "knowledge_chunks" for row in results)
        assert database.search("robot", include_memories=False)
        document.write_text("replaced guide")
        assert database.import_markdown([document]) == 1
        assert not database.search("robot", include_memories=False)
        session = database.start_session()
        database.save_turn(session, "hello", "reply")
        assert database.history(session)[-1]["content"] == "reply"
        database.record_actions(session, [Action("head_nod"), Action("eye_happy")], "sent")
        with database.engine.connect() as connection:
            assert (
                len(
                    connection.execute(
                        select(database.actions).where(database.actions.c.user_id == database.user)
                    ).all()
                )
                == 2
            )
        database.forget()
        assert not database.list_memories()
        assert friend.list_memories()[0]["id"] == friend_identity
    finally:
        with database.engine.begin() as connection:
            for table in (
                database.memories,
                database.chunks,
                database.documents,
                database.messages,
                database.sessions,
                database.actions,
                database.skills,
            ):
                connection.execute(delete(table).where(table.c.user_id.in_([database.user, friend.user])))
            connection.execute(
                delete(database.users).where(database.users.c.id.in_([database.user, friend.user]))
            )
        friend.close()
        database.close()


def test_demo_ignores_existing_embedding_configuration(settings, archive):
    from dataclasses import replace

    reply = Companion(replace(settings, embedding_model="existing-config"), archive, DemoCloud()).ask("hi")
    assert "演示模式" in reply.text
    assert reply.warnings


def test_real_action_and_skill_logs(settings, archive):
    from sqlalchemy import select

    companion = Companion(settings, archive, DemoCloud())
    companion.ask("hello")
    with archive.engine.connect() as connection:
        actions = connection.execute(select(archive.actions)).mappings().all()
        skills = connection.execute(select(archive.skills)).mappings().all()
    assert len(actions) == 2 and actions[0]["status"] == "simulated"
    assert skills[0]["status"] == "ok" and skills[0]["kind"] == "fast"


def test_flash_arguments_are_literal(tmp_path, monkeypatch):
    import subprocess

    from emobot.speech import flash_image

    seen = []
    image = tmp_path / "literal;name.bin"
    image.write_bytes(b"image")

    def execute(command, **kwargs):
        seen.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", execute)
    assert flash_image("port", image, offset="0x10000") == "ok"
    assert seen[0][0][-1] == str(image)
    assert seen[0][0][-2] == "0x10000"
    assert "shell" not in seen[0][1]
    with pytest.raises(ValueError):
        flash_image("port", image, offset="0xfff")


def test_speech_recognition_converts_wav_on_python313():
    import io
    import wave

    sr = pytest.importorskip("speech_recognition")
    audio = sr.AudioData(b"\0\0" * 1600, 16000, 2)
    converted = audio.get_wav_data(convert_rate=8000, convert_width=1)
    with wave.open(io.BytesIO(converted)) as recording:
        assert recording.getframerate() == 8000
        assert recording.getsampwidth() == 1
        assert recording.getnchannels() == 1
        assert recording.readframes(recording.getnframes())
