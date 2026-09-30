# Measurement data (TDMS)

| Layout | Groups | Structure |
|---|---|---|
| **unsorted** (raw) | `Read.PNAX`, `Read.Fieldbefore/-after`, opt. `Read.Temperature` | one full frequency sweep per field value → matrix `(n_field × n_freq)`; field = mean of before/after; `_flush` files are cut to full sweeps |
| **sorted** | `ZVB`, `Field` | reduced to the resonance band; points per frequency vary (grouped to 1 kHz) |

No profile matches → `MappingErforderlich` → mapping dialog ([Channel mapping](kanal-mapping.md)).

```python
@dataclass
class Linescan:            # one frequency, one field sweep
    frequenz: float        # Hz
    feld: np.ndarray       # T, ascending
    re, im: np.ndarray     # S21
    s21 -> re + 1j*im
```
`Messdatensatz` = list of `Linescan` (sorted by frequency) + `meta`; `ds.frequenzen`, `ds.feld_bereich()`, `ds.komplexe_matrix()`.
