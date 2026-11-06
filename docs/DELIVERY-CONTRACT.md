# Capability selection and delivery

Project roles are compiled from the current request, authorized methods and tool skills. `harness_skills` exposes the owner's environment profiles and authorized tool catalog, without preparing software or granting permissions. Select only capabilities needed for the task. The runtime can reuse a compatible prepared image; a profile is not a mandatory list of tools to execute. A role with no selected tools or methods must explicitly explain its base-runtime choice in `capability_rationale`.

Global skill disables take precedence over saved environment selections. Definitions retain those selections so a future explicit re-enable can restore them, but the configuration shows disabled skills unchecked and unavailable. A method requiring a disabled tool is inactive too. Existing images may still contain the installed binaries; their presence does not authorize agents to use them. Disabling a skill is not a request to delete cached software.

## The product and its source

Use `delivery.files[].primary: true` to identify one final product. An editable native document can be both product and source; no duplicate export is required. Without an explicit primary, exports remain the default, followed by a single unambiguous editable source. Reports and previews never become the final product automatically. Multiple editable files require an explicit choice.

DOCX, XLSX and PPTX receive bounded structural validation of the ZIP, XML vocabulary, content types and internal relationships. Missing linked assets or invalid packages block delivery. Structural validation does not certify layout, spreadsheet calculations, visual quality or reopening in Word/Excel/PowerPoint. Unavailable native checks and their limitations remain visible, and any corresponding request-specific acceptance criteria must still pass independently.

Failed optional environment probes can use `checks[].scope: environment` when an actual working alternative was used. Preserve their evidence. Product defects must remain current failed checks. A passed separate review triggers completion only through the existing file-hash, source, contract and media gates, with no pending/running/failed work. It does not override unavailable required observations or approve partial experiments.

## Model and preparation controls

After **Load available models**, choose from the visible **Available models** select. The model ID remains editable for endpoints supporting additional IDs. Official account login and model assignment remain separate actions.

An HTTP 404 during environment preparation means the referenced release file was not found, rather than a failed native application test. The failure card names the affected tool. After installing the corrected release, retry preparation of the failed environment; do not delete unrelated ready environments.
