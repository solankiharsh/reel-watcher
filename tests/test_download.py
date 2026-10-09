import httpx
from fastapi.testclient import TestClient
from reel_watcher.app import create_app
from reel_watcher.download import Downloader


def test_apify_uses_header_auth_and_capped_runs_without_automatic_paid_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "synthetic-test-token")
    seen = []

    def handle(request):
        seen.append(request)
        assert "synthetic-test-token" not in str(request.url)
        assert request.headers["Authorization"] == "Bearer synthetic-test-token"
        if request.method == "POST":
            assert float(request.url.params["maxTotalChargeUsd"]) == 0.05
            return httpx.Response(201, json={"data": {"id": "test-run", "status": "RUNNING"}})
        return httpx.Response(
            200, json={"data": {"id": "test-run", "status": "FAILED", "usageTotalUsd": 0.01}}
        )

    provider = Downloader(tmp_path, client=httpx.Client(transport=httpx.MockTransport(handle)))
    with TestClient(create_app(tmp_path, downloader=provider, analyzer=object())) as client:
        item = client.post(
            "/api/import", json={"text": "https://instagram.com/reel/EXAMPLE/"}
        ).json()[0]

        def run():
            preview = client.post(
                "/api/batches/preview",
                json={"ids": [item["id"]], "provider": "apify", "unit_cost": 0.01, "cap": 0.05},
            ).json()
            return client.post(
                "/api/batches/run", json={"preview_id": preview["id"], "approve_cost": True}
            )

        assert run().status_code == 200
        assert run().status_code == 200
        assert len([r for r in seen if r.method == "POST"]) == 1
        assert "test-run" in client.get(f"/api/items/{item['id']}").json()["error"]
        assert "synthetic-test-token" not in (tmp_path / "apify_cost.jsonl").read_text()


def test_failed_acquisition_removes_partial_media(tmp_path):
    import subprocess
    from unittest.mock import patch

    provider = Downloader(tmp_path)
    item = {"id": "synthetic", "url": "https://www.instagram.com/reel/EXAMPLE/"}

    def failed_download(*args, **kwargs):
        (tmp_path / "media" / "synthetic" / "video.mp4.part").write_bytes(b"synthetic partial")
        raise subprocess.TimeoutExpired("yt-dlp", 180)

    import pytest

    with patch("subprocess.run", failed_download), pytest.raises(ValueError):
        provider.fetch(item, {"provider": "public"})
    assert not (tmp_path / "media" / "synthetic").exists()
