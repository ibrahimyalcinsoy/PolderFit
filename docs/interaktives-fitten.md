# Interactive fitting

One mode at a time (active mode blue + status bar, `Esc` cancels). Zoom (wheel/box) is **off** by default: *View → Zoom*; double-click resets, keys `+`/`-`/`0` always work. Undo/redo: `Ctrl+Z` / `Ctrl+Shift+Z` (50 steps). **All tools work without Auto-Fit** (`leerer_stapel`: unfitted frequencies stay invisible and outside all evaluations).

| Tool | Access | Effect |
|---|---|---|
| Auto-Fit (all) | `F5` | dialog: jumper (absolute), range, **resonances per window** (1–4; > 1 = sum fit) and **automatic count (BIC)**; mode 1 per frequency, then all corridors |
| Corridors | `Ctrl+L` or panel *Corridors*, 2 clicks along the resonance | corridor ± width; anchors by dragging the green limits (linescan panel) or handles (color plot); “Resonances in corridor” = n dips (sum fit, B_res per dip in its segment; or hard split); “Set separator” = yellow line, moves with the corridor centre; “Fit corridor …” (frequency range, mode, jumper, BIC) |
| Refit region (rectangle) | `Ctrl+B` | same dialog (range editable); `B_res` stays inside the region |
| Drag limits in linescan | fit panel | single frequency, immediate fit; number of resonances selectable |
| Exclusion zone | *Functions → Draw exclusion zone*, rectangle | points removed from all (post-)fits, kept on Auto-Fit (`F5`); hatched; `Ctrl+Z` |
| Rating | `Ctrl+1/2/3`, `Ctrl+I`, panel buttons | confirm good / problematic / automatic / ignore ([Rating](bewertung.md)) |

A targeted refit of **one** frequency (drag limits, “Refit”, separator) counts as **user-confirmed** (green, blue edge; switch off in `Ctrl+P`); corridor and region fits over many frequencies are rated by the criteria. “M1/M2 …” in the linescan panel = selected mode; dragging limits sets a corridor anchor at that frequency.

While fitting: busy cursor, status bar (phase, progress, elapsed/remaining time), banner, points drawn live; `Cancel` stops after the running fit, the rest stays “not fitted” (`fitte_alle(abbruch=…)`).

Region fit window search = Auto-Fit, limited to the field interval. Corridor fits search no window: the corridor is the window; start value from the local dip, else from the neighbour.

| Problem | Tool |
|---|---|
| limits too narrow | rectangle + “Fixed window width” |
| several modes (e.g. nanostructured CoFe) | resonances = 2/3 (panel, `Ctrl+P` or Auto-Fit dialog); bands one after another per mode; Kittel/LLG per mode (`Ctrl+K`); all modes exported |
| wrong signal next to the mode | tight rectangle or corridor |
| fit rated ok, physically wrong | `Ctrl+2` or rectangle *overwrite* + exclusion zone |
| fit yellow but visibly right (“alpha unphysical”, broad lines) | `Ctrl+1` or raise α plausibility limit (`Ctrl+P`) |
| single fit off | drag limits in the linescan panel |

```python
st = leerer_stapel(ds)                                   # without Auto-Fit
k = Korridor(mode=2, anker=[Anker(40.5e9, 2.70, 2.80), Anker(43.8e9, 2.80, 2.90)])
neu, uebersprungen = fitte_korridor(st, k, schritt=1)
neu, uebersprungen = fitte_bereich(stapel, feld_min=0.55, feld_max=1.30, frequenz_min=8e9, frequenz_max=18e9, modus="ueberschreiben", breite_punkte=25)
stapel.bewerte(i, "bestaetigt")                          # "auto" | "bestaetigt" | "verworfen"
```
