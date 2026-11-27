---
name: skill-materialcraft
description: "Author and verify editable procedural PBR materials with MaterialCraft's headless CLI. Use for reusable material graphs and texture maps."
---

# MaterialCraft

Use `materialcraft` with `harness_delegate` when the brief calls for a repeatable procedural surface or PBR maps. Use the selected CLI release and [its command map](references/CAPABILITIES.md). Work with a small sample before committing to final resolutions. MaterialCraft authors materials. Mesh modeling, UV layout and final scene rendering belong in the tool already chosen for those jobs.

Confirm the target engine, material scale, resolution, repeatability, normal convention and desired channels. Build the graph with the smallest useful set of exposed controls. Check the result by varying a representative input, inspecting seams and rendering against lighting that reveals roughness and normal errors.

Use the [CLI recipe](references/CLI-RECIPE.md) and the [quality checks](references/QUALITY.md). On v0.4.1, `new` accepts `empty`, `pbr` or `atomics`. Use `commands`, `nodes` and `graph.templates` to inspect the running release before choosing commands or templates.

## Delivery: editable sources and compatibility

Deliver the native `.sbs` with its local resource files, the requested maps, a preview and channel conventions. Record MaterialCraft and the observed CLI version as the opener. Stage a copy with all resources and reopen it with `info` and a fresh `export`. Compare its maps with the original export. Record CLI reopen evidence in the delivery. Exported PNGs and `.mcmat` interchange packages are separate from the editable graph. Claim compatibility with another editor only after a round trip in that editor.
