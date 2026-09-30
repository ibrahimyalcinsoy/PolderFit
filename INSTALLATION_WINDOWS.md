# Installation (Windows)

## 1. Python and Git

- Python ≥ 3.11: <https://www.python.org/downloads/windows/> – tick **“Add python.exe to PATH”**
- Git: <https://git-scm.com/download/win> – default settings

Check in a new Command Prompt (`cmd`):

```bat
python --version
git --version
```

## 2. Install

```bat
cd %USERPROFILE%
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git
cd PolderFit
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[gui]"
polderfit
```

Linux/macOS: `source .venv/bin/activate` instead of `.venv\Scripts\activate`.
If `polderfit` is not found: `python -m polderfit.app`

## Start

```bat
cd %USERPROFILE%\PolderFit
.venv\Scripts\activate
polderfit
```

Optional `start.bat` (double-click):

```bat
@echo off
cd /d "%USERPROFILE%\PolderFit"
call .venv\Scripts\activate
polderfit
```

## Update

```bat
cd %USERPROFILE%\PolderFit
git fetch origin
git reset --hard origin/main
.venv\Scripts\activate
pip install -e ".[gui]"
```

Program files are overwritten; own files (measurements, projects) are kept.
“not a git repository” (e.g. folder from ZIP): `ren PolderFit PolderFit_old`, then step 2.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not recognized | Reinstall Python with “Add python.exe to PATH” |
| `git` not recognized | Reinstall Git, open a new `cmd` |
| `.venv\Scripts\activate` fails | `cd %USERPROFILE%\PolderFit`, `python -m venv .venv` |
| `pip install` aborts | Check internet connection, run again |
| GUI does not open | Prompt must start with `(.venv)` → `.venv\Scripts\activate` |
| Plot/panels misplaced | View → Reset window layout (`Ctrl+Shift+R`) |
| Work lost after crash | File → Restore auto-backup |
