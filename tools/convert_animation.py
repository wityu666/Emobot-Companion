"""Convert the GPL upstream bitmap arrays to lossless run-length flash data."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def convert(source: Path, destination: Path) -> dict:
    original = source.read_bytes()
    arrays = re.findall(r"const byte PROGMEM frames(\d+)\[\]\[512\] = \{(.*?)\n\};", original.decode(), re.S)
    if len(arrays) != 42:
        raise ValueError("Expected all 42 upstream animations")
    packed, offsets = bytearray(), []
    for number, body in arrays:
        frames = re.findall(r"\{([^{}]+)\}", body)
        if len(frames) != 28:
            raise ValueError(f"Animation {number} does not have 28 frames")
        for frame in frames:
            pixels = bytes(int(n.strip()) for n in frame.split(",") if n.strip())
            if len(pixels) != 512:
                raise ValueError("Frame size mismatch")
            offsets.append(len(packed))
            start = 0
            while start < len(pixels):
                stop = start + 1
                while stop < len(pixels) and pixels[stop] == pixels[start] and stop - start < 255:
                    stop += 1
                packed.extend((stop - start, pixels[start]))
                start = stop
    offsets.append(len(packed))
    header = "// GPL-3.0-only. Generated from Smh-GOAT/Emobot; see assets/NOTICE.md.\n#pragma once\n#include <Arduino.h>\n"
    header += "constexpr uint32_t clipOffsets[] PROGMEM = {" + ",".join(map(str, offsets)) + "};\n"
    header += "constexpr uint8_t clipPixels[] PROGMEM = {\n"
    header += (
        "\n".join(",".join(map(str, packed[i : i + 40])) + "," for i in range(0, len(packed), 40)) + "\n};\n"
    )
    destination.write_text(header)
    return {
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "animations": 42,
        "frames_each": 28,
        "raw_bytes": 42 * 28 * 512,
        "rle_bytes": len(packed),
        "header_sha256": hashlib.sha256(header.encode()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.destination), indent=2))
