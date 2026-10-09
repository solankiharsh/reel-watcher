"""Command-line entry points. URL studies are previews unless explicitly started."""

import argparse
import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path

from .imports import parse_import
from .library import Library
from .models import LocalModels, model_paths, setup_models


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reel-watcher")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Open the local browser library")
    serve.add_argument("--out-root", type=Path, default=Path("out"))
    serve.add_argument("--port", type=int, default=8765)
    export = commands.add_parser("export", help="Convert saved-data JSON, HTML or text to URLs")
    export.add_argument("input", type=Path)
    export.add_argument("-o", "--output", type=Path, required=True)
    study = commands.add_parser("study", help="Preview a batch or study local media")
    study.add_argument("--out-root", type=Path, default=Path("out"))
    source = study.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--local", type=Path, nargs="+")
    source.add_argument("--preview-id")
    study.add_argument("--run", action="store_true")
    study.add_argument("--approve-cost", action="store_true")
    study.add_argument("--provider", choices=["public", "apify"], default="public")
    study.add_argument("--unit-cost", type=float)
    study.add_argument("--cap", type=float)
    study.add_argument("--limit", type=int, default=3)
    study.add_argument("--retry-failed", action="store_true")
    models = commands.add_parser("models", help="Preview or explicitly download model weights")
    models.add_argument("--download", action="store_true")
    commands.add_parser("doctor", help="Check local prerequisites without network or model loading")
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            import uvicorn
            from .app import create_app

            print(f"Open http://127.0.0.1:{args.port} (local only).")
            uvicorn.run(
                create_app(args.out_root), host="127.0.0.1", port=args.port, access_log=False
            )
        elif args.command == "export":
            entries = parse_import(args.input.read_text(encoding="utf-8-sig"))
            if not entries:
                raise ValueError("No Instagram reel/post URLs found in this export.")
            args.output.write_text(
                "".join(
                    entry["url"]
                    + ("\t" + ", ".join(entry["collections"]) if entry["collections"] else "")
                    + "\n"
                    for entry in entries
                )
            )
            print(
                f"Wrote {len(entries)} unique references to {args.output}. No network requests made."
            )
        elif args.command == "models":
            setup_models(args.download)
        elif args.command == "doctor":
            from .media import ffmpeg

            try:
                LocalModels().check_ready()
                readiness = "ready"
            except ValueError as error:
                readiness = str(error)
            print(
                json.dumps(
                    {
                        "platform": platform.system(),
                        "architecture": platform.machine(),
                        "free_gb": round(shutil.disk_usage(".").free / 1024**3, 2),
                        "ffmpeg": ffmpeg(),
                        "models": {k: str(v) for k, v in model_paths().items()},
                        "model_readiness": readiness,
                        "model_dependencies": {
                            name: importlib.util.find_spec(name) is not None
                            for name in ["mlx_vlm", "mlx_whisper", "Vision", "llguidance"]
                        },
                    },
                    indent=2,
                )
            )
        else:
            library = Library(args.out_root)
            with library.session():
                if args.preview_id:
                    if not args.run:
                        raise ValueError("Pass --run to start a reviewed preview.")
                    preview = library.reserve(args.preview_id, args.approve_cost)
                    library.execute(preview)
                    print(json.dumps([library.store.get(i) for i in preview["ids"]], indent=2))
                    return int(
                        any(library.store.get(i)["status"] == "failed" for i in preview["ids"])
                    )
                if not 1 <= args.limit <= 20:
                    raise ValueError("--limit must be between 1 and 20.")
                if args.local:
                    items = []
                    for path in args.local[: args.limit]:
                        with path.open("rb") as stream:
                            items.append(library.upload(stream, path.name))
                else:
                    entries = parse_import(args.input.read_text(encoding="utf-8-sig"))
                    if not entries:
                        raise ValueError("No Instagram references found.")
                    items = [
                        library.store.add(entry["url"], title=entry["url"].split("/")[-2], **entry)
                        for entry in entries
                    ]
                    items = [
                        i
                        for i in items
                        if i["study"] is None and (args.retry_failed or i["status"] != "failed")
                    ][: args.limit]
                if not items:
                    print(
                        json.dumps(
                            {"message": "No new items. Use --retry-failed to include failures."}
                        )
                    )
                    return 0
                if all(item["study"] for item in items):
                    print(json.dumps(items, indent=2))
                    return 0
                preview = library.preview(
                    [i["id"] for i in items], args.provider, args.unit_cost, args.cap
                )
                if args.run or args.local:
                    if preview["paid"]:
                        print(json.dumps(preview, indent=2))
                        raise ValueError(
                            "Review this cost first, then use study --preview-id ID --run --approve-cost with the same --out-root."
                        )
                    library.execute(library.reserve(preview["id"]))
                    print(json.dumps([library.store.get(i) for i in preview["ids"]], indent=2))
                    return int(
                        any(library.store.get(i)["status"] == "failed" for i in preview["ids"])
                    )
                print(json.dumps(preview, indent=2))
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
