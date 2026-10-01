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
        self._loop = None
        self._thread = None
        self._closed = False
        self._generation = 0
        self._lock = threading.RLock()
        self._decoder = LineDecoder()
        self._reader = None
        self._stop_reader = threading.Event()
        self.events: queue.Queue[dict] = queue.Queue(maxsize=100)

    @property
    def connected(self) -> bool:
        return bool((self._serial and self._serial.is_open) or (self._ble and self._ble.is_connected))

    def _publish(self, message: dict) -> None:
        while True:
            try:
                self.events.put_nowait(message)
                return
            except queue.Full:
                try:
                    self.events.get_nowait()
                except queue.Empty:
                    pass  # The GUI may have drained the queue before this eviction.

    def _event(self, chunk: bytes, generation: int | None = None) -> None:
        if generation is not None and generation != self._generation:
            return
        for message in self._decoder.feed(chunk):
            self._publish(message)

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("Robot link is closed")

    def _ensure_loop(self) -> None:
        self._require_open()
        if self._loop is not None:
            return
        loop = self._loop = asyncio.new_event_loop()

        def run():
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

        self._thread = threading.Thread(target=run, daemon=True, name="emobot-ble-worker")
        self._thread.start()

    def _await(self, coroutine, timeout: int = 15):
        try:
            self._ensure_loop()
        except Exception:
            coroutine.close()
            raise
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

        with self._lock:
            return self._await(discover())

    def _reset_events(self) -> None:
        self._decoder = LineDecoder()
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                return

    def connect_usb(self, port: str) -> None:
        import serial

        with self._lock:
            self._require_open()
            self.disconnect()
            self._serial = serial.Serial(port, 115200, timeout=0.05, write_timeout=3)
            self._reset_events()
            self._stop_reader.clear()
            port_handle = self._serial
            generation = self._generation

            def read():
                failed = False
                try:
                    while not self._stop_reader.is_set():
                        chunk = port_handle.read(max(1, min(port_handle.in_waiting, 8192)))
                        if chunk:
                            self._event(chunk, generation)
                except OSError:
                    failed = not self._stop_reader.is_set()
                finally:
                    try:
                        port_handle.close()
                    except OSError:
                        pass
                    if failed and generation == self._generation:
                        self._publish({"connected": False, "transport": "usb", "error": "Serial read failed"})

            self._reader = threading.Thread(target=read, daemon=True, name="emobot-usb-reader")
            self._reader.start()

    def connect_ble(self, address: str) -> None:
        from bleak import BleakClient

        async def connect():
            client = BleakClient(address, timeout=10)
            try:
                await client.connect()
                await client.start_notify(
                    BLE_CHARACTERISTIC, lambda _sender, data: self._event(bytes(data), generation)
                )
            except (Exception, asyncio.CancelledError):
                await client.disconnect()
                raise
            return client

        with self._lock:
            self._require_open()
            self.disconnect()
            self._reset_events()
            generation = self._generation
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
            self._generation += 1
            if self._serial:
                port, self._serial = self._serial, None
                self._stop_reader.set()
                port.close()
                if self._reader:
                    self._reader.join(timeout=1)
                    self._reader = None
            if self._ble:
                client, self._ble = self._ble, None
                self._await(client.disconnect(), timeout=5)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self.disconnect()
            finally:
                self._closed = True
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                    self._thread.join(timeout=6)
                    if self._thread.is_alive():
                        raise RuntimeError("Bluetooth worker did not stop")
