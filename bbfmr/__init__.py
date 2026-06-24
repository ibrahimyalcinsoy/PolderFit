"""bbFMR – Breitband-FMR-Auswertung (Portierung von LabVIEW nach Python).

Das Paket gliedert sich in klar getrennte Schichten:

* :mod:`bbfmr.io`         – Einlesen/Schreiben von TDMS, interne Datenstruktur
* :mod:`bbfmr.physik`     – Konstanten, Polder-Suszeptibilitaet, Fitmodell, Kittel/LLG
* :mod:`bbfmr.fit`        – AutoWindows, Einzel-Linescan-Fit, Stapelverarbeitung
* :mod:`bbfmr.persistenz` – Export der Fitparameter, Sitzungszustand
* :mod:`bbfmr.auswertung` – uebergreifende Plots (Resonanz vs. T / f, Kittel, LLG)
* :mod:`bbfmr.gui`        – interaktive PySide6-Oberflaeche
"""

__version__ = "0.1.0"
