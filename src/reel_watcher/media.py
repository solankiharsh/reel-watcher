"""Bounded media inspection and frame extraction using a bundled ffmpeg."""

import math
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

MAX_MEDIA_BYTES = 250 * 1024 * 1024


def ffmpeg():
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def inspect_video(path: Path):
    if path.stat().st_size > MAX_MEDIA_BYTES:
        raise ValueError("Video exceeds the 250 MB pilot limit.")
    reader = imageio_ffmpeg.read_frames(str(path))
    try:
        meta = next(reader)
    except Exception:
        raise ValueError("This file is not a readable video. Upload an MP4, MOV or WebM.") from None
    finally:
        reader.close()
    duration = float(meta.get("duration", 0))
    if not math.isfinite(duration) or not 0 < duration <= 600:
        raise ValueError("Pilot videos must be between 0 and 600 seconds long.")
    return {
        "duration_s": duration,
        "size": list(meta["size"]),
        "has_audio": bool(meta.get("audio_codec")),
    }


def run_ffmpeg(args):
    try:
        subprocess.run(
            [ffmpeg(), "-nostdin", "-y", "-loglevel", "error", *args],
            check=True,
            capture_output=True,
            timeout=180,
        )
    except (subprocess.SubprocessError, OSError):
        raise ValueError("Media conversion failed. Try a different local MP4.") from None


def sample_frames(path, workspace, duration):
    workspace.mkdir(parents=True, exist_ok=True)
    times = sorted(
        set(
            round(min(t, duration - 0.04), 2)
            for t in [0, 0.5, 1, 2, 3, *[duration * i / 8 for i in range(1, 8)]]
            if t < duration
        )
    )
    frames = []
    sheet = Image.new("RGB", (4 * 256, math.ceil(len(times) / 4) * 280), "#15171c")
    draw = ImageDraw.Draw(sheet)
    for i, t in enumerate(times):
        name = f"frame-{i:02d}.jpg"
        frame_path = workspace / name
        run_ffmpeg(
            [
                "-ss",
                str(t),
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                "scale=512:-2",
                str(frame_path),
            ]
        )
        with Image.open(frame_path) as raw:
            thumb = raw.copy()
            thumb.thumbnail((250, 248))
            x, y = (i % 4) * 256, (i // 4) * 280
            sheet.paste(thumb, (x, y + 26))
            draw.text((x + 6, y + 6), f"{i + 1}: {t:.2f}s", fill="white")
        frames.append({"t": t, "file": name, "ocr": ""})
    sheet.save(workspace / "contact.jpg")
    return frames
