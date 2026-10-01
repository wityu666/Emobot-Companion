import json
import re
from pathlib import Path

import pytest

from emobot.protocol import ACTIONS, Action, LineDecoder, frame, parse_actions, validate_factory

ROOT = Path(__file__).resolve().parents[1]


def test_all_59_actions_and_firmware_names_match():
    assert len(ACTIONS) == len(set(ACTIONS)) == 59
    hardware = (ROOT / "firmware/EmobotS3/RobotHardware.h").read_text()
    for action in ACTIONS:
        assert f'"{action}"' in hardware
        assert json.loads(frame((Action(action),)))["actions"][0]["action"] == action


@pytest.mark.parametrize("duration", [-1, 0, 49, 5001, True, "600", 600.0])
def test_invalid_durations_rejected(duration):
    with pytest.raises(ValueError):
        Action("eye_happy", duration)


def test_sequence_limits():
    with pytest.raises(ValueError):
        parse_actions([{"action": "delay", "duration": 5000}] * 5)
    with pytest.raises(ValueError):
        parse_actions([{"action": "delay", "duration": 50}] * 13)


@pytest.mark.parametrize(
    "command",
    [
        "adjust_x 46",
        "head_left5",
        "head_move 181 0 100",
        "head_move 0 0 10",
        "reboot; rm -rf /",
        "reset_wifi trailing",
    ],
)
def test_invalid_factory_rejected(command):
    with pytest.raises(ValueError):
        validate_factory(command)


def test_fragmentation_and_oversize_resynchronization():
    payload = frame((Action("head_nod"),))
    for fragment_size in range(1, 30):
        decoder, messages = LineDecoder(), []
        for start in range(0, len(payload), fragment_size):
            messages += decoder.feed(payload[start : start + fragment_size])
        assert messages == [json.loads(payload)]
    decoder = LineDecoder(20)
    assert decoder.feed(b"x" * 21 + b'\n{"ok":true}\n') == [{"ok": True}]
    assert decoder.feed(b'\xff\nnull\n[]\n{"ok":false}\n') == [{"ok": False}]


def test_every_rle_frame_is_lossless_and_bounded():
    header = (ROOT / "firmware/EmobotS3/Clips.h").read_text()
    offsets = list(map(int, re.search(r"clipOffsets\[\].*?\{(.*?)\}", header, re.S)[1].split(",")))
    pixels = list(
        map(int, re.search(r"clipPixels\[\].*?\{(.*?)\}", header, re.S)[1].strip().strip(",").split(","))
    )
    assert len(offsets) == 42 * 28 + 1
    assert offsets[-1] == len(pixels)
    for start, stop in zip(offsets, offsets[1:]):
        assert (stop - start) % 2 == 0
        expanded = []
        for index in range(start, stop, 2):
            assert 1 <= pixels[index] <= 255 and 0 <= pixels[index + 1] <= 255
            expanded.extend([pixels[index + 1]] * pixels[index])
        assert len(expanded) == 512
