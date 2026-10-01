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
            time.sleep(.02)
        assert results and results[0] != main_thread
        desktop.question.insert("1.0", "我喜欢猫")
        desktop.send()
        deadline = time.monotonic() + 3
        while desktop.busy and time.monotonic() < deadline:
            desktop.window.update()
            time.sleep(.02)
        assert "演示模式" in desktop.transcript.get("1.0", "end")
        assert not desktop.busy
        desktop.config_vars["theme"].set("dark")
        desktop.save_settings()
        assert desktop.companion.settings.theme == "dark"
    finally:
        desktop.close()
    assert robot.closed
