# Retained animation artwork

`firmware/EmobotS3/Clips.h` is generated bitmap data from `firmware/Arduino_Esp32s3/esp32s3_v2.0.1/animation.h` in [Smh-GOAT/Emobot at 2c3e4a7](https://github.com/Smh-GOAT/Emobot/blob/2c3e4a76bb0c7b64ca0253fd1ede169cdc339de0/firmware/Arduino_Esp32s3/esp32s3_v2.0.1/animation.h). That repository retains the GPLv3 license and credits Desk-Emoji upstream. All 42 sets, 28 frames each, are preserved. `animation-atlas.jpg` shows their first frames.

The original C++ array declaration and playback implementation are not copied. `tools/convert_animation.py` encodes the byte data as count/value pairs; the new renderer decompresses exactly one 512-byte frame into a fixed stack buffer. The manifest records input and output hashes. Art/bitmap similarity is intentionally excluded from the implementation similarity report and is **not** claimed to be low.
