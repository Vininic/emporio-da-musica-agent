# 006 Snapshot clock

Status: assumption, documented.

The data stops in March 2026. With the real clock, shipped order 8 (estimated delivery 2026-02-28) looks eight months late and every return window is closed.

The data is a snapshot, so "today" is injected and defaults to 2026-03-25, right after the latest order. `STORE_TODAY` overrides it. Tests pin the clock. Business hours follow the same injected clock.
