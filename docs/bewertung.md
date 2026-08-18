# Bewertung der Fits

`bewerte_fit` (`fit/kriterien.py`) – problematisch, sobald **eine** Bedingung zutrifft:

| | Kriterium | Bedingung | Konstante |
|---|---|---|---|
| a | Residuum | `rmse_norm > 0.35` (RMSE/Signalhub nach Untergrundabzug); Notbremse `chi2_red > 1e6` | `RMSE_NORM_SCHWELLE`, `CHI2_RED_NOTBREMSE` |
| b | an Schranke | `alpha`, `phi`, `B_res` innerhalb 1 % des Schrankenabstands | `GRENZ_NAEHE_REL` |
| c | außerhalb | `B_res` ∉ Fenster | |
| d | unphysikalisch | `alpha > 0.05` (bzw. `alpha_max/2`) | `ALPHA_PLAUSIBEL_MAX` |
| e | Konvergenz/Kovarianz | kein Erfolg; keine Unsicherheiten **und** `rmse_norm > 0.10` | `RMSE_NORM_EXZELLENT` |
| f | Unsicherheit | `B_res_err/|B_res| > 2 %` | `B_RES_REL_UNSICHERHEIT_MAX` |

R² ist **kein** Gütemaß (Untergrund dominiert die Varianz → R² ≈ 1 auch ohne Resonanz). `chi2_red` (Rauschen aus zweiten Differenzen, MAD/√6) wird exportiert, nicht zur Einstufung genutzt.

![Kriterien](abb/abb_kriterien.png)

Nur unproblematische Fits gehen in Kittel/LLG (`_gute_ergebnisse`). Schwellen nicht zur Schönung lockern.
