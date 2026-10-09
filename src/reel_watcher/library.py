"""Library operations shared by the HTTP API and CLI."""

from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from .media import MAX_MEDIA_BYTES, inspect_video, run_ffmpeg
from .schema import validate_study
from .store import Store


class Library:
    def __init__(self, root, analyzer=None, downloader=None):
        self.store = Store(root)
        self.root = self.store.root
        self.analyzer = analyzer
        self.downloader = downloader
        self.lock = threading.RLock()
        self.running = False

    @contextmanager
    def session(self):
        with (self.root / ".library.lock").open("a") as lockfile:
            try:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError(
                    "This library is already open in another process. Stop it or use another --out-root."
                ) from None
            try:
                for item in self.store.items():
                    if item["status"] == "processing":
                        item.update(
                            status="failed", error="Processing was interrupted. Retry this item."
                        )
                        self.store.save(item)
                yield
            finally:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)

    def upload(self, stream, filename, item_id=None):
        temp = self.root / f"{uuid.uuid4().hex}.upload"
        try:
            total = 0
            digest = hashlib.sha256()
            with temp.open("wb") as output:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_MEDIA_BYTES:
                        raise ValueError("Video exceeds the 250 MB pilot limit.")
                    digest.update(chunk)
                    output.write(chunk)
            inspect_video(temp)
            with self.lock:
                if self.running:
                    raise ValueError("Wait for the current batch before attaching media.")
                item = (
                    self.store.get(item_id)
                    if item_id
                    else self.store.add(
                        "local:" + digest.hexdigest(), title=Path(filename).stem[:200]
                    )
                )
                if item["study"]:
                    if item.get("media_sha256") != digest.hexdigest():
                        raise ValueError(
                            "Only the identical original video can restore a completed study."
                        )
                    if item["media"] and (self.root / item["media"]).is_file():
                        return item
                directory = self.root / "media" / item["id"]
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / "video.mp4"
                if item["study"]:
                    workspace = self.root / "frames" / item["id"]
                    workspace.mkdir(parents=True, exist_ok=True)
                    for frame in item["study"]["frames"]:
                        if frame["file"]:
                            run_ffmpeg(
                                [
                                    "-ss",
                                    str(frame["t"]),
                                    "-i",
                                    str(temp),
                                    "-frames:v",
                                    "1",
                                    "-vf",
                                    "scale=512:-2",
                                    str(workspace / frame["file"]),
                                ]
                            )
                temp.replace(target)
                item.update(
                    media=str(target.relative_to(self.root)),
                    status="ready" if item["study"] else "queued",
                    error=None,
                    media_revision=uuid.uuid4().hex,
                    media_sha256=digest.hexdigest(),
                )
                self.export_study(item)
                return self.store.save(item)
        finally:
            temp.unlink(missing_ok=True)

    def preview(self, ids, provider="public", unit_cost=None, cap=None):
        ids = list(dict.fromkeys(ids))
        if not ids or len(ids) > 20:
            raise ValueError("Select between 1 and 20 items.")
        items = [self.store.get(item_id) for item_id in ids]
        pending = [item for item in items if item["study"] is None]
        remote = [item for item in pending if not item["media"]]
        if any(not item["url"] for item in remote):
            raise ValueError("Attach local media before processing this item.")
        paid = provider == "apify" and bool(remote)
        if paid:
            if len(remote) > 3:
                raise ValueError("Paid pilot batches are limited to three new downloads.")
            if unit_cost is None or cap is None or not 0 < unit_cost <= cap <= 2:
                raise ValueError("Set a current per-reel estimate and a cap of at most $2.")
            if Decimal(str(cap)) % Decimal("0.01"):
                raise ValueError("Batch caps must be in whole cents, such as 0.05.")
            if round(unit_cost * len(remote), 6) > cap:
                raise ValueError("Estimated cost exceeds the batch cap.")
        preview = dict(
            id=uuid.uuid4().hex,
            ids=[item["id"] for item in pending],
            skipped=len(items) - len(pending),
            remote_count=len(remote),
            provider=provider,
            estimated_usd=round(unit_cost * len(remote), 6) if paid else 0,
            cap_usd=cap if paid else 0,
            paid=paid,
            created_at=time.time(),
            used=False,
            sources={
                item["id"]: [
                    item["url"],
                    item["media"],
                    item.get("media_revision"),
                    bool(item["study"]),
                ]
                for item in pending
            },
            items=[
                {"id": item["id"], "title": item["title"], "url": item["url"]} for item in pending
            ],
        )
        return self.store.put_document("preview", preview["id"], preview)

    def reserve(self, preview_id, approve_cost=False):
        with self.lock:
            preview = self.store.document("preview", preview_id)
            if not preview or preview["used"] or time.time() - preview["created_at"] > 900:
                raise ValueError("Preview expired or already used. Review a new batch.")
            if self.running:
                raise ValueError("A batch is already running.")
            for item_id, expected in preview.get("sources", {}).items():
                item = self.store.get(item_id)
                if [
                    item["url"],
                    item["media"],
                    item.get("media_revision"),
                    bool(item["study"]),
                ] != expected:
                    raise ValueError("Selected media changed. Calculate a new preview.")
            if preview["paid"] and not approve_cost:
                raise ValueError("Explicit approval of this preview and cost cap is required.")
            if preview["paid"]:
                import os

                if not os.environ.get("APIFY_TOKEN") and self.downloader is None:
                    raise ValueError(
                        "Set APIFY_TOKEN in the server shell, then restart. Never paste it here."
                    )
            if self.analyzer is None:
                from .models import LocalModels

                self.analyzer = LocalModels()
            if hasattr(self.analyzer, "check_ready"):
                self.analyzer.check_ready()
            preview["used"] = True
            self.store.put_document("preview", preview_id, preview)
            self.running = True
            return preview

    def execute(self, preview):
        try:
            for item_id in preview["ids"]:
                item = self.store.get(item_id)
                if item["study"]:
                    continue
                item.update(status="processing", error=None)
                self.store.save(item)
                try:
                    if not item["media"]:
                        if self.downloader is None:
                            from .download import Downloader

                            self.downloader = Downloader(self.root)
                        media, post = self.downloader.fetch(item, preview)
                        with media.open("rb") as downloaded:
                            fingerprint = hashlib.file_digest(downloaded, "sha256").hexdigest()
                        item.update(
                            media=str(media.relative_to(self.root)),
                            post=post,
                            media_sha256=fingerprint,
                        )
                        self.store.save(item)
                    if self.analyzer is None:
                        from .models import LocalModels

                        self.analyzer = LocalModels()
                    workspace = self.root / "frames" / item_id
                    workspace.mkdir(parents=True, exist_ok=True)
                    value = self.analyzer.study(self.root / item["media"], workspace, item["post"])
                    study = validate_study(value, item["post"])
                    item.update(study=study, title=study["title"], status="ready", error=None)
                    self.export_study(item)
                except Exception as exc:
                    # Never persist provider/HTTP exception bodies or credentials.
                    message = (
                        str(exc)
                        if isinstance(exc, ValueError)
                        else "Processing failed. Check setup and retry, or attach a local video."
                    )
                    import os

                    token = os.environ.get("APIFY_TOKEN")
                    if token:
                        message = message.replace(token, "[redacted]")
                    item.update(status="failed", error=message[:500])
                self.store.save(item)
        finally:
            with self.lock:
                self.running = False

    def delete_media(self, item_id):
        with self.lock:
            if self.running:
                raise ValueError("Wait for the current batch before deleting media.")
            item = self.store.get(item_id)
            if item["media"]:
                (self.root / item["media"]).unlink(missing_ok=True)
            shutil.rmtree(self.root / "media" / item_id, ignore_errors=True)
            shutil.rmtree(self.root / "frames" / item_id, ignore_errors=True)
            item["media"] = None
            self.export_study(item)
            return self.store.save(item)

    def export_study(self, item):
        if not item["study"]:
            return
        directory = self.root / "study"
        directory.mkdir(exist_ok=True)
        temporary = directory / (item["id"] + ".tmp")
        temporary.write_text(json.dumps(item, indent=2))
        temporary.replace(directory / (item["id"] + ".json"))

    def storage(self):
        files = [
            p
            for folder in ["media", "frames"]
            for p in (self.root / folder).rglob("*")
            if p.is_file()
        ]
        return {
            "media_bytes": sum(p.stat().st_size for p in files),
            "free_bytes": shutil.disk_usage(self.root).free,
        }

    def brief(self, ids, topic, overrides):
        from .schema import Brief, Profile

        references = [self.store.get(item_id) for item_id in dict.fromkeys(ids)]
        if not references or any(not item["study"] for item in references):
            raise ValueError("Select completed studies as references.")
        profile = self.store.document("profile", "default", Profile().model_dump())
        profile = Profile.model_validate({**profile, **overrides}).model_dump()
        with self.lock:
            if self.running:
                raise ValueError("Wait for current processing to finish.")
            self.running = True
        try:
            if self.analyzer is None:
                from .models import LocalModels

                self.analyzer = LocalModels()
            draft = Brief.model_validate(
                self.analyzer.brief(references, profile, topic)
            ).model_dump()
            allowed = {item["id"]: item for item in references}
            if any(ref["id"] not in allowed for ref in draft["references"]):
                raise ValueError("The model returned an unknown reference. Please retry.")
            if len(set(draft["hooks"])) != 3 or any(not hook.strip() for hook in draft["hooks"]):
                raise ValueError("The model must return three distinct original hook options.")
            import re

            source_texts = [
                text
                for item in references
                for text in [
                    item["post"].get("caption", ""),
                    *[segment["text"] for segment in item["study"]["transcript"]],
                    *[frame["ocr"] for frame in item["study"]["frames"]],
                ]
            ]
            normalized_sources = [
                " ".join(re.findall(r"\w+", text.lower())) for text in source_texts
            ]
            for hook in draft["hooks"]:
                normalized = " ".join(re.findall(r"\w+", hook.lower()))
                if normalized and any(normalized in source for source in normalized_sources):
                    raise ValueError("A hook copies source wording. Generate a new brief.")
            for ref in draft["references"]:
                ref["title"] = allowed[ref["id"]]["title"]
                ref["url"] = allowed[ref["id"]]["url"]
            draft.update(id=uuid.uuid4().hex, profile=profile, topic=topic, created_at=time.time())
            return self.store.put_document("brief", draft["id"], draft)
        finally:
            with self.lock:
                self.running = False

    def similar(self, item_id, mode):
        import re

        item = self.store.get(item_id)
        if not item["study"]:
            return []
        field = "topics" if mode == "subject" else "creative_tags"

        def tokens(study):
            return {
                word
                for tag in study[field]
                for word in re.findall(r"[a-z0-9]+", tag.lower())
                if word not in {"a", "the", "and", "with", "in", "of", "to"}
            }

        original = tokens(item["study"])
        matches = []
        for other in self.store.items():
            if other["id"] == item_id or not other["study"]:
                continue
            candidate = tokens(other["study"])
            shared = sorted(original & candidate)
            if shared:
                matches.append(
                    {
                        "item": other,
                        "score": len(shared) / len(original | candidate),
                        "reason": (
                            "Shared subjects: "
                            if mode == "subject"
                            else "Shared creative techniques: "
                        )
                        + ", ".join(shared),
                    }
                )
        return sorted(matches, key=lambda match: (-match["score"], match["item"]["title"]))[:10]
