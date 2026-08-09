---
name: blue-gradient-slide-generator
description: Generate and quality-check finished 16:9 PNG seminar slides in KOU's cobalt-to-cyan visual system. Use for producing slides from an approved outline, matching approved references, revising existing slide images, or learning from explicit visual feedback.
---

# Blue Gradient Slide Generator

Create finished slide PNGs with an adaptive **visual sentence**, exact Japanese copy, and a one-shot-first production path.

## Required context

Read before generation:

- [speed-first-workflow.md](references/speed-first-workflow.md) — generation budget and failure routing;
- [layout-selection.md](references/layout-selection.md) — relationship diagnosis and composition;
- [style-spec.md](references/style-spec.md) — visual system and header geometry;
- [prompt-template.md](references/prompt-template.md) — normalized prompt and literal ledger;
- [quality-gate.md](references/quality-gate.md) — single-sweep QA;
- [feedback-log.md](references/feedback-log.md) — accepted lessons and failure modes;
- the complete `$imagegen` skill — generation procedure.

Use `assets/reference-board.png` for general style. Add `assets/semantic-reference-board.png` only for adaptive compositions. Use `assets/reference-images/20260713T170058Z-user-approved-output-f34084a9.png` as the header reference. Default to these two or three inputs; add a specialized reference only when it changes a necessary semantic detail, and never exceed five.

If the source is not yet decomposed into approved slides, use `$slide-message-architect` first.

## Time and quality contract

- Budget one initial image-generation call per slide.
- Permit at most one additional consolidated image-generation call when copy, semantics, or composition is materially wrong.
- Never use image generation to repair header height or header-title color. Run `scripts/normalize_header.py` instead.
- Finish the complete first-pass batch before QA. Inspect each slide once, collect every defect, then choose one repair route.
- Never repair defects one at a time through sequential image edits.
- Preserve the existing quality gate; speed comes from prevention, batching, and deterministic repair, not relaxed acceptance.

### Review-first handoff mode

Use this mode only when the user explicitly asks to see the complete first pass before any correction.

- Generate the complete first-pass batch and run the normal single-sweep QA.
- Do not run `normalize_header.py`, regeneration, or image edits during that turn, even when QA finds a hard failure.
- Keep every first-pass image unchanged and label each result `accept` or `needs user-selected revision`.
- Deliver one consolidated revision shortlist with the slide number, visible defect, quality-gate category, and recommended repair route.
- Wait for the user to select which slides to revise. A later revision turn still follows the normal two-call maximum per slide, counting the first pass already made.
- This mode changes repair timing, not the quality standard. Failed slides must never be described as final or approved.

## 1. Lock and preflight

For every slide, record one conclusion, the literal copy ledger, emphasized phrases, relationship diagnosis, decisive visual object, and composition rationale.

Normalize all slide prompts in one prompt-set file. Require text silence inside illustrations: no lettering on brains, buildings, signs, charts, clothing, screens, or icons unless that exact string appears in the ledger.

For beginner-facing decks, verify before preflight that each new concept has already been introduced with `what it is` and `why it is needed`. If not, return to `$slide-message-architect` and split the sequence before generation.

Do not render long operational prompts, commands, or dense checklists as slide-body text. Move the full text to a named companion handout and keep only purpose, input, output, and the pre-run check on the slide. If copy is unreadable at seminar distance, split the slide instead of reducing type size.

Run before any expensive generation:

```bash
python3 scripts/preflight_prompt.py <prompt-set.md>
```

Resolve every `FAIL`. Treat warnings as density risk: remove decorative copy, shorten secondary text upstream, or simplify the composition before generation.

Completion criterion: every slide has one conclusion, a character-exact ledger, one visual sentence, and a passing preflight.

## 2. Generate the first pass once

Inspect only the selected references with `view_image`. Generate one finished image per slide with built-in image generation and the normalized prompt. For four or more slides, parallelize independent calls when agents are available, sharing the same prompt set and style contract.

Do not start revisions while other first-pass slides are still generating. Save project-bound outputs under `output/imagegen/<descriptive-slug>/` with versioned names.

Completion criterion: every approved slide has exactly one first-pass PNG and one normalized prompt before QA starts.

## 3. Run one QA sweep and route failures

Measure the whole batch in one command:

```bash
python3 scripts/check_header_ratio.py <slide-01.png> <slide-02.png> <slide-03.png>
```

Inspect every first-pass image once with `view_image`. Transcribe visible strings against the ledger and apply [quality-gate.md](references/quality-gate.md). Record all defects before modifying anything.

When review-first handoff mode is active, stop after recording and classifying the full defect list. Do not execute any repair route until the user selects the slides to revise.

Route repairs:

- Header ratio, header-title color, or header-title rendering: run `scripts/normalize_header.py`; use zero additional image-generation calls.
- Broad message, hierarchy, semantic, or body-copy failure: issue one simplified regeneration containing all corrections.
- Small creative defect that cannot be repaired deterministically: issue one consolidated precise edit containing every defect on that slide.
- A third image-generation call is prohibited. If the second result still fails, simplify the slide upstream or report the blocker.

After repair, run the mechanical checker again and inspect only the changed final once.

Completion criterion: every final is 16:9, reports a 14–16% header, matches the ledger, uses an all-white header title, passes the quality gate, and communicates within three seconds.

## 4. Learn and deliver

Register a non-sensitive image only after explicit user praise or approval:

```bash
python3 scripts/register_reference.py \
  --image /absolute/path/to/approved-slide.png \
  --source user-approved-output \
  --rating 5 \
  --feedback "Reusable reason this slide worked" \
  --tags "relationship,composition,semantic-purpose" \
  --approved
```

Record rejected-output lessons in [feedback-log.md](references/feedback-log.md) without adding rejected images to the positive board.

Deliver final paths, prompt-set path, consolidated revisions, header results, and confirmation that built-in image generation was used.

## Runtime routing

- **Codex**: execute this skill directly. Image generation uses the built-in `$imagegen` skill as described above.
- **Claude Code** (no `$imagegen` available): never attempt image generation yourself. Delegate the entire generation batch to Codex in one foreground call: run `codex exec` from a trusted git directory with `< /dev/null` and an explicit timeout, embedding the approved slide table and the instruction to use `$blue-gradient-slide-generator`. Receive the output PNG paths, then perform review and hand the results back to the user. Do not re-implement the visual system in another tool.
