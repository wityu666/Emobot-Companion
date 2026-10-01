"""Robot commands are a small, bounded language, never arbitrary model-generated code."""
from __future__ import annotations

import json
from dataclasses import dataclass

ANIMATIONS = tuple("heart calendar face_id cola laugh dumbbell skateboard battery basketball rugby alarm screen wifi youtube tv movie cat write phone sunny cloudy rainy windy snow beer walk shit cry puzzled football volleyball badminton rice gym boat thinking money wait plane rocket ok love".split())
EYES = tuple("eye_blink eye_happy eye_sad eye_anger eye_surprise eye_left eye_right".split())
HEADS = tuple("head_left head_right head_up head_down head_nod head_shake head_roll_left head_roll_right head_center".split())
ACTIONS = EYES + HEADS + ANIMATIONS + ("delay",)
MAX_WIRE_BYTES = 8192


@dataclass(frozen=True)
class Action:
    name: str
    duration: int = 600

    def __post_init__(self) -> None:
        if self.name not in ACTIONS or type(self.duration) is not int or not 50 <= self.duration <= 5000:
            raise ValueError("Unknown action or duration outside 50–5000 ms")

    def as_dict(self) -> dict:
        return {"action": self.name, "duration": self.duration}


def parse_actions(value: object) -> tuple[Action, ...]:
    if not isinstance(value, list) or len(value) > 12:
        raise ValueError("actions must be an array of at most 12 items")
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Every action must be an object")
        result.append(Action(item.get("action", ""), item.get("duration", 600)))
    if sum(a.duration for a in result) > 20000:
        raise ValueError("Action sequence exceeds 20 seconds")
    return tuple(result)


def frame(actions: tuple[Action, ...] = (), factory: str | None = None) -> bytes:
    payload = {"actions": [a.as_dict() for a in actions]} if factory is None else {"factory": factory}
    if factory is not None:
        validate_factory(factory)
    else:
        parse_actions(payload["actions"])
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_WIRE_BYTES:
        raise ValueError("Command exceeds device frame limit")
    return encoded


def validate_factory(command: str) -> None:
    words = command.split()
    if not words:
        raise ValueError("Empty factory command")
    if words[0] in {"reboot", "restart", "on", "off", "reset_wifi", "mac_address"} and len(words) == 1:
        return
    if words[0] in {"adjust_x", "adjust_y"} and len(words) == 2:
        amount = int(words[1])
        if -45 <= amount <= 45:
            return
    if words[0] == "head_move" and len(words) == 4:
        x, y, duration = map(int, words[1:])
        if 0 <= x <= 180 and 0 <= y <= 180 and 50 <= duration <= 5000:
            return
    raise ValueError("Invalid factory command")


class LineDecoder:
    """Fragment-safe stream decoder, resynchronizing after an oversized line."""
    def __init__(self, limit: int = MAX_WIRE_BYTES):
        self.buffer = bytearray()
        self.limit = limit
        self.discarding = False

    def feed(self, chunk: bytes) -> list[dict]:
        messages = []
        for byte in chunk:
            if byte == 10:
                if self.buffer and not self.discarding:
                    try:
                        value = json.loads(self.buffer)
                        if isinstance(value, dict):
                            messages.append(value)
                    except (ValueError, UnicodeDecodeError):
                        pass
                self.buffer.clear()
                self.discarding = False
            elif not self.discarding:
                self.buffer.append(byte)
                if len(self.buffer) > self.limit:
                    self.buffer.clear()
                    self.discarding = True
        return messages
