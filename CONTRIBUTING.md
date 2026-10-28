# Contributing to RigHaven

Thank you for contributing to **RigHaven** (*The Evolving Agent Harness & Open-Source CLI Environment Integrator*).

## Codebase Standards (Non-Negotiable)

1. **100% English Codebase & Documentation**: All Python/TypeScript/JavaScript source code, variable and function names, comments, log messages, configuration files, C4/D2/BPMN/Typst diagrams, and GitHub documentation must be written in professional English.
2. **Native Bilingual UI (i18n)**: Every user-facing string added to the Frontend, Cloud Portal, or Community Gallery must be added to both `/locales/en/common.json` (Default) and `/locales/it/common.json` (100% key parity is enforced by `tests/test_i18n.py`).
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
