"""Cookie-free public fetching and explicitly capped Apify runs."""

import json
import shutil
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .imports import canonical_url
from .media import MAX_MEDIA_BYTES, inspect_video
from .store import Store


class Downloader:
    def __init__(self, root: Path, client=None):
        self.store = Store(root)
        self.root = self.store.root
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)

    def fetch(self, item, preview):
        try:
            return self._fetch(item, preview)
        except Exception:
            shutil.rmtree(self.root / "media" / item["id"], ignore_errors=True)
            raise

    def _fetch(self, item, preview):
        url = canonical_url(item["url"])
        directory = self.root / "media" / item["id"]
        directory.mkdir(parents=True, exist_ok=True)
        if preview["provider"] == "apify":
            return self.apify(item, preview, directory)
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "yt_dlp",
                    "--ignore-config",
                    "--no-plugin-dirs",
                    "--no-playlist",
                    "--quiet",
                    "--no-warnings",
                    "--no-progress",
                    "--max-filesize",
                    "250M",
                    "--socket-timeout",
                    "20",
                    "--retries",
                    "0",
                    "--fragment-retries",
                    "0",
                    "-f",
                    "best[ext=mp4]/best",
                    "--write-info-json",
                    "-o",
                    str(directory / "video.%(ext)s"),
                    url,
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
            candidates = [
                p
                for p in directory.glob("video.*")
                if p.suffix in {".mp4", ".webm", ".mov", ".mkv"}
            ]
            if not candidates:
                raise ValueError("No video returned.")
            path = candidates[0]
            inspect_video(path)
            info_path = directory / "video.info.json"
            info = json.loads(info_path.read_text()) if info_path.exists() else {}
            info_path.unlink(missing_ok=True)
            return path, {
                "caption": info.get("description") or "",
                "author": info.get("uploader") or "",
                "views": info.get("view_count"),
                "likes": info.get("like_count"),
            }
        except Exception:
            raise ValueError(
                "Public download unavailable. Attach a local video, or explicitly review an Apify batch. No login or cookies were used."
            ) from None

    def apify(self, item, preview, directory):
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            raise ValueError(
                "Set APIFY_TOKEN in the server shell. Never paste it into the library."
            )
        headers = {"Authorization": "Bearer " + token}
        journal = self.store.document("apify_run", item["id"])
        if not journal:
            # Write intent first: an ambiguous network failure must never start another paid run.
            journal = {
                "item_id": item["id"],
                "run_id": None,
                "state": "starting",
                "cap_usd": preview["cap_usd"] / preview["remote_count"],
                "preview_id": preview["id"],
            }
            self.store.put_document("apify_run", item["id"], journal)
            try:
                response = self.client.post(
                    "https://api.apify.com/v2/acts/apify~instagram-scraper/runs",
                    headers=headers,
                    params={
                        "maxTotalChargeUsd": journal["cap_usd"],
                        "timeout": 120,
                        "restartOnError": "false",
                    },
                    json={"directUrls": [item["url"]], "resultsType": "posts", "resultsLimit": 1},
                )
                response.raise_for_status()
                run = response.json()["data"]
                journal.update(run_id=run["id"], state=run["status"])
                self.store.put_document("apify_run", item["id"], journal)
            except Exception:
                raise ValueError(
                    "Apify start outcome is unknown. Check your Apify console before any new paid attempt. Automatic paid retry is blocked."
                ) from None
        if not journal.get("run_id"):
            raise ValueError(
                "An earlier Apify start is unresolved. Check your Apify console; automatic paid retry is blocked."
            )
        run_id = journal["run_id"]
        try:
            deadline = time.monotonic() + 150
            while True:
                response = self.client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}", headers=headers
                )
                response.raise_for_status()
                run = response.json()["data"]
                if run["status"] in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                    break
                if time.monotonic() >= deadline:
                    raise ValueError(
                        f"Apify run {run_id} is still pending. Retry to check the same run; no new charge will be started."
                    )
                time.sleep(2)
            if not journal.get("cost_recorded"):
                with (self.root / "apify_cost.jsonl").open("a") as log:
                    log.write(
                        json.dumps(
                            {
                                "run_id": run_id,
                                "item_id": item["id"],
                                "status": run["status"],
                                "actual_usd": run.get("usageTotalUsd"),
                                "cap_usd": journal["cap_usd"],
                            }
                        )
                        + "\n"
                    )
                journal["cost_recorded"] = True
                journal["state"] = run["status"]
                self.store.put_document("apify_run", item["id"], journal)
            if run["status"] != "SUCCEEDED":
                raise ValueError(
                    f"Apify run {run_id} ended as {run['status']}. Attach local media. Automatic paid retry is blocked."
                )
            response = self.client.get(
                f"https://api.apify.com/v2/datasets/{run['defaultDatasetId']}/items",
                headers=headers,
                params={"format": "json", "clean": "true"},
            )
            response.raise_for_status()
            rows = response.json()
            row = next(
                (
                    row
                    for row in rows
                    if row.get("shortCode") == item["url"].strip("/").split("/")[-1]
                ),
                None,
            )
            if not row or not row.get("videoUrl"):
                raise ValueError(
                    "Apify returned no matching video. Carousels are not supported in this pilot; attach a local video."
                )
            path = directory / "video.mp4"
            self.download_cdn(row["videoUrl"], path)
            inspect_video(path)
            return path, {
                "caption": row.get("caption") or "",
                "author": row.get("ownerUsername") or "",
                "views": row.get("videoViewCount"),
                "likes": row.get("likesCount"),
            }
        except ValueError:
            raise
        except Exception:
            raise ValueError(
                f"Could not retrieve Apify run {run_id}. Retry to inspect the existing run, or attach local media."
            ) from None

    @staticmethod
    def download_cdn(url, path):
        temporary = path.with_suffix(".part")
        try:
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                for _ in range(5):
                    parsed = urlparse(url)
                    host = parsed.hostname or ""
                    if (
                        parsed.scheme != "https"
                        or parsed.port not in {None, 443}
                        or parsed.username
                        or not any(
                            host.endswith("." + domain)
                            for domain in ["cdninstagram.com", "fbcdn.net"]
                        )
                    ):
                        raise ValueError("Provider returned an unsupported media host.")
                    with client.stream("GET", url) as response:
                        if response.is_redirect:
                            url = str(response.url.join(response.headers["location"]))
                            continue
                        response.raise_for_status()
                        size = 0
                        with temporary.open("wb") as file:
                            for chunk in response.iter_bytes(1024 * 1024):
                                size += len(chunk)
                                if size > MAX_MEDIA_BYTES:
                                    raise ValueError(
                                        "Downloaded video exceeds the 250 MB pilot limit."
                                    )
                                file.write(chunk)
                        temporary.replace(path)
                        return
                raise ValueError("Too many media redirects.")
        finally:
            temporary.unlink(missing_ok=True)
