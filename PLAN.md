# Reel-watcher MVP plan

Status: Product decisions agreed through the planning interview. Implementation authorized on 2026-10-07, including FastAPI, SQLite, a lightweight browser UI, and HTTP/CLI test seams. See README.md for delivered behavior and docs/VALIDATION.md for verification limits. Historical proposed slices below are retained as planning context.

## Problem and outcome

Saved reels are difficult to revisit, compare, and turn into original content. The initial collection is about AI, with other topics supported rather than hard-coded out.

Build a personal local browser library that lets the user understand hooks and creative techniques, retrieve related examples from their own collection, and develop an original content brief. Knowledge extraction supports this workflow; a cross-reel advice library is deferred.

## Agreed boundaries

- Use uv for Python package and environment management.
- Keep model analysis local; no hosted LLM or paid analysis API dependency.
- No Instagram login, browser cookies, or Instagram UI automation.
- Accept pasted links, the user's official saved-data export, and local video uploads.
- Media acquisition providers remain undecided. Apify is a candidate, not a dependency decision.
- Never incur download charges without explicit approval for the reviewed batch and cost limit.
- Tokens come from the environment only, never chat, files, logs, URLs, or commits.
- Do not publish or push without owner approval.
- Keep real media, transcripts, exports, and study output out of version control. Use synthetic fixtures in tests.
- Pilot language: English.
- Pilot size: 10-20 varied reels from one theme. This is a target sample, not a claim about the user's backlog size.

## User journey

1. Import links, a saved-data export, or local videos into a preview queue.
2. Select a batch. Review which items require downloads, the estimated charge, and the enforced spending limit before approving paid acquisition.
3. Process the selected items locally. Reuse completed studies, surface failures clearly, and allow individual retries.
4. Browse and filter the library, open a study, and inspect its supporting excerpts or timestamps beside retained media.
5. Explore Same subject or Similar creative approach results, each with an explanation of the match.
6. Select references and use a reusable creator profile, with per-brief overrides, to generate a content brief.
7. Review three original hook options, a beat outline, visual suggestions, and the references informing those suggestions.
8. Inspect storage usage and optionally delete retained video while preserving its study and original source link where one exists.

## Study contract

A study emphasizes hook wording and delivery, opening visuals, content structure, the promise to the viewer, supporting evidence, CTA, and adaptable creative techniques.

Key observations must include timestamps or source excerpts. Preserve source identity and distinguish speech, on-screen text, and caption evidence. Explanations of effectiveness are hypotheses, never causal claims inferred from engagement numbers. Do not invent quotations or references. Missing or uncertain information must remain visibly uncertain.

Keep creator agreement separate from evidence quality. Do not convert repetition into a truth score. These distinctions apply to individual studies even though aggregate advice scoring is deferred.

The schema in the supplied notes is a starting point, not an approved field-by-field contract. Exact fields and validation rules require technical design.

## Failure and retention behavior

- A failed download remains in the library with its URL, a clear reason, and actions to retry or attach a local file.
- An alternative download provider may be attempted only within an approved cost limit. Provider choice and enforcement feasibility must be validated first.
- Caption-only material must never be represented as a full video study.
- Retain pilot media and show storage consumption.
- Deleting media must preserve the study and available source link. The UI must reflect that local playback is no longer available.
- Retry behavior must not silently repeat paid downloads or discard successful analysis.

## MVP scope

Included: import preview queue, selected processing batches, cost review, resumable individual studies, local browsing and filtering, evidence inspection, two similarity views, reusable profiles with overrides, original briefs, media retention controls, and visible failures.

Deferred: public reel discovery, aggregated advice principles and strength rankings, standalone giveaway features, full scripts, video generation, publishing, and non-English support. CTA observations remain in scope.

## Proposed implementation sequence

These are proposed work slices, not permission to start building.

### 1. Validate feasibility and choose the technical design

Read-only checks: Mac architecture, available memory, disk capacity, and installed tools. Research current primary documentation for acquisition providers, export formats, local model compatibility, and cost-cap semantics. Verify model names and licenses before selecting them.

Present decisions for model selection, media acquisition, local storage, browser/backend integration, and similarity matching. Do not silently settle consequential architecture choices. The quoted $0.002 per reel, model download sizes, 32 GB cutoff, and processing-time estimates are unverified starting claims.

Exit: a reviewed technical design and an explicit plan for any downloads or paid experiments.

### 2. Prove one local-video study

Establish the uv project and synthetic tests. Implement a local-file path through media inspection, transcription, visual evidence extraction, and validated study output. Test actual model quality separately from mocked automated tests.

First-time dependencies and model weights require network access even though inference stays local. Explain download sizes before downloading. Only describe a run as offline after its dependencies and weights are available.

Exit: one user-provided local video produces a study whose key observations can be checked against its source.

### 3. Deliver the local library and import queue

Add the local browser experience, upload and link/export imports, preview selection, processing status, study inspection, storage usage, and media deletion that preserves studies.

Exit: the core journey works on local media, including failure and retention paths.

### 4. Add approved remote acquisition

Integrate the selected provider and any validated fallback. Show the exact batch count, estimate, and cap before paid processing. Record actual charges where the provider exposes them.

The supplied notes conflict on a first paid batch of three versus five. Proposed resolution: start with at most three after specific cost approval, then review before expanding toward the pilot target. No paid execution is currently authorized.

Exit: duplicate imports, failed fetches, retries, and spending limits behave as designed.

### 5. Add similarity and original briefs

Implement the two distinct similarity views with match explanations. Add profile reuse and per-brief overrides. Generate briefs from selected references with three original hook options, a beat outline, visual suggestions, and linked sources.

Exit: the user can move from a study to related references to a usable original brief.

### 6. Run the pilot and decide what to improve

Use 10-20 varied English reels from one theme. Review five studies, inspect matches, and create one brief. Record quality failures and prioritize fixes before adding deferred capabilities.

## Acceptance checks

Product acceptance agreed by the user:

- Review five studies from the pilot and trace their key observations to source evidence.
- Find at least three useful related references within the collection.
- Produce one brief the user would actually use.
- Treat invented quotes or unsupported observations as failures to fix.

Proposed behavioral checks for implementation:

- Import preview and dry runs cannot trigger paid fetching.
- Local uploads do not invoke a remote media provider.
- Retry and resume preserve completed work and respect approved spending.
- Failed acquisition offers an actionable recovery path.
- Source references remain attached through study and brief generation.
- Profile overrides affect the current brief without unexpectedly changing the saved profile.
- Media deletion preserves studies and does not leave a working-playback claim.
- Synthetic automated tests require neither network access nor real models; model quality receives separate manual evaluation.
- Once a test suite exists, run uv run pytest before and after code changes. Preserve the supplied no-em-dash Python-source convention.

## Remaining validation and decisions

- Hardware and practical local-model performance have not been checked.
- Export contents and preservation of Instagram collections need validation against a user-provided export.
- Carousel support, filtering details, profile fields, and the scope of retained derived images need explicit treatment during technical design; do not assume they are already implemented or settled.
- Provider pricing, reliability, fallback charging, and hard cost-cap behavior remain unverified.
- Model choices, frame-sampling strategy, matching method, storage schema, and UI framework remain open.
- The supplied file map and CLI commands describe intended direction, not existing code.

## Next checkpoint

Confirm that this consolidated plan matches the intended product, including the proposed maximum of three reels for the first paid sample. Then perform feasibility research and return with the technical design decisions. Implementation and paid execution require their own authorization.
