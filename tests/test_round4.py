import asyncio
import gzip
import json
import queue
import threading

import pytest
from test_cloud import cloud_with
from test_conversation import ScriptedCloud, envelope

from emobot.companion import Companion
from emobot.link import RobotLink


@pytest.mark.parametrize("service", ["chat", "speech"])
def test_compressed_provider_response_is_decoded_once(settings, service):
    import httpx

    content = (
        json.dumps({"choices": [{"message": {"content": "hello"}}]}).encode()
        if service == "chat"
        else b"mp3data"
    )

    def handler(_request):
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=gzip.compress(content))

    cloud = cloud_with(settings, handler)
    try:
        result = cloud.complete([]) if service == "chat" else cloud.synthesize("hello")
        assert result == ("hello" if service == "chat" else content)
    finally:
        cloud.close()


@pytest.mark.parametrize("question", ["I don't like cats", "I don't like cats but I like dogs"])
def test_automatic_memory_preserves_user_negation(settings, archive, question):
    candidate = {"content": "User likes cats", "confidence": 0.99}
    companion = Companion(settings, archive, ScriptedCloud([envelope(memories=[candidate])]))
    companion.ask(question)
    assert [row["content"] for row in archive.list_memories()] == [question]


def test_long_utterance_is_not_automatically_persisted_as_a_summary(settings, archive):
    question = "I like cats. " + "a" * 500
    companion = Companion(
        settings,
        archive,
        ScriptedCloud([envelope(memories=[{"content": "User likes cats", "confidence": 0.99}])]),
    )
    assert companion.ask(question).text
    assert not archive.list_memories()


def test_ble_timeout_disconnects_client_during_notification_setup(monkeypatch):
    import bleak

    disconnected = threading.Event()
    clients = []

    class PendingBLE:
        is_connected = False

        def __init__(self, *args, **kwargs):
            clients.append(self)

        async def connect(self):
            self.is_connected = True

        async def start_notify(self, _characteristic, _callback):
            await asyncio.Event().wait()

        async def disconnect(self):
            self.is_connected = False
            disconnected.set()

    monkeypatch.setattr(bleak, "BleakClient", PendingBLE)
    link = RobotLink()
    wait = link._await
    monkeypatch.setattr(link, "_await", lambda task, timeout=15: wait(task, min(timeout, 0.1)))
    try:
        with pytest.raises(RuntimeError, match="timed out"):
            link.connect_ble("fake")
        assert disconnected.wait(1), "Cancelled BLE setup must release the connected client"
        assert clients and not clients[0].is_connected and not link.connected
    finally:
        link.close()


def test_notification_queue_survives_consumer_drain_during_overflow():
    class ConcurrentlyDrainedQueue(queue.Queue):
        def put_nowait(self, item):
            try:
                super().put_nowait(item)
            except queue.Full:
                # Model the UI draining the full queue before the producer evicts an old event.
                while True:
                    try:
                        super().get_nowait()
                    except queue.Empty:
                        break
                raise

    link = RobotLink()
    link.events = ConcurrentlyDrainedQueue(maxsize=1)
    try:
        link.events.put_nowait({"old": True})
        link._event(b'{"ok":true}\n')
        assert link.events.get_nowait() == {"ok": True}
    finally:
        link.close()
