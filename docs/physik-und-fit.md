# Physik und Fit

Dieses Kapitel fasst die physikalischen Modelle zusammen, auf denen die Auswertung
beruht, und beschreibt das Anpassungsverfahren. Die Korrektheit der Modellfunktionen
wurde gegen die Quelldokumente verifiziert; die Zuordnung ist am Ende des Kapitels
angegeben.

## Einheitenkonvention

Sämtliche Magnetfelder werden konsequent als `μ0·H` in Tesla geführt (`μ0H0` als
äußeres Feld, `μ0Meff` als effektive Magnetisierung). Das gyromagnetische Verhältnis
`γ` ist in rad/(s·T) angegeben. Eine Vermischung von `H` (in A/m) mit `μ0H` (in T)
ist zu vermeiden. Die physikalischen Konstanten sind in
`ananas/physik/konstanten.py` definiert:

```
γ = g · μ_B / ħ            (gamma_aus_g)
```

Für `g = 2` ergibt sich `γ ≈ 1,7588·10¹¹ rad/(s·T)`. Der Standardwert
`GAMMA_STANDARD` ist hieraus vorberechnet.

## Resonanzbedingung (Kittel)

Das Resonanzfeld hängt über die Kittel-Gleichungen von der Frequenz ab. Die
Auswertung verwendet je nach Geometrie (`ananas/physik/kittel_llg.py`):

Senkrechte Anisotropie / Out-of-plane (oop):

```
f = (γ / 2π) · (μ0H0 − μ0Meff)
```

In-plane (ip):

```
f = (γ / 2π) · √[ (μ0H0 + μ0Hu) · (μ0H0 + μ0Hu + μ0Meff) ]
```

Hieraus werden durch Anpassung an die gemessenen Wertepaare `(f, B_res)` die
effektive Magnetisierung `μ0Meff` und – bei freigegebenem Parameter – der g-Faktor
bestimmt (`fit_kittel_oop`, `fit_kittel_ip`).

## Linienbreite und Gilbert-Dämpfung

Die frequenzabhängige Linienbreite folgt im LLG-Bild einer Geraden:

```
μ0ΔH(f) = μ0ΔH_inh + (4π / γ) · α · f
```

Dabei ist `μ0ΔH_inh` die inhomogene (frequenzunabhängige) Verbreiterung und `α` die
Gilbert-Dämpfung. Aus der Steigung der Geraden `μ0ΔH(f)` wird `α` bestimmt
(`fit_linienbreite`).

## Modellfunktion des Einzel-Fits

Der Einzel-Fit eines Linescans passt das komplexe Transmissionssignal an
(`ananas/physik/fitmodell.py`):

```
S21(B) = A · exp(i·φ) · χ(B; B_res, α, ω, γ)  +  Untergrund(B)
```

mit der Anregungskreisfrequenz `ω = 2π·f`. Der Untergrund wird als komplexe,
feldabhängige Gerade modelliert (Offset und Steigung getrennt für Real- und
Imaginärteil), um die dominierende Untergrund-Rampe abzubilden. Der Vorfaktor
`A·exp(i·φ)` erfasst Amplitude und Phasenlage des Resonanzbeitrags.

Die Suszeptibilität `χ` (`ananas/physik/suszeptibilitaet.py`) ist als
Polder-Suszeptibilität implementiert. Der Einzel-Fit verwendet die
Out-of-plane-Komponente `χ_oop`; die Umschaltung zwischen oop und ip greift in der
übergreifenden Kittel-/LLG-Auswertung.

## Anpassungsverfahren

Der Fit erfolgt mit `lmfit` als nichtlineare Ausgleichsrechnung (Levenberg-Marquardt,
`method="leastsq"`) und passt Real- und Imaginärteil simultan an
(`fitte_linescan` in `ananas/fit/linescan_fit.py`). Die freien Parameter sind:

| Parameter | Bedeutung | Schranken |
|---|---|---|
| `B_res` | Resonanzfeld | innerhalb des Fitfensters (verbindlich) |
| `alpha` | Gilbert-Dämpfung | `[ALPHA_MIN, ALPHA_MAX]` |
| `A` | Amplitude | frei |
| `phi` | Phasenwinkel | `[PHI_MIN, PHI_MAX]` |
| `off_re`, `off_im` | Untergrund-Offset (Re, Im) | frei |
| `slope_re`, `slope_im` | Untergrund-Steigung (Re, Im) | frei |

Die Bedingung, dass `B_res` im Fitfenster liegen muss, koppelt die Qualität des Fits
unmittelbar an die korrekte Fensterwahl durch das [AutoWindow](autowindow.md).

### Startwerte

Werden keine Startwerte vorgegeben, schätzt `schaetze_startwerte` sie aus den Daten.
Der Startwert für `α` wird aus der Halbwertsbreite des Absorptionssignals
zurückgerechnet:

```
α_start = γ · μ0ΔH / (2·√3·ω)
```

Der Faktor `√3` ist wesentlich: `μ0ΔH` ist als Halbwertsbreite der Absorption `χ''`
definiert, während der Betrag `|χ|` erst bei `x = ±√3` auf die Hälfte abfällt. Ohne
diesen Faktor wäre der Startwert um etwa 73 % zu groß. Die konvergierten Werte sind
gegenüber dieser Korrektur robust; betroffen sind Startwert und Fensterbreite.

## Gütemaße

Das primäre Gütemaß ist das **normierte Residuum** (`rmse_norm`): der quadratische
Mittelwert der Anpassungsreste relativ zum Signalhub **nach** Abzug von Offset und
feldabhängiger Steigung. Diese Normierung ist erforderlich, weil die Gesamtvarianz
des Signals vom konstanten Offset und vom feldabhängigen Untergrund dominiert wird –
eine nahezu gerade Linie erreicht andernfalls `R² ≈ 1`, obwohl sie die Resonanz
ignoriert. Das Bestimmtheitsmaß `R²` wird daher nur nachrangig geführt.

Als zusätzliche Kennzahl wird das reduzierte Chi-Quadrat berechnet. Die hierfür
benötigte Rauschschätzung erfolgt fit-unabhängig aus den zweiten Differenzen der
Messwerte (`_rausch_sigma`), die glatte Anteile (Offset, breite Resonanz)
unterdrücken und vorwiegend das Messrauschen abbilden.

## Quellenzuordnung

Die Modellfunktionen wurden gegen folgende Quellen verifiziert:

1. **Müller, M., Dissertation (2023), Kapitel 2** – Kittel-Gleichungen (oop, ip) und
   Linienbreite im LLG-Bild einschließlich aller Vorfaktoren.
2. **Mathematica-Notebook** `Chi_Fit_Functions_and_Inductances_2020-04-06.nb` –
   Suszeptibilitäts- und S21-Fitfunktionen; das Programm portiert die exportierten
   Ausdrücke zeichengenau.
3. **Messprotokoll** `Protokoll_FMR_Python_2026-05-08` – Anforderungen sowie die
   inverse Suszeptibilität (Weiler, Gl. 2.7) als Quelle der Fitfunktionen. Die
   implementierte `χ_oop` stimmt numerisch mit der Inversion dieser Matrix überein.
