"""Allow ``python -m righaven_core.tui`` to launch the workbench."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
