"""Polder-Suszeptibilitaet der ferromagnetischen Resonanz.

Die geschlossenen Ausdruecke sind 1:1 aus dem verbindlichen Mathematica-Notebook
``Chi_Fit_Functions_and_Inductances_2020-04-06.nb`` uebernommen (Form chi/Ms).
Konvention exakt wie dort: ``mu0H0`` und ``mu0Meff`` in Tesla, ``gamma`` in
rad/(s*T), ``omega = 2*pi*f`` in rad/s, ``alpha`` dimensionslos, ``mu0`` = MU0.

Out-of-plane (oop), Realteil ``chi'`` und Imaginaerteil ``chi''`` mit
gemeinsamem Nenner ``N``::

    N = gamma**4*(mu0H0-mu0Meff)**4
        + 2*(-1+alpha**2)*gamma**2*(mu0H0-mu0Meff)**2*omega**2
        + (1+alpha**2)**2*omega**4

    chi'_oop  =  gamma**2*mu0*(mu0H0-mu0Meff)
                 * (gamma**2*(mu0H0-mu0Meff)**2 + (-1+alpha**2)*omega**2) / N
    chi''_oop = -alpha*gamma*mu0*omega
                 * (gamma**2*(mu0H0-mu0Meff)**2 + (1+alpha**2)*omega**2) / N

Die Resonanz liegt bei ``mu0H0 - mu0Meff = omega/gamma``. Zur direkten
Parametrisierung ueber das Resonanzfeld ``B_res`` wird intern
``mu0Meff = B_res - omega/gamma`` gesetzt (siehe :func:`chi_oop`).

Der absolute Vorfaktor (inkl. ``mu0`` und ``Ms``) wird im Fit ohnehin vom
komplexen Vorfaktor ``A`` aufgenommen; die Form bleibt der Treue halber erhalten.
"""

from __future__ import annotations

import numpy as np

from .konstanten import MU0


def chi_oop_komponenten(
    mu0H0: np.ndarray,
    mu0Meff: float,
    alpha: float,
    omega: float,
    gamma: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Real- und Imaginaerteil der oop-Suszeptibilitaet (chi/Ms).

    Parameter exakt in Notebook-Konvention (Felder in Tesla). Gibt
    ``(chi_real, chi_imag)`` als Arrays gleicher Form wie ``mu0H0`` zurueck.
    """
    mu0H0 = np.asarray(mu0H0, dtype=float)
    d = mu0H0 - mu0Meff
    g2 = gamma * gamma
    g4 = g2 * g2
    w2 = omega * omega
    w4 = w2 * w2
    a2 = alpha * alpha

    nenner = (
        g4 * d**4
        + 2.0 * (-1.0 + a2) * g2 * d**2 * w2
        + (1.0 + a2) ** 2 * w4
    )

    chi_real = (
        g2 * MU0 * d * (g2 * d**2 + (-1.0 + a2) * w2) / nenner
    )
    chi_imag = (
        -(alpha * gamma * MU0 * omega * (g2 * d**2 + (1.0 + a2) * w2)) / nenner
    )
    return chi_real, chi_imag


def chi_oop(
    mu0H: np.ndarray,
    B_res: float,
    alpha: float,
    omega: float,
    gamma: float,
) -> np.ndarray:
    """Komplexe oop-Suszeptibilitaet, parametrisiert ueber das Resonanzfeld.

    ``B_res`` ist das Resonanzfeld in Tesla; intern wird
    ``mu0Meff = B_res - omega/gamma`` gesetzt, sodass die Resonanz exakt bei
    ``mu0H = B_res`` liegt. Rueckgabe: ``chi' + i*chi''``.
    """
    mu0Meff = B_res - omega / gamma
    re, im = chi_oop_komponenten(mu0H, mu0Meff, alpha, omega, gamma)
    return re + 1j * im


def chi_ip_komponenten(
    mu0H0: np.ndarray,
    mu0Meff: float,
    alpha: float,
    omega: float,
    gamma: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Real-/Imaginaerteil der in-plane-Suszeptibilitaet (chi/Ms).

    1:1 aus dem Notebook, Abschnitt "In-plane (H orthogonal to CPW, H || y)",
    Variante OHNE ``ratio`` (die Standard-ip-bbFMR-Konfiguration: Feld in der
    Ebene, senkrecht zum CPW-Innenleiter).

    HINWEIS – noch nicht im Linescan-Fit verdrahtet: Der Einzelfit
    (:func:`bbfmr.physik.fitmodell.s21_modell`) verwendet derzeit
    ausschliesslich :func:`chi_oop`; das ``oop``/``ip``-Umschalten greift nur in
    der uebergreifenden Kittel-/LLG-Auswertung (auf bereits extrahierte ``B_res``).
    Fuer einen echten ip-Linienform-Fit braucht es zusaetzlich einen
    ``B_res``-parametrisierten Wrapper (die ip-Resonanz liegt NICHT einfach bei
    ``mu0H0-mu0Meff=omega/gamma``, sondern bei der ip-Kittel-Bedingung, vgl.
    :func:`bbfmr.physik.kittel_llg.kittel_ip`) und einen ``geometrie``-Parameter
    durch Startwertschaetzung/Modell/Fit. Beispielmessung ist oop.
    """
    mu0H0 = np.asarray(mu0H0, dtype=float)
    g2 = gamma * gamma
    g4 = g2 * g2
    w2 = omega * omega
    w4 = w2 * w2
    a2 = alpha * alpha

    nenner = (
        g4 * mu0H0**2 * (mu0H0 + mu0Meff) ** 2
        + g2
        * (
            2.0 * (-1.0 + a2) * mu0H0**2
            + 2.0 * (-1.0 + a2) * mu0H0 * mu0Meff
            + a2 * mu0Meff**2
        )
        * w2
        + (1.0 + a2) ** 2 * w4
    )

    chi_real = (
        g2
        * MU0
        * (g2 * mu0H0**2 * (mu0H0 + mu0Meff) + ((-1.0 + a2) * mu0H0 + a2 * mu0Meff) * w2)
        / nenner
    )
    chi_imag = (
        -(alpha * gamma * MU0 * omega * (g2 * mu0H0**2 + (1.0 + a2) * w2)) / nenner
    )
    return chi_real, chi_imag
