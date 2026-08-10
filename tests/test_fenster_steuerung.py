# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Tests des Bereichs-Fits (Rechteck -> nur dort neu fitten).

Kernszenario (Aufgabenbereich 3): Zwei aehnlich starke Signale im Sweep -
die echte Mode auf der Kittel-Geraden und ein Stoersignal daneben. Der
Auto-Fit haengt am Stoersignal; das Rechteck um die Mode zwingt Fenstersuche
und B_res in den markierten Bereich, Ergebnisse ausserhalb bleiben unberuehrt.
"""

import numpy as np

from polderfit.fit import fitte_alle, fitte_bereich
from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.physik.konstanten import GAMMA_STANDARD
from polderfit.physik.suszeptibilitaet import chi_oop

GAMMA = GAMMA_STANDARD
MU0MEFF = 0.4


def _zweimoden_datensatz(n_freq=6, n_feld=200, stoer_staerke=2.0):
    """Echte oop-Mode auf der Kittel-Geraden + staerkeres Stoersignal daneben.

    Nur 6 Linescans (< 8): der feld-stationaere Untergrundabzug der
    AutoWindows greift nicht, und das Stoersignal driftet zusaetzlich leicht
    mit der Frequenz - der Auto-Fit soll sich hier absichtlich fangen lassen.

    Das Stoersignal ist bewusst eine lokalisierte, SPIEGELFREIE Lorentz-Linie
    (kein ``chi_oop``): Der Polder-Nenner von ``chi_oop`` ist symmetrisch in
    ``mu0H - mu0Meff`` und erzeugt zu jeder Resonanz bei ``B_res`` eine gleich
    starke Spiegelresonanz bei ``B_res - 2*omega/gamma``. Fuer ein Stoersignal
    bei hohem Feld faellt diese Spiegelung bei tiefen Frequenzen mitten ins
    Rechteck und wuerde die von diesem Test geforderte Trennung (Stoersignal
    ausserhalb, Mode innerhalb) physikalisch unmoeglich machen. Eine reine
    Lorentz-Linie modelliert ein Artefakt/eine Stoermode ohne Spiegelung.
    """
    freqs = np.linspace(8e9, 18e9, n_freq)
    B = np.linspace(0.5, 1.6, n_feld)
    rng = np.random.default_rng(11)
    linescans, b_res_wahr = [], []
    for k, f in enumerate(freqs):
        omega = 2 * np.pi * f
        br = omega / GAMMA + MU0MEFF
        b_res_wahr.append(br)
        mode = chi_oop(B, br, 0.01, omega, GAMMA)
        # Stoersignal: lokalisierte, spiegelfreie komplexe Lorentz-Linie abseits
        # der Kittel-Geraden (bei hohem Feld, driftet leicht mit k), auf die
        # Modenamplitude skaliert und staerker als die echte Mode.
        skala = float(np.abs(mode).max())
        b_stoer = 1.45 + 0.01 * k
        hwhm = 0.02
        stoerung = skala * hwhm / ((B - b_stoer) + 1j * hwhm)
        s = 5e4 * (mode + stoer_staerke * stoerung) + (0.02 + 0.01j)
        s += rng.normal(scale=2e-4, size=n_feld) + 1j * rng.normal(scale=2e-4, size=n_feld)
        linescans.append(Linescan(frequenz=float(f), feld=B, re=s.real, im=s.imag))
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=linescans)
    return ds, np.array(b_res_wahr)


def test_rechteck_loest_mehrdeutigkeit_auf():
    ds, b_res_wahr = _zweimoden_datensatz()
    stapel = fitte_alle(ds)

    # Vorbedingung des Szenarios: der Auto-Fit haengt (mindestens teilweise)
    # am Stoersignal bei hohem Feld.
    gefangen = [i for i, e in enumerate(stapel.ergebnisse)
                if abs(e.B_res - b_res_wahr[i]) > 0.05]
    assert gefangen, "Szenario-Aufbau: Auto-Fit sollte sich am Stoersignal fangen."

    # Rechteck eng um die echte Mode (Stoersignal bei ~1.45+ T liegt draussen).
    neu, uebersprungen = fitte_bereich(
        stapel, feld_min=0.55, feld_max=1.30,
        frequenz_min=ds.frequenzen.min(), frequenz_max=ds.frequenzen.max())
    assert len(neu) == len(ds) and not uebersprungen
    for i in neu:
        e = stapel.ergebnisse[i]
        assert 0.55 <= e.B_res <= 1.30, f"B_res {e.B_res:.3f} T verlaesst das Rechteck"
        assert abs(e.B_res - b_res_wahr[i]) < 0.02, (
            f"f={e.frequenz/1e9:.1f} GHz: B_res={e.B_res:.3f} T, "
            f"wahr {b_res_wahr[i]:.3f} T")
        assert e.nachbearbeitet is True
        # Fenster liegt im Rechteck.
        unten, oben = stapel.fenster[i]
        assert unten >= 0.55 - 1e-9 and oben <= 1.30 + 1e-9


def test_ausserhalb_bleibt_unangetastet():
    ds, _ = _zweimoden_datensatz()
    stapel = fitte_alle(ds)
    vorher = list(stapel.ergebnisse)
    fenster_vorher = list(stapel.fenster)

    # Rechteck nur ueber die mittleren Frequenzen.
    f = ds.frequenzen
    neu, _ = fitte_bereich(stapel, 0.55, 1.30, f[2], f[3])
    assert neu == [2, 3]
    for i in range(len(ds)):
        if i in neu:
            assert stapel.ergebnisse[i] is not vorher[i]
        else:
            # Identische Objekte: garantiert nicht angefasst.
            assert stapel.ergebnisse[i] is vorher[i]
            assert stapel.fenster[i] == fenster_vorher[i]


def test_rechteck_ohne_daten_wird_uebersprungen():
    ds, _ = _zweimoden_datensatz()
    stapel = fitte_alle(ds)
    vorher = list(stapel.ergebnisse)

    # Feldbereich ausserhalb der Messung: alles wird uebersprungen.
    neu, uebersprungen = fitte_bereich(stapel, 5.0, 6.0,
                                       ds.frequenzen.min(), ds.frequenzen.max())
    assert neu == [] and len(uebersprungen) == len(ds)
    assert all(stapel.ergebnisse[i] is vorher[i] for i in range(len(ds)))

    # Frequenzband ohne Linescans: nichts betroffen.
    neu, uebersprungen = fitte_bereich(stapel, 0.55, 1.30, 100e9, 200e9)
    assert neu == [] and uebersprungen == []


def test_verdrehte_grenzen_werden_sortiert():
    ds, _ = _zweimoden_datensatz(n_freq=6)
    stapel = fitte_alle(ds)
    f = ds.frequenzen
    neu1, _ = fitte_bereich(stapel, 1.30, 0.55, f[3], f[2])  # beides verdreht
    assert neu1 == [2, 3]


def test_feste_fensterbreite_in_punkten():
    """Option 'Fensterbreite fest': Fenster = Zentrum +/- Breite/2 Feldpunkte."""
    import pytest

    ds, _ = _zweimoden_datensatz(n_freq=6)
    stapel = fitte_alle(ds)
    breite = 40
    neu, _ = fitte_bereich(stapel, 0.55, 1.30,
                           ds.frequenzen.min(), ds.frequenzen.max(),
                           breite_punkte=breite)
    assert neu
    for i in neu:
        ls = ds.linescans[i]
        schritt = float(np.ptp(ls.feld)) / (ls.feld.size - 1)
        unten, oben = stapel.fenster[i]
        # Ans Rechteck geklemmt, sonst exakt die verlangte Breite.
        assert oben - unten <= breite * schritt + 1e-9
        assert unten >= 0.55 - 1e-9 and oben <= 1.30 + 1e-9

    with pytest.raises(ValueError):
        fitte_bereich(stapel, 0.55, 1.30, ds.frequenzen.min(),
                      ds.frequenzen.max(), breite_punkte=2)


def _datensatz_mit_stationaerem_stoerstreifen(n_freq=24, n_feld=220):
    """Wandernde Mode + STARKER feld-stationaerer Stoerstreifen (fester B-Wert).

    Reproduziert das Fehlerbild aus der Praxis (stehende Wellen als senkrechte
    Streifen im Farbplot): Der Streifen sitzt bei festem Feld INNERHALB des
    Nachfit-Rechtecks und ist staerker als die Mode. Ohne den feld-stationaeren
    Untergrundabzug schnappt die Fenstersuche im Rechteck auf den Streifen.
    n_freq >= 8 und gemeinsames Feldgitter, damit der Abzug greift.
    """
    freqs = np.linspace(8e9, 18e9, n_freq)
    B = np.linspace(0.5, 1.6, n_feld)
    rng = np.random.default_rng(7)
    moden, b_res_wahr = [], []
    for f in freqs:
        omega = 2 * np.pi * f
        br = omega / GAMMA + MU0MEFF
        b_res_wahr.append(br)
        moden.append(chi_oop(B, br, 0.01, omega, GAMMA))
    # Stationaerer Streifen: fester Feldwert, ueber ALLE Frequenzen identisch
    # (stehende Welle), deutlich staerker als die Mode.
    skala = max(float(np.abs(m).max()) for m in moden)
    hwhm = 0.015
    streifen = 3.0 * skala * hwhm / ((B - 1.30) + 1j * hwhm)
    linescans = []
    for f, mode in zip(freqs, moden):
        s = 5e4 * (mode + streifen) + (0.02 + 0.01j)
        s += rng.normal(scale=2e-4, size=n_feld) + 1j * rng.normal(scale=2e-4, size=n_feld)
        linescans.append(Linescan(frequenz=float(f), feld=B, re=s.real, im=s.imag))
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=linescans)
    return ds, np.array(b_res_wahr)


def test_bereichs_fit_ignoriert_stationaeren_stoerstreifen():
    """Rechteck enthaelt Mode UND stationaeren Streifen -> Fit trifft die Mode."""
    ds, b_res_wahr = _datensatz_mit_stationaerem_stoerstreifen()
    stapel = fitte_alle(ds)
    # Rechteck grosszuegig: enthaelt bewusst auch den Streifen bei 1.30 T.
    neu, uebersprungen = fitte_bereich(
        stapel, feld_min=0.55, feld_max=1.55,
        frequenz_min=ds.frequenzen.min(), frequenz_max=ds.frequenzen.max())
    assert len(neu) == len(ds) and not uebersprungen
    daneben = [i for i in neu if abs(stapel.ergebnisse[i].B_res - b_res_wahr[i]) > 0.03]
    assert not daneben, (
        f"{len(daneben)} Fits haengen am stationaeren Streifen statt an der Mode: "
        + ", ".join(f"f={ds.frequenzen[i]/1e9:.1f} GHz B={stapel.ergebnisse[i].B_res:.3f}"
                    for i in daneben[:5]))


def test_grenzgerade_erlaubtes_intervall():
    from polderfit.fit import Grenzgerade

    # Feld-konstante Gerade (senkrecht im Plot): trennt links/rechts.
    g = Grenzgerade(b1=1.0, f1=5e9, b2=1.0, f2=50e9, gruen_positiv=True)
    lo, hi = g.erlaubtes_intervall(20e9, 0.5, 1.6)
    assert (lo, hi) == (1.0, 1.6)          # gruen = hohe Felder
    g.seite_wechseln()
    lo, hi = g.erlaubtes_intervall(20e9, 0.5, 1.6)
    assert (lo, hi) == (0.5, 1.0)          # nach dem Wechsel: tiefe Felder

    # Frequenz-konstante Gerade (waagerecht): ganze Zeile erlaubt oder nicht.
    g2 = Grenzgerade(b1=0.5, f1=20e9, b2=1.6, f2=20e9, gruen_positiv=True)
    oben = g2.erlaubtes_intervall(30e9, 0.5, 1.6)
    unten = g2.erlaubtes_intervall(10e9, 0.5, 1.6)
    assert (oben is None) != (unten is None)  # genau eine Seite erlaubt

    # Schraege Gerade: Grenzfeld wandert linear mit der Frequenz.
    g3 = Grenzgerade(b1=1.0, f1=10e9, b2=1.2, f2=20e9, gruen_positiv=True)
    a = g3.erlaubtes_intervall(10e9, 0.0, 2.0)
    b = g3.erlaubtes_intervall(20e9, 0.0, 2.0)
    assert a is not None and b is not None
    grenze_a = a[0] if a[0] > 0.0 else a[1]
    grenze_b = b[0] if b[0] > 0.0 else b[1]
    assert abs(grenze_a - 1.0) < 1e-9 and abs(grenze_b - 1.2) < 1e-9


def test_grenzgeraden_fit_nur_gruene_seite():
    from polderfit.fit import Grenzgerade, fitte_geraden_bereich

    ds, b_res_wahr = _datensatz_mit_stationaerem_stoerstreifen()
    stapel = fitte_alle(ds)
    # Senkrechte Gerade bei 1.25 T, gruen = tiefe Felder (Mode-Seite; der
    # Streifen bei 1.30 T liegt auf der roten Seite).
    gerade = Grenzgerade(b1=1.25, f1=ds.frequenzen.min(),
                         b2=1.25, f2=ds.frequenzen.max(), gruen_positiv=False)
    neu, uebersprungen = fitte_geraden_bereich(stapel, [gerade])
    assert neu
    for i in neu:
        e = stapel.ergebnisse[i]
        unten, oben = stapel.fenster[i]
        assert oben <= 1.25 + 1e-9          # Fenster bleibt auf der gruenen Seite
        if b_res_wahr[i] <= 1.25:           # Mode liegt im gruenen Bereich
            assert abs(e.B_res - b_res_wahr[i]) < 0.03

    # Zwei Geraden -> Band: nur Frequenzen, deren Zeile das Band schneidet.
    quer = Grenzgerade(b1=0.5, f1=12e9, b2=1.6, f2=12e9, gruen_positiv=True)
    erlaubt_oben = quer.erlaubtes_intervall(15e9, 0.5, 1.6) is not None
    neu2, ueber2 = fitte_geraden_bereich(stapel, [gerade, quer])
    betroffene_f = {stapel.datensatz.frequenzen[i] for i in neu2}
    if erlaubt_oben:
        assert all(f > 12e9 for f in betroffene_f)
    else:
        assert all(f < 12e9 for f in betroffene_f)
    assert set(neu2) | set(ueber2) == set(range(len(ds)))
