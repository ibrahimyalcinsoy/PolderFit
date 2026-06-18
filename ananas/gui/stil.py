"""Schlankes, helles Erscheinungsbild (QSS) fuer die Ananas-GUI.

Akzentfarben aus dem App-Icon: Ananas-Gold (#E8A317) und Blattgruen (#3FA34D).
Bewusst zurueckhaltend – klar und leicht, aber nicht ueberladen.
"""

from __future__ import annotations

ANANAS_GOLD = "#E8A317"
ANANAS_GRUEN = "#3FA34D"

ANANAS_QSS = f"""
QMainWindow, QDialog, QWidget {{
    background-color: #FAFAF6;
    color: #2B2B28;
    font-size: 13px;
}}
QToolBar {{
    background-color: #FFFFFF;
    border: none;
    border-bottom: 1px solid #E6E2D8;
    padding: 5px 6px;
    spacing: 3px;
}}
QToolBar QToolButton {{
    padding: 6px 12px;
    border-radius: 7px;
    color: #3A372F;
}}
QToolBar QToolButton:hover {{ background-color: #F6EDD3; }}
QToolBar QToolButton:pressed {{ background-color: #ECDFB8; }}
QToolBar QToolButton:disabled {{ color: #BBB6A8; }}
QToolBar::separator {{ background: #E6E2D8; width: 1px; margin: 4px 6px; }}

QPushButton {{
    background-color: #FFFFFF;
    border: 1px solid #D9D4C6;
    border-radius: 7px;
    padding: 6px 14px;
    color: #3A372F;
}}
QPushButton:hover {{ border-color: {ANANAS_GOLD}; background-color: #FCF6E8; }}
QPushButton:pressed {{ background-color: #ECDFB8; }}
QPushButton:disabled {{ color: #AFA99A; background-color: #F2F0EA; border-color: #E6E2D8; }}

QDockWidget {{ font-weight: 600; }}
QDockWidget::title {{
    background-color: #F2ECDC;
    padding: 7px 10px;
    border-bottom: 1px solid #E6E2D8;
}}

QProgressBar {{
    background-color: #FFFFFF;
    border: 1px solid #D9D4C6;
    border-radius: 7px;
    height: 16px;
    text-align: center;
    color: #3A372F;
}}
QProgressBar::chunk {{ background-color: {ANANAS_GOLD}; border-radius: 6px; }}

QPlainTextEdit {{
    background-color: #FFFFFF;
    border: 1px solid #E6E2D8;
    border-radius: 7px;
    selection-background-color: #F6EDD3;
    selection-color: #2B2B28;
}}
QStatusBar {{ background-color: #FFFFFF; border-top: 1px solid #E6E2D8; color: #5A5648; }}
QSplitter::handle {{ background-color: #E6E2D8; }}
QSplitter::handle:hover {{ background-color: {ANANAS_GOLD}; }}
QLabel#aktivitaet {{ font-weight: 600; color: #3A372F; }}
"""
