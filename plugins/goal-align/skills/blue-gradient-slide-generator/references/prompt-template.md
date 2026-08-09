# Image-generation prompt template

Use this structure for every slide. Remove unused lines rather than leaving placeholders. Run `scripts/preflight_prompt.py` on the complete prompt set before generation.

```text
Use case: productivity-visual
Asset type: polished 16:9 Japanese seminar slide PNG
Input images: reference-board.png is the general style reference; 20260713T170058Z-user-approved-output-f34084a9.png is the authoritative header-height reference; semantic-reference-board.png is optional for adaptive composition. Default to two or three references. Selected images are style references only, not edit targets.
Primary request: Create one slide that communicates this single conclusion: "<one message>".
Relationship diagnosis: <state the semantic relationship in one sentence: ownership split, handoff, checkpoint, stop/go gate, sequence, grouping, comparison, cycle, etc.>

Header text (verbatim, exactly once, one line): "<title>"
Subtitle text (verbatim): "<subtitle>"
Body/card text (verbatim): "<all required strings>"
Bottom conclusion (verbatim): "<conclusion>"

Composition: <name a standard, custom, or hybrid structure>. <Explain why this structure is the clearest visual sentence for the diagnosed relationship. Describe zones, card count, arrow direction, dominant element, and line-art subjects. Do not force the message into a familiar template.>
Style/medium: clean vector-like productivity slide, consistent navy/cobalt line art, white rounded cards with blue outlines.
Header: exactly 15% of canvas height, with an acceptable range of 14–16%; horizontal dark cobalt-to-light cyan background gradient; only the solid-white bold centered title appears inside. Render every title character in identical pure white. Never apply blue, cyan, multicolor, gradient fill, or partial recoloring to header text. Keep this band height fixed even when the title is long. Never compress it to gain body space; reduce title font size while preserving seminar readability.
Background: white or extremely pale blue-white.
Typography: large bold Japanese sans-serif, readable from the back of a seminar room.
Emphasis: in the white body area only, apply dark-blue-to-cyan text gradient to "<phrase 1>", "<phrase 2>", and optionally "<phrase 3>". If any phrase also appears in the header, do not emphasize its header occurrence; the entire header title must remain solid white.
Constraints: render every required Japanese string exactly; no additions, omissions, paraphrases, corrupted characters, or extra labels.
Text silence: no letters, words, numbers, pseudo-text, signage, or labels inside illustrations, icons, charts, screens, buildings, or clothing unless the exact string appears in the COPY LEDGER. Specifically prohibit standalone "AI" inside brain icons, "DENTAL CLINIC", chart-axis labels, English signage, logos, and watermark-like marks.
Avoid: photography, 3D, heavy shadows, colorful accents, logos, page numbers, watermarks, tiny footnotes, unnecessary English, decorative clutter.
Semantic constraints: <state any illustration facts that must be true>.
Three-second test: <state what a viewer must understand from shapes, scale, and arrows before reading the small copy>.
```

Copy the title, subtitle, body, and conclusion directly from the approved outline. Do not normalize punctuation or add sentence-ending `。` when it is absent from the source.

Before the tool call, preserve a literal copy ledger. Do not add decorative strings outside it:

```text
COPY LEDGER
title=<title>
subtitle=<subtitle>
body_1=<body>
conclusion=<conclusion>
```

After viewing the output, transcribe the visible strings and compare them character by character with this ledger. Any punctuation change requires repair.

Before visual approval, run the checker once across the complete batch:

```bash
python3 /absolute/path/to/blue-gradient-slide-generator/scripts/check_header_ratio.py /absolute/path/to/slide-01.png /absolute/path/to/slide-02.png
```

Only `PASS` is acceptable. A 941 px-high slide must report a header between 132 and 151 px. Repair a thin or thick band even if the rest of the slide is strong.

## Repair routing

Do not revise immediately after finding the first defect. Finish the full QA sweep, collect every issue on the slide, and choose one route.

For header height, header-title color, or exact header-title rendering, do not call image generation. Run:

```bash
python3 /absolute/path/to/blue-gradient-slide-generator/scripts/normalize_header.py input.png \
  --output output-v2.png \
  --title "<exact approved title>"
```

For multiple local creative defects, use one consolidated precise edit:

```text
Change only these collected defects: <complete defect list>. Preserve every approved Japanese string, layout, spacing, colors, line weight, and all other elements exactly. Do not introduce new text. Text silence: no new letters or labels inside illustrations.
```

For widespread text or hierarchy errors, regenerate once with fewer secondary strings and the same ledger. Never make a third image-generation call for the slide.
