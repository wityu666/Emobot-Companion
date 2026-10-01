import threading
import time

from emobot.link import RobotLink
from emobot.protocol import Action


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.pending = bytearray(b'{"ready":true}\n')
        self.written = []
        self.lock = threading.Lock()

    @property
    def in_waiting(self):
        with self.lock:
            return len(self.pending)

    def read(self, size):
        with self.lock:
            data = bytes(self.pending[:size])
            del self.pending[:size]
        if not data:
            time.sleep(0.01)
        return data

    def write(self, payload):
        self.written.append(payload)
        with self.lock:
            self.pending += b'{"ok":true}\n'
        return len(payload)

    def close(self):
        self.is_open = False


def test_usb_background_receive_disconnect_and_shutdown(monkeypatch):
    import serial

    monkeypatch.setattr(serial, "Serial", FakeSerial)
    link = RobotLink()
    try:
        link.connect_usb("fake")
        assert link.connected
        assert link.events.get(timeout=1) == {"ready": True}
        link.send_actions([Action("head_nod")])
        assert link.events.get(timeout=1) == {"ok": True}
        assert b"head_nod" in link._serial.written[0]
        link.disconnect()
        assert not link.connected
        assert link._reader is None
    finally:
        link.close()
    assert not link._thread.is_alive()


def test_ble_chunking_and_notification(monkeypatch):
    import bleak

    class FakeBLE:
        is_connected = False
        writes = []

        def __init__(self, *args, **kwargs):
            pass

        async def connect(self):
            self.is_connected = True

        async def start_notify(self, characteristic, callback):
            callback(characteristic, b'{"ok":')
            callback(characteristic, b"true}\n")

        async def write_gatt_char(self, characteristic, payload, response):
            assert response and len(payload) <= 20
            self.writes.append(payload)

        async def disconnect(self):
            self.is_connected = False

    monkeypatch.setattr(bleak, "BleakClient", FakeBLE)
    link = RobotLink()
    try:
        link.connect_ble("fake")
        assert link.events.get(timeout=1) == {"ok": True}
        link.send_actions([Action("eye_happy")])
        assert b"eye_happy" in b"".join(link._ble.writes)
        link.disconnect()
        assert not link.connected
    finally:
        link.close()
