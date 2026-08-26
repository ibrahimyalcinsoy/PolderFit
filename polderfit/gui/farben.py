# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Farbsystem der PolderFit-Oberflaeche nach den Sicherheits-/Signalfarben der
deutschen Maschinen- und Softwarenormen.

Grundlage ist die Bedeutungszuordnung von Farben an Anzeigeelementen in
DIN EN 60073 / IEC 60073 (VDE 0199, "Grund- und Sicherheitsregeln fuer die
Mensch-Maschine-Schnittstelle: Codierungsgrundsaetze fuer Anzeigegeraete und
Bedienteile"), ergaenzt um ISO 3864 / DIN EN ISO 7010 (Sicherheitsfarben) und
DIN EN ISO 9241-112/-125 (Informationsdarstellung; Farbe nie als einziges
Unterscheidungsmerkmal). Die dort festgelegte Bedeutung wird im ganzen Programm
EINHEITLICH verwendet - in Qt-Widgets, Protokoll und Matplotlib-Overlays:

======  ===========================================  ===============================
Farbe   Bedeutung nach DIN EN 60073 / ISO 3864       Verwendung in PolderFit
======  ===========================================  ===============================
ROT     Gefahr, Notfall - schwerer Fehler,           Fit fehlgeschlagen (keine
        sofortiges Eingreifen noetig                 Konvergenz/kein Ergebnis),
                                                     Fehlermeldungen, Ignorier-Seite
GELB    Warnung, anormaler Zustand - Aufmerksamkeit  problematischer Fit (Kriterien
        erforderlich, Pruefung durch den Menschen    verletzt), Warnungen im Protokoll
GRUEN   sicher, normal, in Ordnung                   guter Fit, Neu-Fit-Seite der
                                                     Grenzgeraden, Erfolgsmeldungen
BLAU    Gebot / Hinweis - Handlung des Menschen      aktiver Interaktionsmodus,
        erforderlich bzw. erfolgt, Auswahl           gewaehlte Frequenz, vom Menschen
                                                     bestaetigter Fit (blauer Rand)
GRAU    keine besondere Bedeutung, neutral,          ignorierte Punkte (Ausreisser),
        ausser Betrieb                               nicht gefittet, inaktiv
======  ===========================================  ===============================

Die RGB-Werte sind bildschirmtaugliche Entsprechungen der RAL-Verkehrs-/
Signalfarben (RAL 3020, 1023, 6024, 5017, 7042) - die Normen selbst legen
keine RGB-Werte fest, nur die Bedeutung. Zusaetzlich zu jeder Farbe traegt
jede Statusklasse ein eigenes Symbol (Punkt/Kreuz/Dreieck; siehe
:data:`STATUS_MARKER`), damit auch Menschen mit Farbfehlsichtigkeit die
Klassen unterscheiden koennen (DIN EN ISO 9241-125).
"""

from __future__ import annotations

# --- Signalfarben (Bedeutung siehe Modulkopf) -------------------------------
SIGNAL_ROT = "#D0021B"      # RAL 3020 Verkehrsrot   - Gefahr / schwerer Fehler
SIGNAL_GELB = "#F5B800"     # RAL 1023 Verkehrsgelb  - Warnung / anormal
SIGNAL_GRUEN = "#2E9E4F"    # RAL 6024 Verkehrsgruen - sicher / in Ordnung
SIGNAL_BLAU = "#1F5FBF"     # RAL 5017 Verkehrsblau  - Gebot / Hinweis / aktiv
NEUTRAL_GRAU = "#8C8F94"    # RAL 7042 Verkehrsgrau  - neutral / ignoriert

# Dunklere Varianten fuer Text auf hellem Grund (Kontrast >= 4.5:1, ISO 9241-303).
TEXT_ROT = "#B00016"
TEXT_GELB = "#8A6400"       # "Warngelb" als Text ist auf Weiss unlesbar -> Ocker
TEXT_GRUEN = "#1F7A3A"
TEXT_BLAU = "#174A96"
TEXT_GRAU = "#5F6368"

# Helle Hintergruende der Signalfarben (Hinweisfelder, Zeilenhervorhebung).
HELL_ROT = "#FDE7E9"
HELL_GELB = "#FFF4CC"
HELL_GRUEN = "#E3F4E8"
HELL_BLAU = "#E6EEF9"
HELL_GRAU = "#EEF0F2"

# --- Neutrale Oberflaeche (unbunt, damit die Signalfarben wirken) -----------
FLAECHE = "#F3F4F6"         # Fensterhintergrund
PANEL = "#FFFFFF"           # Panels, Eingabefelder
RAND = "#D0D4DA"            # Rahmen/Trennlinien
RAND_STARK = "#AEB4BC"
TEXT = "#1F2328"            # Standardtext
TEXT_SCHWACH = "#5F6368"    # Nebentext
INAKTIV = "#A6ABB3"

# --- Statusklassen der Fits ----------------------------------------------------
#: Status -> (Fuellfarbe, Randfarbe). Bedeutung: siehe Modulkopf.
#: Randfarbe dunkel: Auf der hellen Resonanzlinie (Viridis gelb/gruen) sind
#: helle Raender unsichtbar - ein dunkler Rand hebt jeden Marker vom Grund ab.
STATUS_FARBEN = {
    "gut": (SIGNAL_GRUEN, "#0B2E14"),
    "bestaetigt": (SIGNAL_GRUEN, SIGNAL_BLAU),
    "problem": (SIGNAL_GELB, "#1F2328"),
    "fehler": (SIGNAL_ROT, "#3A0008"),
    "ignoriert": (NEUTRAL_GRAU, "#1F2328"),
    "nebenmode": ("none", "#0B2E14"),
}
#: Status -> Matplotlib-Marker (Form als zweites Unterscheidungsmerkmal).
STATUS_MARKER = {
    "gut": "o",
    "bestaetigt": "o",
    "problem": "^",
    "fehler": "X",
    "ignoriert": "o",
    "nebenmode": "D",
}
#: Klartext je Status (Legende, Tooltips, Export).
STATUS_TEXTE = {
    "gut": "gut (automatisch)",
    "bestaetigt": "gut (vom Nutzer bestätigt)",
    "problem": "problematisch – prüfen",
    "fehler": "Fit fehlgeschlagen",
    "ignoriert": "ignoriert (Ausreißer)",
    "nebenmode": "weitere Resonanz (Nebenmode)",
}

#: Kurztexte mit Symbol (Status-Chip im Linescan-Panel).
STATUS_KURZ = {
    "gut": "● gut",
    "bestaetigt": "● gut, bestätigt",
    "problem": "▲ problematisch",
    "fehler": "✕ fehlgeschlagen",
    "ignoriert": "● ignoriert",
    "nebenmode": "◇ Nebenmode",
}

#: Farben des Aktivitaetsprotokolls je Meldungsart (gleiche Semantik).
LOG_FARBEN = {
    "info": TEXT_BLAU,
    "ok": TEXT_GRUEN,
    "warn": TEXT_GELB,
    "problem": TEXT_ROT,
    "auto": TEXT_GRAU,
}


#: Farbe je Mode (Zweig) bei mehreren Resonanzen - Grenzgeraden/Baender im
#: Farbplot (Mode 1 = Textfarbe) und Kittel/LLG je Mode (Mode 1 = Signalgruen).
MODE_FARBEN = {2: "#7B2CBF", 3: "#0077B6", 4: "#E36414", 5: "#2A9D8F", 6: "#B5179E"}


def mode_farbe(mode: int, standard: str = SIGNAL_GRUEN) -> str:
    """Farbe der Mode ``mode`` (1 = ``standard``; ab Mode 7 zyklisch)."""
    mode = int(mode)
    if mode <= 1:
        return standard
    farben = list(MODE_FARBEN.values())
    return farben[(mode - 2) % len(farben)]


def status_von(ergebnis, ignoriert: bool = False) -> str:
    """Statusklasse eines :class:`~polderfit.fit.linescan_fit.FitErgebnis`.

    Reihenfolge: ignoriert > nicht gefittet/fehlgeschlagen > vom Nutzer
    bestaetigt > problematisch > gut.
    """
    import numpy as np
    if ignoriert:
        return "ignoriert"
    if not getattr(ergebnis, "gefittet", True):
        return "ignoriert"
    if (not ergebnis.erfolg) or not np.isfinite(getattr(ergebnis, "B_res", np.nan)):
        return "fehler"
    if getattr(ergebnis, "bewertung", "auto") == "bestaetigt":
        return "bestaetigt"
    if ergebnis.problematisch:
        return "problem"
    return "gut"
