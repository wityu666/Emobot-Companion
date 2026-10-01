"""Synthetic SQLite benchmark; never reads a user's actual archive or provider keys."""

import argparse
import importlib.util
import json
import platform
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path

from sqlalchemy import event, insert

from emobot.archive import Archive
from emobot.settings import Settings


def measure(archive_type):
    settings = Settings(embedding_dimensions=768)
    imports, insert_calls = [], []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic.md"
        path.write_text("robot archive " * 64_285)  # 899,990 characters / 1,000 chunks.
        for _ in range(3):
            database = archive_type(settings, "sqlite:///:memory:")
            calls = []
            event.listen(database.engine, "before_cursor_execute", lambda _c, _u, sql, *_a: calls.append(sql))
            start = time.perf_counter()
            database.import_markdown([path])
            imports.append(time.perf_counter() - start)
            insert_calls.append(sum(sql.startswith("INSERT") for sql in calls))
            database.close()
    database = archive_type(settings, "sqlite:///:memory:")
    try:
        with database.engine.begin() as connection:
            connection.execute(
                insert(database.chunks),
                [
                    dict(
                        id=str(i),
                        user_id=settings.user,
                        document_id="synthetic",
                        position=i,
                        heading="robot",
                        content=f"robot archive item {i}",
                        vector=[1.0] + [0.0] * 767,
                    )
                    for i in range(2000)
                ],
            )
        database.search("robot archive")
        searches = []
        for _ in range(5):
            start = time.perf_counter()
            results = database.search("robot archive")
            searches.append(time.perf_counter() - start)
        tracemalloc.start()
        database.search("robot archive")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {
            "import_median_seconds": statistics.median(imports),
            "import_insert_calls": insert_calls,
            "keyword_search_median_seconds": statistics.median(searches),
            "keyword_search_traced_peak_bytes": peak,
            "top_results": results,
        }
    finally:
        database.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, help="Archive module extracted from the earlier commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "current": measure(Archive),
    }
    if args.baseline:
        spec = importlib.util.spec_from_file_location("emobot._benchmark_baseline", args.baseline)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report["baseline"] = measure(module.Archive)
        assert report["current"]["top_results"] == report["baseline"]["top_results"]
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered)


if __name__ == "__main__":
    main()
