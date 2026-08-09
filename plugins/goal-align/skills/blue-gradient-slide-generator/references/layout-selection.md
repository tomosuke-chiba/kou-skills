# Layout selection by message relationship

Choose the diagram after diagnosing the message, not before. Pattern names are starting points, not constraints.

## Decision method

1. Write the conclusion in one sentence.
2. Identify the semantic relationship: comparison, ownership, handoff, sequence, aggregation, checkpoint, hierarchy, cycle, or stop/go.
3. Identify the decisive visual object: person, artifact, gate, destination, or outcome.
4. Arrange zones, scale, and arrows so the relationship is visible before all labels are read.
5. Use a standard pattern only when it is the clearest fit. Otherwise combine or invent a structure.

## Relationship-to-composition guidance

| Relationship | Useful composition | Visual requirement |
|---|---|---|
| Different owners do different work | Split zones with a handoff | Make ownership labels dominant and show the transferred artifact crossing the boundary |
| One artifact must be checked from several viewpoints | Central artifact with surrounding checkpoints | Connect each checkpoint to the exact area it governs; keep the artifact central |
| A dangerous action must pause | Dominant stop gate followed by confirmation stages | Make the stop symbol the focal point; place risky actions before it and confirmation after it |
| Inputs become one prioritized result | Converging funnel or hub | Show many sources narrowing into one ordered output |
| Work advances through stages | Directional sequence | Use a single reading direction and make the completed outcome visually distinct |
| Two approaches differ | Balanced comparison | Keep corresponding elements aligned so the difference is scannable |
| Repetition improves the system | Cycle with a visible return path | Make the feedback or improvement step explicit, not decorative |
| One conclusion matters more than detail | Hero statement with one supporting analogy | Give the conclusion most of the visual weight |

## Approved adaptive examples

### Ownership split plus handoff

Use separate zones for `AI = 集める・整理する・作る` and `人 = 確認する・決める`. Move the work product from the AI zone to the human zone. The layout communicates division of labor and a decision boundary at the same time.

### Central artifact plus four checkpoints

Place the plan or screen in the center and connect `対象`, `変更内容`, `保存先`, and `リスク` around it. This is clearer than four equal cards in a row because all four questions apply to one artifact.

### Dominant stop gate plus final confirmation

Place destructive or external actions around a large stop sign. Continue with `AIの自己確認 → 人の最終確認`. The oversized gate communicates safety before the supporting text is read.

## Three-second test

- Can a viewer identify the main actor or artifact?
- Can a viewer see direction, grouping, or the decision boundary?
- Does the largest element represent the decisive idea?
- Would the layout still make sense if the small labels disappeared?
- Is the custom structure clearer than the nearest standard template?

If any answer is no, redesign the composition before generating.
