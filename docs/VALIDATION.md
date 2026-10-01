# Validation — 2026-10-01

## Current target: version 1.2.0 / Python 3.13.x only

Three additional optimization rounds are documented in [round 1](OPTIMIZATION-1.md), [round 2](OPTIMIZATION-2.md) and [round 3](OPTIMIZATION-3.md), with one commit per round. Local Python 3.13.5/macOS checks: **104 non-GUI tests passed, one PostgreSQL service test skipped**, and **three native Tk cases passed separately** (107 passes across these runs). Ruff lint/format and whitespace checks passed. The wheel's Python metadata excludes the 3.11/3.12 series; its packaged source/resources match, and an installed-wheel demo passed.

Application and FFat firmware builds succeed locally: static RAM **67,996/327,680 bytes**, application flash **2,147,945/3,145,728 bytes**, FFat **5,173,248 bytes**. The archive benchmark against the preceding release reports identical top results with fewer database calls and lower local keyword-search cost; workload and limits are in OPTIMIZATION-1.md.

All three CI jobs run Python 3.13, including native Tk under Xvfb, the expanded real PostgreSQL/pgvector integration and firmware. CI also smoke-tests the installed wheel. The exact published commit's result is available in [GitHub Actions](https://github.com/wityu666/Emobot-Companion/actions) and the delivery manifest, separate from local results. Hardware and live provider checks still require your equipment/accounts.

## Historical Python 3.13 adaptation: version 1.1.0

Review 4 targets only Python 3.13. Local Python 3.13.5/macOS checks: **78 non-GUI tests passed, one PostgreSQL service test skipped**, and **three native Tk cases each passed in a separate process**. Local combined coverage is 81 passes across these runs. A software speech resampling/WAV conversion check passed with SpeechRecognition 3.17 and its Python 3.13 compatibility dependencies.

Ruff and packaging checks and PlatformIO application/FFat builds run under 3.13. Local firmware static RAM is **67,996/327,680 bytes**; application flash is **2,147,945/3,145,728 bytes**. Physical hardware and live provider checks remain pending. Current changes, reproduced failures and the macOS multi-root test limitation are recorded in [review 4](REVIEW-4.md).

CI now has three jobs, all using 3.13: full desktop tests under Xvfb (with voice/flash extras and NumPy), a real PostgreSQL/pgvector service, and application/FFat firmware builds. The first published snapshot passed [its initial CI run](https://github.com/wityu666/Emobot-Companion/actions/runs/36850275277); each later revision must pass its own run before being claimed as verified.

## Historical evidence: initial three reviews

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

The initial three sequential self-review/fix rounds have separate documents and Git commits. Review 4 and the current 3.13 evidence are also recorded. The same implementation assistant performed them; there is no claim of independent human review. Machine evidence and versions are in `validation.json`.

## Remaining target-environment checks

No physical board, calibrated mechanism, microphones/speakers or provider credentials were supplied. Real ASR/chat/TTS/embeddings, BLE radio, Wi-Fi provisioning, I²S quality and mechanical output therefore remain unverified. PostgreSQL server integration passed for the preceding releases and is expanded for the current version; remote checks are recorded separately from local passes. Complete the bring-up checklist in HARDWARE.md using your device/account before presenting a physical end-to-end success claim.

The test suite uses scripted/demo providers and HTTP contract mocks; it does not measure real model empathy or answer quality. Local source-overlap figures in SIMILARITY.md describe their specific lexical method, excluding declared shared material, rather than a universal plagiarism score.
