# PolderFit

**Version 2.1 · Stand 2026-09-04** · Breitband-FMR: TDMS → `B_res`, `µ0ΔH` je Frequenz → Kittel/LLG → `g`, `µ0M_eff`, `µ0H_u`, `α`, `µ0ΔH_0`.
[Dokumentation](https://ibrahimyalcinsoy.github.io/PolderFit/) · [Windows-Anleitung](INSTALLATION_WINDOWS.md)

> [!CAUTION]
> **Im Ordner `PolderFit` (cmd): neueste Version holen und starten**
>
> ```bat
> git fetch origin && git reset --hard origin/main && .venv\Scripts\activate && pip install -q -e ".[gui]" && polderfit
> ```

Nur starten: `.venv\Scripts\activate && polderfit`

## Erstinstallation

Python ≥ 3.11 („Add python.exe to PATH“) und Git installiert; Ordner `PolderFit` anlegen, dann:

```bat
cd PolderFit
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git .
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[gui]"
polderfit
```

Linux/macOS: `source .venv/bin/activate` statt `.venv\Scripts\activate`.

## Bedienung

TDMS laden → Auto-Fit `F5` → Korridor je Mode `Strg+L` → „Korridor fitten …“ → Kittel/LLG `Strg+K` → Export.

| Verzeichnis | Inhalt |
|---|---|
| `polderfit/` | `io` (TDMS), `physik` (χ, Kittel/LLG), `fit` (AutoWindow, Einzelfit, Korridore), `auswertung`, `persistenz`, `gui` |
| `tests/`, `benchmark_ftf/`, `docs/` | pytest-Suite, FTF-Benchmark, Dokumentation |
