# Messdaten (TDMS)

| Layout | Gruppen | Struktur |
|---|---|---|
| **unsortiert** (roh) | `Read.PNAX`, `Read.Fieldbefore/-after`, opt. `Read.Temperature` | je Feldwert ein voller Frequenz-Sweep → Matrix `(n_feld × n_freq)`; Feld = Mittel aus vor/nach; `_flush`-Dateien werden auf volle Sweeps gekürzt |
| **sortiert** | `ZVB`, `Field` | schon aufs Resonanzband reduziert; Punktzahl je Frequenz variabel (Gruppierung auf 1 kHz) |

Passt kein Profil → `MappingErforderlich` → Zuordnungsdialog ([Kanal-Mapping](kanal-mapping.md)).

```python
@dataclass
class Linescan:            # eine Frequenz, ein Feld-Sweep
    frequenz: float        # Hz
    feld: np.ndarray       # T, aufsteigend
    re, im: np.ndarray     # S21
    s21 -> re + 1j*im
```
`Messdatensatz` = Liste von `Linescan` (nach Frequenz sortiert) + `meta`; `ds.frequenzen`, `ds.feld_bereich()`, `ds.komplexe_matrix()`.
