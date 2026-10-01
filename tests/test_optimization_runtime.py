import asyncio
import queue
import threading
import time
from types import SimpleNamespace

import pytest

from emobot.gui import Desktop
from emobot.link import RobotLink


def test_unused_usb_link_does_not_start_ble_worker_and_close_is_idempotent():
    link = RobotLink()
    try:
        assert link._thread is None
    finally:
        link.close()
    link.close()


def test_closed_link_rejects_reconnection_without_opening_port(monkeypatch):
    import serial

    calls = []
    monkeypatch.setattr(serial, "Serial", lambda *_a, **_k: calls.append("opened"))
    link = RobotLink()
    link.close()
    with pytest.raises(RuntimeError, match="closed"):
        link.connect_usb("fake")
    assert not calls


def test_ble_shutdown_cancels_pending_tasks_and_closes_loop():
    link = RobotLink()
    cancelled = threading.Event()

    async def pending():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def start():
        asyncio.create_task(pending())
        await asyncio.sleep(0)

    link._await(start())
    link.close()
    link.close()
    assert cancelled.is_set()
    assert not link._thread.is_alive() and link._loop.is_closed()


def test_late_ble_notification_cannot_enter_new_usb_connection(monkeypatch):
    import bleak
    import serial
    from test_link import FakeSerial

    callbacks = []

    class BLE:
        is_connected = False

        def __init__(self, *_args, **_kwargs):
            pass

        async def connect(self):
            self.is_connected = True

        async def start_notify(self, _characteristic, callback):
            callbacks.append(callback)

        async def disconnect(self):
            self.is_connected = False

    monkeypatch.setattr(bleak, "BleakClient", BLE)
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    link = RobotLink()
    try:
        link.connect_ble("old")
        link.connect_usb("new")
        assert link.events.get(timeout=1) == {"ready": True}
        callbacks[0](None, b'{"stale":true}\n')
        assert link.events.empty()
    finally:
        link.close()


def test_serial_read_failure_closes_handle_and_reports_disconnect(monkeypatch):
    import serial

    class LostPort:
        is_open = True
        in_waiting = 0

        def __init__(self, *_args, **_kwargs):
            pass

        def read(self, _size):
            raise serial.SerialException("unplugged")

        def close(self):
            self.is_open = False

    monkeypatch.setattr(serial, "Serial", LostPort)
    link = RobotLink()
    try:
        link.connect_usb("fake")
        deadline = time.monotonic() + 1
        while link.connected and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not link.connected
        event = link.events.get(timeout=1)
        assert event["connected"] is False and event["transport"] == "usb"
    finally:
        link.close()


def fake_desktop(events):
    desktop = Desktop.__new__(Desktop)
    desktop.closing = False
    desktop.busy = True
    desktop.results = queue.Queue()
    desktop.robot = SimpleNamespace(events=events)
    values, scheduled = [], []
    desktop.status = SimpleNamespace(set=values.append)
    desktop.window = SimpleNamespace(after=lambda *args: scheduled.append(args))
    return desktop, values, scheduled


def test_continuous_robot_notifications_yield_to_tk_event_loop():
    class ContinuousEvents:
        count = 0

        def get_nowait(self):
            self.count += 1
            if self.count > 1000:
                raise AssertionError("Unbounded drain starves the Tk event loop")
            return {"sequence": self.count}

    events = ContinuousEvents()
    desktop, values, scheduled = fake_desktop(events)
    desktop._drain()
    assert events.count <= 32
    assert len(values) == 1
    assert scheduled and scheduled[0][0] == 50


def test_failed_ui_callback_keeps_polling_and_delivers_later_results():
    desktop, values, scheduled = fake_desktop(queue.Queue())
    received = []

    def failed(_result):
        raise ValueError("private-payload")

    desktop.results.put((True, "first", failed, True))
    desktop.results.put((True, "second", received.append, True))
    desktop._drain()
    assert received == ["second"] and not desktop.busy
    assert scheduled
    assert any("ValueError" in value for value in values)
    assert not any("private-payload" in value for value in values)
