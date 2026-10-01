"""Optional PC microphone and speaker. Temporary recordings are removed even on failure."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path


class Speech:
    def __init__(self, cloud):
        self.cloud = cloud

    def listen(self) -> str:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.Microphone(sample_rate=16000) as microphone:
            recognizer.adjust_for_ambient_noise(microphone, duration=0.3)
            audio = recognizer.listen(microphone, timeout=8, phrase_time_limit=10)
        with tempfile.TemporaryDirectory(prefix="emobot-input-") as directory:
            target = Path(directory) / "recording.wav"
            target.write_bytes(audio.get_wav_data())
            return self.cloud.transcribe(target)

    def speak(self, content: str) -> None:
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()
        with tempfile.TemporaryDirectory(prefix="emobot-output-") as directory:
            target = Path(directory) / "reply.mp3"
            target.write_bytes(self.cloud.synthesize(content))
            try:
                pygame.mixer.music.load(str(target))
                pygame.mixer.music.play()
                deadline = time.monotonic() + 90
                while pygame.mixer.music.get_busy() and time.monotonic() < deadline:
                    time.sleep(0.05)
            finally:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()


def flash_image(port: str, image: Path, chip: str = "esp32s3", offset: str = "0x0") -> str:
    """Merged images use 0x0; application-only images use 0x10000."""
    import subprocess
    import sys

    if chip not in {"esp32", "esp32s3"} or offset not in {"0x0", "0x10000"}:
        raise ValueError("Unsupported chip or image offset")
    if not image.is_file() or image.suffix.lower() != ".bin":
        raise ValueError("Select an existing .bin image")
    command = [
        sys.executable,
        "-m",
        "esptool",
        "--chip",
        chip,
        "--port",
        port,
        "--baud",
        "460800",
        "write_flash",
        offset,
        str(image),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(f"Flashing failed (exit {result.returncode}): {result.stderr[-1500:]}")
    return result.stdout[-3000:]
