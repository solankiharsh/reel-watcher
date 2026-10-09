# Validation record

## Automated and browser checks

- 2026-10-09: 20 HTTP/CLI/provider tests passed. Ruff checks and formatting passed; mypy passed across 13 source files; JavaScript syntax check passed. One upstream Starlette TestClient deprecation warning remains.

- HTTP/CLI tests use synthetic media and fake model/provider interfaces. Covered: import deduplication and persistence; local upload; study evidence validation; media deletion; paid approval and replay prevention; existing Apify run reuse; profile overrides; brief persistence; similarity modes; local-origin protection; readiness before downloads; changed-media preview invalidation; export/dry-run CLI behavior; Whisper NPZ model readiness; Python no-em-dash rule.
- Browser verified on a separate `out/ui-smoke` library: empty library layout, link import, duplicate canonicalization, collection display, batch selection, zero-cost preview and model-readiness error before download. Synthetic URL only. Creator profile fields were saved successfully. The main empty library was verified separately on port 8765. User library remains separate. The final synthetic study card, source timestamp control, hypothesis notice and saved three-hook brief were also verified in the browser.
- Real model and provider validation is recorded below when completed. No paid Apify call is authorized or made by automated tests.

## Review

Separate standards and specification reviews identified completed-media reuse/restoration, failed-download cleanup, fractional-cent caps and restored thumbnails. These were fixed and regression-tested. Follow-up reviews found no blocking issues. Evidence normalization accepts only the known plural frame label and reclassifies quoted frame evidence as OCR only when the exact quotation matches OCR at that sampled timestamp.

## Real local inference

- Apple Silicon M4, 16 GB RAM. Synthetic 2.47-second video with locally synthesized English narration and a title card, no real reel data.
- Apple Vision OCR recovered the title-card text. Whisper-small produced the expected narration with segment timestamps.
- Qwen2-VL 2B generated malformed or schema-incompatible output; a valid response echoed template wording. Brief generation failed the three-hook contract. This model is not considered validated for useful studies or briefs.
- Final preset: Qwen2.5-VL 3B 4-bit with local llguidance JSON constraints. A fresh CLI study completed with the expected transcript, one source-linked observation and two hypotheses. A generated brief passed validation with three distinct non-copied hooks, beats, visual suggestions and a linked local reference.
- Constraints restrict evidence to exact extracted excerpts across each text source and sampled timestamps, and restrict brief IDs to selected studies. They do not prove that an observation follows from its cited evidence.
- Qualitative limits observed: basic hooks, repetitive topic/creative tags, and effectiveness interpretation mixed into observation prose. The UI explicitly labels all effectiveness explanations as hypotheses, including those in observations. Real-reel usefulness and creative quality have not passed pilot acceptance.
- Earlier 2B weights remain in ignored `out/models/vision-2b`; the active default is `out/models/vision`.
- No public Instagram acquisition or paid Apify execution was performed.

## Remaining pilot acceptance

Use 10-20 user-selected English reels from one theme. Review five studies for evidence traceability, find at least three useful related references, and produce one brief the user would actually use. Invented quotations and unsupported observations are failures to fix. This requires the user's real sample and judgment.

## Known limits

- Video-only pilot. Imported carousel links cannot be analyzed as slides.
- Model tags drive explainable lexical matching; semantic retrieval is not claimed.
- Fixed opening and spaced frame samples can miss fast events. No scene-cut completeness claim.
- Transcript timing is at segment level.
- Model output validation rejects unsupported quotations but cannot prove visual or OCR correctness.
- Current user export layout, public Instagram fetching, and real paid Apify execution require separate live validation.
