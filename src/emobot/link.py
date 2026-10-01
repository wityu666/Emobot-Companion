"""USB and BLE adapters with one owner thread per device and bounded frames."""

from __future__ import annotations

import asyncio
import queue
import threading
from concurrent.futures import TimeoutError

from .protocol import LineDecoder, frame

BLE_SERVICE = "4db9a22d-6db4-d9fe-4d93-38e350abdc3c"
BLE_CHARACTERISTIC = "ff1cdaef-0105-e4fb-7be2-018500c2e927"


class RobotLink:
    def __init__(self):
        self._serial = None
        self._ble = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._lock = threading.RLock()
        self._decoder = LineDecoder()
        self._reader = None
        self._stop_reader = threading.Event()
        self.events: queue.Queue[dict] = queue.Queue(maxsize=100)

    @property
    def connected(self) -> bool:
        return bool((self._serial and self._serial.is_open) or (self._ble and self._ble.is_connected))

    def _event(self, chunk: bytes) -> None:
        for message in self._decoder.feed(chunk):
            try:
                self.events.put_nowait(message)
            except queue.Full:
                self.events.get_nowait()
                self.events.put_nowait(message)

    def _await(self, coroutine, timeout: int = 15):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout)
        except TimeoutError:
            future.cancel()
            raise RuntimeError("Bluetooth operation timed out") from None

    @staticmethod
    def serial_ports() -> list[str]:
        from serial.tools.list_ports import comports

        return [item.device for item in comports()]

    def ble_devices(self) -> list[tuple[str, str]]:
        from bleak import BleakScanner

        async def discover():
            devices = await BleakScanner.discover(timeout=5)
            return [
                (item.name or "Unnamed", item.address)
                for item in devices
                if "Emobot" in (item.name or "") or "Desk-Emoji" in (item.name or "")
            ]

        return self._await(discover())

    def connect_usb(self, port: str) -> None:
        import serial

        with self._lock:
            self.disconnect()
            self._serial = serial.Serial(port, 115200, timeout=0.05, write_timeout=3)
            self._decoder = LineDecoder()
            self._stop_reader.clear()
            port_handle = self._serial

            def read():
                while not self._stop_reader.is_set():
                    try:
                        chunk = port_handle.read(max(1, min(port_handle.in_waiting, 8192)))
                        if chunk:
                            self._event(chunk)
                    except OSError:
                        break

            self._reader = threading.Thread(target=read, daemon=True, name="emobot-usb-reader")
            self._reader.start()

    def connect_ble(self, address: str) -> None:
        from bleak import BleakClient

        async def connect():
            client = BleakClient(address, timeout=10)
            try:
                await client.connect()
                await client.start_notify(BLE_CHARACTERISTIC, lambda _sender, data: self._event(bytes(data)))
            except Exception:
                await client.disconnect()
                raise
            return client

        with self._lock:
            self.disconnect()
            self._decoder = LineDecoder()
            self._ble = self._await(connect())

    def _send(self, payload: bytes) -> None:
        with self._lock:
            if self._serial and self._serial.is_open:
                if self._serial.write(payload) != len(payload):
                    raise OSError("Incomplete serial write")
            elif self._ble and self._ble.is_connected:

                async def transmit():
                    for start in range(0, len(payload), 20):
                        await self._ble.write_gatt_char(
                            BLE_CHARACTERISTIC, payload[start : start + 20], response=True
                        )

                self._await(transmit())
            else:
                raise RuntimeError("Connect a robot first")

    def send_actions(self, actions) -> None:
        self._send(frame(tuple(actions)))

    def factory(self, command: str) -> None:
        self._send(frame(factory=command))

    def disconnect(self) -> None:
        with self._lock:
            if self._serial:
                self._stop_reader.set()
                if self._reader:
                    self._reader.join(timeout=1)
                    self._reader = None
                self._serial.close()
                self._serial = None
            if self._ble:
                client, self._ble = self._ble, None
                self._await(client.disconnect(), timeout=5)

    def close(self) -> None:
        try:
            self.disconnect()
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=6)
            if not self._thread.is_alive():
                self._loop.close()
