# Bewertung der Fits

Jeder Einzel-Fit wird automatisch als unauffällig oder als problematisch eingestuft.
Die Einstufung erfolgt in der Funktion `bewerte_fit` in `bbfmr/fit/kriterien.py`,
in der sämtliche Schwellwerte als benannte Konstanten an einer Stelle gebündelt
sind.

## Motivation

Das Bestimmtheitsmaß `R²` ist als Gütemaß in diesem Anwendungsfall ungeeignet, da die
Gesamtvarianz des Signals vom konstanten Offset und vom feldabhängigen Untergrund
dominiert wird. Eine nahezu gerade Linie erreicht dadurch `R² ≈ 1`, obwohl sie die
Resonanz nicht beschreibt. Als primäres Gütemaß dient deshalb das normierte Residuum
(`rmse_norm`); die Einstufung beruht zudem auf mehreren physikalisch motivierten
Kriterien.

## Kriterien

Ein Fit gilt als problematisch, sobald **eine** der folgenden Bedingungen zutrifft:

| Kriterium | Bedingung | Problemgrund |
|---|---|---|
| (a) Residuum | `rmse_norm > RMSE_NORM_SCHWELLE` oder nicht endlich | „Residuum zu gross" |
| (b) Parameter an Schranke | `alpha`, `phi` oder `B_res` nahe einer Schranke | „… an Grenze" |
| (c) Resonanz außerhalb | `B_res` außerhalb des Fitfensters | „B_res ausserhalb Fenster" |
| (d) Dämpfung unphysikalisch | `alpha > ALPHA_PLAUSIBEL_MAX` | „alpha unphysikalisch" |
| (e) Konvergenz / Kovarianz | kein Erfolg oder keine Unsicherheiten bestimmbar | „keine Konvergenz" / „keine Unsicherheiten" |
| (f) Parameter-Unsicherheit | `B_res_err / |B_res| > B_RES_REL_UNSICHERHEIT_MAX` | „B_res-Unsicherheit zu gross" |

Die zutreffenden Gründe werden als Klartext-Liste zurückgegeben und stehen in der
grafischen Oberfläche sowie im Export zur Verfügung (`erg.problem_text`).

## Schwellwerte

Die maßgeblichen Konstanten (`bbfmr/fit/kriterien.py`):

| Konstante | Wert | Bedeutung |
|---|---|---|
| `ALPHA_MIN` | `1e-5` | untere harte Fit-Schranke der Dämpfung |
| `ALPHA_MAX` | `0.1` | obere harte Fit-Schranke der Dämpfung |
| `ALPHA_PLAUSIBEL_MAX` | `0.05` | Dämpfung darüber gilt als unphysikalisch |
| `PHI_MIN`, `PHI_MAX` | `∓2π` | Schranken des Phasenwinkels |
| `GRENZ_NAEHE_REL` | `0.01` | „an Schranke", wenn innerhalb 1 % des Schrankenabstands |
| `RMSE_NORM_SCHWELLE` | `0.35` | normiertes Residuum darüber → problematisch |
| `CHI2_RED_NOTBREMSE` | `1e6` | Sicherheitsnetz für Totalausreißer (red. Chi²) |
| `B_RES_REL_UNSICHERHEIT_MAX` | `0.02` | max. relative Unsicherheit des Resonanzfeldes |

!!! note "Reduziertes Chi-Quadrat"
    Das reduzierte Chi-Quadrat wird als zusätzliche Kennzahl exportiert, aber nicht
    zur harten Einstufung herangezogen. Es hängt von einer verlässlichen
    Punkt-Rauschschätzung ab, die hier nicht vorliegt; bei sehr rauscharmen, real
    leicht modellabweichenden Resonanzen würde es sonst auch gute Fits verwerfen. Der
    großzügige Wert `CHI2_RED_NOTBREMSE` dient ausschließlich als Sicherheitsnetz
    gegen Totalausreißer.

## Bedeutung für die Robustheit

Die Bewertung ist das Meldeinstrument des Programms: Ein falsch sitzendes Fenster
äußert sich typischerweise in einem der Kriterien (b), (c) oder (a) und wird dadurch
als problematisch gemeldet. Die Robustheitsprüfung (siehe
[Robustheits-Harness](test-harness.md)) unterscheidet entsprechend zwischen einem
gemeldeten Problem (zulässig) und einem **still** falsch gesetzten Fenster (der
eigentliche Fehlerfall).

!!! warning "Schwellwerte nicht zur Schönung verändern"
    Die Schwellwerte sind physikalisch motiviert. Eine Lockerung, die schlechte
    Fenster als unauffällig durchgehen ließe, würde die Aussagekraft der Auswertung
    untergraben. So wurde etwa eine probeweise Lockerung des Kriteriums „alpha an
    Grenze" wieder verworfen, da hierdurch zahlreiche objektiv falsche Fenster ihre
    einzige Meldung verloren hätten. Hinweise zur sachgerechten Anpassung enthält das
    Kapitel [Tuning](tuning.md).
