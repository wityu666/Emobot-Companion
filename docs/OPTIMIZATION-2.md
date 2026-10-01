# Optimization 2 — transport lifecycle and desktop scheduling

Date: 2026-10-01. Same implementation assistant; additional optimization after round 1.

The Bluetooth loop/thread is started only by Bluetooth work. USB-only use and an unused link allocate no Bluetooth worker. Closing is idempotent; a closed link rejects reconnection. The worker cancels remaining async tasks and closes its own loop at shutdown. USB read failures release the port and report a disconnected event. A connection generation excludes notifications arriving from a replaced BLE client; pending old events and partial frame state are reset at connection setup.

The desktop drains at most 32 worker results and 32 robot notifications per 50 ms poll, applying only the last robot status in that batch. A continuously replenished notification queue can no longer hold the Tk thread indefinitely. Exceptions in a result callback are reported by exception type and polling continues, allowing subsequent operations to finish.

Five new regression/efficiency checks failed before these changes. All now pass; two additional checks cover cancellation/loop release and stale BLE callbacks after switching to USB. Existing BLE timeout cancellation, fragmented acknowledgments and USB delivery checks also pass. Python 3.13.5: **91 non-GUI tests passed, one PostgreSQL test skipped locally**. All **three native Tk cases passed in separate macOS processes**, covering worker delivery, cleanup after a disconnect failure and chat text appearing before speech completes. The separate-process choice follows the previously documented local Tk multi-root limitation.

No physical USB/BLE hardware was supplied. Device unplugging and late BLE callbacks were reproduced with transport substitutes; this validates application lifecycle logic without claiming radio or hardware reliability.
