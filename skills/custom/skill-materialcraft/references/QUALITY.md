# Material quality

- Check scale, texel density and repeat seams on a tiled plane. Check highlights and roughness on a sphere.
- Document channel names, bit depth, color versus data textures, normal handedness and any channel packing. Confirm them with the destination tool.
- Verify base color is free of baked lighting when the material is intended for PBR. Check normal orientation, roughness range and whether height is intended for bump or displacement.
- Reopen the packaged graph with its resources and regenerate the maps. Verify dimensions and compare representative pixels, then review the actual preview against the brief.
