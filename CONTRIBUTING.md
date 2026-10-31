# Contributing to RigHaven

Thank you for contributing to **RigHaven** (*The Evolving Agent Harness & Open-Source CLI Environment Integrator*).

## Codebase Standards (Non-Negotiable)

1. **100% English Codebase & Documentation**: All Python/TypeScript/JavaScript source code, variable and function names, comments, log messages, configuration files, C4/D2/BPMN/Typst diagrams, and GitHub documentation must be written in professional English.
2. **Native Bilingual UI (i18n)**: Every user-facing string must exist in Italian and English.
   - Shared labels go in both `/locales/en/common.json` (default) and `/locales/it/common.json`; key parity is enforced by `tests/test_i18n.py`.
   - Text that belongs to one workspace panel is written inline as `tr("Italiano", "English")` from `frontend/ui-text.ts` (or `trMap({...})` for label tables). Every component that shows such text calls `useUiLanguage()` first, so a language change re-renders it.
   - Gateway errors are written once (Italian or English) and translated by `locales/en/errors.json` and `locales/it/errors.json` according to the viewer's locale cookie or `Accept-Language`. `tests/test_error_catalog.py` fails when a raised message has no entry, or an entry is no longer raised.
3. **Zero Legacy Branding**: Never introduce legacy identifiers (`rh-`, `righaven`, and `harness_` are the canonical prefixes).

## Submitting a New Pack to the Community Gallery

1. Author a manifest conforming to `config/righaven-pack.schema.json` (`righaven-pack.json`).
2. Provide complete `i18n.en` and `i18n.it` titles and descriptions.
3. Specify `security_policy` with `"rootless": true` and `"$RIGHAVEN_OUTPUT_DIR"` as the sole writable path.
4. Provide a deterministic `verification_command` for the mandatory `reopen check`.
5. Run the validation and unit test suite before opening a Pull Request:

```bash
python3 scripts/validate.py
python3 scripts/render_capability_docs.py --check
python3 scripts/check_tool_capabilities.py --root .
python3 -m unittest discover -s tests -v
```
