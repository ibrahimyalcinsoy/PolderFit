# Die Messdaten (TDMS)

Ananas liest **TDMS-Dateien** (das Dateiformat von LabVIEW). Eine TDMS-Datei ist
intern in **Gruppen** und **Kanäle** unterteilt – ähnlich wie eine Excel-Mappe mit
mehreren Tabellenblättern und Spalten.

Alle Felder kommen bereits in **Tesla**, Frequenzen in **Hertz**.

## Zwei Formate – automatisch erkannt

Ananas kennt zwei Sorten von FMR-Messdateien. Welche vorliegt, erkennt
`lade_tdms()` automatisch an den vorhandenen Gruppen (`ananas/io/tdms_laden.py`):

| Format | Erkannt an Gruppe | Bedeutung |
|---|---|---|
| **unsortiert** (Rohdaten) | `Read.PNAX` | komplette Messung, ganzer Feld-Sweep je Frequenz |
| **sortiert** (vorverarbeitet) | `ZVB` | schon auf das Resonanzband reduziert |

```python
from ananas.io.tdms_laden import lade_tdms
ds = lade_tdms("Messung.tdms")
print(ds.format_typ)   # "unsortiert" oder "sortiert"
```

Liegt keine der beiden Gruppen vor, wirft Ananas einen klaren Fehler
(`Unbekanntes TDMS-Format …`). Das ist **gewollt**: solche Dateien sind keine
Feld-FMR-Linescans (siehe [Troubleshooting](troubleshooting.md#nicht_fmr)).

---

## Unsortiert (Rohdaten)

Die wichtigsten Kanäle:

- `Read.PNAX/Frequency`, `Read.PNAX/REALS21`, `Read.PNAX/IMAGinaryS21` – das Signal,
  hintereinanderweg gespeichert.
- `Read.Fieldbefore/IPS X-Field` und `Read.Fieldafter/IPS X-Field` – das Magnetfeld
  **vor** und **nach** jedem Schritt. Ananas nimmt den Mittelwert als Feldwert.
- optional `Read.Temperature/LakeshoreTemperature`.

**Die zentrale Annahme:** Pro Feldwert wird *ein vollständiger Frequenz-Sweep*
gespeichert. Sind es z. B. 725 Feldwerte × 1001 Frequenzpunkte, liegen 725 725
Zahlen am Stück vor. Ananas formt diese in eine Matrix `(n_feld × n_freq)` um
("reshape") und schneidet daraus pro Frequenz einen **Linescan** heraus.

!!! warning "Sicherung gegen vertauschte Achsen"
    Nach dem Umformen prüft Ananas, ob der Frequenz-Sweep je Feldwert wirklich
    identisch ist (`np.allclose`). Stimmt das nicht, bricht es mit einer klaren
    Meldung ab, statt still vertauschte Daten auszuwerten.

### `_flush`-Dateien (abgebrochene Messungen)

Dateien mit `_flush` im Namen wurden **mitten in der Messung** auf die Platte
geschrieben. Der letzte Feldschritt hat dann einen **unvollständigen**
Frequenz-Sweep: die Punktzahl passt nicht mehr glatt zur Feldanzahl.

Ananas erkennt das und **rettet** solche Dateien automatisch
(`ananas/io/tdms_laden.py`):

1. Es leitet die Sweep-Länge `n_freq` aus der Frequenzachse ab (sie wiederholt sich
   periodisch).
2. Es berechnet, wie viele Sweeps **vollständig** sind.
3. Es kürzt auf diese vollständigen Sweeps und wertet sie normal aus.

Vorher führte das zu einem Absturz (`Punktzahl … nicht durch Feldanzahl … teilbar`),
heute laden diese Dateien sauber. Lässt sich die Periode nicht bestimmen, kommt eine
verständliche Fehlermeldung.

---

## Sortiert (vorverarbeitet)

Hier sind die Daten bereits aufs Resonanzband reduziert. Kanäle in Gruppe `ZVB`:
`frequency`, `ReS21`, `ImS21`; Feld in Gruppe `Field` (`Field-before`,
`Field-after`). Die Punktzahl je Frequenz ist **nicht** konstant – Ananas gruppiert
die Daten nach Frequenz (auf 1 kHz gerundet, gegen Rundungsrauschen).

Sortierte Dateien sind ideal als **Referenz / Ground Truth**: Wenn zu einer
Rohdatei eine sortierte Variante existiert, kann man das automatisch gefundene
Fenster gegen das „richtige" Band der sortierten Datei vergleichen. Genau das nutzt
das [Robustheits-Harness](test-harness.md).

!!! note "Namens-Konvention der sortierten Gegenstücke"
    Sortierte Dateien enden meist auf `-sorted`, `-sorted (1)` oder `-for-FTF`.
    Die Rohdatei hat denselben Namen ohne dieses Anhängsel.

---

## Die interne Datenstruktur

Egal welches Format – beide werden auf dieselben Python-Objekte abgebildet
(`ananas/io/datensatz.py`):

```python
@dataclass
class Linescan:
    frequenz: float        # Hz
    feld: np.ndarray       # Tesla, aufsteigend sortiert
    re: np.ndarray         # Realteil S21
    im: np.ndarray         # Imaginärteil S21
    # ... feld_before, feld_after, temperatur (optional)

    @property
    def s21(self):         # komplexes Signal Re + i·Im
        return self.re + 1j*self.im
```

Ein `Messdatensatz` ist im Wesentlichen eine **Liste von `Linescan`** plus
Metadaten. Nützliche Helfer:

```python
ds.frequenzen        # alle Frequenzen (aufsteigend)
ds.feld_bereich()    # (min, max) Feld über alle Linescans
len(ds)              # Anzahl Linescans (= Anzahl Frequenzen)
```

Sämtliche nachfolgenden Verarbeitungsschritte operieren ausschließlich auf dieser
Liste von Linescans; das Verständnis des Datenmodells ist daher Voraussetzung für
das Verständnis der übrigen Module.
