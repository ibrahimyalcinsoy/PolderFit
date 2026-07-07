# Kanal-Mapping und Mapping-Profile

Verschiedene Messrechner erzeugen unterschiedlich benannte und angeordnete
TDMS-Dateien. Damit die übrige Verarbeitung unabhängig vom konkreten Dateiaufbau
bleibt, wird beim Laden jede Datei über ein Mapping auf kanonische Rollen abgebildet
(`polderfit/io/kanal_mapping.py`). Alle weiteren Schritte – AutoWindow, Fit,
Kittel/LLG, Export – rechnen ausschließlich mit diesen internen Rollen. Ohne
Zuordnung startet kein Auto-Fit (kein Fit auf ungemappten Daten).

## Die kanonischen Rollen

| Rolle | Bedeutung | Pflicht |
|---|---|---|
| `frequenz` | Frequenzachse (Hz) | ✔ |
| `re_s21` | Realteil des komplexen S21 | ✔ |
| `im_s21` | Imaginärteil des komplexen S21 | ✔ |
| `feld_before` | externes Feld **vor** dem Sweep (T) | ✔ |
| `feld_after` | externes Feld **nach** dem Sweep (T) | – (dann zählt `feld_before` allein) |
| `temperatur` | Temperatur (K) | – |

Sind beide Feldkanäle zugeordnet, verwendet PolderFit den **Mittelwert** als
Feldwert des Punktes.

## Ablauf beim Laden (GUI)

1. **Struktur inspizieren** – nur Metadaten: alle Gruppen und Kanäle der Datei
   werden aufgelistet (`inspiziere_tdms`), ohne die Daten zu laden.
2. **Zuordnungs-Dialog** – pro Rolle wählt man (Gruppe, Kanal) per Dropdown.
   Passt ein bekanntes Profil auf die Datei, ist es bereits vorausgewählt
   (mit ✓ markiert); bei fremden Dateien macht eine Namens-Heuristik einen
   Vorschlag. Der Dialog prüft live: fehlende Pflichtrollen, doppelt vergebene
   Kanäle, Layout-Plausibilität.
3. **Import-Validierung vor Übernahme** – nach dem Laden erscheinen Bericht und
   Daten-Vorschau (`pruefe_datensatz`): Dimensionen, Monotonie der Achsen,
   NaN-Anteil, Feld-/Frequenzbereiche und einige Beispiel-Linescans. Erst mit
   **„Übernehmen"** wird der Datensatz aktiv; „Zuordnung ändern" springt in den
   Dialog zurück.

## Speicher-Layouts

Neben den Kanalnamen unterscheidet sich auch die **Struktur** der Dateien:

| Layout | Struktur | typische Quelle |
|---|---|---|
| `unsortiert` | pro Feldschritt ein kompletter, identischer Frequenz-Sweep; Feldkanäle kurz (`n_feld`), Signalkanäle lang (`n_feld·n_freq`) | Rohdaten-Messrechner (PNA-X) |
| `sortiert` | ein Eintrag je Messpunkt, alle Kanäle gleich lang; Punkte werden nach Frequenz gruppiert | vorverarbeitete Dateien |

Das Layout wird aus den Kanal-Längen **vorgeschlagen** (gleich lang → sortiert;
Signalkanal ganzzahliges Vielfaches des Feldkanals → unsortiert) und kann im
Dialog jederzeit explizit übersteuert werden.

## Mapping-Profile (JSON)

Damit man pro Messrechner nur **einmal** zuordnen muss, lassen sich Zuordnungen
als Profil speichern und laden – im Dialog über „Profil speichern …" /
„Profil laden …". Profile sind einfache JSON-Dateien (UTF-8) und liegen
standardmäßig unter `~/.polderfit/mapping-profile/`:

```json
{
  "polderfit_mapping_profil": 1,
  "name": "Messrechner K3",
  "layout": "sortiert",
  "zuordnung": {
    "frequenz":    ["ZVB", "frequency"],
    "re_s21":      ["ZVB", "ReS21"],
    "im_s21":      ["ZVB", "ImS21"],
    "feld_before": ["Field", "Field-before"],
    "feld_after":  ["Field", "Field-after"]
  }
}
```

Zwei Profile für die bekannten WMI-Layouts sind **eingebaut**
(`EINGEBAUTE_PROFILE`):

* **WMI unsortiert/roh** – Gruppen `Read.PNAX`, `Read.Fieldbefore`,
  `Read.Fieldafter`, optional `Read.Temperature`.
* **WMI sortiert/vorverarbeitet** – Gruppen `ZVB` und `Field`.

Dateien dieser Layouts laden daher wie bisher ohne jede Nachfrage-Zuordnung –
der Dialog zeigt das erkannte Profil nur zur Bestätigung an.

## Skript-Nutzung

```python
from polderfit.io import lade_tdms, inspiziere_tdms, MappingErforderlich

ds = lade_tdms("Messung.tdms")            # Profil wird automatisch erkannt

# Unbekanntes Layout: Struktur ansehen und manuell zuordnen
try:
    ds = lade_tdms("fremd.tdms")
except MappingErforderlich as fehler:
    print(fehler.struktur)                 # {gruppe: {kanal: n_werte}}
    ds = lade_tdms("fremd.tdms", zuordnung={
        "frequenz":    ("Acq", "f_Hz"),
        "re_s21":      ("Acq", "S21_re"),
        "im_s21":      ("Acq", "S21_im"),
        "feld_before": ("Magnet", "B_vor_T"),
    })                                     # layout wird vorgeschlagen

ds.meta["zuordnung"]        # verwendete Zuordnung (Nachvollziehbarkeit)
ds.meta["mapping_profil"]   # Profilname oder "manuell"
```

## Defekte `.tdms_index`-Dateien (bekannter Windows-Fehler)

Neben einer `.tdms`-Datei liegt oft eine gleichnamige `.tdms_index`-Datei –
ein reiner Beschleunigungs-Index. Wird die Datendatei kopiert/umbenannt oder
neu geschrieben, ohne den Index zu aktualisieren, passt der Index nicht mehr
und nptdms bricht ab mit:

```
ValueError: Attempted to read data segment at position … but did not find
segment start header. Check that the tdms_index file matches the tdms data file.
```

PolderFit fängt das ab: die Datei wird automatisch ohne Index-Datei erneut
gelesen (etwas langsamer, Daten vollständig) und eine Warnung im Protokoll und
in `ds.meta["lade_warnungen"]` vermerkt. Empfehlung: die veraltete
`.tdms_index`-Datei löschen.
