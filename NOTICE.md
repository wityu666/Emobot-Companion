# Project lineage and credits

This portfolio edition originates from **Emobot**, which the repository owner and **Smh-GOAT** describe as a jointly developed project. The previous maintained implementation is published at [Smh-GOAT/Emobot](https://github.com/Smh-GOAT/Emobot). The reference snapshot for this edition is commit `2c3e4a76bb0c7b64ca0253fd1ede169cdc339de0`.

That repository identifies itself as a fork of [ideamark/desk-emoji](https://github.com/ideamark/desk-emoji). Existing copyright and license obligations are preserved. This edition is released under **GPL-3.0-only**, with the complete license in `LICENSE`.

The desktop application and firmware control/service implementation were newly written for this edition, with AI assistance, using the existing behavior, device wiring and protocol as compatibility requirements. The 42 bitmap animation sets are retained upstream material, transformed losslessly into RLE flash data. Shared protocol action names, BLE UUIDs and hardware pin assignments are compatibility data, not claims of original invention. See `assets/NOTICE.md` and `assets/animation-manifest.json`.

No individual work allocation is asserted here: the original contributors' detailed responsibilities have not been independently established. For an interview, describe the parts you personally designed, implemented and tested, and identify the parts completed jointly or with assistance.

Third-party dependencies retain their own licenses: SQLAlchemy (MIT), httpx (BSD), pyserial (BSD), Bleak (MIT), ArduinoJson (MIT), Adafruit libraries (BSD/MIT/LGPL), ESP32Servo (LGPL), Arduino WebSockets (LGPL), RevEng PAJ7620 (MIT), and the Espressif/Arduino toolchain. Their source and license files are supplied by their respective package distributions; this repository does not relabel them as original code.
