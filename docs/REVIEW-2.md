# Review 2 — privacy, failure paths and ownership

Reviewed by the same implementation assistant, after review 1. This is a documented second self-review, not a separate reviewer endorsement.

Before fixes: **53 passed, 6 failed**. The failures covered an invented memory, restatements surviving forgetting, and four invalid configuration types.

| Finding | Correction |
|---|---|
| Model confidence alone allowed a fabricated preference | Normalize preference wording and require all remaining factual terms to occur in the user's statement; reject sensitive/transient candidates |
| Deleting one source turn was insufficient because later answers could repeat it | Deleting a selected memory also clears this user's complete saved chat/action/skill history and in-process conversation context; other memories and imported docs remain |
| JSON strings/numbers could masquerade as booleans; true could masquerade as a dimension | Validate exact configuration types, size limits and credential newlines |
| A fixed temporary settings filename was vulnerable to pre-existing files/symlinks | Use a private, randomly named file, flush/fsync, atomically replace and always clean up |
| Connection jobs read Tk variables from a worker | Capture the selected port/address on the GUI thread before submission |
| Saving configuration during a model call could block the GUI on a service lock | Require the current operation to finish before applying runtime configuration |
| Query embedding values could be invalid | Check dimension/finite values; retain keyword document retrieval after embedding failures |
| Native gesture dependency used an AVR include name on ESP32 | Add a minimal ESP32 compatibility include; pin the upstream tag; clean cross-build succeeds |
| Device preferences could change before the voice worker marked itself busy | Mark the voice phase before creating the worker; clear state if task creation fails |
| Binary TTS frames needed serialization, sequence and length checks | Reject non-PCM serialization, inconsistent sequence flags, odd PCM size and truncated payloads |

Regression coverage additionally exercises USB unsolicited replies, reader shutdown, BLE 20-byte fragmentation, notification reassembly and 50,000 deterministic malformed TTS packets under AddressSanitizer and UndefinedBehaviorSanitizer.

No secret values from the original repository, old screenshots, private settings or local recordings are copied into this release. Device HTTPS and WebSocket calls require configured trusted root CAs; they never disable certificate validation. Recordings and cloud request scratch files are deleted after each standalone voice turn. Firmware history remains local in FFat; desktop Forget does not erase a separate device's history.

Post-fix headless result: **62 passed**; both parser sanitizers completed without findings. The optional desktop test requires an actual desktop/Tk session and is assessed in round 3. Firmware cross-compilation after the fixes is recorded separately.
