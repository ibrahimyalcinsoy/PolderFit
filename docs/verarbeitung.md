# Verarbeitung des Farbplots

Der Farbplot zeigt standardmäßig nicht mehr das rohe |S21|, sondern das
Ergebnis einer **Verarbeitungskette** (`polderfit/verarbeitung/`), die aus dem
historischen Referenzprogramm *pybbfmr* portiert und mit dem zugrunde
liegenden Paper abgeglichen wurde:

> H. Maier-Flaig *et al.*, „Derivative divide, a method for the analysis of
> broadband ferromagnetic resonance in the frequency domain",
> *Rev. Sci. Instrum.* **89**, 076101 (2018),
> [doi:10.1063/1.5045135](https://doi.org/10.1063/1.5045135) —
> im Folgenden **[MF18]**.

## Zweck der Verarbeitung

Das gemessene S21 ist ([MF18] Gl. (3))

```
S21(ω, H₀) = ( −i·ω·A·V₀·χ(ω, H₀) + V₀ᴮᴳ(ω) ) / Vᵢ · e^(iφ)
```

Der frequenzabhängige Untergrund `V₀ᴮᴳ(ω)` (Transmission des Aufbaus) und die Phase
`e^(iφ)` (elektrische Länge) übersteigen das Resonanzsignal `χ` meist um mehrere
Größenordnungen; im rohen Farbplot bleibt die Mode dadurch oft unsichtbar. Die
Verarbeitungskette entfernt beides ohne Mikrowellen-Kalibrierung, sodass die Mode als
Kittel-Dispersion (typisch von links unten nach rechts oben) sichtbar wird.

## Die drei Operationen (Reihenfolge der Kette)

Alle Operationen arbeiten auf der komplexen Matrix `Z (n_freq × n_feld)` auf
gemeinsamem Feldgitter (`Messdatensatz.komplexe_matrix()`); jede ist im Panel
**einzeln zu-/abschaltbar und parametrisierbar**.

### 1 · divide-slice — Normierung durch Referenz-Slice

Teilt die gesamte Matrix durch das Spektrum bei **einem festen Feldwert**
(Referenz-Spalte; per Index oder Feldwert wählbar, auch „letzter Slice" via
Index −1). Ist der Referenz-Slice resonanzfrei, kürzt sich der komplette
frequenzabhängige Untergrund `V₀ᴮᴳ(ω)·e^(iφ)` heraus. Alternativ geht auch
ein Referenz-Slice auf der Frequenzachse (fester Frequenzwert, teilt jede
Zeile) gegen feldabhängige Drift.

### 2 · derivative-divide — Kern des Verfahrens

Zentraler Differenzenquotient entlang des Feldes, geteilt durch den zentralen
Wert ([MF18] Gl. (4)):

```
d_D S21 = [ S21(ω, H₀+ΔH) − S21(ω, H₀−ΔH) ] / [ S21(ω, H₀) · ΔH ]  ≈  −i·ω·A′·dχ/dω
```

Die Division durch `S21(ω, H₀)` eliminiert Untergrund **und** Phase; die
Differenz wirkt wie eine Feldmodulation mit Amplitude ΔH. Parameter:

| Parameter | Bedeutung |
|---|---|
| **Δn** (`delta_n`) | Punktabstand der Differenzbildung (pybbfmr: `modulation_amp`). Verglichen werden die Slices `i−Δn` und `i+Δn`; effektive Modulationsamplitude ΔH = Δn·Feldschritt. **Größeres Δn glättet** — für schwache Moden nötig, verbreitert aber Strukturen schmaler als 2·ΔH. |
| **mitteln** | Fenstermittelung statt Zwei-Punkt-Differenz (pybbfmr `average`): links Mittel über `[i−Δn, i)`, rechts über `[i, i+Δn]` — zusätzliche Glättung. |
| **Achse** | Feld (Standard, wie im Paper) oder Frequenz. |

Für **quantitative Fits** auf dd-verarbeiteten Daten ist bei großem Δn die
Verzerrung der Linienform über [MF18] Gl. (5) (Differenzenquotient von χ mit
bekanntem Δω± = ΔH·γ·µ₀) zu berücksichtigen. Der Linescan-Fit von PolderFit
arbeitet auf dem rohen S21; die Verarbeitungskette dient der Visualisierung.

### 3 · relation-amplitude — Nachbar-Slice-Division

Teilt jeden Slice durch den Nachbar-Slice im Abstand Δn
(`Z[i] / Z[i+Δn]`, pybbfmr `referenced_fmr`): der entfernte Slice dient als
lokale Untergrund-Referenz, Amplitude und Phase kürzen sich heraus. Divisive
Alternative/Ergänzung zu derivative-divide; auch hier steuert Δn Glättung
gegen Auflösung.

## Bedienung (GUI)

Das Dock „Verarbeitung (Farbplot)" (Menü *Ansicht → Panel: Verarbeitung*) zeigt die
drei Schritte als abhakbare Gruppen sowie die Anzeige-Wahl (Betrag, dB, Real-,
Imaginärteil, Phase). Jede Änderung wird unmittelbar angewendet; die Kette rechnet
stets auf der zwischengespeicherten komplexen Rohmatrix, nie auf bereits
verarbeiteten Daten. Zoom, Resonanz-Overlay und Frequenzmarkierung bleiben erhalten.
„Alles aus (Rohdaten |S21|)" schaltet zurück auf die unverarbeitete Ansicht.

Standard nach dem Laden: derivative-divide aktiv (Δn = 4, mitteln), entsprechend den
pybbfmr-Loadern; damit ist die Mode direkt sichtbar. Die Farbskala nutzt robuste
Perzentile (2 %–98 %), damit einzelne Ausreißer die Skala nicht dominieren.

## Skript-Nutzung

```python
from polderfit.io import lade_tdms
from polderfit.verarbeitung import (
    Verarbeitungskette, KettenSchritt, derivative_divide, anzeige_transform)

ds = lade_tdms("Messung.tdms")
feld, freq, Z = ds.komplexe_matrix()          # komplex, NaN ausserhalb

# Einzeloperation …
feld, freq, G = derivative_divide(feld, freq, Z, delta_n=4, mitteln=True)

# … oder als Kette (JSON-serialisierbar fuer Projektsitzungen):
kette = Verarbeitungskette(schritte=[
    KettenSchritt("divide_slice", aktiv=True, parameter={"achse": "feld", "index": 0}),
    KettenSchritt("derivative_divide", aktiv=True, parameter={"delta_n": 4}),
])
feld, freq, G = kette.anwenden(*ds.komplexe_matrix())
bild = anzeige_transform(G, "betrag")
kette_json = kette.als_dict()
```

## Abweichungen von pybbfmr (dokumentiert)

* **Orientierung**: PolderFit nutzt `Z (n_freq × n_feld)` (Farbplot-Konvention);
  pybbfmr die Transponierte. Die Formeln sind identisch, die Tests
  (`tests/test_verarbeitung.py`) übernehmen die bit-genauen
  pybbfmr-Referenzrechnungen in gespiegelter Konvention.
* **Ränder**: Punkte ohne vollständiges Differenzfenster werden **NaN**
  (pybbfmr: 0) — NaN wird im Farbplot maskiert, 0 wäre eine stille
  Falschfarbe. `relation_amplitude` behält die Matrixform (NaN-Rand) statt zu
  kürzen.
* γ-Konvention: PolderFit rechnet durchgängig mit γ in rad·s⁻¹·T⁻¹
  (pybbfmr: γ/2π in Hz/T) — relevant nur für die Gl.-(5)-Umrechnung
  Δω± = ΔH·γ·µ₀.
