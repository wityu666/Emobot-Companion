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
def test_postgres_vector_crud_and_user_scope(settings):
    from dataclasses import replace
    from uuid import uuid4

    from sqlalchemy import delete

    database = Archive(replace(settings, user="test-" + uuid4().hex), os.environ["EMOBOT_TEST_POSTGRES"])
    try:
        identity = database.remember("I like cats")

        class Embedder:
            def embed(self, _text):
                return [1.0, 0.0, 0.0]

        assert database.index(Embedder()) == 1
        assert database.search("cats", [1.0, 0.0, 0.0])[0]["id"] == identity
        database.edit_memory(identity, "I like dogs")
        assert database.list_memories()[0]["vector"] is None
        database.forget()
        assert not database.list_memories()
    finally:
        with database.engine.begin() as connection:
            connection.execute(delete(database.users).where(database.users.c.id == database.user))
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
