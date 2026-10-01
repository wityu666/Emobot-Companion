from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from .archive import Archive
from .companion import Companion
from .providers import Cloud, DemoCloud
from .settings import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emobot", description="Desktop companion and ESP32-S3 controller")
    parser.add_argument("--demo", action="store_true", help="explicit offline model; never sends to cloud")
    parser.add_argument("--config", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("gui")
    chat = commands.add_parser("chat")
    chat.add_argument("question", nargs="?", default="你好 / Hello")
    docs = commands.add_parser("import-docs")
    docs.add_argument("paths", nargs="+", type=Path)
    commands.add_parser("index")
    commands.add_parser("doctor")
    args = parser.parse_args(argv)
    try:
        config = Settings.load(args.config)
        if args.command == "doctor":
            result = {
                name: importlib.util.find_spec(name) is not None
                for name in (
                    "tkinter",
                    "serial",
                    "bleak",
                    "speech_recognition",
                    "pyaudio",
                    "pygame",
                    "psycopg",
                    "pgvector",
                    "esptool",
                )
            }
            print(
                json.dumps(
                    {
                        "dependencies": result,
                        "api_key_configured": bool(config.api_key),
                        "language": config.language,
                    },
                    indent=2,
                )
            )
            return 0
        archive = Archive(config)
        cloud = DemoCloud() if args.demo else Cloud(config)
        try:
            if args.command == "import-docs":
                print(f"Imported: {archive.import_markdown(args.paths)}")
            elif args.command == "index":
                if args.demo:
                    raise ValueError("Vector indexing requires a configured embedding provider")
                print(f"Indexed: {archive.index(cloud)}")
            else:
                if args.command == "gui":
                    from .gui import Desktop
                    from .link import RobotLink

                    robot = RobotLink()
                    Desktop(Companion(config, archive, cloud, robot), robot, args.demo).run()
                else:
                    reply = Companion(config, archive, cloud).ask(args.question)
                    print(
                        json.dumps(
                            {
                                "reply": reply.text,
                                "route": reply.route,
                                "actions": [a.as_dict() for a in reply.actions],
                                "references": list(reply.references),
                                "warnings": list(reply.warnings),
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
        finally:
            cloud.close()
            archive.close()
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
