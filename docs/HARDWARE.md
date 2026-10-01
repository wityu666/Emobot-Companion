# ESP32-S3 hardware and build

Target: ESP32-S3-DevKitC-1, **8 MB flash**. The pinned PlatformIO environment uses Arduino ESP32 core 2.0.17 and an 8 MB custom partition table (3 MB application, FFat remainder). No OTA updater is implemented. This repository supplies firmware and wiring, not a fabricated enclosure/CAD model.

| Module signal | GPIO |
|---|---:|
| OLED/PAJ7620 SDA, SCL | 8, 9 |
| OLED I²C address | 0x3c |
| Yaw / pitch servo | 12 / 13 |
| INMP441 WS / SCK / SD | 46 / 21 / 14 |
| MAX98357 LRC / BCLK / DIN | 18 / 17 / 19 |
| MAX98357 SD / GAIN | 3 / 20 |
| WS2812 status pixel | 48 |
| USB-UART TX / RX | 43 / 44 |

GPIO19/20 also carry native USB; do not enable native USB CDC with this audio wiring. Use USB-UART. GPIO3 and GPIO46 are strapping pins: keep external modules from forcing an incorrect reset strap. Verify the actual board pin labels and power supplies. Servo power must support both motors' peak current; share ground and do not draw servo current from a weak 3.3V output. Calibrate mechanical travel with the enclosure open.

The pin map is derived from the reference implementation. Electrical behavior, mechanical travel and recording quality still require testing on your actual device. See [Espressif's GPIO guide](https://docs.espressif.com/projects/esp-idf/en/v4.4.5/esp32s3/api-reference/peripherals/gpio.html) and [DevKitC-1 guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide.html).

## Build and initialize storage

```bash
python -m pip install -e '.[dev,flash]'
pio run
pio run -t upload
pio run -t buildfs
pio run -t uploadfs
pio device monitor -b 115200
```

`uploadfs` initializes the FFat partition from `data/history.json` and overwrites device history. Use it for initial setup or intentional reset, not on every firmware update. USB, BLE and gesture control remain available when cloud voice cannot start. A missing/unformatted FFat disables standalone voice rather than silently formatting user storage.

The gesture library's AVR include spelling is adapted by a small header in `avr/pgmspace.h`. `tools/prepare_firmware.py` applies an explicit compatibility patch to the pinned WebSockets header so the bounded 150 KB message limit takes effect. The dependency license is retained. This avoids the old manual library-edit step. Memory needed for a large incoming TTS packet still depends on free heap; unsupported/oversized/truncated packets fail instead of being played unchecked.

## Standalone voice

Copy `secrets.example.h` to ignored `secrets.h`. Configure API key, Qwen chat/ASR URLs and models, ByteDance TTS app/token/cluster/voice, and **current trusted PEM root CAs for both services**. Obtain trusted roots from the relevant certificate authority or service documentation. No key or CA-bypass is embedded in the release. Services require internet access, accurate NTP time and the appropriate account entitlement.

If saved Wi-Fi is absent or connection fails after 20s, join AP **Desk-Emoji**, default setup password `emobot2026` (change `EMOBOT_AP_PASSWORD` for your device), and open `http://192.168.4.1`. Provisioning occurs on the local protected hotspot. Wi-Fi passwords are stored locally in NVS and are not printed to serial logs. USB/BLE controls do not wait for network setup. The IP is periodically broadcast over UDP port 4210.

Move your hand toward the gesture sensor to start one voice turn. A worker records 10s of 16 kHz mono WAV using fixed buffers, streams base64 into a file rather than allocating the whole recording in RAM, transcribes, requests a JSON reply and streams PCM speech to I²S. Yellow/blue/green indicate recording/thinking/speaking. The last 10 turns remain in FFat. Temporary recording/request files are removed at completion. Persistent chat history is plain local text; see the privacy guide before sharing devices.

Other gestures retain left/right/up/down control, blink, happy eyes, a random animation and head shake. Action names and BLE UUIDs retain protocol compatibility. See `docs/FEATURE-MAP.md`.

## Bring-up checklist

Verify boot/serial acknowledgment, I²C addresses, one eye expression, small servo movements, each gesture, BLE reconnection, Wi-Fi provisioning, calibrated ranges, microphone waveform, ASR language, JSON reply, TTS end-of-stream and offline control after Wi-Fi loss. Record observed results in a separate hardware test log. Cross-compilation alone does not establish these physical outcomes.
