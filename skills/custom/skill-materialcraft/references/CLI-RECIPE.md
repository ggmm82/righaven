# Native CLI recipe

Run in the assignment staging directory. This smoke check exercises the native graph and export. Adapt the graph and map settings for the brief.

```sh
materialcraft-cli --version
materialcraft-cli commands --filter graph
materialcraft-cli nodes --filter noise
materialcraft-cli new pbr surface.sbs --size 256
materialcraft-cli info surface.sbs
materialcraft-cli export surface.sbs maps --format png --depth 8 --size 256
materialcraft-cli render surface.sbs preview.png --size 256x256 --scene sphere
```

Use `run <input> <command-id> <params-json> -o <out.sbs>` or `batch` for scripted edits. Preserve the graph and imported resource files together. Reopen the delivery from a clean folder and re-export the required channels. Treat `file.exportMaterial` as an optional handoff and verify its format version against the intended reader.
