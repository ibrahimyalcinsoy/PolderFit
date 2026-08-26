# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Einstiegspunkt der PolderFit-Anwendung.

Startet die grafische Oberflaeche. Aufruf ueber das Konsolenskript ``polderfit``
oder ``python -m polderfit.app``.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Startet die GUI und liefert den Qt-Exit-Code."""
    # Der Fit laeuft in einem Thread und haelt den GIL fast dauernd; mit dem
    # Standard-Wechselintervall (5 ms) wartet jeder GUI-Schritt bis zu 5 ms -
    # 1 ms haelt die Oberflaeche reaktionsfaehig (Kosten fuer den Fit: gering).
    sys.setswitchinterval(0.001)
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
