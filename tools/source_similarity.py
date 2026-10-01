"""Reproducible lexical overlap, excluding retained art and third-party dependencies.

This is a local diagnostic, not a plagiarism verdict or a MOSS/JPlag score.
"""

from __future__ import annotations

import argparse
import io
import json
import keyword
import re
import tokenize
from pathlib import Path

CPP_KEYWORDS = set(
    "alignas alignof auto bool break case catch char class const constexpr continue default delete do double else enum explicit extern false float for friend if inline int long namespace new nullptr operator private protected public return short signed sizeof static struct switch template this throw true try typedef typename union unsigned using virtual void volatile while".split()
)


def tokens(path: Path, structural: bool = False) -> list[str]:
    source = path.read_text(encoding="utf-8")
    values = []
    if path.suffix == ".py":
        for item in tokenize.generate_tokens(io.StringIO(source).readline):
            if item.type in {tokenize.STRING, tokenize.NUMBER}:
                values.append("LITERAL")
            elif item.type == tokenize.NAME:
                values.append(
                    "IDENTIFIER" if structural and not keyword.iskeyword(item.string) else item.string
                )
            elif item.type == tokenize.OP:
                values.append(item.string)
    else:
        pattern = r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]'
        for match in re.finditer(pattern, source):
            value = match.group()
            if value.startswith(("//", "/*")):
                continue
            if value[0] in {'"', "'"} or value[0].isdigit():
                value = "LITERAL"
            elif structural and value[0].isalpha() and value not in CPP_KEYWORDS:
                value = "IDENTIFIER"
            values.append(value)
    return values


def grams(values: list[str], width: int) -> set[tuple[str, ...]]:
    return {tuple(values[i : i + width]) for i in range(max(0, len(values) - width + 1))}


def sources(root: Path, original: bool) -> list[Path]:
    paths = []
    starts = (
        [root / "pc_client/pc_client_v3.0.0", root / "firmware/Arduino_Esp32s3/esp32s3_v2.0.1"]
        if original
        else [root / "src/emobot", root / "firmware/EmobotS3"]
    )
    for start in starts:
        for path in start.rglob("*"):
            if path.suffix not in {".py", ".cpp", ".h", ".ino"}:
                continue
            if path.name in {
                "Clips.h",
                "animation.h",
                "emoji.h",
                "secrets.h",
                "secrets.example.h",
                "pgmspace.h",
            }:
                continue
            if any(part in {"tests", "evals", "__pycache__"} for part in path.parts):
                continue
            paths.append(path)
    return sorted(paths)


def measure(old: Path, new: Path) -> dict:
    old_paths, new_paths = sources(old, True), sources(new, False)
    result = {
        "reference_commit": "2c3e4a76bb0c7b64ca0253fd1ede169cdc339de0",
        "old_logic_files": len(old_paths),
        "new_logic_files": len(new_paths),
        "excluded": [
            "bitmap artwork and generated Clips.h",
            "GPL license and documentation",
            "third-party libraries",
            "tests/evaluators",
            "secrets examples and include shim",
        ],
        "metrics": {},
    }
    for label, structural, width in [
        ("literal_normalized_5gram", False, 5),
        ("identifier_normalized_8gram", True, 8),
    ]:
        old_sets = {str(path.relative_to(old)): grams(tokens(path, structural), width) for path in old_paths}
        new_sets = {str(path.relative_to(new)): grams(tokens(path, structural), width) for path in new_paths}
        old_all = set().union(*old_sets.values())
        new_all = set().union(*new_sets.values())
        pairs = []
        for new_name, new_set in new_sets.items():
            if not new_set:
                continue
            old_name, old_set = max(
                old_sets.items(), key=lambda item: len(new_set & item[1]) / max(1, len(new_set | item[1]))
            )
            pairs.append(
                {
                    "new": new_name,
                    "closest_old": old_name,
                    "jaccard_percent": round(
                        100 * len(new_set & old_set) / max(1, len(new_set | old_set)), 2
                    ),
                }
            )
        result["metrics"][label] = {
            "new_unique_ngrams": len(new_all),
            "new_ngrams_also_in_old_percent": round(100 * len(new_all & old_all) / max(1, len(new_all)), 2),
            "corpus_jaccard_percent": round(100 * len(new_all & old_all) / max(1, len(new_all | old_all)), 2),
            "strongest_pairs": sorted(pairs, key=lambda item: item["jaccard_percent"], reverse=True)[:5],
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("rewritten", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(args.original, args.rewritten)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
