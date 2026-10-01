import json
from dataclasses import replace

import pytest

from emobot.companion import Companion, acceptable_memory, decode_reply
from emobot.providers import DemoCloud, ProviderError


class ScriptedCloud:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def complete(self, messages, *, reasoning=False):
        self.calls.append((messages, reasoning))
        value = next(self.replies)
        if isinstance(value, Exception):
            raise value
        return value


def envelope(reply="hello", actions=None, memories=None):
    return json.dumps({"reply": reply, "actions": actions or [], "memories": memories or []})


def test_context_and_automatic_fallback(settings, archive):
    cloud = ScriptedCloud([ProviderError("offline"), envelope("one"), envelope("two")])
    companion = Companion(settings, archive, cloud)
    assert companion.ask("first question").route == "fallback"
    companion.ask("second question")
    assert cloud.calls[0][1] is False
    assert cloud.calls[1][1] is True
    assert cloud.calls[2][0][1:3] == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "one"},
    ]
    assert len(archive.history(companion.session)) == 4


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "null",
        "[]",
        "{}",
        '{"reply":null}',
        '{"reply":"","actions":[]}',
        '{"reply":"x","actions":[null]}',
        '{"reply":"x","actions":[{"action":"exec","duration":50}]}',
    ],
)
def test_invalid_model_contract_fails(raw):
    with pytest.raises(ProviderError):
        decode_reply(raw)


def test_malformed_memory_candidates_do_not_crash(settings, archive):
    cloud = ScriptedCloud([envelope(memories=[None, "wrong", {"content": "cat", "confidence": "high"}])])
    assert Companion(settings, archive, cloud).ask("I like cats").text == "hello"
    assert not archive.list_memories()


def test_only_durable_explicit_preferences_saved(settings, archive):
    candidate = {"content": "用户喜欢猫", "category": "preference", "confidence": 0.95}
    cloud = ScriptedCloud([envelope(memories=[candidate])])
    companion = Companion(settings, archive, cloud)
    companion.ask("我喜欢猫")
    assert archive.list_memories()[0]["content"] == "我喜欢猫"


@pytest.mark.parametrize(
    "question",
    [
        "My password is abc",
        "我的银行卡是12345678",
        "我喜欢的药物是x",
        "I feel sad today",
        "My phone is 123456789",
    ],
)
def test_sensitive_or_transient_memory_rejected(question):
    assert not acceptable_memory({"content": question, "confidence": 0.99}, question)


def test_privacy_switches(settings, archive):
    candidate = {"content": "用户喜欢猫", "confidence": 0.9}
    cloud = ScriptedCloud([envelope(memories=[candidate])])
    companion = Companion(replace(settings, save_history=False, memory_enabled=False), archive, cloud)
    companion.ask("我喜欢猫")
    assert not archive.list_memories()
    assert not archive.history(companion.session)


def test_keyword_docs_route_works_in_english(settings, archive, tmp_path):
    path = tmp_path / "hardware.md"
    path.write_text("# Firmware\nFlash the ESP32-S3 firmware with PlatformIO over USB.")
    archive.import_markdown([path])
    cloud = ScriptedCloud([envelope("Use PlatformIO")])
    reply = Companion(replace(settings, language="en"), archive, cloud).ask("How to flash firmware?")
    assert reply.route == "retrieval" and reply.references
    assert cloud.calls[0][1] is True


def test_offline_demo_labels_both_languages(settings, archive):
    assert "演示模式" in Companion(settings, archive, DemoCloud()).ask("hello").text
    assert "Demo:" in Companion(replace(settings, language="en"), archive, DemoCloud()).ask("hello").text


def test_robot_failure_preserves_reply_and_records_failed_delivery(settings, archive):
    from sqlalchemy import select

    class RobotError(Exception):
        pass

    class Robot:
        connected = True

        def send_actions(self, _actions):
            raise RobotError("radio lost")

    companion = Companion(settings, archive, DemoCloud(), Robot())
    reply = companion.ask("hello")
    assert reply.text and "Robot delivery failed" in reply.warnings[0]
    with archive.engine.connect() as connection:
        rows = connection.execute(select(archive.actions)).mappings().all()
    assert rows[0]["status"] == "failed"
