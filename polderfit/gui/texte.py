# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Anzeige-Uebersetzung der Texte aus dem Fit-Kern (bleiben dort deutsch, weil
sie auch exportiert werden): Problemgruende, Kriterien, Bewertungen."""

from __future__ import annotations

from ..fit.kriterien import kriterien_kurz, kriterien_text
from ..sprache import tr

_VERWORFEN = " (verworfen)"


def gruende_tr(gruende) -> str:
    return ", ".join(tr(g) for g in gruende)


def problem_text_tr(erg) -> str:
    """:attr:`FitErgebnis.problem_text` in der Oberflaechensprache."""
    if erg.bewertung == "bestaetigt" and not erg.problematisch:
        return tr("vom Nutzer als gut bestätigt")
    if erg.bewertung == "verworfen":
        return tr("vom Nutzer als problematisch markiert") + (
            f" ({gruende_tr(erg.problem_gruende)})" if erg.problem_gruende else "")
    return gruende_tr(erg.problem_gruende) if erg.problem_gruende else "OK"


def kriterien_kurz_tr(erg) -> str:
    text = kriterien_kurz(erg)
    if text.endswith(_VERWORFEN):
        return text[:-len(_VERWORFEN)] + tr(_VERWORFEN)
    return tr(text)


def kriterien_text_tr(erg) -> str:
    return "\n".join(tr(zeile) for zeile in kriterien_text(erg).split("\n"))
