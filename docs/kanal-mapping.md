# Kanal-Mapping und Profile

Jede Datei wird auf kanonische Rollen abgebildet (`io/kanal_mapping.py`); alle weiteren Schritte rechnen nur mit diesen Rollen.

| Rolle | Pflicht |
|---|---|
| `frequenz` (Hz), `re_s21`, `im_s21`, `feld_before` (T) | ✔ |
| `feld_after` (T) → Feld = Mittelwert vor/nach | – |
| `temperatur` (K) | – |

Ablauf GUI: Struktur inspizieren → Zuordnungsdialog (Profil vorausgewählt, Heuristik-Vorschlag, Live-Prüfung) → Import-Validierung → Übernehmen.

Eingebaute Profile: *WMI unsortiert* (`Read.PNAX`, `Read.Fieldbefore/-after`), *WMI sortiert* (`ZVB`, `Field`). Eigene Profile als JSON unter `~/.polderfit/mapping-profile/`:

```json
{"polderfit_mapping_profil": 1, "name": "Messrechner K3", "layout": "sortiert",
 "zuordnung": {"frequenz": ["ZVB","frequency"], "re_s21": ["ZVB","ReS21"], "im_s21": ["ZVB","ImS21"],
               "feld_before": ["Field","Field-before"], "feld_after": ["Field","Field-after"]}}
```

```python
ds = lade_tdms("fremd.tdms", zuordnung={"frequenz": ("Acq","f_Hz"), "re_s21": ("Acq","S21_re"),
                                        "im_s21": ("Acq","S21_im"), "feld_before": ("Magnet","B_T")})
ds.meta["zuordnung"], ds.meta["mapping_profil"]
```

Defekte `.tdms_index` (Windows): wird automatisch ohne Index neu gelesen; Warnung in `ds.meta["lade_warnungen"]`.
