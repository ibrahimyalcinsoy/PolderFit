"""Tests der portierten Verarbeitungsoperationen und der Verarbeitungskette.

Referenzen:

* Bit-Treue zu pybbfmr 0.2.1: ``bbfmr/test/test_processing.py`` dort prueft
  ``derivative_divide`` fuer modulation_amp 1 und 2 (average=False) gegen den
  von Hand gebildeten Zentral-Differenzenquotienten – diese Tests sind hier
  in der Achsen-Konvention des Projekts (Zeilen = Frequenzen) uebernommen.
* Physik: Maier-Flaig et al., Rev. Sci. Instrum. 89, 076101 (2018), Gl. (3)/(4):
  derivative divide eliminiert frequenzabhaengigen Untergrund und Phase und
  legt die Mode entlang der Kittel-Geraden frei.
"""

import numpy as np
import pytest

from bbfmr.io.datensatz import Linescan, Messdatensatz
from bbfmr.physik.konstanten import GAMMA_STANDARD
from bbfmr.physik.suszeptibilitaet import chi_oop
from bbfmr.verarbeitung import (
    KettenSchritt,
    Verarbeitungskette,
    anzeige_transform,
    derivative_divide,
    divide_slice,
    relation_amplitude,
)


def _zufallsmatrix(n_freq=5, n_feld=21, seed=7):
    rng = np.random.default_rng(seed)
    feld = np.sort(rng.uniform(0.5, 1.5, n_feld))     # unregelmaessiges Gitter
    frequenz = np.linspace(5e9, 15e9, n_freq)
    Z = rng.normal(size=(n_freq, n_feld)) + 1j * rng.normal(size=(n_freq, n_feld))
    return feld, frequenz, Z


# --- derivative_divide -----------------------------------------------------------

def test_dd_delta1_gegen_handrechnung():
    """pybbfmr testDerivativeDivide_modamp1, uebertragen auf unsere Orientierung."""
    feld, frequenz, Z = _zufallsmatrix()
    _, _, G = derivative_divide(feld, frequenz, Z, delta_n=1, mitteln=False)
    for i in (1, 10, 19):
        d = (feld[i + 1] - feld[i - 1]) / 2.0
        erwartet = (Z[:, i + 1] - Z[:, i - 1]) / Z[:, i] / d
        np.testing.assert_allclose(G[:, i], erwartet, rtol=1e-12)


def test_dd_delta2_gegen_handrechnung():
    """pybbfmr testDerivativeDivide_modamp2: Schrittweite (x[i+2]-x[i-2])/4."""
    feld, frequenz, Z = _zufallsmatrix()
    _, _, G = derivative_divide(feld, frequenz, Z, delta_n=2, mitteln=False)
    for i in (2, 9, 18):
        d = (feld[i + 2] - feld[i - 2]) / 4.0
        erwartet = (Z[:, i + 2] - Z[:, i - 2]) / Z[:, i] / d
        np.testing.assert_allclose(G[:, i], erwartet, rtol=1e-12)


def test_dd_raender_nan_und_form_bleibt():
    feld, frequenz, Z = _zufallsmatrix()
    _, _, G = derivative_divide(feld, frequenz, Z, delta_n=3, mitteln=False)
    assert G.shape == Z.shape
    assert np.all(np.isnan(G[:, :3])) and np.all(np.isnan(G[:, -3:]))
    assert np.all(np.isfinite(G[:, 3:-3]))


def test_dd_mitteln_fenster_manuell():
    """mitteln=True: links Mittel ueber [i-Δn, i), rechts ueber [i, i+Δn] (pybbfmr)."""
    feld = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    frequenz = np.array([1e9])
    Z = (np.arange(5, dtype=float) + 1j * np.arange(5, dtype=float) ** 2)[np.newaxis, :]
    _, _, G = derivative_divide(feld, frequenz, Z, delta_n=2, mitteln=True)
    z_links = np.mean(Z[:, 0:2], axis=1)
    z_rechts = np.mean(Z[:, 2:5], axis=1)
    d = np.mean(np.diff(feld)[0:4])
    np.testing.assert_allclose(G[:, 2], (z_rechts - z_links) / Z[:, 2] / d, rtol=1e-12)
    assert np.all(np.isnan(G[:, [0, 1, 3, 4]]))


def test_dd_entlang_frequenzachse_ist_transponiert():
    feld, frequenz, Z = _zufallsmatrix(n_freq=9, n_feld=7)
    _, _, G_f = derivative_divide(feld, frequenz, Z, delta_n=1, mitteln=False,
                                  achse="frequenz")
    _, _, G_t = derivative_divide(frequenz, feld, Z.T, delta_n=1, mitteln=False,
                                  achse="feld")
    np.testing.assert_allclose(G_f, G_t.T, rtol=1e-12, equal_nan=True)


def test_dd_parameter_validierung():
    feld, frequenz, Z = _zufallsmatrix()
    with pytest.raises(ValueError):
        derivative_divide(feld, frequenz, Z, delta_n=0)
    with pytest.raises(ValueError):
        derivative_divide(feld, frequenz, Z, delta_n=11)  # 21 Punkte: max 10
    with pytest.raises(ValueError):
        derivative_divide(feld, frequenz, Z, achse="quer")


# --- divide_slice ------------------------------------------------------------------

def test_divide_slice_feld_referenz():
    feld, frequenz, Z = _zufallsmatrix()
    _, _, G = divide_slice(feld, frequenz, Z, achse="feld", index=0)
    np.testing.assert_allclose(G, Z / Z[:, 0][:, np.newaxis], rtol=1e-12)
    np.testing.assert_allclose(G[:, 0], 1.0 + 0j)  # Referenzspalte wird 1

    # Auswahl ueber Feldwert stattdessen Index.
    _, _, G2 = divide_slice(feld, frequenz, Z, achse="feld", index=None, wert=feld[5])
    np.testing.assert_allclose(G2, Z / Z[:, 5][:, np.newaxis], rtol=1e-12)


def test_divide_slice_frequenz_referenz():
    feld, frequenz, Z = _zufallsmatrix()
    _, _, G = divide_slice(feld, frequenz, Z, achse="frequenz", index=-1)
    np.testing.assert_allclose(G, Z / Z[-1, :][np.newaxis, :], rtol=1e-12)


def test_divide_slice_validierung():
    feld, frequenz, Z = _zufallsmatrix()
    with pytest.raises(ValueError):
        divide_slice(feld, frequenz, Z, achse="feld", index=None, wert=None)
    with pytest.raises(ValueError):
        divide_slice(feld, frequenz, Z, achse="feld", index=99)


# --- relation_amplitude ---------------------------------------------------------------

def test_relation_amplitude_feld():
    feld, frequenz, Z = _zufallsmatrix()
    _, _, G = relation_amplitude(feld, frequenz, Z, delta_n=3)
    np.testing.assert_allclose(G[:, :-3], Z[:, :-3] / Z[:, 3:], rtol=1e-12)
    assert np.all(np.isnan(G[:, -3:]))


def test_relation_amplitude_frequenz():
    feld, frequenz, Z = _zufallsmatrix()
    _, _, G = relation_amplitude(feld, frequenz, Z, delta_n=2, achse="frequenz")
    np.testing.assert_allclose(G[:-2, :], Z[:-2, :] / Z[2:, :], rtol=1e-12)
    assert np.all(np.isnan(G[-2:, :]))


# --- Physik: Untergrund-Elimination und Kittel-Gerade -------------------------------

def _synthetisches_s21(a_signal=0.02):
    """S21 nach Maier-Flaig 2018 Gl. (3): Untergrund + Phase + Polder-Resonanz.

    oop-Kittel: B_res(f) = omega/gamma + mu0Meff (Resonanz exakt auf Gerade).
    """
    gamma = GAMMA_STANDARD
    mu0Meff = 0.4
    alpha = 0.008
    feld = np.linspace(0.45, 1.05, 301)
    frequenz = np.linspace(5e9, 15e9, 21)
    Z = np.empty((frequenz.size, feld.size), dtype=complex)
    b_res = np.empty(frequenz.size)
    for j, f in enumerate(frequenz):
        omega = 2.0 * np.pi * f
        b_res[j] = omega / gamma + mu0Meff
        chi = chi_oop(feld, b_res[j], alpha, omega, gamma)
        chi = chi / np.max(np.abs(chi))  # normiert; Skala uebernimmt a_signal
        untergrund = 1.0 + 0.5 * np.sin(2.0 * np.pi * f / 2e9)      # V_bg(omega)
        phase = np.exp(1j * (0.3 + 2.0 * np.pi * f * 5e-9))          # e^(i*phi(omega))
        Z[j, :] = (untergrund + a_signal * untergrund * chi) * phase
    return feld, frequenz, Z, b_res


def test_dd_eliminiert_reinen_untergrund_exakt():
    """Ohne Resonanzsignal (A=0) ist d_D S21 exakt 0: Gl. (4) entfernt V_bg und Phase."""
    feld, frequenz, Z, _ = _synthetisches_s21(a_signal=0.0)
    _, _, G = derivative_divide(feld, frequenz, Z, delta_n=2)
    inneres = G[:, 2:-2]
    np.testing.assert_allclose(np.abs(inneres), 0.0, atol=1e-12)


def test_kette_legt_kittel_gerade_frei():
    """divide-slice + derivative-divide: Peak je Frequenz liegt auf B_res(f)."""
    feld, frequenz, Z, b_res = _synthetisches_s21()
    kette = Verarbeitungskette(schritte=[
        KettenSchritt("divide_slice", aktiv=True, parameter={"achse": "feld", "index": 0}),
        KettenSchritt("derivative_divide", aktiv=True,
                      parameter={"delta_n": 2, "mitteln": True, "achse": "feld"}),
    ])
    _, _, G = kette.anwenden(feld, frequenz, Z)
    betrag = np.abs(G)
    schritt = feld[1] - feld[0]
    for j in range(frequenz.size):
        spalte = np.nanargmax(betrag[j])
        assert abs(feld[spalte] - b_res[j]) <= 3 * schritt, (
            f"Peak bei f={frequenz[j]/1e9:.1f} GHz liegt {feld[spalte]:.4f} T, "
            f"erwartet {b_res[j]:.4f} T")


# --- Kette & Serialisierung ------------------------------------------------------------

def test_kette_reihenfolge_und_abschalten():
    feld, frequenz, Z = _zufallsmatrix()
    kette = Verarbeitungskette.standard()
    # Standard: nur derivative_divide aktiv (Δn=4, mitteln=True).
    aktive = [s.operation for s in kette.aktive_schritte()]
    assert aktive == ["derivative_divide"]
    _, _, G_kette = kette.anwenden(feld, frequenz, Z)
    _, _, G_direkt = derivative_divide(feld, frequenz, Z, delta_n=4, mitteln=True)
    np.testing.assert_allclose(G_kette, G_direkt, rtol=1e-12, equal_nan=True)

    # Alles aus -> Identitaet.
    for s in kette.schritte:
        s.aktiv = False
    _, _, G_roh = kette.anwenden(feld, frequenz, Z)
    np.testing.assert_array_equal(G_roh, Z)
    assert kette.beschreibung() == "roh"


def test_kette_json_roundtrip():
    kette = Verarbeitungskette.standard()
    kette.schritte[0].aktiv = True
    kette.schritte[1].parameter["delta_n"] = 7
    import json
    daten = json.loads(json.dumps(kette.als_dict()))
    kopie = Verarbeitungskette.aus_dict(daten)
    assert [s.operation for s in kopie.schritte] == [s.operation for s in kette.schritte]
    assert [s.aktiv for s in kopie.schritte] == [s.aktiv for s in kette.schritte]
    assert kopie.schritte[1].parameter["delta_n"] == 7


def test_unbekannte_operation_abgelehnt():
    with pytest.raises(ValueError):
        KettenSchritt("fourier_hexerei")


def test_anzeige_transformationen():
    Z = np.array([[1.0 + 1.0j, -2.0 + 0.0j]])
    np.testing.assert_allclose(anzeige_transform(Z, "betrag"), np.abs(Z))
    np.testing.assert_allclose(anzeige_transform(Z, "real"), Z.real)
    np.testing.assert_allclose(anzeige_transform(Z, "imag"), Z.imag)
    np.testing.assert_allclose(anzeige_transform(Z, "db"), 20 * np.log10(np.abs(Z)))
    np.testing.assert_allclose(anzeige_transform(Z, "phase"),
                               np.degrees(np.angle(Z)))
    with pytest.raises(ValueError):
        anzeige_transform(Z, "kubisch")


# --- komplexe Matrix des Datensatzes -----------------------------------------------------

def test_komplexe_matrix_und_anzeige_matrix_konsistent():
    b1 = np.linspace(1.0, 2.0, 50)
    b2 = np.linspace(1.2, 1.8, 30)  # engerer Feldbereich -> NaN-Raender
    ls1 = Linescan(frequenz=10e9, feld=b1, re=np.cos(b1), im=np.sin(b1))
    ls2 = Linescan(frequenz=20e9, feld=b2, re=np.cos(b2), im=-np.sin(b2))
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=[ls1, ls2])

    feld, freq, Z = ds.komplexe_matrix(80)
    assert Z.shape == (2, 80) and np.iscomplexobj(Z)
    # Zeile 2 hat NaN ausserhalb [1.2, 1.8].
    aussen = (feld < b2[0]) | (feld > b2[-1])
    assert np.all(np.isnan(Z[1, aussen])) and np.all(np.isfinite(Z[1, ~aussen]))
    # Interpolationstreue an den Stuetzstellen der Gitterpunkte.
    j = 40
    erwartet = np.interp(feld[j], b1, np.cos(b1)) + 1j * np.interp(feld[j], b1, np.sin(b1))
    np.testing.assert_allclose(Z[0, j], erwartet, rtol=1e-12)
    # anzeige_matrix ist exakt der Betrag der komplexen Matrix.
    _, _, mag = ds.anzeige_matrix(80)
    np.testing.assert_allclose(mag, np.abs(Z), equal_nan=True)
