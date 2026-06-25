# bbFMR unter Windows installieren und starten

Diese Anleitung führt **Schritt für Schritt** durch die komplette Installation –
ohne Vorkenntnisse. Einfach von oben nach unten abarbeiten. Jeder Schritt ist
einzeln aufgeführt und erklärt, was passiert und woran man erkennt, dass es
geklappt hat.

> **Zeitaufwand:** ca. 15–20 Minuten.
> **Voraussetzung:** Windows 10 oder 11 mit Internetverbindung und den Rechten,
> Programme zu installieren.

---

## Schritt 1 – Python installieren

bbFMR ist in Python geschrieben. Python muss zuerst installiert werden.

1. Webseite öffnen: <https://www.python.org/downloads/windows/>
2. Auf den großen gelben Knopf **„Download Python 3.x.x“** klicken
   (es muss **Version 3.11 oder neuer** sein).
3. Die heruntergeladene Datei (`python-3.x.x-amd64.exe`) per Doppelklick starten.
4. **WICHTIG – nicht überspringen:** Ganz unten im Installationsfenster den Haken
   bei **„Add python.exe to PATH“** setzen. ✅
   (Ohne diesen Haken funktionieren die späteren Befehle nicht.)
5. Auf **„Install Now“** klicken und warten, bis „Setup was successful“ erscheint.
6. Fenster mit **„Close“** schließen.

**Erfolgskontrolle:** Im Startmenü `cmd` eintippen, **Eingabeaufforderung** öffnen,
folgendes eingeben und mit Enter bestätigen:

```bat
python --version
```

Wenn eine Zeile wie `Python 3.12.4` erscheint, hat alles geklappt. Erscheint
stattdessen eine Fehlermeldung, wurde der Haken aus Schritt 4 vergessen – dann
Python deinstallieren und neu installieren.

---

## Schritt 2 – Git installieren

Git wird benötigt, um das Programm von GitHub herunterzuladen.

1. Webseite öffnen: <https://git-scm.com/download/win>
2. Der Download (**„64-bit Git for Windows Setup“**) startet automatisch.
3. Die Datei per Doppelklick starten.
4. Bei allen Fragen im Installationsfenster einfach immer auf **„Next“** klicken,
   am Ende auf **„Install“**, danach auf **„Finish“**.
   (Die Standardeinstellungen sind völlig in Ordnung.)

**Erfolgskontrolle:** Eine **neue** Eingabeaufforderung öffnen (siehe Schritt 1)
und eingeben:

```bat
git --version
```

Erscheint z. B. `git version 2.45.1`, ist Git einsatzbereit.

---

## Schritt 3 – Das Programm herunterladen

Jetzt wird bbFMR von GitHub auf den eigenen Rechner geladen.

1. Eingabeaufforderung öffnen (Startmenü → `cmd` → Enter).
2. In den eigenen Benutzerordner wechseln (dort landet das Programm):

   ```bat
   cd %USERPROFILE%
   ```

3. Das Programm herunterladen:

   ```bat
   git clone https://github.com/ibrahimyalcinsoy/bbFMR.git
   ```

4. In den heruntergeladenen Ordner wechseln:

   ```bat
   cd bbFMR
   ```

**Erfolgskontrolle:** Der Befehl `dir` zeigt jetzt unter anderem die Dateien
`README.md` und `pyproject.toml` an.

---

## Schritt 4 – Umgebung einrichten (virtuelle Umgebung + Abhängigkeiten)

Damit bbFMR sauber und ohne Konflikte läuft, bekommt es eine eigene, abgekapselte
Python-Umgebung.

1. Virtuelle Umgebung anlegen:

   ```bat
   python -m venv .venv
   ```

2. Virtuelle Umgebung aktivieren:

   ```bat
   .venv\Scripts\activate
   ```

   Danach steht am Zeilenanfang **`(.venv)`** – das zeigt, dass die Umgebung
   aktiv ist.

3. bbFMR samt grafischer Oberfläche und allen benötigten Paketen installieren
   (das dauert ein paar Minuten und lädt einiges aus dem Internet):

   ```bat
   pip install -e ".[gui]"
   ```

   Wenn am Ende eine Zeile wie `Successfully installed bbfmr-0.1.0 ...` erscheint,
   ist die Installation fertig.

---

## Schritt 5 – Das Programm starten

```bat
bbfmr
```

Die grafische Oberfläche von bbFMR öffnet sich. **Fertig!** 🎉

Falls der Befehl `bbfmr` einmal nicht funktioniert, geht alternativ auch:

```bat
python -m bbfmr.app
```

---

## Beim nächsten Mal starten

Python, Git und die Installation sind dann schon vorhanden. Es genügen **zwei**
Befehle in der Eingabeaufforderung:

```bat
cd %USERPROFILE%\bbFMR
.venv\Scripts\activate
bbfmr
```

> **Tipp:** Damit man sich diese Befehle nicht merken muss, kann man sie in eine
> Startdatei schreiben. Dazu im Ordner `bbFMR` mit dem Editor eine Datei
> `start.bat` mit folgendem Inhalt anlegen und künftig einfach doppelklicken:
>
> ```bat
> @echo off
> cd /d "%USERPROFILE%\bbFMR"
> call .venv\Scripts\activate
> bbfmr
> ```

---

## Auf eine neue Version aktualisieren

Wenn es eine neuere Programmversion gibt:

```bat
cd %USERPROFILE%\bbFMR
git pull
.venv\Scripts\activate
pip install -e ".[gui]"
```

---

## Häufige Probleme

| Problem | Lösung |
|---|---|
| `python` wird nicht erkannt | Haken **„Add python.exe to PATH“** bei der Installation vergessen (Schritt 1, Punkt 4). Python deinstallieren und neu installieren. |
| `git` wird nicht erkannt | Git neu installieren (Schritt 2) und eine **neue** Eingabeaufforderung öffnen. |
| `.venv\Scripts\activate` bringt einen Fehler | Sicherstellen, dass man sich im Ordner `bbFMR` befindet (`cd %USERPROFILE%\bbFMR`) und Schritt 4 Punkt 1 ausgeführt wurde. |
| Bei `pip install` bricht der Download ab | Internetverbindung prüfen und den Befehl einfach erneut ausführen. |
| Fenster der Oberfläche öffnet sich nicht | Prüfen, ob `(.venv)` am Zeilenanfang steht; falls nicht, zuerst `.venv\Scripts\activate` ausführen. |

Weitergehende Hinweise zur Bedienung und zur Fehlersuche stehen in der
ausführlichen Dokumentation im Ordner [`docs/`](docs/).
