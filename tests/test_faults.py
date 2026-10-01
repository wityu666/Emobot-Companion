import json
from dataclasses import replace

import pytest
from test_conversation import ScriptedCloud, envelope

from emobot.companion import Companion, acceptable_memory
from emobot.providers import ProviderError
from emobot.settings import Settings


def test_model_cannot_invent_memory():
    assert not acceptable_memory({"content": "用户喜欢狗", "confidence": 0.99}, "我喜欢猫")
    assert acceptable_memory({"content": "User likes cats", "confidence": 0.99}, "I like cats")


def test_forgetting_clears_later_chat_restatements(settings, archive):
    companion = Companion(
        settings, archive, ScriptedCloud([envelope("You like cats"), envelope("Still remember your cats")])
    )
    companion.ask("I like cats")
    identity = archive.remember("I like cats")
    old_session = companion.session
    companion.ask("what do you know about me?")
    companion.forget(identity)
    assert archive.history(old_session) == []


@pytest.mark.parametrize(
    "changes",
    [{"memory_enabled": "false"}, {"api_key": 123}, {"embedding_dimensions": True}, {"save_history": 1}],
)
def test_json_configuration_rejects_wrong_types(settings, changes):
    with pytest.raises(ValueError):
        replace(settings, **changes).validate()


def test_embedding_failure_keeps_keyword_documents(settings, archive, tmp_path):
    class Cloud(ScriptedCloud):
        def embed(self, _text):
            raise ProviderError("temporary outage")

    doc = tmp_path / "robot.md"
    doc.write_text("# Servo\nCalibrate servo yaw and pitch using head_move.")
    archive.import_markdown([doc])
    cloud = Cloud([envelope("Use head_move")])
    reply = Companion(replace(settings, embedding_model="configured"), archive, cloud).ask(
        "servo calibration"
    )
    assert reply.references and "keyword" in reply.warnings[0]


def test_corrupt_settings_does_not_leak_secret(settings, tmp_path):
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(["a-secret"]))
    with pytest.raises(ValueError) as error:
        Settings.load(target)
    assert "a-secret" not in str(error.value)
