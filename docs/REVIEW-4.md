# Review 4 — boundary failures and Python 3.13

Baseline: `5674abc`. Fourth sequential self-review by the implementation assistant, requested after publication. No independent human review is claimed.

| Priority | Trigger and previous behavior | Change and verification |
|---|---|---|
| P1 | An English user says “I don't like cats”; a model candidate saying “User likes cats” passes token grounding and is stored as a false preference | Accepted automatic memories now store the user's original utterance. Negation and mixed preferences survive model paraphrasing. Inputs over 500 characters are not automatically summarized into memory. Three failing regressions now pass; manual editing remains available |
| P1 | off during a timed factory head_move leaves movingMs active, so a subsequent on can resume the old target; new action sequences can overlap the manual move | on/off and calibration clear pending movement; disabled/manual-move state rejects new action sequences; disabled state rejects head_move. Source state transitions inspected and firmware rebuilt. Physical cancellation still requires hardware verification |
| P2 | A gzip chat or audio response is decoded by HTTPX, then reconstructed with its original encoding headers and decoded again | Remove encoding/framing/old length headers from the reconstructed response. Both compressed chat and binary audio regressions failed before correction and now pass |
| P2 | BLE setup times out after connection while notification registration is pending; cancellation bypasses except Exception | Explicitly handle asyncio.CancelledError and disconnect the partially connected client. Timeout regression failed before correction and now confirms cleanup |
| P2 | The GUI drains a full notification queue before the reader evicts its oldest event | Retry bounded enqueue/eviction and tolerate concurrent emptying; a deterministic consumer-drain regression now preserves the new acknowledgment |
| P2 | A device disconnect exception during window closing prevents provider/database cleanup and window destruction | Attempt every cleanup independently, finish worker shutdown, destroy the window, and log exception types without raw messages. A native Python 3.13 Tk regression failed before correction and now passes |

Seven provider/memory/transport regressions first failed against the previous implementation. The separate native shutdown regression also failed before the GUI fix. These eight regressions are retained in the suite.

## Python 3.13 migration

Version 1.1.0 targets **Python 3.13.x**: requires-python is `>=3.13,<3.14`. All Python, PostgreSQL and firmware CI jobs use 3.13; the older CI version matrix is removed. README and installation instructions use an explicit 3.13 interpreter. The first three review documents retain their historical run details and do not declare current version support.

The voice extra requires SpeechRecognition 3.17 or later, whose dependencies include the audioop/aifc replacements needed on 3.13. A software WAV conversion check exercises resampling and sample-width conversion. CI installs the voice/flash extras and PortAudio development headers, and dev dependencies include NumPy so vector-array coverage is no longer skipped.

Local verification used Python 3.13.5/macOS ARM64: **78 non-GUI tests passed, one live PostgreSQL test skipped**, plus **three native Tk tests passed in isolated processes**. An initial macOS run creating multiple Tk roots in one process stalled in Tk event processing; its thread dump showed an idle worker. Each native case subsequently passed independently, matching the application's single-window process. Linux CI runs the full suite through Xvfb. This environment issue is recorded separately from the successfully reproduced shutdown defect.

Application and FFat builds ran through PlatformIO under Python 3.13. Build-time static RAM is 67,996/327,680 bytes; flash is 2,147,945/3,145,728 bytes on the local build. Firmware compilation and source inspection do not establish physical servo, BLE, microphone or cloud-provider outcomes.

The previous published snapshot passed all four initial CI jobs at [run 36850275277](https://github.com/wityu666/Emobot-Companion/actions/runs/36850275277). This round's new run must be checked against its own commit; the previous run is not evidence that later changes passed.

Reference behavior: [HTTPX automatic content decoding](https://www.python-httpx.org/quickstart/#binary-response-content), [SpeechRecognition dependency metadata](https://github.com/Uberi/speech_recognition/blob/master/pyproject.toml). API contracts are supplemented by the retained executable regressions.
