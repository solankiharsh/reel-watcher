"""Isolated MLX worker; only invoked after offline readiness checks."""

import json
import sys
from typing import Any, cast


def main():
    payload = json.load(sys.stdin)
    if sys.argv[1] == "transcribe":
        import mlx_whisper
        import numpy as np
        import wave

        with wave.open(payload["audio"], "rb") as audio:
            if (
                audio.getframerate() != 16000
                or audio.getnchannels() != 1
                or audio.getsampwidth() != 2
            ):
                raise ValueError("Expected mono 16 kHz PCM audio")
            samples = (
                np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16).astype(
                    np.float32
                )
                / 32768.0
            )

        result = mlx_whisper.transcribe(
            samples, path_or_hf_repo=payload["model"], language="en", word_timestamps=True
        )
        output = [
            {"start": row["start"], "end": row["end"], "text": row["text"].strip()}
            for row in result.get("segments", [])
            if row["text"].strip()
        ]
    else:
        from mlx_vlm import generate, load
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config
        from mlx_vlm.structured import build_json_schema_logits_processor

        model, processor = load(payload["model"])
        prompt = apply_chat_template(
            processor,
            load_config(payload["model"]),
            payload["prompt"],
            num_images=len(payload["images"]),
        )
        if not isinstance(prompt, str):
            raise ValueError("Model chat template did not produce a text prompt.")
        result = generate(
            model,
            cast(Any, processor),  # MLX attaches its detokenizer dynamically after load.
            prompt,
            image=payload["images"] or None,
            max_tokens=2400,
            temperature=0.0,
            logits_processors=[
                build_json_schema_logits_processor(processor.tokenizer, payload["schema"])
            ],
            verbose=False,
        )
        text = result.text if hasattr(result, "text") else str(result)
        start, end = text.find("{"), text.rfind("}")
        output = json.loads(text[start : end + 1])
    print("REEL_RESULT=" + json.dumps(output))


if __name__ == "__main__":
    main()
