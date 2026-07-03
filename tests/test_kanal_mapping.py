"""Tests des Kanal-Mappings: Profile, Heuristik, Laden ueber Zuordnung,
Index-Datei-Fallback (Windows-Bug) und Import-Validierung.

Alle Tests arbeiten mit kleinen, synthetisch geschriebenen TDMS-Dateien –
keine Abhaengigkeit von den grossen Beispiel-Messdaten.
"""

import numpy as np
import pytest
from nptdms import ChannelObject, TdmsWriter

from bbfmr.io import (
    EINGEBAUTE_PROFILE,
    MappingErforderlich,
    MappingProfil,
    finde_profil,
    inspiziere_tdms,
    lade_profil,
    lade_profile,
    lade_tdms,
    pruefe_datensatz,
    rate_zuordnung,
    schlage_layout_vor,
    speichere_profil,
)
from bbfmr.io.datensatz import Linescan, Messdatensatz
from bbfmr.io.kanal_mapping import PROFIL_SORTIERT, PROFIL_UNSORTIERT


# --- Hilfen: synthetische TDMS-Dateien ----------------------------------------

def _schreibe_tdms(pfad, gruppen):
    """Schreibt ``{gruppe: {kanal: array}}`` als TDMS-Datei."""
    kanaele = [
        ChannelObject(gruppe, kanal, np.asarray(werte))
        for gruppe, kv in gruppen.items()
        for kanal, werte in kv.items()
    ]
    with TdmsWriter(str(pfad)) as schreiber:
        schreiber.write_segment(kanaele)


def _sortiert_daten(n_freq=3, n_feld=20):
    """Kanaldaten im sortierten Layout (ein Eintrag je Messpunkt)."""
    frequenz = np.repeat(np.array([10e9, 20e9, 30e9])[:n_freq], n_feld)
    feld = np.tile(np.linspace(0.5, 1.5, n_feld), n_freq)
    re = np.cos(feld) * 0.01
    im = np.sin(feld) * 0.01
    return frequenz, feld, re, im


def _schreibe_sortiert(pfad):
    frequenz, feld, re, im = _sortiert_daten()
    _schreibe_tdms(pfad, {
        "ZVB": {"frequency": frequenz, "ReS21": re, "ImS21": im},
        "Field": {"Field-before": feld - 0.001, "Field-after": feld + 0.001},
    })


def _schreibe_unsortiert(pfad, n_feld=5, n_freq=7):
    """Matrix-Layout: je Feldschritt ein identischer Frequenzsweep."""
    sweep = np.linspace(5e9, 11e9, n_freq)
    frequenz = np.tile(sweep, n_feld)
    signal = np.arange(n_feld * n_freq, dtype=float)
    feld = np.linspace(0.2, 1.0, n_feld)
    _schreibe_tdms(pfad, {
        "Read.PNAX": {"Frequency": frequenz, "REALS21": signal, "IMAGinaryS21": -signal},
        "Read.Fieldbefore": {"IPS X-Field": feld - 0.002},
        "Read.Fieldafter": {"IPS X-Field": feld + 0.002},
        "Read.Temperature": {"LakeshoreTemperature": np.full(n_feld, 5.0)},
    })


# --- Profile -------------------------------------------------------------------

def test_profil_json_roundtrip(tmp_path):
    profil = MappingProfil(
        name="Messrechner Käfig 3",  # Umlaut: UTF-8-Roundtrip pruefen
        layout="sortiert",
        zuordnung={"frequenz": ("G", "f"), "re_s21": ("G", "re"),
                   "im_s21": ("G", "im"), "feld_before": ("M", "B")},
        beschreibung="Testprofil",
    )
    pfad = tmp_path / "profil.json"
    speichere_profil(profil, pfad)
    geladen = lade_profil(pfad)
    assert geladen.name == profil.name
    assert geladen.layout == "sortiert"
    assert geladen.zuordnung == profil.zuordnung

    # Verzeichnis-Lader ueberspringt fremde JSON-Dateien.
    (tmp_path / "fremd.json").write_text('{"irgendwas": 1}', encoding="utf-8")
    profile = lade_profile(tmp_path)
    assert [p.name for p in profile] == [profil.name]


def test_unbekanntes_layout_und_rollen_abgelehnt():
    with pytest.raises(ValueError):
        MappingProfil(name="x", layout="quer", zuordnung={})
    with pytest.raises(ValueError):
        MappingProfil.aus_dict({"name": "x", "layout": "sortiert",
                                "zuordnung": {"phantasie_rolle": ["G", "k"]}})


def test_eingebaute_profile_werden_erkannt(tmp_path):
    pfad = tmp_path / "sortiert.tdms"
    _schreibe_sortiert(pfad)
    struktur, warnungen = inspiziere_tdms(pfad)
    assert warnungen == []
    assert finde_profil(struktur) is PROFIL_SORTIERT

    pfad2 = tmp_path / "unsortiert.tdms"
    _schreibe_unsortiert(pfad2)
    struktur2, _ = inspiziere_tdms(pfad2)
    assert finde_profil(struktur2) is PROFIL_UNSORTIERT

    # Nutzerprofile haben Vorrang vor den eingebauten.
    eigenes = MappingProfil(name="eigen", layout="sortiert",
                            zuordnung=dict(PROFIL_SORTIERT.zuordnung))
    assert finde_profil(struktur, [eigenes]) is eigenes


def test_rate_zuordnung_heuristik():
    struktur = {
        "Messung": {"Frequency (Hz)": 60, "REAL S21": 60, "IMAG S21": 60},
        "Magnet": {"Field-before (T)": 60, "Field-after (T)": 60},
        "Sensorik": {"Temperature": 60},
    }
    vorschlag = rate_zuordnung(struktur)
    assert vorschlag["frequenz"] == ("Messung", "Frequency (Hz)")
    assert vorschlag["re_s21"] == ("Messung", "REAL S21")
    assert vorschlag["im_s21"] == ("Messung", "IMAG S21")
    assert vorschlag["feld_before"] == ("Magnet", "Field-before (T)")
    assert vorschlag["feld_after"] == ("Magnet", "Field-after (T)")
    assert vorschlag["temperatur"] == ("Sensorik", "Temperature")


def test_schlage_layout_vor():
    zuordnung = {"frequenz": ("G", "f"), "feld_before": ("G", "B")}
    assert schlage_layout_vor({"G": {"f": 60, "B": 60}}, zuordnung) == "sortiert"
    assert schlage_layout_vor({"G": {"f": 60, "B": 6}}, zuordnung) == "unsortiert"
    assert schlage_layout_vor({"G": {"f": 61, "B": 6}}, zuordnung) is None


# --- Laden ueber Mapping ---------------------------------------------------------

def test_lade_sortiert_synthetisch(tmp_path):
    pfad = tmp_path / "sortiert.tdms"
    _schreibe_sortiert(pfad)
    ds = lade_tdms(pfad)
    assert ds.format_typ == "sortiert"
    assert len(ds) == 3
    assert ds.meta["mapping_profil"] == PROFIL_SORTIERT.name
    assert "zuordnung" in ds.meta
    ls = ds.linescans[0]
    assert ls.feld.size == 20
    assert np.all(np.diff(ls.feld) >= 0)
    # Feld = Mittel aus before/after.
    np.testing.assert_allclose(ls.feld, 0.5 * (ls.feld_before + ls.feld_after))


def test_lade_unsortiert_synthetisch(tmp_path):
    pfad = tmp_path / "unsortiert.tdms"
    _schreibe_unsortiert(pfad, n_feld=5, n_freq=7)
    ds = lade_tdms(pfad)
    assert ds.format_typ == "unsortiert"
    assert ds.meta["n_feld"] == 5 and ds.meta["n_freq"] == 7
    assert len(ds) == 7
    assert ds.linescans[0].temperatur is not None


def test_unbekanntes_layout_verlangt_mapping(tmp_path):
    pfad = tmp_path / "fremd.tdms"
    frequenz, feld, re, im = _sortiert_daten()
    _schreibe_tdms(pfad, {
        "Acq": {"f_Hz": frequenz, "S21_re": re, "S21_im": im},
        "Magnet": {"B_vor_T": feld},
    })
    with pytest.raises(MappingErforderlich) as fehler:
        lade_tdms(pfad)
    assert "Acq" in fehler.value.struktur  # Struktur fuer den Dialog verfuegbar

    # Mit expliziter Zuordnung laedt dieselbe Datei sauber.
    zuordnung = {
        "frequenz": ("Acq", "f_Hz"),
        "re_s21": ("Acq", "S21_re"),
        "im_s21": ("Acq", "S21_im"),
        "feld_before": ("Magnet", "B_vor_T"),
    }
    ds = lade_tdms(pfad, zuordnung=zuordnung)  # Layout automatisch: sortiert
    assert ds.format_typ == "sortiert"
    assert len(ds) == 3
    assert ds.meta["mapping_profil"] == "manuell"
    # Ohne feld_after ist das Feld direkt feld_before.
    np.testing.assert_allclose(ds.linescans[0].feld, np.sort(feld[:20]))


def test_unvollstaendige_zuordnung_abgelehnt(tmp_path):
    pfad = tmp_path / "fremd.tdms"
    frequenz, feld, re, im = _sortiert_daten()
    _schreibe_tdms(pfad, {"Acq": {"f_Hz": frequenz, "S21_re": re, "S21_im": im}})
    with pytest.raises(ValueError, match="feld_before"):
        lade_tdms(pfad, zuordnung={
            "frequenz": ("Acq", "f_Hz"),
            "re_s21": ("Acq", "S21_re"),
            "im_s21": ("Acq", "S21_im"),
            "feld_before": ("Magnet", "gibt_es_nicht"),
        }, layout="sortiert")


# --- Index-Datei-Fallback (Windows-Bug) -----------------------------------------

def test_defekte_index_datei_faellt_zurueck(tmp_path):
    """Reproduktion des Windows-Fehlers: .tdms_index passt nicht zur Datendatei.

    nptdms bricht dann beim Pfad-basierten Lesen ab; der Fallback liest die
    Datei ueber ein offenes Dateiobjekt (ohne Index) und vermerkt eine Warnung.
    """
    pfad = tmp_path / "messung.tdms"
    _schreibe_sortiert(pfad)

    # Fremde/veraltete Index-Datei simulieren: anderer, aber TDMS-artiger Inhalt.
    andere = tmp_path / "andere.tdms"
    _schreibe_unsortiert(andere)
    index_pfad = tmp_path / "messung.tdms_index"
    index_pfad.write_bytes(andere.read_bytes())

    ds = lade_tdms(pfad)
    assert ds.format_typ == "sortiert"
    assert len(ds) == 3
    warnungen = ds.meta.get("lade_warnungen", [])
    assert warnungen and "Index-Datei" in warnungen[0]


def test_inspektion_mit_defekter_index_datei(tmp_path):
    pfad = tmp_path / "messung.tdms"
    _schreibe_sortiert(pfad)
    (tmp_path / "messung.tdms_index").write_bytes(b"kaputt, kein TDMS-Header")
    struktur, warnungen = inspiziere_tdms(pfad)
    assert "ZVB" in struktur
    assert warnungen and "Index-Datei" in warnungen[0]


# --- Import-Validierung -----------------------------------------------------------

def _datensatz(linescans):
    return Messdatensatz(quelle="test", format_typ="sortiert", linescans=linescans,
                         meta={"zuordnung": {}})


def test_pruefbericht_unauffaellig(tmp_path):
    pfad = tmp_path / "sortiert.tdms"
    _schreibe_sortiert(pfad)
    bericht = pruefe_datensatz(lade_tdms(pfad))
    assert bericht.in_ordnung, bericht.warnungen
    assert bericht.n_frequenzen == 3
    assert bericht.punkte_min == bericht.punkte_max == 20
    assert "Keine Auffaelligkeiten" in bericht.als_text()


def test_pruefbericht_meldet_nan_und_konstantes_feld():
    b = np.linspace(1.0, 2.0, 30)
    re = np.cos(b)
    re[3] = np.nan
    ls_nan = Linescan(frequenz=10e9, feld=b, re=re, im=np.sin(b))
    ls_konstant = Linescan(frequenz=20e9, feld=np.full(30, 1.5),
                           re=np.cos(b), im=np.sin(b))
    bericht = pruefe_datensatz(_datensatz([ls_nan, ls_konstant]))
    text = " ".join(bericht.warnungen)
    assert "NaN" in text or "nicht-endliche" in text
    assert "konstantem Feld" in text
    assert not bericht.in_ordnung


def test_pruefbericht_meldet_leeren_datensatz_und_zu_wenig_punkte():
    assert not pruefe_datensatz(_datensatz([])).in_ordnung
    winzig = Linescan(frequenz=10e9, feld=np.array([1.0, 1.1]),
                      re=np.zeros(2), im=np.zeros(2))
    bericht = pruefe_datensatz(_datensatz([winzig]))
    assert any("< 4" in w for w in bericht.warnungen)
