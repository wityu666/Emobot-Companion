# Validation — 2026-10-01

Reference snapshot: `Smh-GOAT/Emobot@2c3e4a76bb0c7b64ca0253fd1ede169cdc339de0`.

- **72 tests passed, 1 skipped** on Python 3.12.14/macOS ARM64, including two native Tk tests. The skip is an actual PostgreSQL/pgvector server integration test; an isolated service job is configured in CI.
- All 59 action names match firmware; fragmented USB/BLE framing, continuous USB replies, simulated delivery and failed robot delivery are tested.
- All 1176 RLE frames were independently compared byte-for-byte against the reference artwork. Every decoded frame is 512 bytes; raw/source/header hashes are recorded.
- 50,000 malformed binary TTS frames were tested under AddressSanitizer and UndefinedBehaviorSanitizer; both completed without findings.
- Native Tk checks exercise seven pages, worker-to-main delivery, text appearing before speech completion, dark theme and custom configuration/restart settings. They are functional widget/event tests; they do not constitute a full visual/usability study.
- Ruff lint/format and clang-format checks passed. Source diff whitespace checks passed.
- ESP32-S3 firmware successfully cross-compiled. Static RAM: **67,996/327,680 bytes (20.8%)**; application flash: **2,147,901/3,145,728 bytes (68.3%)**. These are build-time totals, not runtime peak heap measurements.
- FFat image built successfully: **5,173,248 bytes**.
- Python wheel and source distribution built successfully; packaged prompt resources and a demo run from the installed wheel were verified.

Three sequential self-review/fix rounds have separate documents and Git commits. The same implementation assistant performed them; there is no claim of independent human review. Machine evidence and versions are in `validation.json`.

## Remaining target-environment checks

No physical board, calibrated mechanism, microphones/speakers or provider credentials were supplied. Real ASR/chat/TTS/embeddings, BLE radio, Wi-Fi provisioning, I²S quality and mechanical output therefore remain unverified. PostgreSQL server integration and remote GitHub Actions have not been relabeled as local passes. Complete the bring-up checklist in HARDWARE.md using your device/account before presenting a physical end-to-end success claim.

The test suite uses scripted/demo providers and HTTP contract mocks; it does not measure real model empathy or answer quality. Local source-overlap figures in SIMILARITY.md describe their specific lexical method, excluding declared shared material, rather than a universal plagiarism score.
