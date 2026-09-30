# Channel mapping and profiles

Every file is mapped to canonical roles (`io/kanal_mapping.py`); all later steps use only these roles.

| Role | Required |
|---|---|
| `frequenz` (Hz), `re_s21`, `im_s21`, `feld_before` (T) | ✔ |
| `feld_after` (T) → field = mean of before/after | – |
| `temperatur` (K) | – |

GUI: inspect structure → mapping dialog (profile preselected, heuristic suggestion, live check) → import validation → apply.

Built-in profiles: *WMI unsorted* (`Read.PNAX`, `Read.Fieldbefore/-after`), *WMI sorted* (`ZVB`, `Field`). Custom profiles as JSON in `~/.polderfit/mapping-profile/`:

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

Broken `.tdms_index` (Windows): re-read without index automatically; warning in `ds.meta["lade_warnungen"]`.
