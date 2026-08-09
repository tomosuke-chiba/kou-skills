# Speed-first production workflow

Keep image quality constant while removing avoidable image-generation calls.

## Call budget

| State | Action | Image-generation calls |
|---|---|---:|
| Approved outline and passing preflight | Generate first pass | 1 |
| Header is thin, thick, or title is not pure white | Run `normalize_header.py` | 0 additional |
| Several local creative defects exist | Combine them into one precise edit | 1 additional maximum |
| Copy, message, or composition is broadly wrong | Simplify and regenerate once | 1 additional maximum |
| Second generated result still fails | Simplify upstream or stop and report | Never call a third time |

## Prevention before generation

1. Use one conclusion and one dominant visual object.
2. Remove all decorative labels. Every visible string must appear in the ledger.
3. Add this constraint to every prompt: `Text silence: no letters, words, numbers, pseudo-text, signage, or labels inside illustrations, icons, charts, screens, buildings, or clothing unless the exact string is in the ledger.`
4. Explicitly prohibit recurring contamination: standalone `AI` inside brain icons, `DENTAL CLINIC`, chart-axis labels, English signage, logos, and watermark-like marks.
5. Prefer two or three reference images. More references increase contamination risk and processing time.
6. If copy is dense, remove secondary prose before reducing font size. Keep charts symbolic and textless.

## Batch order

1. Freeze every ledger and prompt.
2. Run preflight across the prompt set.
3. Generate all first passes in parallel.
4. Run the header checker across all outputs once.
5. Inspect every image once and write one defect list per slide.
6. Choose exactly one route: accept, deterministic header repair, consolidated edit, or simplified regeneration.
7. Recheck only changed files.

Do not alternate generation and QA slide by slide. Do not repair a header before checking for copy or semantic defects. Do not make separate image edits for separate defects on one slide.

## Review-first handoff

When explicitly requested, complete steps 1–5 and pause before step 6. Preserve all first-pass files unchanged, mark each as `accept` or `needs user-selected revision`, and deliver one consolidated shortlist. Do not run deterministic header repair or a second image-generation call until the user selects the slides.

## Deterministic header repair

Use when the creative body is already good:

```bash
python3 scripts/normalize_header.py input.png \
  --output output-v2.png \
  --title "承認済みタイトルを一字一句そのまま"
```

The script detects the old band, fits the body below a 15% header, redraws the cobalt-to-cyan gradient, and renders the exact title in solid white with a local Japanese bold font. Always run `check_header_ratio.py` on the output.

## Quality-preserving simplification

When a second image-generation call is necessary, simplify the prompt instead of adding more prose:

- repeat the ledger once;
- retain one relationship diagnosis;
- name one decisive object;
- remove decorative scene detail;
- list every correction in one consolidated block;
- keep the text-silence constraint.

This makes the second call easier to satisfy and prevents revision cascades.
