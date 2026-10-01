# Optimization 1 — archive work and bounded retrieval

Date: 2026-10-01. Baseline: `05087bb21d730b67d3f5972b27891461f3197480`. This is an additional optimization after the four recorded self-review rounds, performed by the same implementation assistant.

Conversation pairs, action logs and document chunks now use transactional batch inserts. Replacement still deletes and replaces one document in a single transaction, including rollback on a failed batch. Keyword search selects only IDs/content; hybrid search also selects vectors. A streaming candidate iterator and bounded top-result selection retain ranking and ties without collecting all matches. User filters and the memory-recall fallback remain in place. Index progress counts successful updates only and rejects stale results after a concurrent edit or another index write.

Python 3.13.5/macOS ARM64: **84 non-GUI tests passed, one local PostgreSQL service test skipped**. Six additional checks cover database call counts, ranking/ties, user isolation, omitted vector reads, concurrent editing and transactional replacement failures. Native desktop and real PostgreSQL coverage will be validated with the final revision.

Synthetic SQLite benchmark against the baseline:

| Workload | Before | After |
| --- | ---: | ---: |
| Import 899,990 characters / 1,000 chunks: INSERT calls | 1,001 | 2 |
| Import median of 3 runs | 47.3 ms | 12.0 ms |
| Keyword search: 2,000 rows, 768-dimensional vectors; median of 5 runs | 58.6 ms | 5.2 ms |
| Keyword search: traced peak Python allocation, separate run | 704,746 B | 35,831 B |

The six returned rows and scores match exactly. These are local synthetic results, not guarantees for a real deployment or PostgreSQL. Retrieval still scans scoped text; this change does not introduce an ANN index or database full-text search. Python allocation measurements exclude database and operating-system memory. Raw evidence is in [optimization-benchmark.json](optimization-benchmark.json).

Reproduce from the repository using its Python 3.13 environment:

```bash
git show 05087bb:src/emobot/archive.py > /tmp/emobot-baseline-archive.py
python tools/archive_benchmark.py --baseline /tmp/emobot-baseline-archive.py
```

The benchmark uses isolated temporary SQLite databases and synthetic text, without reading personal archives or sending provider requests.
