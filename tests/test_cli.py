import json
import subprocess
import sys


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "reel_watcher", *map(str, args)], capture_output=True, text=True
    )


def test_cli_export_and_default_dry_run(tmp_path):
    export = tmp_path / "saved.json"
    export.write_text(
        json.dumps(
            {
                "saved_saved_media": [
                    {
                        "string_map_data": {
                            "Saved on": {
                                "href": "https://instagram.com/reel/EXAMPLE/?source=export"
                            }
                        }
                    }
                ]
            }
        )
    )
    urls = tmp_path / "urls.tsv"
    result = cli("export", export, "-o", urls)
    assert result.returncode == 0
    assert urls.read_text() == "https://www.instagram.com/reel/EXAMPLE/\n"
    result = cli("study", "--input", urls, "--out-root", tmp_path / "out")
    assert result.returncode == 0
    preview = json.loads(result.stdout)
    assert preview["remote_count"] == 1
    assert preview["estimated_usd"] == 0
    assert preview["used"] is False
    assert not (tmp_path / "out" / "media").exists()


def test_no_em_dash_in_python_sources():
    from pathlib import Path

    assert not [str(p) for p in Path("src").rglob("*.py") if chr(0x2014) in p.read_text()]


def test_doctor_recognizes_whisper_npz_weights(tmp_path, monkeypatch, capsys):
    from reel_watcher.cli import main
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setenv("REEL_WATCHER_MODELS", str(tmp_path))
    for name, weights in [("vision", "model.safetensors"), ("whisper", "weights.npz")]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / "config.json").write_text("{}")
        (folder / weights).write_bytes(b"synthetic-presence-marker")
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["model_readiness"] == "ready"
