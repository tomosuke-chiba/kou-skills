# Slide quality gate

Apply every relevant check to every generated or revised slide.

Run one QA sweep after the complete first-pass batch. Record all defects before any repair.

## Message and visual sentence

- The slide communicates one conclusion.
- Title, diagram, and bottom conclusion reinforce that conclusion.
- The composition expresses the actual relationship: comparison, ownership, handoff, sequence, checkpoint, grouping, cycle, or stop/go.
- Major shapes, scale, and arrows reveal the relationship before small labels are read.
- A custom or hybrid layout is used when it explains the relationship faster than a standard pattern.

## Copy

- Every required string matches the literal copy ledger character for character, including punctuation and full-width symbols.
- Visible text contains no unapproved labels or incidental English.
- Typography is unclipped and readable at seminar distance.
- Gradient emphasis is limited to one to three decisive phrases in the white body area only.

## Visual system

- The bundled header-ratio checker reports PASS: 14–16% of canvas height, targeting 15%.
- The header contains one centered title rendered entirely in solid white on the cobalt-to-cyan background gradient.
- No header-title character uses blue, cyan, multicolor, gradient fill, or partial recoloring. Any colored header text is a hard failure.
- Background, cards, arrows, icons, and line art match [style-spec.md](style-spec.md).
- The decisive element is larger than supporting elements.
- Whitespace and margins remain consistent across the sequence.

## Semantic illustration

- Actors, artifacts, arrows, and states match the copy precisely.
- Completion states look complete; before/after states are visually distinct.
- Decision boundaries, checkpoints, and confirmation stages appear in the intended order.
- Domain facts remain credible, such as completed orthodontic treatment showing no braces.

## Output hygiene

- The canvas is 16:9.
- The final contains no unintended logo, page number, watermark, photograph, 3D element, or tiny footnote.
- The saved final and normalized prompt use stable, descriptive paths.

Any failed item keeps the slide in revision.

## Speed-safe failure routing

- Header ratio, header-title color, or title rendering: use `normalize_header.py`; do not call image generation.
- Broad message, copy, hierarchy, or semantic failure: simplify and regenerate once.
- Several local creative defects: combine them into one precise edit.
- Recheck only changed files after repair.
- Never make sequential image edits for separate defects, and never exceed two image-generation calls per slide.
