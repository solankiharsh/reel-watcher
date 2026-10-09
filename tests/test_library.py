import pytest
from fastapi.testclient import TestClient
from reel_watcher.app import create_app


def test_import_is_a_deduplicated_preview_without_processing(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        result = client.post(
            "/api/import",
            json={
                "text": "https://www.instagram.com/reel/EXAMPLE/?igsh=x\tAI\nhttps://instagram.com/reel/EXAMPLE/"
            },
        )
        assert result.status_code == 200
        items = client.get("/api/items").json()
        assert len(items) == 1
        assert items[0]["url"] == "https://www.instagram.com/reel/EXAMPLE/"
        assert items[0]["collections"] == ["AI"]
        assert items[0]["status"] == "queued"
        assert items[0]["study"] is None


def test_uploaded_video_can_be_studied_and_deleted_without_losing_evidence(tmp_path):
    import subprocess
    import imageio_ffmpeg

    clip = tmp_path / "example.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x240:d=1",
            "-c:v",
            "libx264",
            str(clip),
        ],
        check=True,
        capture_output=True,
    )

    class Model:
        def study(self, path, workspace, post):
            return {
                "title": "Blue opening",
                "topics": ["AI"],
                "creative_tags": ["color hook"],
                "duration_s": 1,
                "transcript": [],
                "frames": [{"t": 0, "file": "frame-00.jpg", "ocr": "SYNTHETIC"}],
                "observations": [
                    {
                        "aspect": "opening_visual",
                        "text": "Blue screen",
                        "evidence": [{"source": "frames", "t": 0, "quote": "SYNTHETIC"}],
                    }
                ],
                "hypotheses": ["A solid color may create contrast."],
            }

    with TestClient(create_app(tmp_path / "data", analyzer=Model())) as client:
        response = client.post(
            "/api/upload", files={"file": ("example.mp4", clip.read_bytes(), "video/mp4")}
        )
        assert response.status_code == 200
        item_id = response.json()["id"]
        preview = client.post("/api/batches/preview", json={"ids": [item_id]}).json()
        assert preview["estimated_usd"] == 0
        assert client.get(f"/api/items/{item_id}").json()["study"] is None
        result = client.post("/api/batches/run", json={"preview_id": preview["id"]})
        assert result.status_code == 200
        item = client.get(f"/api/items/{item_id}").json()
        assert item["status"] == "ready"
        assert item["study"]["observations"][0]["evidence"][0]["source"] == "ocr"
        assert item["study"]["observations"][0]["evidence"][0]["t"] == 0
        assert client.delete(f"/api/items/{item_id}/media").status_code == 200
        retained = client.get(f"/api/items/{item_id}").json()
        assert retained["study"] == item["study"]
        assert retained["media"] is None
        assert client.get(f"/api/items/{item_id}/media").status_code == 404
        restored = client.post("/api/upload", files={"file": ("example.mp4", clip.read_bytes())})
        assert restored.status_code == 200
        assert restored.json()["id"] == item_id
        assert restored.json()["study"] == item["study"]
        repeated = client.post("/api/upload", files={"file": ("example.mp4", clip.read_bytes())})
        assert repeated.status_code == 200
        assert repeated.json()["id"] == item_id
        assert client.get(f"/api/items/{item_id}/media").status_code == 200
        assert client.get(f"/api/items/{item_id}/frames/frame-00.jpg").status_code == 200


def test_paid_batch_requires_exact_preview_approval_and_cannot_be_replayed(tmp_path):
    class Provider:
        calls = []

        def fetch(self, item, preview):
            self.calls.append((item["url"], preview["cap_usd"]))
            raise RuntimeError("private provider diagnostics")

    provider = Provider()
    with TestClient(create_app(tmp_path, downloader=provider, analyzer=object())) as client:
        item = client.post(
            "/api/import", json={"text": "https://instagram.com/reel/EXAMPLE/"}
        ).json()[0]
        preview = client.post(
            "/api/batches/preview",
            json={"ids": [item["id"]], "provider": "apify", "unit_cost": 0.01, "cap": 0.05},
        ).json()
        assert preview["estimated_usd"] == 0.01
        assert provider.calls == []
        assert (
            client.post("/api/batches/run", json={"preview_id": preview["id"]}).status_code == 422
        )
        assert provider.calls == []
        assert (
            client.post(
                "/api/batches/run", json={"preview_id": preview["id"], "approve_cost": True}
            ).status_code
            == 200
        )
        assert provider.calls == [(item["url"], 0.05)]
        assert (
            client.post(
                "/api/batches/run", json={"preview_id": preview["id"], "approve_cost": True}
            ).status_code
            == 422
        )
        failed = client.get(f"/api/items/{item['id']}").json()
        assert failed["status"] == "failed"
        assert "private provider" not in failed["error"]


@pytest.mark.parametrize("source", ["transcript", "frame", "frames", "ocr"])
def test_study_rejects_invented_quote_and_keeps_media_for_retry(tmp_path, source):
    import subprocess
    import imageio_ffmpeg

    clip = tmp_path / "example.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x240:d=1",
            str(clip),
        ],
        check=True,
        capture_output=True,
    )

    class Model:
        def study(self, path, workspace, post):
            return {
                "title": "Test",
                "topics": [],
                "creative_tags": [],
                "duration_s": 1,
                "transcript": [{"start": 0, "end": 1, "text": "Actual words"}],
                "frames": [{"t": 0, "file": None, "ocr": ""}],
                "observations": [
                    {
                        "aspect": "hook",
                        "text": "Unsupported",
                        "evidence": [{"source": source, "t": 0, "quote": "Invented words"}],
                    }
                ],
                "hypotheses": [],
            }

    with TestClient(create_app(tmp_path / "data", analyzer=Model())) as client:
        item = client.post("/api/upload", files={"file": ("example.mp4", clip.read_bytes())}).json()
        preview = client.post("/api/batches/preview", json={"ids": [item["id"]]}).json()
        client.post("/api/batches/run", json={"preview_id": preview["id"]})
        failed = client.get(f"/api/items/{item['id']}").json()
        assert failed["status"] == "failed"
        assert failed["study"] is None
        assert failed["media"]
        assert "quote" in failed["error"]
        retry = client.post("/api/batches/preview", json={"ids": [item["id"]]}).json()
        assert retry["remote_count"] == 0


def test_export_import_and_persistence(tmp_path):
    import json

    export = {
        "saved_saved_media": [
            {"string_map_data": {"Saved on": {"href": "https://www.instagram.com/p/EXAMPLE/"}}}
        ]
    }
    with TestClient(create_app(tmp_path)) as client:
        result = client.post("/api/import", json={"text": json.dumps(export)})
        assert result.status_code == 200
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/items").json()[0]["url"] == "https://www.instagram.com/p/EXAMPLE/"


def test_browser_cannot_drive_local_app_from_another_origin(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert (
            client.post(
                "/api/import",
                headers={"Origin": "https://untrusted.example"},
                json={"text": "https://instagram.com/reel/EXAMPLE/"},
            ).status_code
            == 403
        )
        assert client.get("/api/items", headers={"Host": "untrusted.example"}).status_code == 400


@pytest.mark.parametrize("copied", [False, True])
def test_profile_is_reusable_and_overrides_are_per_brief(tmp_path, copied):
    import subprocess
    import imageio_ffmpeg

    clip = tmp_path / "example.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x240:d=1",
            str(clip),
        ],
        check=True,
        capture_output=True,
    )

    class Model:
        def study(self, path, workspace, post):
            return {
                "title": "AI tutorial",
                "duration_s": 1,
                "topics": ["AI"],
                "creative_tags": ["demonstration"],
                "transcript": [{"start": 0, "end": 1, "text": "Source hook only"}],
                "frames": [{"t": 0}],
                "observations": [
                    {
                        "aspect": "opening_visual",
                        "text": "Blue frame",
                        "evidence": [{"source": "frame", "t": 0}],
                    }
                ],
                "hypotheses": [],
            }

        def brief(self, references, profile, topic):
            assert profile["audience"] == "Designers"
            return {
                "title": topic,
                "hooks": [
                    "Source hook only" if copied else "Try this workflow",
                    "Start with a blank page",
                    "Watch this idea take shape",
                ],
                "beats": ["Introduce the problem", "Show an original demonstration"],
                "visuals": ["Screen recording"],
                "references": [
                    {"id": references[0]["id"], "reason": "Adapt the demonstration structure."}
                ],
            }

    with TestClient(create_app(tmp_path / "data", analyzer=Model())) as client:
        item = client.post("/api/upload", files={"file": ("example.mp4", clip.read_bytes())}).json()
        preview = client.post("/api/batches/preview", json={"ids": [item["id"]]}).json()
        client.post("/api/batches/run", json={"preview_id": preview["id"]})
        assert (
            client.put(
                "/api/profile",
                json={"audience": "Beginners", "objective": "Teach", "format": "Tutorial"},
            ).status_code
            == 200
        )
        response = client.post(
            "/api/briefs",
            json={
                "ids": [item["id"]],
                "topic": "AI design workflow",
                "overrides": {"audience": "Designers"},
            },
        )
        if copied:
            assert response.status_code == 422
            assert client.get("/api/briefs").json() == []
            return
        assert response.status_code == 200
        brief = response.json()
        assert len(brief["hooks"]) == 3
        assert brief["references"][0]["id"] == item["id"]
        assert client.get("/api/profile").json()["audience"] == "Beginners"
        assert client.get("/api/briefs").json()[0]["id"] == brief["id"]


def test_two_similarity_views_explain_different_matches(tmp_path):
    import subprocess
    import imageio_ffmpeg

    clip = tmp_path / "example.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x240:d=1",
            str(clip),
        ],
        check=True,
        capture_output=True,
    )

    class Provider:
        def fetch(self, item, preview):
            import shutil

            media = tmp_path / "data" / (item["id"] + ".mp4")
            shutil.copyfile(clip, media)
            return media, {"caption": item["title"]}

    class Model:
        def study(self, path, workspace, post):
            code = post["caption"]
            return {
                "title": code,
                "duration_s": 1,
                "topics": ["AI"] if code != "OTHER" else ["Cooking"],
                "creative_tags": ["demonstration"] if code != "TOPIC" else ["question"],
                "transcript": [],
                "frames": [{"t": 0}],
                "observations": [
                    {
                        "aspect": "opening_visual",
                        "text": "Blue frame",
                        "evidence": [{"source": "frame", "t": 0}],
                    }
                ],
                "hypotheses": [],
            }

    with TestClient(
        create_app(tmp_path / "data", analyzer=Model(), downloader=Provider())
    ) as client:
        items = client.post(
            "/api/import",
            json={
                "text": "\n".join(
                    f"https://instagram.com/reel/{code}/" for code in ["BASE", "TOPIC", "OTHER"]
                )
            },
        ).json()
        preview = client.post("/api/batches/preview", json={"ids": [i["id"] for i in items]}).json()
        client.post("/api/batches/run", json={"preview_id": preview["id"]})
        subject = client.get(f"/api/items/{items[0]['id']}/similar?mode=subject").json()
        creative = client.get(f"/api/items/{items[0]['id']}/similar?mode=creative").json()
        assert [row["item"]["title"] for row in subject] == ["TOPIC"]
        assert [row["item"]["title"] for row in creative] == ["OTHER"]
        assert "ai" in subject[0]["reason"].lower()
        assert "demonstration" in creative[0]["reason"]


def test_models_must_be_ready_before_any_download(tmp_path):
    class UnavailableModel:
        def check_ready(self):
            raise ValueError("Install local models first.")

    class Provider:
        def fetch(self, item, preview):
            raise AssertionError("Must never download before model preflight")

    with TestClient(
        create_app(tmp_path, analyzer=UnavailableModel(), downloader=Provider())
    ) as client:
        item = client.post(
            "/api/import", json={"text": "https://instagram.com/reel/EXAMPLE/"}
        ).json()[0]
        preview = client.post("/api/batches/preview", json={"ids": [item["id"]]}).json()
        response = client.post("/api/batches/run", json={"preview_id": preview["id"]})
        assert response.status_code == 422
        assert "models" in response.json()["detail"]
        assert client.get(f"/api/items/{item['id']}").json()["status"] == "queued"


def test_changed_media_invalidates_old_preview(tmp_path):
    import subprocess
    import imageio_ffmpeg

    clip = tmp_path / "example.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x240:d=1",
            str(clip),
        ],
        check=True,
        capture_output=True,
    )
    with TestClient(
        create_app(tmp_path / "data", analyzer=object(), downloader=object())
    ) as client:
        item = client.post(
            "/api/import", json={"text": "https://instagram.com/reel/EXAMPLE/"}
        ).json()[0]
        client.post(
            "/api/upload",
            params={"item_id": item["id"]},
            files={"file": ("example.mp4", clip.read_bytes())},
        )
        preview = client.post("/api/batches/preview", json={"ids": [item["id"]]}).json()
        assert preview["remote_count"] == 0
        client.delete(f"/api/items/{item['id']}/media")
        response = client.post("/api/batches/run", json={"preview_id": preview["id"]})
        assert response.status_code == 422
        assert "changed" in response.json()["detail"]


def test_paid_cap_cannot_hide_fractional_cents(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        item = client.post(
            "/api/import", json={"text": "https://instagram.com/reel/EXAMPLE/"}
        ).json()[0]
        response = client.post(
            "/api/batches/preview",
            json={"ids": [item["id"]], "provider": "apify", "unit_cost": 0.01, "cap": 0.014},
        )
        assert response.status_code == 422
        assert "cent" in response.json()["detail"]
