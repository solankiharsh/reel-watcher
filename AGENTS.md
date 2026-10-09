# Reel-watcher

Read README.md for actual behavior and setup, PLAN.md for product scope, and CONTEXT.md for domain terms. Follow relevant installed skills before implementation or review.

## Guardrails

- Use uv. Run `uv run pytest` before and after code changes. Model-enabled commands need `--extra models` so uv retains optional dependencies.
- Paid execution requires the owner's approval of the exact batch and cap. Preview first, at most three new paid downloads, maximum $2 batch cap. Never treat implementation permission as spending approval.
- APIFY_TOKEN is environment-only. Never write it to files, logs, URLs or commits. Never send it to a model process.
- Obtain references from user exports, supplied URLs or local files. No Instagram login, browser cookies or Instagram UI automation.
- Keep model inference local. Model setup downloads are explicit; normal processing must not fetch weights.
- Preserve source evidence. Quotes must match transcript, OCR or caption text; visual observations need sampled timestamps. Label effectiveness explanations as hypotheses.
- Real exports, media, transcripts, studies and weights stay outside version control. Tests and examples use synthetic data only.
- No em dash characters in Python sources.
- Do not publish or push without the owner's approval.

## Verification

HTTP API and CLI are the agreed test seams. Inject models/providers only at their external interfaces, use a real temporary database, and keep test network access blocked. Source tests do not prove model quality or provider reliability. Record real-model and browser verification separately in docs/VALIDATION.md.

## Code ownership

- app.py: loopback browser API and request validation.
- library.py and store.py: workflow state, persistence, previews, retention, profiles and briefs.
- imports.py: canonical URL and saved-export parsing.
- download.py: public downloading and durable capped Apify runs.
- media.py, models.py, model_worker.py and ocr.py: local extraction and inference.
- schema.py: evidence and output validation.
- static/: browser interface without a build toolchain.
- cli.py: CLI entry points, sharing the library workflow.
