# Physikalisches Modell und Fit

Dieses Kapitel fasst die physikalischen Modelle zusammen, auf denen die Auswertung
beruht, und beschreibt das Anpassungsverfahren. Die Korrektheit der Modellfunktionen
wurde gegen die Quelldokumente verifiziert; die Zuordnung ist am Ende des Kapitels
angegeben.

## Einheitenkonvention

Sämtliche Magnetfelder werden konsequent als `μ0·H` in Tesla geführt (`μ0H0` als
äußeres Feld, `μ0Meff` als effektive Magnetisierung). Das gyromagnetische Verhältnis
`γ` ist in rad/(s·T) angegeben. Eine Vermischung von `H` (in A/m) mit `μ0H` (in T)
ist zu vermeiden. Die physikalischen Konstanten sind in
`polderfit/physik/konstanten.py` definiert:

```
γ = g · μ_B / ħ            (gamma_aus_g)
```

Für `g = 2` ergibt sich `γ ≈ 1,7588·10¹¹ rad/(s·T)`. Der Standardwert
`GAMMA_STANDARD` ist hieraus vorberechnet.

Dieses feste `γ` ist ein Startwert für den Einzelfit (Fensterlage und
Anfangsschätzung der Dämpfung), nicht das Auswertungsergebnis. Das Resonanzfeld
`B_res` jeder Frequenz wird frei gefittet und ist von `γ` unabhängig; der g-Faktor
folgt erst aus der Kittel-Anpassung an die Dispersion `B_res(f)` (siehe unten).

## Resonanzbedingung (Kittel)

Das Resonanzfeld hängt über die Kittel-Gleichungen von der Frequenz ab. Die
Auswertung verwendet je nach Geometrie (`polderfit/physik/kittel_llg.py`):

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
(`polderfit/physik/fitmodell.py`):

```
S21(B) = A · exp(i·φ) · χ(B; B_res, α, ω, γ)  +  Untergrund(B)
```

mit der Anregungskreisfrequenz `ω = 2π·f`. Der Untergrund wird als komplexe,
feldabhängige Gerade modelliert (Offset und Steigung getrennt für Real- und
Imaginärteil), um die dominierende Untergrund-Rampe abzubilden. Der Vorfaktor
`A·exp(i·φ)` erfasst Amplitude und Phasenlage des Resonanzbeitrags.

Die Suszeptibilität `χ` (`polderfit/physik/suszeptibilitaet.py`) ist als
Polder-Suszeptibilität implementiert. Der Einzel-Fit verwendet die
Out-of-plane-Komponente `χ_oop`; die Umschaltung zwischen oop und ip greift in der
übergreifenden Kittel-/LLG-Auswertung.

## Anpassungsverfahren

Der Fit erfolgt mit `lmfit` als nichtlineare Ausgleichsrechnung (Levenberg-Marquardt,
`method="leastsq"`) und passt Real- und Imaginärteil simultan an
(`fitte_linescan` in `polderfit/fit/linescan_fit.py`). Die freien Parameter sind:

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

## Einstellbare Parameter (GUI)

*Funktionen → Physikalische Parameter …* (`Strg+P`) öffnet den Dialog für die
vom Nutzer wählbaren Größen (Konvention wie oben: Felder als µ₀H in Tesla,
γ = g·µ_B/ħ in rad/(s·T); Müller 2023, Kap. 2):

| Parameter | Wirkung | Standard |
|---|---|---|
| g-Faktor | γ = g·µ_B/ħ — Einzelfits (ΔH = 2ωα/γ), Fenstersuche, Startwert des Kittel-Fits | 2.0 |
| γ festhalten | Kittel-Fit (oop) fittet nur µ₀M_eff; γ bleibt beim eingestellten Wert | aus |
| Kittel-Geometrie | Vorgabe für das Auswertungsfenster: oop (Gl. 2.24) oder ip (Gl. 2.26) | oop |
| Fensterbreite-Faktor | automatisches Fenster = Faktor × lokale FWHM | 8.0 |
| R²-Schwelle (Einzelfit) | sekundäres Gütemaß der Problem-Einstufung | 0.9 |
| R²-Minimum (Kittel/LLG) | Punktauswahl der übergreifenden Auswertung | 0.9 |
| erwartetes α | Fensterbreite (ΔB = 2ωα/γ) beim Auto-Fit mit vorgegebener Resonanz | 0.01 |
| α-Obergrenze (Einzelfit) | harte obere Fitschranke für α; für sehr breite Resonanzen (z. B. FeCr₂S₄, α ≈ 0.2–0.5) anheben. Die Plausibilitätsgrenze („alpha unphysikalisch") liegt bei der Hälfte | 0.1 |
| Nachfenster (± ΔH-Vielfache) | zweiter Fit-Durchgang auf B_res ± Faktor·µ₀ΔH des ersten Durchgangs (Auto- und Bereichs-Fit); wird nur übernommen, wenn der Nachfit unproblematisch ist. 0 = aus | 2.5 |

Änderungen wirken ab dem nächsten (Auto-/Nach-)Fit; die Kittel/LLG-Auswertung
und der Excel-Export rechnen sofort mit den neuen Werten. „Standardwerte"
setzt alles zurück.

!!! note "Warum ein zweiter Fit-Durchgang?"
    Das Detektionsfenster der Automatik ist bewusst breit (≈ ±7 Linienbreiten).
    Auf so breiten Fenstern passt der lineare Untergrund des Modells bei
    strukturiertem Hintergrund (Ripple, Nachbarsignale) nicht mehr, und die
    Linienbreite fällt systematisch 5–15 % zu klein aus. Bis ≈ ±3 Linienbreiten
    ist µ₀ΔH fensterunabhängig. Der Benchmark gegen das LabVIEW-Tool FTF
    (`benchmark_ftf/BERICHT.md`) zeigt: mit dem Nachfenster stimmen ΔH je
    Frequenz auf < 1 % und g, µ₀M_eff, µ₀H_u, α, µ₀ΔH₀ innerhalb 1σ überein.

Der Kittel-ip-Fit ist unter (µ₀M_eff, µ₀H_u) → (−µ₀M_eff, µ₀H_u + µ₀M_eff) exakt
entartet; PolderFit liefert daher immer den Ast µ₀M_eff ≥ 0.
