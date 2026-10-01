# Existing feature → new implementation

Reference: Smh-GOAT/Emobot commit `2c3e4a7`. The scope is its current maintained PC client and ESP32-S3 firmware, not removed historical versions or functions only described by stale screenshots.

| Existing behavior | New implementation | Verification |
|---|---|---|
| Desktop text chat | `gui.Desktop`, `Companion.ask`, `Cloud.complete` | CLI and native Tk event-delivery tests |
| Chinese / English replies | Settings language, packaged contract, demo | Bilingual tests; live model quality needs provider |
| Persona / soul editor | Persona editor and runtime Settings | Tk save/apply test |
| Light / dark / system themes | Explicit themes and native system theme | Tk construction/theme test |
| Fast and retrieval/backup models | Single service routes; automatic fast failure fallback added | Scripted provider tests |
| PostgreSQL messages/memories | SQLAlchemy archive; same functional records, fresh schema | SQLite tests, optional PostgreSQL service test |
| Memory extraction/filter and manual CRUD | Grounded candidate filter, scoped CRUD, hard forgetting | Positive/negative and deletion regressions |
| Markdown docs import / replacement | Transactional SHA-based importer, heading chunks | Idempotence and replacement tests |
| Embeddings and hybrid retrieval | Configurable vector type, indexer and exact cosine/keyword ranker | Dimension/finite/invalidation tests; no live embedding call |
| Action / skill logs | Archive records real service outcomes | Application integration tests |
| USB serial JSON | Continuous reader, bounded newline codec | Fake serial lifecycle/ack test |
| BLE control using established UUID | Async BLE owner and bounded write fragments; firmware BLE service added | Fake BLE fragmentation/reconnect lifecycle; device radio needs hardware |
| 7 eye + 9 head + 42 animations + delay | Allowlisted action specs and new hardware player | Name agreement; RLE frame size/hash tests; firmware build |
| Factory enable/disable, center offsets, head_move, reset Wi-Fi, reboot | Validated factory grammar and NVS calibration | Invalid/bounds tests; hardware outcome requires device |
| Factory UI device address / directions | Implemented mac_address; directions use valid head_move grammar | Contract verification; repairs old GUI mismatch |
| PC microphone ASR | Optional SpeechRecognition + multipart compatible transcription | HTTP payload test; real microphone requires equipment |
| PC speaker, six voices | Temporary MP3 playback, compatible TTS | HTTP media test; real speaker requires equipment |
| Volcano input fields | Actual ByteDance TTS adapter, editable credentials/voice | Contract tests; corrects previously unwired callback |
| Firmware flashing | Explicit chip and merged/application offsets via esptool | Image argument validation; no physical flashing performed |
| OLED 128×64; 42×28 frames | New procedural eyes and lossless RLE decoder | 1176 frames; build; physical display needs hardware |
| Servos yaw12/pitch13; calibrated ranges | New time-driven player and interpolated factory move | Build and bounds inspection |
| PAJ7620 gestures | Same gesture mapping; random clip includes all 42 | Build and mapping inspection |
| Standalone 16 kHz ASR/chat/TTS | Fixed-buffer WAV and streamed base64 file; bounded HTTPS; validated PCM WebSocket | Firmware compile; 50k parser fuzz cases with sanitizers; cloud+audio needs bring-up |
| Wi-Fi saved credentials / provisioning AP | NVS credentials, nonblocking connection, protected local setup page | Build; network tests need device |
| UDP4210 discovery | Periodic local-IP announcement | Build; packet observation needs device |
| Local 10-round device history | FFat history; bounded load; request scratch cleanup | Build and inspection; flash behavior needs device |
| WS2812 status | Voice phase status colors | Build; visual output needs hardware |

Compatibility intentionally retains all 59 protocol action identifiers, established BLE service/characteristic UUIDs and the reference pin map. New guardrails impose a 12-action, 20-second sequence budget. Old invalid factory GUI command strings are replaced by the documented grammar. Desktop code is packaged rather than depending on a working directory or hard-coded Python 3.11 executable.

Current robot firmware has no implemented OTA updater, CAD enclosure generator or camera pipeline; this edition does not advertise those as existing features. Real provider access, PostgreSQL server and hardware measurements must be verified in the target environment before claiming a full physical demo.
