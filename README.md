# bbFMR – Auswertung breitbandiger FMR-Messungen

bbFMR dient der quantitativen Auswertung breitbandiger ferromagnetischer
Resonanzmessungen (bbFMR). Das Programm liest die TDMS-Rohdaten des Messplatzes ein,
bestimmt je Frequenz das Resonanzfenster, passt das komplexe Transmissionssignal an
die Polder-Suszeptibilität an und gewinnt aus der Dispersion `B_res(f)` sowie der
Linienbreite die Materialgrößen (effektive Magnetisierung `μ0Meff`, Landé-Faktor `g`,
Gilbert-Dämpfung `α`).

Die Bedienung erfolgt wahlweise über eine grafische Oberfläche oder programmatisch
aus Python heraus. Die vollständige Beschreibung des Aufbaus, der physikalischen
Modelle und der Fehlersuche befindet sich im Verzeichnis [`docs/`](docs/).

---

## Installation

Die Installation gliedert sich in drei Schritte, die auf allen Plattformen identisch
sind:

1. **Systemwerkzeuge bereitstellen** – Python (Version 3.11 oder neuer) und Git.
2. **Quelltext beziehen** – Herunterladen der jeweils neuesten Fassung per `git`.
3. **Programmumgebung einrichten** – Anlegen einer gekapselten virtuellen Umgebung
   und Installation von bbFMR samt grafischer Oberfläche.

Die nachfolgenden Abschnitte führen diese Schritte für die einzelnen Betriebssysteme
vollständig aus. Es genügt, den zur eigenen Plattform passenden Block von oben nach
unten abzuarbeiten.

> **Hinweis zum Bezugspunkt.** In allen Anleitungen wird der Quelltext per
> `git clone` aus dem öffentlichen HTTPS-Endpunkt bezogen. Dieses Verfahren liefert
> stets den aktuellen Stand des Hauptzweiges und erlaubt es, spätere Aktualisierungen
> mit einem einzigen Befehl (`git pull`) nachzuziehen (siehe Abschnitt
> [Aktualisierung](#aktualisierung)).

### Windows 11

Für Anwenderinnen und Anwender ohne Vorkenntnisse steht eine ausführliche,
bebildert kommentierte Schritt-für-Schritt-Fassung bereit:
**[INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md)**. Der folgende Block fasst
denselben Weg kompakt zusammen.

**(a) Python und Git installieren** – einmalig:

- **Python 3.11+**: Installationsprogramm von <https://www.python.org/downloads/windows/>
  herunterladen und ausführen. Im Installationsfenster zwingend das Kontrollkästchen
  **„Add python.exe to PATH"** aktivieren; andernfalls sind die folgenden Befehle
  nicht auffindbar.
- **Git für Windows**: Installationsprogramm von <https://git-scm.com/download/win>
  herunterladen und mit den Standardeinstellungen ausführen.

Anschließend eine **neue** Eingabeaufforderung (Startmenü → `cmd`) öffnen und die
Verfügbarkeit prüfen:

```bat
python --version
git --version
```

Beide Befehle müssen eine Versionsnummer ausgeben.

**(b) Quelltext beziehen und Umgebung einrichten:**

```bat
cd %USERPROFILE%
git clone https://github.com/ibrahimyalcinsoy/bbFMR.git
cd bbFMR
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[gui]"
```

Nach erfolgreicher Aktivierung der virtuellen Umgebung steht `(.venv)` am
Zeilenanfang. Die abschließende Installationsmeldung lautet sinngemäß
`Successfully installed bbfmr-0.1.0 ...`.

> **Ausführungsrichtlinie (PowerShell).** Wird statt der Eingabeaufforderung
> *PowerShell* verwendet und die Aktivierung mit der Meldung
> *„running scripts is disabled"* abgewiesen, ist die Skriptausführung für den
> eigenen Benutzer einmalig freizugeben:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```
> Danach `.\.venv\Scripts\Activate.ps1` erneut ausführen. Die Eingabeaufforderung
> (`cmd`) ist von dieser Einschränkung nicht betroffen.

### Fedora

Systemwerkzeuge installieren, Quelltext beziehen, Umgebung einrichten:

```bash
sudo dnf install -y python3 python3-pip git

cd ~
git clone https://github.com/ibrahimyalcinsoy/bbFMR.git
cd bbFMR
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[gui]"
```

### Debian

Unter Debian (und davon abgeleiteten Distributionen wie Ubuntu) ist das Paket
`python3-venv` gesondert zu installieren, da die Standardinstallation das Modul zum
Anlegen virtueller Umgebungen nicht enthält:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

cd ~
git clone https://github.com/ibrahimyalcinsoy/bbFMR.git
cd bbFMR
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[gui]"
```

> **Qt-Systembibliothek.** Öffnet sich unter Debian 12 das Programmfenster nicht und
> erscheint die Meldung *„could not load the Qt platform plugin xcb"*, fehlt eine
> Systembibliothek der grafischen Oberfläche. Sie wird mit
> `sudo apt install -y libxcb-cursor0` nachinstalliert.

---

## Start

Nach erfolgreicher Installation und **aktivierter** virtueller Umgebung wird die
grafische Oberfläche gestartet mit:

```bash
bbfmr
```

Gleichbedeutend, etwa zur Fehlersuche bei Startproblemen, ist der modulbasierte
Aufruf:

```bash
python -m bbfmr.app
```

Ist die grafische Oberfläche (`PySide6`) nicht installiert, gibt das Programm einen
erläuternden Hinweis samt nachzuholendem Installationsbefehl aus.

**Erneuter Start in einer späteren Sitzung.** Python, Git und die Programmumgebung
sind dann bereits vorhanden; es genügt, in das Projektverzeichnis zu wechseln, die
virtuelle Umgebung zu aktivieren und das Programm aufzurufen:

```bat
:: Windows 11
cd %USERPROFILE%\bbFMR
.venv\Scripts\activate
bbfmr
```

```bash
# Fedora / Debian
cd ~/bbFMR
source .venv/bin/activate
bbfmr
```

### Programmatische Nutzung

Die Auswertung lässt sich auch ohne grafische Oberfläche aus Python heraus
ansteuern; dies eignet sich für eigene Auswerteskripte:

```python
from bbfmr.io.tdms_laden import lade_tdms
from bbfmr.fit.batch import fitte_alle

datensatz = lade_tdms("Messung.tdms")   # Format wird automatisch erkannt
stapel = fitte_alle(datensatz)          # AutoWindow + Fit über alle Frequenzen
```

---

## Aktualisierung

Eine neuere Programmfassung wird durch Abgleich mit dem HTTPS-Endpunkt bezogen.
Dazu in das Projektverzeichnis wechseln, den aktuellen Stand abholen, die virtuelle
Umgebung aktivieren und die Abhängigkeiten auffrischen:

```bat
:: Windows 11
cd %USERPROFILE%\bbFMR
git pull
.venv\Scripts\activate
pip install -e ".[gui]"
```

```bash
# Fedora / Debian
cd ~/bbFMR
git pull
source .venv/bin/activate
pip install -e ".[gui]"
```

---

## Dokumentation

Die vollständige Beschreibung des Aufbaus, der physikalischen Modelle, der
einstellbaren Parameter und der Fehlersuche befindet sich im Verzeichnis `docs/`
(Format nach Art von ReadTheDocs). Die HTML-Fassung wird mit
[MkDocs](https://www.mkdocs.org/) erzeugt:

```bash
pip install mkdocs && mkdocs serve   # Vorschau unter http://127.0.0.1:8000
```

| Kapitel | Inhalt |
|---|---|
| `docs/index.md` | Überblick und Auswertekette |
| `docs/installation.md` | Installation, Start, Tests |
| `docs/datenformate.md` | TDMS-Formate (sortiert/unsortiert), Datenmodell |
| `docs/pipeline.md` | Ablauf: Laden → AutoWindow → Fit → Bewertung |
| `docs/autowindow.md` | automatische Resonanzbestimmung |
| `docs/physik-und-fit.md` | Suszeptibilität, S21-Modell, Kittel/LLG, Quellen |
| `docs/bewertung.md` | Gütemaße und Problem-Einstufung |
| `docs/tuning.md` | sämtliche einstellbaren Parameter |
| `docs/troubleshooting.md` | typische Fehlerbilder |
| `docs/test-harness.md` | Robustheitsprüfung über reale Messdaten |

---

## Architektur

```
bbfmr/
  io/          Einlesen/Schreiben TDMS, Datenstruktur (Linescan, Messdatensatz)
  physik/      Konstanten, Polder-Suszeptibilität, Fitmodell, Kittel/LLG
  fit/         AutoWindow, Einzelfit (lmfit), Stapelverarbeitung, Bewertung
  auswertung/  Resonanz vs. f/T, Kittel-/LLG-Fit, Publikationsplots
  persistenz/  Excel/CSV-Export, Sitzungszustand
  gui/         PySide6-Oberfläche mit eingebettetem Matplotlib
  app.py       Einstiegspunkt
```

Die physikalischen Modelle sind zeichengenaue Portierungen verbindlicher Quellen
(Mathematica-Notebook der Polder-Suszeptibilität, Dissertation M. Müller Kap. 2,
Messprotokoll); die Quellenzuordnung ist in `docs/physik-und-fit.md` dokumentiert.

## Kernabhängigkeiten

`numpy`, `scipy`, `lmfit`, `npTDMS`, `matplotlib`, `pandas`, `openpyxl`; die grafische
Oberfläche zusätzlich `PySide6`. Sämtliche Pakete werden bei der Installation
automatisch aufgelöst.
