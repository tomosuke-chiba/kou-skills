# Blue gradient slide style specification

## Canvas and header

- Format: 16:9 landscape.
- Header: 14–16% of slide height, targeting 15%. This is a geometric requirement, not a visual suggestion.
- For a 941 px-high output, the header must be 132–151 px tall; target 141 px. For a 1080 px-high output, it must be 151–173 px; target 162 px.
- Never make the header thinner to accommodate body content or a long title. Reduce title size within seminar-readable limits or revise the approved copy upstream.
- Gradient: dark cobalt blue on the left to bright light blue/cyan on the right.
- Header copy: exactly one solid-white bold centered title, kept on one line.
- Render every header-title character in the same solid white. Never apply blue/cyan color, gradient fill, partial recoloring, or emphasized color to any word inside the blue header.
- The cobalt-to-cyan gradient belongs to the header background only, never to the title text.
- No subtitle, note, logo, or page number inside the header.

After generation, run `python3 scripts/check_header_ratio.py <image>`. A result outside 14–16% is a hard failure. Repair it with `scripts/normalize_header.py`; never spend another image-generation call on header geometry or title color.

Use `assets/reference-images/20260713T170058Z-user-approved-output-f34084a9.png` as the authoritative header-height reference. Other references may inform illustration or density, but must not override its band thickness.

## Background and palette

- Main background: white or a barely blue-tinted white.
- Normal copy: very dark navy or black.
- Primary lines: cobalt and navy.
- Body-area highlight copy may use a dark-blue-to-cyan gradient. Never use this treatment inside the header.
- Avoid unrelated accent colors.

## Typography

- Use bold Japanese sans-serif typography.
- Use large type readable at seminar distance.
- Maintain a clear hierarchy: header title, subtitle, card headings, supporting copy, conclusion.
- Highlight only one to three important phrases in the white body area. The header title is excluded from phrase highlighting and always remains solid white.
- Keep exact copy intact; reduce secondary copy before reducing font size.

## Visual grammar

- Use consistent blue/navy line art for people, icons, teeth, apps, documents, arrows, and frames.
- Use one stroke family throughout a slide.
- Use white rounded cards with clean blue outlines.
- Use thick blue arrows with clear direction.
- Make the decisive element visibly larger.
- Start from familiar structures such as comparison, process, cause-effect, loop, or hero, but do not treat them as a fixed template catalog.
- Diagnose the semantic relationship first. Use a custom or hybrid composition when it makes ownership, handoff, checkpoints, risk, or decision boundaries clearer.
- Build a visual sentence with a readable subject, action, and consequence. The viewer should understand the direction and decision logic before reading all supporting copy.
- Use shape hierarchy to encode meaning: a dominant gate for a stop condition, a central artifact for surrounding checks, or separated zones for different owners.

## Density target

The bundled references are dense but readable. A slide may contain:

- two large cards with one shared conclusion;
- three process cards with one shared conclusion;
- one central cycle with up to three labeled stages;
- one strong analogy with a dominant statement.

Do not use density to introduce a second message.

## Avoid

- Photography, photorealistic rendering, or 3D.
- Heavy shadows, glossy effects, or colorful decoration.
- Multiple unrelated fonts or stroke weights.
- Tiny annotations and long disclaimers.
- Unrequested English on buildings, clothing, screens, or signs.
- Generic stock icons that break the line-art system.
