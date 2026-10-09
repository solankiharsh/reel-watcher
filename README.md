# Reel watcher

A private browser library for studying saved reels and developing original content briefs. Built with Python, FastAPI, SQLite and a lightweight browser UI. Uses `uv`.

## Start the library

```bash
uv sync
uv run reel-watcher serve
```

Open http://127.0.0.1:8765. The server listens only on loopback. One process may use a library directory at a time. Use `--out-root PATH` for a separate library and `--port PORT` for another local instance.

On this checkout, uv was bootstrapped into `.tools/bin/uv` without changing your shell configuration. If `uv` is not on PATH:

```bash
export PATH="$PWD/.tools/bin:$PATH"
export UV_CACHE_DIR="$PWD/.uv-cache"
uv run reel-watcher serve
```

The base installation is enough to import, browse and manage a library. Processing and brief generation require the optional local models below. No model weights are downloaded by starting the app or importing references.

## Local model setup

Inference requires an Apple Silicon Mac. This machine was checked as an M4 with 16 GB RAM. The small preset uses Qwen2.5-VL 3B 4-bit and Whisper-small. Models run in separate, sequential processes to release memory between them. Close memory-heavy applications during analysis.

```bash
uv sync --extra models
uv run --extra models reel-watcher doctor
uv run --extra models reel-watcher models             # setup preview, no network
uv run --extra models reel-watcher models --download  # explicit weight download
uv run --extra models reel-watcher serve
```

Use `--extra models` for model-enabled commands so uv retains the optional packages. The default weights total about 3.6 GB, plus Python dependencies. Setup checks current repository sizes and requires a 2 GB free-space reserve. Downloads use Hugging Face; inference uses local paths with offline mode enabled. The built-in ffmpeg binary is provided by `imageio-ffmpeg`; a system ffmpeg takes precedence if installed.

`REEL_WATCHER_MODELS` changes the model directory (default `out/models`). `REEL_WATCHER_VLM` and `REEL_WATCHER_WHISPER` override the **local model directory paths**, not remote repository IDs. The `models --download` command downloads the default small models; custom models must be prepared separately. Do not point this command at directories containing a different model.

## Workflow

1. Add Instagram links, a saved-data export (JSON/HTML), a plain URL list, or local videos. Optional TSV format: `URL<TAB>collection`. Exact repeated URLs are canonicalized and deduplicated; export titles are not guessed to be collection names.
2. Select references and choose **Study selected**. Review the method, download count, estimate and cap before starting.
3. Public downloading uses yt-dlp without cookies, browser sessions or configuration files. Public access can fail; attach a local video or explicitly select Apify. There is no automatic paid fallback.
4. Open a completed study, inspect timestamps and excerpts, and explore **Same subject** or **Similar creative approach**. Matches use overlapping normalized model tags with a visible explanation, not a claim of semantic certainty.
5. Save your audience, objective, format and voice in **Creator profile**. Select up to five completed studies, choose **Create a brief**, and optionally override profile fields for this brief only.
6. Review three original hook options, a beat outline, visual suggestions and linked references. Briefs are drafts; review originality and factual claims before use.
7. Inspect media storage and delete retained videos/frames when desired. Studies, briefs and source URLs remain. Local uploads have no invented Instagram source link.

The pilot supports English videos up to 250 MB and 10 minutes, and batches of up to 20 references. Carousels, multilingual studies and public discovery are not implemented. Instagram post URLs may be imported, but processing requires a video.

## Apify and spending

Create your own account and set `APIFY_TOKEN` in the shell that launches the server. Do not paste the token in chat or the browser UI. The app uses authorization headers; it never writes the token to a file or URL.

Select Apify in the batch dialog, enter a current per-reel estimate from the provider, and choose a total cap (maximum $2). The estimate is user-entered and is **not a live price quote**. Paid pilot batches are limited to three new downloads. The final button states the exact cap being approved.

The cap is divided between the requested downloads and passed as `maxTotalChargeUsd` on each actor run. Starting a run writes a durable intent and records its ID. An uncertain start blocks automatic re-creation. Retries inspect the same recorded run; a failed terminal run requires a local attachment or manual investigation in Apify. Do not delete run records to retry without first reconciling charges. Costs, including unknown costs as `null`, are recorded in `out/apify_cost.jsonl` when terminal run information is available. A failed download may still incur charges.

Readiness is checked before any download. Previews expire after 15 minutes, can be consumed once, and are invalidated if selected media changes.

## CLI

```bash
uv run reel-watcher export saved_posts.json -o urls.tsv
uv run reel-watcher study --input urls.tsv --out-root ./out
uv run --extra models reel-watcher study --local clip.mp4 --out-root ./out
uv run --extra models reel-watcher study --input urls.tsv --run --limit 3 --out-root ./out
```

URL studies are dry runs by default. `--local` runs local analysis. The last example opts into public downloading only. Stop the browser server before using the CLI with the same data directory.

For paid processing, first generate and review a preview:

```bash
uv run reel-watcher study --input urls.tsv --provider apify --unit-cost 0.01 --cap 0.05 --limit 3 --out-root ./out
# The numbers above are illustrative, not current Apify prices.
uv run --extra models reel-watcher study --preview-id PREVIEW_ID --run --approve-cost --out-root ./out
```

Use `--retry-failed` to include failed references in a new CLI preview. Completed studies are reused. Retained media prevents another download when only analysis needs a retry.

## Getting saved references

Use Instagram's own Accounts Center information export, choose saved content if offered, and export to your device as JSON or HTML. Import the resulting saved-posts file in the browser or use the `export` command. The parser recursively finds Instagram `/reel/`, `/reels/`, `/p/` and `/tv/` references. The current shape of your real export still needs verification. The app does not log in to Instagram or automate its UI.

## Study output and evidence

SQLite is the primary library. Successful studies are also exported to `out/study/<item-id>.json`. Each exported item includes its ID, source URL when available, title, collections, status, media-relative path, post metadata and study:

```json
{
  "title": "Synthetic blue opening",
  "duration_s": 1.0,
  "topics": ["AI"],
  "creative_tags": ["color hook"],
  "transcript": [],
  "frames": [{"t": 0.0, "file": "frame-00.jpg", "ocr": ""}],
  "observations": [{
    "aspect": "opening_visual",
    "text": "A blue frame opens the video.",
    "evidence": [{"source": "frame", "t": 0.0, "quote": null}]
  }],
  "hypotheses": ["The solid color may create contrast."]
}
```

Frames are sampled at opening moments and spaced points, combined into a labeled contact sheet, and read with Apple Vision OCR. Speech is transcribed locally with Whisper. Current output retains segment timing, not word timing. This sampling can miss brief transitions; it is not exhaustive shot-by-shot analysis.

Transcript, caption and OCR quotations are checked against extracted source text; visual references must point to sampled timestamps. Those checks establish traceability, **not truth**: transcription, OCR and visual interpretation can still be wrong. Claims by creators remain claims. Explanations of effectiveness are hypotheses, not causal conclusions from view counts. Generation uses a local JSON grammar, with evidence choices limited to extracted excerpts and sampled timestamps. A valid citation can still be irrelevant to an observation, so review the content. Invalid model output fails visibly instead of producing a caption-only or fabricated full study.

Deleting media removes the video and derived images, updates the exported item's media state, and preserves evidence text/timestamps. Past observations remain inspectable but cannot be played locally without retained media.

## Privacy and development

`out/`, model files inside it, `.tools/`, environments, caches, media and database files are ignored by Git. Keep any custom `--out-root` outside the repository, or add it to `.gitignore` before use. Keep analysis local and credit creators. Do not redistribute their media or transcripts. No posting, messaging or engagement automation is included.

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy --check-untyped-defs --ignore-missing-imports src/reel_watcher
node --check src/reel_watcher/static/app.js
```

Tests use synthetic clips, a temporary real database and fake model/provider interfaces. Network access is blocked in the test process. Core tests cross the HTTP API and CLI, as agreed. They do not establish real model quality, public download reliability or actual paid-provider behavior. See `docs/VALIDATION.md` for the recorded checks and remaining pilot acceptance.

## Primary references

- [MLX-VLM usage](https://github.com/Blaizzy/mlx-vlm)
- [Selected vision model files](https://huggingface.co/mlx-community/Qwen2.5-VL-3B-Instruct-4bit/tree/main)
- [Selected Whisper model files](https://huggingface.co/mlx-community/whisper-small-mlx/tree/main)
- [Apify run API and cost cap](https://docs.apify.com/api/v2/actors-runs-post)
- [Instagram scraper input schema](https://apify.com/apify/instagram-scraper/input-schema)
- [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp)
