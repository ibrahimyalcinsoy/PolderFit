# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Sammelt alle zu uebersetzenden Oberflaechentexte (Pruefung der Vollstaendigkeit).

Quellen: erste Argumente von ``tr(...)``/``N_(...)`` in allen Modulen des Pakets
sowie Texte aus dem Fit-Kern, die erst bei der Anzeige uebersetzt werden.
Aufruf ``python -m polderfit.gui._uebersetzung_schluessel`` listet fehlende
englische Eintraege.
"""

from __future__ import annotations

import ast
from pathlib import Path

PAKET = Path(__file__).resolve().parents[1]


def _literal(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def quelltext_schluessel() -> set[str]:
    schluessel: set[str] = set()
    for datei in PAKET.rglob("*.py"):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for node in ast.walk(baum):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("tr", "N_") and node.args):
                text = _literal(node.args[0])
                if text is not None:
                    schluessel.add(text)
    return schluessel


def kern_schluessel() -> set[str]:
    """Texte des Fit-Kerns/der Einlese-Module, die die GUI mit tr() anzeigt."""
    from ..fit.kriterien import GRUND_NICHT_GEFITTET, KRITERIEN_GRUPPEN
    from ..fit.linescan_fit import BEWERTUNG_TEXTE
    from ..io.kanal_mapping import ROLLEN
    from ..persistenz.einstellungen import FARBSKALEN
    from ..persistenz.ergebnis_export import SPALTEN_GRUPPEN
    from ..verarbeitung import ANZEIGE_MODI

    texte = set(KRITERIEN_GRUPPEN)
    texte |= {titel for _k, titel in KRITERIEN_GRUPPEN.values()}
    texte |= {GRUND_NICHT_GEFITTET, "bestätigt", "alle Kriterien erfüllt", " (verworfen)",
              "Zu wenige gute Punkte fuer den Kittel-/LLG-Fit (min. 3)."}
    texte |= set(BEWERTUNG_TEXTE.values())
    texte |= {r.label for r in ROLLEN}
    texte |= set(FARBSKALEN.values())
    texte |= set(ANZEIGE_MODI.values())
    texte |= {titel for titel, _spalten in SPALTEN_GRUPPEN.values()}
    return texte


def alle_schluessel() -> set[str]:
    return quelltext_schluessel() | kern_schluessel()


def fehlende() -> list[str]:
    from .uebersetzung_en import EN
    return sorted(k for k in alle_schluessel() if k not in EN)


if __name__ == "__main__":
    for k in fehlende():
        print(repr(k))
