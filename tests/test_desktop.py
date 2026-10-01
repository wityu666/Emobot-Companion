import os
import queue
import threading
import time

import pytest

from emobot.companion import Companion
from emobot.providers import DemoCloud


@pytest.mark.skipif(os.environ.get("EMOBOT_GUI_TESTS") != "1", reason="Opt-in native Tk test; CI uses Xvfb")
def test_desktop_build_and_worker_delivery(settings, archive):
    from emobot.gui import Desktop

    class Robot:
        connected = False
        events = queue.Queue()
        closed = False

        def close(self):
            self.closed = True

    robot = Robot()
    desktop = Desktop(Companion(settings, archive, DemoCloud()), robot, True)
    desktop.window.withdraw()
    try:
        assert len(desktop.book.tabs()) == 7
        main_thread = threading.get_ident()
        results = []
        desktop.submit(lambda: threading.get_ident(), results.append)
        deadline = time.monotonic() + 3
        while desktop.busy and time.monotonic() < deadline:
            desktop.window.update()
            time.sleep(0.02)
        assert results and results[0] != main_thread
        desktop.question.insert("1.0", "我喜欢猫")
        desktop.send()
        deadline = time.monotonic() + 3
        while desktop.busy and time.monotonic() < deadline:
            desktop.window.update()
            time.sleep(0.02)
        assert "演示模式" in desktop.transcript.get("1.0", "end")
        assert not desktop.busy
        desktop.config_vars["theme"].set("dark")
        desktop.save_settings()
        assert desktop.companion.settings.theme == "dark"
    finally:
        desktop.close()
    assert robot.closed


@pytest.mark.skipif(os.environ.get("EMOBOT_GUI_TESTS") != "1", reason="Opt-in native Tk test; CI uses Xvfb")
def test_desktop_cleanup_finishes_after_robot_disconnect_failure(settings, archive, monkeypatch, caplog):
    from emobot.gui import Desktop

    closed = []

    class Robot:
        connected = False
        events = queue.Queue()

        def close(self):
            raise RuntimeError("disconnect failed: token-test-secret")

    cloud = DemoCloud()
    desktop = Desktop(Companion(settings, archive, cloud), Robot(), True)
    desktop.window.withdraw()
    destroy = desktop.window.destroy
    archive_close = archive.close

    def close_archive():
        archive_close()
        closed.append("archive")

    def destroy_window():
        destroy()
        closed.append("window")

    monkeypatch.setattr(cloud, "close", lambda: closed.append("cloud"))
    monkeypatch.setattr(archive, "close", close_archive)
    monkeypatch.setattr(desktop.window, "destroy", destroy_window)
    try:
        desktop.close()
        assert closed == ["cloud", "archive", "window"]
        assert "RuntimeError" in caplog.text and "token-test-secret" not in caplog.text
    finally:
        if "window" not in closed:
            destroy()


@pytest.mark.skipif(os.environ.get("EMOBOT_GUI_TESTS") != "1", reason="Opt-in native Tk test; CI uses Xvfb")
def test_text_appears_before_speech_finishes_and_config_path_is_honored(
    settings, archive, tmp_path, monkeypatch
):
    from dataclasses import replace

    from emobot.gui import Desktop
    from emobot.settings import Settings

    class Robot:
        connected = False
        events = queue.Queue()

        def close(self):
            pass

    released = threading.Event()

    class Speech:
        def __init__(self, _cloud):
            pass

        def speak(self, _text):
            released.wait(3)

    monkeypatch.setattr("emobot.gui.Speech", Speech)
    target = tmp_path / "custom-settings.json"
    desktop = Desktop(
        Companion(replace(settings, voice_enabled=True), archive, DemoCloud()), Robot(), False, target
    )
    desktop.window.withdraw()
    try:
        desktop.question.insert("1.0", "hello")
        desktop.send()
        deadline = time.monotonic() + 2
        while "Emobot:" not in desktop.transcript.get("1.0", "end") and time.monotonic() < deadline:
            desktop.window.update()
            time.sleep(0.01)
        assert "Emobot:" in desktop.transcript.get("1.0", "end")
        assert desktop.busy  # voice is still waiting
        released.set()
        while desktop.busy and time.monotonic() < deadline:
            desktop.window.update()
            time.sleep(0.01)
        assert not desktop.busy
        desktop.config_vars["user"].set("next-launch-user")
        desktop.save_settings()
        assert Settings.load(target).user == "next-launch-user"
        assert desktop.companion.settings.user == settings.user
        assert "Restart" in desktop.status.get()
    finally:
        released.set()
        deadline = time.monotonic() + 3
        while desktop.busy and time.monotonic() < deadline:
            desktop.window.update()
            time.sleep(0.01)
        desktop.close()
