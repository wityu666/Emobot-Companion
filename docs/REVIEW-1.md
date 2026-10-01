# Review 1 — functional contracts and compatibility

Baseline: `f6c64ef`. Reviewed by the implementation assistant (self-review; no claim of independent human review). Tests run locally on Python 3.12, 2026-10-01.

| Finding | Correction | Evidence |
|---|---|---|
| Forgetting a memory removed its source question but left the same information in the assistant answer | Persist a turn ID and delete both sides of that turn | A failing regression became green |
| USB replies could remain unread until the next command | Give the serial link a dedicated bounded reader with an explicit stop/join lifecycle | Continuous reader implementation; fake-port lifecycle regression added in round 2 |
| BLE notifications could arrive before the stream decoder reset | Reset before connecting/subscribing | Connection ownership review |
| A malformed category from model memory extraction could reach a SQL string column | Validate category type before persistence | Invalid model candidate coverage |
| Factory `head_move` ignored its duration | Interpolate within the duration and clamp calibrated mechanical limits | Firmware inspection; cross-compilation in round 3 |

Validation before corrections: **50 passed, 1 failed**. Validation after corrections: **51 passed**. All 59 action names and fragmented newline frames are covered. Every one of 1176 compressed frames expands to exactly 512 bytes. SQLite import replacement, embedding invalidation, bilingual retrieval, history, fallback, user isolation and privacy switches are covered.

This round does not establish hardware performance, microphone quality, live provider behavior or PostgreSQL server compatibility. Those limitations remain explicit in the release evidence.
