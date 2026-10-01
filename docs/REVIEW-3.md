# Review 3 — integration, packaging and release quality

Third sequential self-review by the implementation assistant, after review 2. No independent human review is claimed.

| Finding | Final change and check |
|---|---|
| Native USB CDC would conflict with the retained speaker GPIO19/20 wiring | Default Serial uses USB-UART; remove native CDC build flag and document UART interface |
| Pinned WebSockets library overwrote the build flag for maximum message size | Reproducible build-time compatibility patch; fixed 150 KB bounded cap; retain dependency license |
| Firmware read raw HTTP stream bytes and did not account for chunked transfer encoding | Use HTTPClient decoded writeToStream with a 16 KB/20s bounded sink |
| Standalone TTS request ID was not a standard UUID and final DMA bytes could be cut off | Generate version-4 formatted ID and allow a short drain before clearing DMA |
| PostgreSQL pgvector can return a NumPy array whose truth value is ambiguous | Check vector presence explicitly and verify array cosine behavior; add optional real PostgreSQL CI test |
| Generic memory recall without repeating a preference could retrieve nothing | Recognize explicit recall intent and provide bounded recent memories |
| Desktop waited for speech playback before showing the model answer | Separate queued progress from completion, display text while voice work continues |
| System theme was implemented as a fixed light palette | Preserve native Tk theme and colors for system mode |
| GUI could not persist restart-only settings, and --config was not honored on save | Save database/user/dimension changes for next launch; carry custom configuration path |
| Demo mode failed when an existing embedding model was configured | Explicit demo embedding failure falls back to local keyword retrieval |
| ByteDance REST authentication differs from OpenAI | Provider-specific Bearer; token header with payload regression test |
| Desktop extras omitted the flashing dependency | Add flash extra and literal subprocess argument regression |
| Python build environment lacked setuptools | Install available official cached build backend, then verify wheel/sdist and installed resources |

Final regression, build, packaging and explicit limitations are recorded in VALIDATION.md. CI includes Python 3.11/3.12, Xvfb desktop tests, a PostgreSQL+pgvector service and ESP32-S3/application/FFat builds. GitHub Actions are pinned to verified commit SHAs. CI has not run until the repository is published; local results must not be relabeled as a remote CI pass.

C++ logic is clang-formatted; generated bitmap data remains excluded. Ruff checks and package metadata/resource readback are part of release verification. The feature map, lineage, source-overlap method and interview notes were checked against the actual implementation.

Two additional lifecycle regressions were deliberately added during this round and failed before correction: (1) SQLite JSON null was not SQL NULL, so an edited memory could not be selected for reindexing; use JSON(none_as_null=True). (2) a transport-specific exception could suppress an otherwise successful chat reply; contain exceptions at the robot adapter boundary and record failed delivery. Both regressions are retained in the final suite.
