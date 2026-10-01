# Optimization 3 — predictable configuration and Python 3.13 delivery

Date: 2026-10-01. Same implementation assistant; version **1.2.0**, Python **3.13.x only**.

Boolean environment overrides now accept explicit true/false forms, trim whitespace and reject typos with the variable name. Settings read/write uses UTF-8 regardless of the system locale; atomic replacement and private permissions remain. A separate Python process with UTF-8 mode disabled and the C locale successfully round-trips Chinese persona text.

Cloud adapters reject empty speech and JSON error bodies before audio playback, normalize malformed/empty Volcano TTS responses as `ProviderError`, and validate embedding dimensions/finite values at the provider boundary. Extremely large embedding numbers are also converted into a controlled provider error. Provider response payloads are omitted from these errors. Existing model fallback and keyword retrieval remain available.

Twelve of thirteen new configuration/provider regression cases failed before these changes; all pass now. Final local Python 3.13.5 evidence:

- **104 non-GUI tests passed, one local PostgreSQL service test skipped**.
- **Three native Tk cases passed individually**, including settings persistence and text delivery during speech.
- Ruff lint/format and diff whitespace checks pass.
- ESP32-S3 application and FFat builds pass: static RAM 67,996/327,680 B, application flash 2,147,945/3,145,728 B; FFat 5,173,248 B.
- Wheel and source distribution build successfully. All 12 Python/prompt source files in the wheel match the working source. An installed-wheel CLI demo runs with the packaged prompt, and its import path confirms the installed copy is used. Package metadata accepts the 3.13 series and excludes 3.11, 3.12 and 3.14.

CI uses Python 3.13 for all jobs and now adds an installed-wheel smoke check. The real PostgreSQL/pgvector integration also exercises batch document replacement, streaming keyword/hybrid retrieval and conversation/action batches. The published revision's workflow result is recorded in the delivery manifest and GitHub Actions after upload.

The current source-overlap report is regenerated with the same declared lexical methods and exclusions. Attribution, jointly originated work, retained artwork and AI assistance remain disclosed. Physical hardware and live provider quality/access still require the target devices and accounts.
