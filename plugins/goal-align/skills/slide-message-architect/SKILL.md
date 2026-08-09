---
name: slide-message-architect
description: Convert spoken notes, transcripts, scripts, briefs, or long-form source material into an optimal slide count and a one-slide-one-message production table. Use when a user asks how many slides content should become, wants a talk split into slide roles and messages, needs final on-slide copy and visual direction, or supplies reference slides whose information density should influence the decomposition.
---

# Slide Message Architect

Turn unstructured source material into an approved slide blueprint before any image or deck production begins.

## Required workflow

1. Read the full source and its surrounding context before proposing a count.
2. If reference slides are supplied, inspect every materially different reference. Estimate their usable density from card count, text groups, visual complexity, whitespace, and type size.
3. Build a first-appearance inventory of concepts that may be new to the audience: tools, skills, files, workflow stages, abbreviations, and technical terms.
4. Extract the audience belief changes, not merely the topics. Label each beat as one of: hook, question, tension, honest limitation, mechanism, analogy, evidence, process, payoff, or conclusion.
5. Determine the recommended slide count with the heuristics in [decomposition-heuristics.md](references/decomposition-heuristics.md).
6. State the recommended count first. Briefly explain why one fewer would overload the message and why one more would fragment it.
7. Write final display copy. Do not leave placeholders or merely summarize what might be written.
8. Return the complete emoji-assisted table defined in [output-contract.md](references/output-contract.md).
9. Run the quality gate before handing off.

## Non-negotiable decisions

- Treat one slide as one audience belief change.
- Keep a deliberate question or tension slide separate when it creates useful suspense.
- Separate a problem analogy from a solution analogy when they do different persuasive jobs.
- Split content when it needs a different visual grammar: comparison, sequence, cause-effect, cycle, or proof.
- Merge beats only when one diagram and one conclusion can express them without competing focal points.
- Use the reference deck to adjust density, never to copy its subject matter blindly.
- Preserve any user-marked exact text verbatim.
- Prefer short, spoken Japanese that can be understood from the back of a seminar room.
- Choose only one to three emphasized phrases per slide.
- For a beginner audience, explain every new concept before asking the audience to use it: first `what it is`, then `why it is needed`, and only then `how to use it`.
- Default to separate `what` and `why` slides. Merge them only when one large diagram and short copy communicate both within three seconds.
- Never protect a target slide count by shrinking type or creating paragraph-heavy slides. Increase the slide count when clarity improves.
- Keep long operational prompts, commands, and detailed checklists out of the slide image. Put the full text in a companion handout or operator guide and show only purpose, input, output, and the pre-run check on the slide.

## Interaction policy

- Make reasonable assumptions when the source and references are sufficient.
- Ask only when a missing choice would materially alter the narrative or number of slides.
- If the user asks only for the slide count, give the count and a compact role/message map first; do not generate images yet.
- If the user approves the blueprint and asks for the blue visual style, hand off to `$blue-gradient-slide-generator`.

## Quality gate

Confirm all of the following:

- Every slide has one distinct role and one declarative message.
- The final display copy supports that message without introducing a second conclusion.
- The central visual can convey the conclusion within three seconds.
- The sequence has a clear before/after relationship between adjacent slides.
- No slide needs more than three emphasized phrases.
- No two adjacent slides repeat the same persuasive job.
- The count reflects the supplied reference density.
- Titles, body copy, and conclusions are written exactly as they should appear.
- Every audience-new concept has a recorded first appearance and is explained with both `what it is` and `why it is needed` before the first action.
- No slide relies on smaller text to preserve the count; dense content has been split.
- Long prompts and commands have a named companion destination and do not dominate the visual sentence.

## Learning from feedback

Use [feedback-log.md](references/feedback-log.md) as durable memory.

- Record explicit praise, approval, or correction that concerns decomposition, count, copy, or visual structure.
- Never treat silence as approval.
- Do not store confidential source text, personal data, patient data, or client identifiers.
- Convert feedback into a reusable principle, not a transcript of the conversation.
- Promote a lesson into this SKILL.md only after repeated evidence or an explicit user instruction that it should become a rule.
- Use [example-original-app.md](references/example-original-app.md) as the initial high-rated example.
