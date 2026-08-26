# -*- coding: utf-8 -*-
"""Foliensatz zum FTF-Benchmark als PDF (16:9, stichpunktartig, bildlastig).

Aufruf aus dem Repo-Wurzelverzeichnis:
    python benchmark_ftf/folien.py
Ausgabe: benchmark_ftf/Folien_Benchmark_FTF.pdf
Bilder: benchmark_ftf/ergebnisse/ und docs/abb/ (müssen vorhanden sein).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

HIER = Path(__file__).resolve().parent
ERG = HIER / "ergebnisse"
ABB = HIER.parent / "docs" / "abb"
AUSGABE = HIER / "Folien_Benchmark_FTF.pdf"

BREITE, HOEHE = 13.333, 7.5  # Zoll, 16:9
BLAU = "#0065BD"      # Akzent (TUM-Blau)
DUNKEL = "#1a2733"
GRAU = "#5a6a78"
GRUEN = "#2e8b57"
ROT = "#b03030"

_seite = [0]


def _grundgeruest(titel, untertitel=None):
    fig = plt.figure(figsize=(BREITE, HOEHE))
    fig.patch.set_facecolor("white")
    _seite[0] += 1
    if titel:
        fig.add_artist(Rectangle((0.045, 0.895), 0.012, 0.062,
                                 transform=fig.transFigure, color=BLAU))
        fig.text(0.07, 0.925, titel, fontsize=23, fontweight="bold",
                 color=DUNKEL, va="center")
        if untertitel:
            fig.text(0.07, 0.878, untertitel, fontsize=13, color=GRAU, va="center")
    fig.text(0.955, 0.028, f"{_seite[0]}", fontsize=10, color=GRAU, ha="right")
    fig.text(0.045, 0.028, "PolderFit vs. FTF (LabVIEW) · Benchmark August 2026",
             fontsize=9, color=GRAU)
    return fig


def punkte(fig, zeilen, x=0.06, y0=0.80, dy=0.062, groesse=14.5, farbe=DUNKEL):
    y = y0
    for z in zeilen:
        hervor = z.startswith("!")
        if hervor:
            z = z[1:]
        fig.text(x, y, "▸", fontsize=groesse, color=BLAU, va="top")
        fig.text(x + 0.017, y, z, fontsize=groesse, va="top",
                 color=BLAU if hervor else farbe,
                 fontweight="bold" if hervor else "normal")
        y -= dy
    return y


def bild(fig, pfad, links, unten, breite, hoehe, titel=None):
    """Bild seitenverhältnistreu in die Box (Figurkoordinaten) einpassen."""
    img = mpimg.imread(str(pfad))
    ih, iw = img.shape[:2]
    box_asp = (breite * BREITE) / (hoehe * HOEHE)
    img_asp = iw / ih
    if img_asp >= box_asp:
        w, h = breite, breite * BREITE / img_asp / HOEHE
    else:
        h, w = hoehe, hoehe * HOEHE * img_asp / BREITE
    x = links + (breite - w) / 2
    y = unten + (hoehe - h) / 2
    ax = fig.add_axes([x, y, w, h])
    ax.imshow(img)
    ax.axis("off")
    if titel:
        fig.text(links + breite / 2, unten + hoehe + 0.008, titel,
                 fontsize=11, color=GRAU, ha="center")
    return ax


def tabelle(fig, links, unten, breite, hoehe, kopf, zeilen, groesse=12.5,
            hervor_spalte=None):
    ax = fig.add_axes([links, unten, breite, hoehe])
    ax.axis("off")
    t = ax.table(cellText=zeilen, colLabels=kopf, loc="center", cellLoc="center")
    t.auto_set_font_size(False)
    t.set_fontsize(groesse)
    t.scale(1, 1.9)
    for (r, c), zelle in t.get_celld().items():
        zelle.set_edgecolor("#c9d2da")
        if r == 0:
            zelle.set_facecolor(BLAU)
            zelle.set_text_props(color="white", fontweight="bold")
        elif hervor_spalte is not None and c == hervor_spalte:
            zelle.set_text_props(color=GRUEN, fontweight="bold")
    return t


def main():
    with PdfPages(AUSGABE) as pdf:

        # ------------------------------------------------ 1 · Titel
        fig = _grundgeruest(None)
        fig.add_artist(Rectangle((0.0, 0.0), 0.018, 1.0,
                                 transform=fig.transFigure, color=BLAU))
        fig.text(0.09, 0.72, "PolderFit vs. FTF (LabVIEW)",
                 fontsize=34, fontweight="bold", color=DUNKEL)
        fig.text(0.09, 0.64, "Benchmark auf realen bbFMR-Datensätzen vom Gruppenlaufwerk",
                 fontsize=17, color=GRAU)
        fig.text(0.09, 0.575, "9 Datensätze · CoFe / YIG / FeCr₂S₄ · Einzelfits + Kittel/LLG",
                 fontsize=13.5, color=GRAU)
        bild(fig, ABB / "abb_benchmark.png", 0.07, 0.10, 0.86, 0.40)
        fig.text(0.09, 0.045, "Ibrahim Yalcinsoy · Stand 17.08.2026", fontsize=12, color=GRAU)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 2 · Programm
        fig = _grundgeruest("PolderFit – das Programm",
                            "Python-Neuauswertung für bbFMR (Ersatz/Ergänzung zum LabVIEW-FTF)")
        punkte(fig, [
            "TDMS laden → Resonanz je Linescan automatisch finden → fitten → Kittel/LLG",
            "Auto-Fenster: Untergrundabzug, Kandidatensuche, Trasse (unten)",
            "Automatische Fit-Bewertung: problematische Fits werden gemeldet",
            "GUI (Plot im Fokus) und Stapelbetrieb; 1000+ Linescans pro Datei",
        ], y0=0.815, dy=0.056)
        bild(fig, ABB / "abb_autowindow.png", 0.04, 0.06, 0.92, 0.50,
             titel="AutoWindow-Pipeline an einer realen Linescan-Datei (1001 Linescans)")
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 3 · Modell
        fig = _grundgeruest("Modell: Polder-Suszeptibilität + Kittel/LLG",
                            "identische Formeln wie im FTF („FTF Formula Document“)")
        punkte(fig, [
            "je Linescan: χ(H) = χ′ + iχ″ mit linearem Untergrund, komplex gefittet",
            "µ₀ΔH = FWHM von χ″ = 2αω/γ  →  direkt mit FTF-„dH“ vergleichbar",
            "global: Kittel (g, µ₀M_eff, µ₀H_u) + LLG-Gerade (α, µ₀ΔH₀)",
        ], y0=0.815, dy=0.056)
        bild(fig, ABB / "abb_chi.png", 0.03, 0.06, 0.52, 0.52,
             titel="Polder-Suszeptibilität: schmale vs. breite Linie")
        bild(fig, ABB / "abb_linescan_fit.png", 0.56, 0.06, 0.42, 0.52,
             titel="Einzelfit mit Fenster, Untergrund, Residuen")
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 4 · Ziel & Daten
        fig = _grundgeruest("Benchmark: Ziel und Datenbasis",
                            "Referenz: fertige FTF-Auswertungen vom Gruppenlaufwerk (821 „(FTF)“-Ordner gesichtet)")
        punkte(fig, [
            "Frage: liefert PolderFit dieselben Ergebnisse wie das etablierte FTF?",
            "9 Datensätze mit vollständiger FTF-Referenz (Einzelfits + Kittel/LLG + TDMS)",
            "gestaffelte Schwierigkeit: CoFe = Standard · YIG = sehr schmal · FeCr₂S₄ = extrem breit",
            "Vergleich je Frequenz: B_res, ΔH, z-Score (kombinierte 1σ)",
            "Isolationstest: PolderFit-Kittel-Fitter auf den FTF-Punkten",
        ], y0=0.815, dy=0.052)
        bild(fig, ERG / "cofe_wm_ip_290K_1.png", 0.02, 0.06, 0.32, 0.42,
             titel="CoFe ip 290 K (ΔH ≈ 10–30 mT)")
        bild(fig, ERG / "yig_konstanz_ip_50K.png", 0.34, 0.06, 0.32, 0.42,
             titel="YIG 50 K (ΔH ≈ 17–23 mT, 367 Linescans)")
        bild(fig, ERG / "fecr2s4_100K_alphamax1.png", 0.66, 0.06, 0.32, 0.42,
             titel="FeCr₂S₄ 100 K (ΔH bis 1,3 T)")
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 5 · Ergebnis CoFe
        fig = _grundgeruest("Ergebnis: Einzelfits deckungsgleich (CoFe 290 K)",
                            "70 Frequenzen 20–66 GHz, PolderFit vollautomatisch vs. FTF-Handauswertung")
        punkte(fig, [
            "!B_res: Median-Differenz −0,04 mT · ΔH: Median +0,1 %",
            "|z| ≤ 2 für 93–100 % der Punkte (Differenzen ≈ Fehlerbalken)",
            "gleiches Bild bei CoFe 5 K und YIG (alle Tabellen im Bericht)",
        ], y0=0.815, dy=0.052)
        bild(fig, ERG / "cofe_wm_ip_290K_1.png", 0.06, 0.05, 0.88, 0.56)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 6 · Kittel/LLG
        fig = _grundgeruest("Ergebnis: Kittel/LLG – alle Parameter innerhalb 1σ",
                            "CoFe ip 290 K, ungewichteter Fit (wie FTF)")
        punkte(fig, [
            "g, µ₀M_eff, µ₀H_u, α, µ₀ΔH₀ stimmen mit FTF überein (≤ 1σ)",
            "PolderFit-Fitter auf den FTF-Punkten reproduziert FTF exakt",
            "Gewichtung 1/u² verzerrt (wenige Punkte dominieren) → Standard: ungewichtet",
        ], y0=0.815, dy=0.052)
        tabelle(fig, 0.05, 0.30, 0.90, 0.26,
                ["Quelle", "g", "µ₀M_eff [T]", "µ₀H_u [mT]", "α [10⁻³]", "µ₀ΔH₀ [mT]"],
                [
                    ["FTF (LabVIEW)", "2.1053 ± 0.0026", "2.2492 ± 0.0098",
                     "3.14 ± 0.43", "7.378 ± 0.199", "−1.01 ± 0.61"],
                    ["PolderFit (auto)", "2.1054 ± 0.0025", "2.2496 ± 0.0096",
                     "3.05 ± 0.47", "7.338 ± 0.187", "−0.92 ± 0.57"],
                    ["PF-Fitter auf FTF-Punkten", "2.1044 ± 0.0028", "2.2529 ± 0.0107",
                     "2.96 ± 0.53", "7.375 ± 0.200", "−1.01 ± 0.61"],
                ])
        bild(fig, ABB / "abb_kittel_llg.png", 0.05, 0.045, 0.90, 0.24,
             titel="Kittel-Dispersion und LLG-Gerade mit Residuen (CoFe 290 K)")
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 7 · Gleiches Fenster
        fig = _grundgeruest("Beweis der Modell-Äquivalenz: gleiches Fenster, gleiches Ergebnis",
                            "FTF-Kurvendateien enthalten das tatsächlich gefittete Feldfenster")
        punkte(fig, [
            "PolderFit auf exakt den FTF-Punkten → ΔH identisch bis 0,1 %",
            "Residuenquadratsumme dabei gleich oder minimal kleiner als FTF",
            "!⇒ Modell und Optimierer sind nicht das Problem – nur das Fenster",
            "gilt auch für FeCr₂S₄ (ΔB = 0,0 mT, ΔH-Abweichung 0,0 %)",
        ], y0=0.815, dy=0.052)
        tabelle(fig, 0.10, 0.08, 0.80, 0.42,
                ["f [GHz]", "FTF-Fenster [T] (n)", "ΔH FTF [mT]",
                 "ΔH PolderFit alt\n(Auto ±7 ΔH)", "ΔH PolderFit auf\nFTF-Fenster"],
                [
                    ["20.11", "0.170–0.205 (40)", "10.48", "10.34", "10.47"],
                    ["43.55", "0.682–0.771 (101)", "23.06", "21.00", "23.06"],
                    ["57.62", "1.079–1.176 (108)", "29.36", "25.79", "29.40"],
                    ["62.31", "1.216–1.320 (116)", "31.31", "28.54", "31.27"],
                ], groesse=13, hervor_spalte=4)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 8 · Ursache Fenster
        fig = _grundgeruest("Ursache der Abweichung: das Fitfenster",
                            "ΔH als Funktion der Fensterbreite k (Fenster = B_res ± k·ΔH), CoFe 290 K")
        punkte(fig, [
            "altes Auto-Fenster ≈ ±7 ΔH → ΔH systematisch 3–14 % zu klein",
            "!Plateau bis k ≈ 2–3: dort ist ΔH fensterunabhängig",
            "FTF-Nutzer wählten von Hand ≈ ±1,7–2 ΔH (im Plateau)",
            "im breiten Fenster: Untergrundstruktur → Residuen nicht mehr weiß",
        ], y0=0.815, dy=0.052)
        bild(fig, ABB / "abb_fenster.png", 0.05, 0.05, 0.90, 0.52)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 9 · Rohdaten-Diagnose
        fig = _grundgeruest("Blick in die Rohdaten: warum das breite Fenster kippt",
                            "CoFe 290 K, zwei Frequenzen · gepunktete Linien = FTF-Fenstergrenzen")
        punkte(fig, [
            "±7-ΔH-Fenster enthält Nachbarsignal, Ripple, Krümmung",
            "linearer Untergrund passt dort nicht → Linienbreite kompensiert",
            "auf ±2–2,5 ΔH: Residuen strukturlos (grün)",
        ], y0=0.815, dy=0.052)
        bild(fig, ERG / "_diag_cofe290K_fenster.png", 0.08, 0.05, 0.84, 0.56)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 10 · Fix Nachfenster
        fig = _grundgeruest("Fix: zweiter Fit-Durchgang auf B_res ± 2,5·ΔH („Nachfenster“)",
                            "neuer Standard in PolderFit; alt = grau, neu = grün")
        punkte(fig, [
            "!ΔH-Abweichung: Median −5,9 % → +0,1 % · |z| ≤ 2: 27 % → 100 %",
            "α (LLG) jetzt 7,34 vs. FTF 7,38 ·10⁻³ (vorher 6,42: −13 %)",
            "Mehrkosten nur ≈ 2 % Fitzeit; Parameter im GUI einstellbar",
        ], y0=0.815, dy=0.052)
        bild(fig, ABB / "abb_benchmark.png", 0.03, 0.30, 0.94, 0.30)
        bild(fig, ABB / "abb_zscore.png", 0.16, 0.035, 0.68, 0.26,
             titel="z-Score-Verteilungen alt/neu gegen Normalverteilung")
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 11 · Bugfix Kittel-ip
        fig = _grundgeruest("Nebenfund 1 (behoben): Kittel-ip-Fit war entartet",
                            "aufgedeckt am YIG-Datensatz")
        punkte(fig, [
            "(M_eff, H_u) → (−M_eff, H_u + M_eff) ergibt exakt dieselbe Kurve",
            "PolderFit landete je nach Startwert auf dem unphysikalischen Ast",
            "YIG alt: µ₀M_eff = −0,13 T, µ₀H_u = +127 mT (FTF: +0,13 T / −4 mT)",
            "!Fix: Schranke µ₀M_eff ≥ 0 + interne g-Parametrisierung → wie FTF",
        ], y0=0.815, dy=0.052)
        bild(fig, ABB / "abb_ip_entartung.png", 0.07, 0.05, 0.86, 0.50)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 12 · FeCr2S4
        fig = _grundgeruest("Nebenfund 2 + Grenzfall: extrem breite Linien (FeCr₂S₄)",
                            "ΔH ≈ 0,15–1,9 T, α ≈ 0,2–0,4 · 100 K mit α-Obergrenze 1,0")
        punkte(fig, [
            "harte α-Obergrenze 0,1 machte FeCr₂S₄ unfittbar → jetzt Parameter (bis 2)",
            "100 K: g = 1,74 vs. FTF 1,76 · α = 0,21 vs. 0,22",
            "auf den FTF-Fenstern exakt identisch (0,0 % Abweichung)",
            "offen: Auto-Fenster für ΔH ≳ 0,3 T (Deckel ±0,4 T) – dokumentierte Grenze",
        ], y0=0.815, dy=0.052)
        bild(fig, ERG / "fecr2s4_100K_alphamax1.png", 0.08, 0.045, 0.84, 0.54)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 13 · FTF-Befunde
        fig = _grundgeruest("Der Benchmark war kritisch in beide Richtungen: Befunde zum FTF",
                            "Referenz ≠ Wahrheit – mehrere FTF-Ergebnisse auf dem Laufwerk sind defekt")
        punkte(fig, [
            "3 Kittel-Fits mit g = 4,000 an der Fitgrenze (Fehler ~10⁸) – Artefakte",
            "ein Ordner mit 6 identischen Parameterdateien (Kopierfehler)",
            "oop-„M eff“ im FTF hat umgekehrtes Vorzeichen (B_res = ω/γ − M)",
            "die Einzelfits (Hres, dH) dieser Ordner sind in Ordnung –",
            "PolderFit reproduziert sie (ΔH-Median +0,1 %) und liefert gültige Kittel-Werte",
        ], y0=0.815, dy=0.052, x=0.05)
        bild(fig, ERG / "cofe_wm_ip_290K_2.png", 0.14, 0.04, 0.72, 0.46,
             titel="cofe_wm_ip_290K_2: Einzelfits deckungsgleich – FTF-Kittel trotzdem g = 4,000")
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 14 · Regression
        fig = _grundgeruest("Absicherung: Regressionslauf über den Gesamtdatenbestand",
                            "AutoWindow-Harness, 286 reale Dateien (12 GB), 122 332 Resonanzen")
        punkte(fig, [
            "!OK-Quote steigt: 82,3 % → 83,4 % (≈ 1 400 Fits zusätzlich sauber)",
            "keine echten neuen stillen Ausfälle (48 Fälle = Prüf-Artefakt, geprüft)",
            "Mehrkosten des zweiten Durchgangs: ≈ 2 % Fitzeit",
            "13 neue Regressionstests (tests/test_benchmark_ftf_fixes.py)",
        ], y0=0.815, dy=0.052)
        ax = fig.add_axes([0.24, 0.07, 0.52, 0.42])
        kat = ["OK", "gemeldet\nproblematisch", "still\nfehlerhaft"]
        vorher = [82.3, 17.2, 0.42]
        nachher = [83.4, 16.1, 0.46]
        x = range(len(kat))
        ax.bar([i - 0.18 for i in x], vorher, width=0.34, color="#9aa7b1", label="vorher")
        ax.bar([i + 0.18 for i in x], nachher, width=0.34, color=GRUEN, label="nachher (Nachfenster 2,5)")
        for i, (v, n) in enumerate(zip(vorher, nachher)):
            ax.text(i - 0.18, v + 1.2, f"{v:.1f} %".replace(".", ","), ha="center", fontsize=11)
            ax.text(i + 0.18, n + 1.2, f"{n:.2f} %".replace(".", ",") if n < 1
                    else f"{n:.1f} %".replace(".", ","), ha="center", fontsize=11,
                    color=GRUEN, fontweight="bold")
        ax.set_xticks(list(x)); ax.set_xticklabels(kat, fontsize=12)
        ax.set_ylabel("Anteil der Resonanzen [%]", fontsize=12)
        ax.set_ylim(0, 100)
        ax.legend(fontsize=11, frameon=False)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        pdf.savefig(fig); plt.close(fig)

        # ------------------------------------------------ 15 · Einordnung & Fazit
        fig = _grundgeruest("Einordnung und Fazit")
        fig.text(0.06, 0.82, "Einordnung", fontsize=16, fontweight="bold", color=BLAU)
        punkte(fig, [
            "alle FTF-Referenzen sind sortierte Colormaps – echte Linescan-",
            "Messungen mit FTF-Auswertung existieren auf dem Laufwerk nicht",
            "Modell-Äquivalenz gilt messmodusunabhängig; Fensterbefund wird auf",
            "einem echten Linescan nachgeprüft, sobald eine Referenz vorliegt",
        ], y0=0.765, dy=0.048, groesse=13.5)
        fig.text(0.06, 0.53, "Fazit", fontsize=16, fontweight="bold", color=BLAU)
        punkte(fig, [
            "!PolderFit ≡ FTF auf gleichem Fenster (B_res 10⁻⁵ T, ΔH 0,1 %)",
            "Abweichungsursache Fitfenster gefunden, erklärt, behoben (Nachfenster 2,5 ΔH)",
            "2 Defekte behoben (Kittel-ip, α-Deckel) · Standard ungewichtet wie FTF",
            "defekte FTF-Referenzen identifiziert · Grenzen dokumentiert (sehr breite Linien)",
            "reproduzierbar: 1 Skriptaufruf je Datensatz – weitere Stichproben in Minuten",
        ], y0=0.475, dy=0.052)
        fig.add_artist(Rectangle((0.045, 0.10), 0.91, 0.002,
                                 transform=fig.transFigure, color="#c9d2da"))
        fig.text(0.06, 0.065, "Details: benchmark_ftf/BERICHT.md · Ergebnisse: benchmark_ftf/ergebnisse/",
                 fontsize=11, color=GRAU)
        pdf.savefig(fig); plt.close(fig)

    print(f"geschrieben: {AUSGABE}")


if __name__ == "__main__":
    main()
