# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Erscheinungsbild (QSS) der PolderFit-GUI: neutrale, unbunte Oberflaeche,
Signalfarben nur mit Bedeutung (DIN EN 60073 / ISO 3864, siehe
:mod:`polderfit.gui.farben`).

Gestaltungsregeln (DIN EN ISO 9241-110/-112, VDI/VDE 3850):

* Flaechen und Rahmen sind unbunt (Grau/Weiss) - Farbe traegt Bedeutung,
  nicht Dekoration. BLAU markiert aktive Zustaende und gewaehlte Elemente
  (Gebot/Hinweis), GRUEN/GELB/ROT nur Statusinformation.
* Schriftgroesse >= 13 px, Kontrast Text/Grund >= 4.5:1.
* Bedienelemente haben deutliche Zustaende (hover/pressed/checked/disabled).
"""

from __future__ import annotations

from . import farben as F

PolderFit_QSS = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {F.FLAECHE};
    color: {F.TEXT};
    font-size: 13px;
}}
QToolTip {{
    background-color: {F.HELL_GELB};
    color: {F.TEXT};
    border: 1px solid {F.SIGNAL_GELB};
    padding: 5px 7px;
    font-size: 12px;
}}
QMenuBar {{
    background-color: {F.PANEL};
    border-bottom: 1px solid {F.RAND};
    padding: 2px 4px;
}}
QMenuBar::item {{ padding: 5px 10px; border-radius: 4px; color: {F.TEXT}; }}
QMenuBar::item:selected {{ background-color: {F.HELL_BLAU}; color: {F.TEXT_BLAU}; }}
QMenuBar::item:pressed {{ background-color: {F.SIGNAL_BLAU}; color: #FFFFFF; }}
QMenu {{
    background-color: {F.PANEL};
    border: 1px solid {F.RAND_STARK};
    border-radius: 4px;
    padding: 5px;
}}
QMenu::item {{ padding: 6px 26px 6px 14px; border-radius: 3px; color: {F.TEXT}; }}
QMenu::item:selected {{ background-color: {F.HELL_BLAU}; color: {F.TEXT_BLAU}; }}
QMenu::item:disabled {{ color: {F.INAKTIV}; }}
QMenu::item:checked {{ background-color: {F.HELL_BLAU}; font-weight: 600; }}
QMenu::separator {{ height: 1px; background: {F.RAND}; margin: 4px 8px; }}

QPushButton, QToolButton {{
    background-color: {F.PANEL};
    border: 1px solid {F.RAND_STARK};
    border-radius: 4px;
    padding: 6px 14px;
    color: {F.TEXT};
}}
QPushButton:hover, QToolButton:hover {{ border-color: {F.SIGNAL_BLAU}; background-color: {F.HELL_BLAU}; }}
QPushButton:pressed, QToolButton:pressed {{ background-color: {F.SIGNAL_BLAU}; color: #FFFFFF; }}
QPushButton:disabled, QToolButton:disabled {{
    color: {F.INAKTIV}; background-color: {F.HELL_GRAU}; border-color: {F.RAND};
}}
QPushButton:checked, QToolButton:checked {{
    background-color: {F.SIGNAL_BLAU};
    border-color: {F.TEXT_BLAU};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton#gut {{ border-color: {F.SIGNAL_GRUEN}; color: {F.TEXT_GRUEN}; }}
QPushButton#gut:hover {{ background-color: {F.HELL_GRUEN}; }}
QPushButton#problem {{ border-color: {F.SIGNAL_GELB}; color: {F.TEXT_GELB}; }}
QPushButton#problem:hover {{ background-color: {F.HELL_GELB}; }}
QPushButton#ignorieren {{ border-color: {F.NEUTRAL_GRAU}; color: {F.TEXT_GRAU}; }}
QPushButton#abbrechen {{ border-color: {F.SIGNAL_ROT}; color: {F.TEXT_ROT}; font-weight: 600; padding: 3px 10px; }}
QPushButton#abbrechen:hover {{ background-color: {F.HELL_ROT}; }}
QPushButton#abbrechen:disabled {{ color: {F.INAKTIV}; border-color: {F.RAND}; }}
QLabel#job_spinner {{ color: {F.SIGNAL_BLAU}; font-weight: 700; font-size: 14px; }}
QLabel#job_text {{ color: {F.TEXT_BLAU}; font-weight: 600; }}
QPushButton#ignorieren:hover {{ background-color: {F.HELL_GRAU}; }}

QLabel#modus_anzeige {{
    background-color: {F.SIGNAL_BLAU};
    color: #FFFFFF;
    font-weight: 600;
    border-radius: 4px;
    padding: 3px 10px;
}}
QLabel#status_gut {{ background-color: {F.HELL_GRUEN}; color: {F.TEXT_GRUEN};
    border: 1px solid {F.SIGNAL_GRUEN}; border-radius: 4px; padding: 3px 8px; font-weight: 600; }}
QLabel#status_bestaetigt {{ background-color: {F.HELL_GRUEN}; color: {F.TEXT_GRUEN};
    border: 2px solid {F.SIGNAL_BLAU}; border-radius: 4px; padding: 2px 8px; font-weight: 600; }}
QLabel#status_problem {{ background-color: {F.HELL_GELB}; color: {F.TEXT_GELB};
    border: 1px solid {F.SIGNAL_GELB}; border-radius: 4px; padding: 3px 8px; font-weight: 600; }}
QLabel#status_fehler {{ background-color: {F.HELL_ROT}; color: {F.TEXT_ROT};
    border: 1px solid {F.SIGNAL_ROT}; border-radius: 4px; padding: 3px 8px; font-weight: 600; }}
QLabel#status_ignoriert {{ background-color: {F.HELL_GRAU}; color: {F.TEXT_GRAU};
    border: 1px solid {F.NEUTRAL_GRAU}; border-radius: 4px; padding: 3px 8px; font-weight: 600; }}

QGroupBox {{
    border: 1px solid {F.RAND};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 8px;
    background-color: {F.PANEL};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {F.TEXT};
    font-weight: 600;
}}
QGroupBox::indicator:checked {{ background-color: {F.SIGNAL_BLAU}; border: 1px solid {F.TEXT_BLAU}; }}
QGroupBox::indicator:unchecked {{ background-color: {F.PANEL}; border: 1px solid {F.RAND_STARK}; }}

QDockWidget {{ font-weight: 600; }}
QDockWidget::title {{
    background-color: {F.HELL_GRAU};
    padding: 7px 10px;
    border-bottom: 1px solid {F.RAND};
}}

QProgressBar {{
    background-color: {F.PANEL};
    border: 1px solid {F.RAND_STARK};
    border-radius: 4px;
    height: 16px;
    text-align: center;
    color: {F.TEXT};
}}
QProgressBar::chunk {{ background-color: {F.SIGNAL_BLAU}; border-radius: 3px; }}

QPlainTextEdit, QTextBrowser, QListWidget, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {F.PANEL};
    border: 1px solid {F.RAND};
    border-radius: 4px;
    selection-background-color: {F.HELL_BLAU};
    selection-color: {F.TEXT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {F.SIGNAL_BLAU}; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 22px; border-left: 1px solid {F.RAND};
    background-color: {F.PANEL};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {{ background-color: {F.HELL_BLAU}; }}
QListWidget::item:selected {{ background-color: {F.HELL_BLAU}; color: {F.TEXT_BLAU}; }}
QStatusBar {{ background-color: {F.PANEL}; border-top: 1px solid {F.RAND}; color: {F.TEXT_SCHWACH}; }}
QSplitter::handle {{ background-color: {F.RAND}; }}
QSplitter::handle:hover {{ background-color: {F.SIGNAL_BLAU}; }}
QLabel#aktivitaet {{ font-weight: 600; color: {F.TEXT}; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {F.SIGNAL_BLAU}; border: 1px solid {F.TEXT_BLAU};
}}
QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {{
    background-color: {F.PANEL}; border: 1px solid {F.RAND_STARK};
}}
QCheckBox::indicator, QRadioButton::indicator {{ width: 14px; height: 14px; border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 7px; }}
"""
