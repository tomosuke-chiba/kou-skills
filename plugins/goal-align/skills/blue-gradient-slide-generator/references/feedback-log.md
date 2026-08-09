# Feedback log

Store reusable, non-sensitive lessons only.

## 2026-07-14 — Explicitly approved

- The user highly rated the cobalt-to-cyan header, selective gradient text emphasis, restrained blue line art, large typography, and dense-but-readable information structure.
- The seven-slide original-app sequence was explicitly rated as excellent.
- Use reference images to infer both visual style and how much information can fit without losing one-slide-one-message clarity.
- Add future user-supplied or generated slides to the reference system only after explicit positive feedback.

## Corrections discovered during QA

- Image models may copy unrequested English signage from references. Explicitly prohibit it and inspect buildings and wall signs.
- Exact-text accuracy improves when secondary copy is removed rather than compressed.
- Semantic details require inspection: post-orthodontic teeth must not retain braces.
- Preserve good layouts with precise-object edits instead of regenerating the entire slide when only one object fails.

## 2026-07-14 — Forward-test correction

- A generation prompt silently added `。` to an approved title and subtitle, and visual QA incorrectly passed it.
- Treat approved copy as a literal character ledger. Never normalize punctuation, and compare visible strings character by character after generation.

## 2026-07-14 — Explicit user correction: thin header

- A generated slide used a header around 10–11% of canvas height, making it visibly thinner than the approved reference system even though the prompt requested 14–16%.
- Treat header height as a measured geometric invariant: target 15%, accept only 14–16%, and reject outliers mechanically before visual QA.
- Never shrink the header to fit a long title or dense body. Adjust title size or upstream copy instead.
- Do not register the rejected slide as a positive reference.

## 2026-07-14 — Explicit praise: adaptive diagram judgment

- The user especially valued three slides that did not mechanically follow a stock template. They judged what relationship needed to be communicated and built a clear diagram around it.
- The praised structures were: an ownership split with a handoff from AI work to human judgment; one central plan artifact connected to four surrounding review points; and a dominant stop gate for irreversible operations followed by AI self-check and human final confirmation.
- Treat the layout catalog as inspiration, not a whitelist. First diagnose the message relationship, then select, combine, or invent the clearest visual sentence.
- Reward semantic clarity over template conformity. A nonstandard composition is preferable when its zones, scale, and arrows make the conclusion understandable within three seconds.

## 2026-07-14 — Explicit praise: progressive geographic zoom

- The user explicitly praised the Hokkaido slide that narrowed a vague direction through `北 → 日本 → 北海道 → 札幌`.
- A progressive geographic zoom works well when each stage uses a recognizable silhouette, one reading direction, and a visibly dominant final destination pin.
- Preserve generous whitespace and large labels so the narrowing relationship is understood before the labels are fully read.

## 2026-07-14 — Explicit correction: header title must stay white

- Slides 04 and 05 applied blue/cyan gradient emphasis to words inside the blue header, reducing contrast and readability.
- Render the entire header title in solid white only. Never color, gradient-fill, or partially recolor any header word, even when that phrase is marked for emphasis elsewhere.
- Limit blue-to-cyan text emphasis to the white body area. Treat any non-white header-title character as a hard QA failure and repair it with deterministic header normalization.

## 2026-07-14 — Explicit correction: production took too long

- Repeated image edits for header geometry and stray labels made a seven-slide batch unnecessarily slow.
- Prevent defects before generation with a literal ledger, text-silence constraints, and prompt preflight.
- Generate the complete first-pass batch before QA, then collect every defect and choose one repair route per slide.
- Fix header height, title color, and exact header rendering deterministically with a local script instead of image generation.
- Limit each slide to one initial generation plus at most one consolidated creative repair. Never fix separate defects through sequential image edits.

## 2026-07-14 — Explicit praise: vehicle analogy and route selection

- The user called the sports-car-to-convenience-store analogy and the model route-selection slide perfect.
- The oversized solution versus tiny destination made wasted capability understandable within three seconds.
- The route-depot composition communicated fit-for-purpose model selection without reducing the models to a simplistic winner ranking.
- Preserve the combination of one dominant illustration, restrained labels, strong directional arrows, and a large bottom conclusion.

## 2026-07-14 — Explicit correction: prompt wall weakened the visual sentence

- The Fable director slide was judged low quality because a large prose prompt dominated the body and reduced the diagram to a generic organizational chart.
- When the message is delegation, show one director supervising specialists who act on a shared artifact. Do not make the instruction text itself the largest object.
- Keep operational prompt wording in the prompt set or companion material; use short role labels on the slide so the ownership relationship is visible before reading.

## 2026-07-15 — Explicit request: parallel first pass before correction

- For a large slide batch, the user may prefer the shortest path to a complete first pass over automatic correction.
- Add a review-first handoff mode: parallelize independent first-pass generation, run one complete QA sweep, preserve imperfect outputs unchanged, and ask the user which slides to revise.
- In this mode, clearly distinguish usable first-pass slides from revision candidates; do not imply that a failed slide is final.

## 2026-07-22 — Explicit praise: palette adaptation without layout drift

- The user explicitly praised a complete warm-brown, camel, ivory, and restrained-gold adaptation of a fifteen-slide batch.
- The successful variant preserved the approved slide order, message, card structure, actor placement, arrow logic, and exact copy while changing the palette and surface tone.
- Treat palette as a separable contract from composition. A color or tone request must not silently trigger a layout redesign.
- Keep non-blue approved examples out of the default blue style board; register them as semantic or palette-variant references so the cobalt system remains stable.

## 2026-07-27 — Explicit beginner readability rule

- When a beginner encounters a new concept, the sequence must explain `what it is` and `why it is needed` before showing the operation.
- Slide count is not a reason to compress body copy. Split dense concepts and keep large seminar-readable text.
- Long execution prompts belong in a companion handout; the slide should show only the operational purpose, input, output, and pre-run check.
