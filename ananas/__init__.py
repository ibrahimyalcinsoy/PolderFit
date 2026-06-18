"""Ananas – Breitband-FMR-Auswertung (Portierung von LabVIEW nach Python).

Das Paket gliedert sich in klar getrennte Schichten:

* :mod:`ananas.io`         – Einlesen/Schreiben von TDMS, interne Datenstruktur
* :mod:`ananas.physik`     – Konstanten, Polder-Suszeptibilitaet, Fitmodell, Kittel/LLG
* :mod:`ananas.fit`        – AutoWindows, Einzel-Linescan-Fit, Stapelverarbeitung
* :mod:`ananas.persistenz` – Export der Fitparameter, Sitzungszustand
* :mod:`ananas.auswertung` – uebergreifende Plots (Resonanz vs. T / f, Kittel, LLG)
* :mod:`ananas.gui`        – interaktive PySide6-Oberflaeche
"""

__version__ = "0.1.0"
