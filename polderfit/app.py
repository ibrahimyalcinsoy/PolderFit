# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Einstiegspunkt der PolderFit-Anwendung.

Startet die grafische Oberflaeche. Aufruf ueber das Konsolenskript ``polderfit``
oder ``python -m polderfit.app``.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Startet die GUI und liefert den Qt-Exit-Code."""
    try:
        from .gui import starte_gui
    except ImportError as exc:  # PySide6 nicht installiert
        print(
            "Die grafische Oberflaeche benoetigt PySide6.\n"
            "Installation:  pip install 'polderfit[gui]'  oder  pip install PySide6\n"
            f"Importfehler: {exc}",
            file=sys.stderr,
        )
        return 1
    return starte_gui(argv)


if __name__ == "__main__":
    raise SystemExit(main())
