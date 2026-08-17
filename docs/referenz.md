# Schnellreferenz: Größen, Formeln, Quellen

Zum **Nachschlagen statt Lesen** — jede Größe mit Einheit, jede Formel mit
anklickbarem Quellenverweis (Dokument + Seite). Die ausführlichen Kapitel
bleiben für die Vertiefung; für den Alltag genügt diese Seite.

!!! note "Zu den Links"
    Jeder Quellenverweis öffnet das Original-PDF aus dem Projektordner
    `Dokumente/` direkt auf der Fundstelle (Seitenanker `#page=…`). Der
    Ordner ist aus Urheberrechtsgründen **nicht Teil des öffentlichen Repos**
    (`.gitignore`); die lokalen Links funktionieren daher auf dem Rechner mit
    dem vollständigen Projektordner (Doku dort per `mkdocs serve` oder direkt
    aus `docs/` öffnen). Die **DOI-Links** funktionieren überall.

## Größen und Einheiten

| Symbol | Bedeutung | Einheit | Export-Spalte / Code |
|---|---|---|---|
| α | Gilbert-Dämpfung (Einzelfit: aus der Linienform je Frequenz; global: Steigung der ΔH(f)-Geraden) | **dimensionslos** | `alpha` ± `alpha_err`; global `llg_alpha` |
| γ | gyromagnetisches Verhältnis, γ = g·µ_B/ħ | **rad s⁻¹ T⁻¹** (γ/2π ≈ 28 GHz/T ist nur die andere Schreibweise) | `kittel_gamma` ± err; [`konstanten.py`](https://github.com/ibrahimyalcinsoy/PolderFit/blob/main/polderfit/physik/konstanten.py) |
| g | Landé-Faktor (g = 2 → γ ≈ 1,7588·10¹¹ rad s⁻¹ T⁻¹) | – | `kittel_g_faktor` ± err |
| µ₀H, B_res | (Resonanz-)Feld — **immer als µ₀H geführt** | **Tesla** | `B_res_T` ± `B_res_err_T` |
| µ₀ΔH | Linienbreite = FWHM der Absorption χ″ | **Tesla** | `mu0_dH_T` ± `mu0_dH_err_T` (schon umgerechnet — kein Rechenschritt nötig) |
| µ₀M_eff | effektive Magnetisierung (M_s − H_u) | **Tesla** | `kittel_mu0Meff` ± err |
| µ₀H_inh | inhomogene Verbreiterung (Achsenabschnitt von ΔH(f)) | **Tesla** | `llg_mu0Hinh` ± err |
| f, ω = 2πf | Anregungsfrequenz / Kreisfrequenz | Hz / rad s⁻¹ | `frequenz_Hz` |
| S₂₁ | komplexer Transmissions-Streuparameter des VNA | – | Rohdaten (`re`, `im`) |
| χ = χ′ + iχ″ | Polder-Suszeptibilität (χ/M_s-Form; Absolutskala steckt im Fitparameter A) | – | `suszeptibilitaet.py` |
| A, φ | komplexer Vorfaktor des Resonanzbeitrags | – / rad | `A`, `phi_rad` ± err |
| alle `*_err` | 1σ-Standardunsicherheit (GUM Typ A, aus der Fit-Kovarianz) | wie die Größe | — |

## Die Kernformeln — mit Fundstelle

| Formel | Bedeutung | Quelle (klickbar) | im Code |
|---|---|---|---|
| γ = g·µ_B/ħ | Definition γ | [Müller 2023, Kap. 2](../Dokumente/Mueller_Manuel_Doktorarbeit_2023.pdf#page=28) | `gamma_aus_g` |
| B_res = µ₀M_eff + 2πf/γ | Kittel **oop** | [Müller Gl. (2.24), S. 15](../Dokumente/Mueller_Manuel_Doktorarbeit_2023.pdf#page=30) · [Kittel 1948](../Dokumente/PhysRev.73.155.pdf) | `kittel_oop` |
| B_res = √[(2πf/γ)² + (µ₀M_eff/2)²] − µ₀M_eff/2 − µ₀H_u | Kittel **ip** (nach B_res aufgelöst) | [Müller Gl. (2.26), S. 15](../Dokumente/Mueller_Manuel_Doktorarbeit_2023.pdf#page=30) | `kittel_ip` |
| **µ₀ΔH = 2ωα/γ = (4π/γ)·α·f** | Linienbreite eines Linescans in **Tesla** (so entsteht `mu0_dH_T` aus α) | [Müller Gl. (2.27), S. 15](../Dokumente/Mueller_Manuel_Doktorarbeit_2023.pdf#page=30) | `FitErgebnis.dH` |
| µ₀ΔH(f) = µ₀H_inh + (4π/γ)·α·f | LLG-Gerade → globales α und H_inh | [Müller Gl. (2.28), S. 16](../Dokumente/Mueller_Manuel_Doktorarbeit_2023.pdf#page=31) | `linienbreite`, `fit_linienbreite` |
| χ_P-Tensor (A₁₁, A₂₂, Det) | Herkunft von χ_oop/χ_ip | [Müller Gl. (2.20)/(2.21), S. 13 f.](../Dokumente/Mueller_Manuel_Doktorarbeit_2023.pdf#page=28) · [Notebook, Abschnitt „Out-of-plane (H‖z)“](../Dokumente/Chi_Fit_Functions_and_Inductances_2020-04-06.nb) | `suszeptibilitaet.py` |
| S₂₁(B) = A·e^{iφ}·χ + B + C·(B−B_ref) | Modell des Einzel-Fits | [Maier-Flaig 2018, Gl. (8)](../Dokumente/MaierFlaig2018_derivative_divide.pdf#page=4) · [doi:10.1063/1.5045135](https://doi.org/10.1063/1.5045135) | `s21_modell` |
| d_D S₂₁ = [S₂₁(H+ΔH)−S₂₁(H−ΔH)] / [S₂₁(H)·ΔH] | derivative divide (Farbplot) | [Maier-Flaig 2018, Gl. (4)/(5)](../Dokumente/MaierFlaig2018_derivative_divide.pdf#page=3) | `derivative_divide` |
| u(g) = ‖∂g/∂x_i‖-Quadratsumme; w = 1/u² | Fehlerfortpflanzung / gewichtete Ausgleichsgerade | [ABW Gl. (19), S. 12](../Dokumente/ABW.pdf#page=12) · [ABW Abschn. 6.3, S. 17](../Dokumente/ABW.pdf#page=17) | `fit_kittel_*`, `fit_linienbreite` |

**Merkhilfe zur häufigsten Frage:** α ist dimensionslos. Die Linienbreite in
Tesla steht fertig im Export (`mu0_dH_T` = (4π/γ)·α·f); wer sie von Hand prüfen
will: ω in rad/s durch γ in rad s⁻¹ T⁻¹ ergibt Tesla.

## Quelldokumente

| Kurzname | lokal (Ordner `Dokumente/`) | offiziell |
|---|---|---|
| Müller 2023 (Dissertation, Kap. 2 ist die Referenz aller Fit-Formeln) | [PDF](../Dokumente/Mueller_Manuel_Doktorarbeit_2023.pdf) | [mediaTUM-Suche „Manuel Müller 2023“](https://mediatum.ub.tum.de/) |
| Mathematica-Notebook (χ-Fitfunktionen, zeichengenau portiert) | [Notebook](../Dokumente/Chi_Fit_Functions_and_Inductances_2020-04-06.nb) | gruppenintern |
| Maier-Flaig 2018 „derivative divide“ | [PDF](../Dokumente/MaierFlaig2018_derivative_divide.pdf) | [doi:10.1063/1.5045135](https://doi.org/10.1063/1.5045135) |
| Kittel 1948 (Original der Resonanzbedingungen) | [PDF](../Dokumente/PhysRev.73.155.pdf) | [doi:10.1103/PhysRev.73.155](https://doi.org/10.1103/PhysRev.73.155) |
| Keffer & Kittel 1952 (AFM-Resonanz → Grenze für CrSBr) | [PDF](../Dokumente/PhysRev.85.329.pdf) | [doi:10.1103/PhysRev.85.329](https://doi.org/10.1103/PhysRev.85.329) |
| Messprotokoll FMR-Python (Anforderungen, Export-Pflichtgrößen) | [DOCX](../Dokumente/Protokoll_FMR_Python_2026-05-08.docx) | gruppenintern |
| ABW — Umgang mit Messunsicherheiten (TUM-Praktikum, GUM) | [PDF](../Dokumente/ABW.pdf) | TUM-Praktikum |
| Vortrag Messunsicherheiten 2020 | [PDF](../Dokumente/Vortrag%20Behandlung%20von%20Messunsicherheiten%202020.pdf) | TUM-Praktikum |

*Seitenangaben: gedruckte Seite der Dissertation; der Link springt zur
entsprechenden PDF-Seite. Verifikation aller Formeln gegen diese Quellen:
siehe [Physik und Fit](physik-und-fit.md), Abschnitt „Quellenzuordnung“.*
