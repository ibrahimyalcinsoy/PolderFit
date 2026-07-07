# Die Messdaten (TDMS)

PolderFit liest TDMS-Dateien (das Dateiformat von LabVIEW). Eine TDMS-Datei gliedert
sich intern in Gruppen und darin in Kanäle.

Alle Felder liegen in Tesla vor, Frequenzen in Hertz.

## Laden über Kanal-Mapping

Seit der Mapping-Erweiterung läuft **jedes** Laden über eine Zuordnung der
TDMS-Kanäle zu kanonischen Rollen (Frequenz, Re/Im(S21), Feld, Temperatur) –
ausführlich beschrieben in [Kanal-Mapping & Profile](kanal-mapping.md).
Für die beiden bekannten WMI-Layouts sind Profile **eingebaut**, sie werden
automatisch erkannt:

| Profil (Layout) | Erkannt an Gruppen | Bedeutung |
|---|---|---|
| **unsortiert** (Rohdaten) | `Read.PNAX`, `Read.Fieldbefore/-after` | komplette Messung, ganzer Feld-Sweep je Frequenz |
| **sortiert** (vorverarbeitet) | `ZVB`, `Field` | schon auf das Resonanzband reduziert |

```python
from polderfit.io import lade_tdms
ds = lade_tdms("Messung.tdms")
print(ds.format_typ)          # "unsortiert" oder "sortiert"
print(ds.meta["zuordnung"])   # verwendetes Kanal-Mapping
```

Passt kein Profil, wirft `lade_tdms` eine `MappingErforderlich`-Ausnahme mit
der kompletten Gruppen-/Kanalliste; die GUI öffnet dann den
**Zuordnungs-Dialog** zur manuellen Zuordnung (siehe
[Kanal-Mapping](kanal-mapping.md)). Winkelkalibrier- und andere
Nicht-FMR-Dateien haben weiterhin keine passenden Kanäle
(siehe [Troubleshooting](troubleshooting.md#nicht_fmr)).

---

## Unsortiert (Rohdaten)

Die wichtigsten Kanäle:

- `Read.PNAX/Frequency`, `Read.PNAX/REALS21`, `Read.PNAX/IMAGinaryS21` – das Signal,
  hintereinanderweg gespeichert.
- `Read.Fieldbefore/IPS X-Field` und `Read.Fieldafter/IPS X-Field` – das Magnetfeld
  **vor** und **nach** jedem Schritt. PolderFit nimmt den Mittelwert als Feldwert.
- optional `Read.Temperature/LakeshoreTemperature`.

Zentrale Annahme: Pro Feldwert wird ein vollständiger Frequenz-Sweep gespeichert.
Bei 725 Feldwerten × 1001 Frequenzpunkten liegen also 725 725 Zahlen am Stück vor.
PolderFit formt diese in eine Matrix `(n_feld × n_freq)` um (reshape) und schneidet
daraus pro Frequenz einen Linescan heraus.

!!! warning "Sicherung gegen vertauschte Achsen"
    Nach dem Umformen prüft PolderFit, ob der Frequenz-Sweep je Feldwert wirklich
    identisch ist (`np.allclose`). Stimmt das nicht, bricht es mit einer klaren
    Meldung ab, statt still vertauschte Daten auszuwerten.

### `_flush`-Dateien (abgebrochene Messungen)

Dateien mit `_flush` im Namen wurden während der laufenden Messung auf die Platte
geschrieben. Der letzte Feldschritt enthält dann einen unvollständigen
Frequenz-Sweep, dessen Punktzahl nicht glatt zur Feldanzahl passt.

PolderFit behandelt solche Dateien automatisch (`polderfit/io/tdms_laden.py`):

1. Die Sweep-Länge `n_freq` wird aus der periodisch wiederkehrenden Frequenzachse
   abgeleitet.
2. Die Zahl der vollständigen Sweeps wird bestimmt.
3. Die Daten werden auf diese vollständigen Sweeps gekürzt und regulär ausgewertet.

Lässt sich die Sweep-Periode nicht eindeutig bestimmen, bricht das Laden mit einer
entsprechenden Fehlermeldung ab.

---

## Sortiert (vorverarbeitet)

Hier sind die Daten bereits aufs Resonanzband reduziert. Kanäle in Gruppe `ZVB`:
`frequency`, `ReS21`, `ImS21`; Feld in Gruppe `Field` (`Field-before`,
`Field-after`). Die Punktzahl je Frequenz ist **nicht** konstant – PolderFit gruppiert
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
(`polderfit/io/datensatz.py`):

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
