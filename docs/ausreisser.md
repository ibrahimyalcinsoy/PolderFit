# Ausreißer und Projektdateien

**Ausreißer** (`Strg+M` im Farbplot oder Klick im Kittel-Fenster `Strg+K`): Punkt aus Kittel/LLG, Plots und Globalparametern entfernt; Einzelfit bleibt; Spalte `ausreisser` im Export; Panel *Wieder aufnehmen*; rückgängig per `Strg+Z`.

![Auswahl](abb/abb_kittel_unsort.png)

**Projekt** (`Datei → Projekt speichern`, JSON Formatversion 2): Quelle, Kanal-Zuordnung, Auswertungsauswahl, γ, Fenster je Frequenz, Zonen, Ausreißer, Parameter (`alpha_max`, `nachfenster_faktor`), `programm` (Name+Version). Laden = TDMS neu lesen + **alle Fits deterministisch neu rechnen**.

```python
speichere_sitzung(stapel, "sitzung.json")
daten = lade_sitzung("sitzung.json")
ds = lade_tdms(daten["quelle"], zuordnung={r: tuple(p) for r, p in daten["zuordnung"].items()}, layout=daten["format_typ"])
stapel = stelle_stapel_wieder_her(daten, ds)
```
