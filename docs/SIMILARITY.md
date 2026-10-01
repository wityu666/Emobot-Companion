# Source overlap measurement

Reference snapshot: `Smh-GOAT/Emobot@2c3e4a76bb0c7b64ca0253fd1ede169cdc339de0`. Reproduce with:

```bash
python tools/source_similarity.py /path/to/original/Emobot . --output docs/source-similarity.json
```

This compares application/firmware logic: 65 reference files and 15 rewritten files. It excludes retained bitmap artwork (`animation.h`, `emoji.h`, generated `Clips.h`), third-party dependency directories, license/docs, tests/evaluators and the secret example/compatibility include. It does not hide copied artwork: its source and hashes are separately recorded in assets/NOTICE.md.

Method 1 tokenizes Python and C++/Arduino, removes comments/formatting, normalizes string/number literals, and compares unique 5-token sequences. Method 2 additionally normalizes non-keyword identifiers and compares unique 8-token sequences, reducing the effect of merely renaming variables. It measures lexical overlap, not behavior or authorship.

| Metric | Literal-normalized 5-gram | Identifier-normalized 8-gram |
|---|---:|---:|
| Corpus Jaccard overlap (intersection / union) | 2.71% | 11.23% |
| Rewritten unique sequences also found anywhere in reference | 6.73% | 22.07% |
| Strongest individual file-pair Jaccard | 5.52% | 14.62% |

Exact machine results and closest file pairs are in source-similarity.json. The percentages depend on the declared scope and algorithm; they are **not** a universal “code similarity percentage,” an external plagiarism-check score, or proof of independent authorship. Shared protocol identifiers and third-party APIs naturally create overlap. The new service boundaries, storage lifecycle, GUI ownership, provider implementation and embedded execution flow are substantive implementation changes.

GPLv3 and credit obligations remain, regardless of these measurements. The retained animations are intentionally identical in pixel content and are not claimed to be original or dissimilar.
