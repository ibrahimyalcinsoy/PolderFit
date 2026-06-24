# Tuning – einstellbare Parameter

Dieses Kapitel führt die einstellbaren Parameter der Auswertung an einer Stelle
zusammen und beschreibt ihre Wirkung. Es richtet sich an Anwenderinnen und Anwender,
die das Verhalten an eigene Proben oder Messbedingungen anpassen möchten.

!!! warning "Grundsatz"
    Die Parameter sind physikalisch begründet voreingestellt. Anpassungen sollten
    gezielt und nachvollziehbar erfolgen. Insbesondere dürfen die Bewertungsschwellen
    (siehe [Bewertung der Fits](bewertung.md)) nicht so verändert werden, dass
    schlechte Fenster als unauffällig durchgehen.

## Aufrufparameter

Mehrere Größen lassen sich direkt beim Aufruf übergeben, ohne den Quelltext zu
ändern (`fitte_alle` in `bbfmr/fit/batch.py`):

| Parameter | Standard | Wirkung |
|---|---|---|
| `gamma` | `GAMMA_STANDARD` | gyromagnetisches Verhältnis; entspricht `g = 2` |
| `breite_faktor` | `8.0` | Skaliert die Fensterbreite relativ zur geschätzten Linienbreite |
| `r2_schwelle` | `0.9` | Schwelle für nachgelagerte R²-Auswertungen |
| `zentren` | `None` | vorgegebene Fenstermitten `B_res(f)`; überspringt die Auto-Detektion |

Beispiel für ein engeres beziehungsweise weiteres Fenster:

```python
from bbfmr.fit.batch import fitte_alle
stapel = fitte_alle(datensatz, breite_faktor=5.0)   # engere Fenster
```

## Parameter des AutoWindow

Die folgenden Konstanten in `bbfmr/fit/autowindows.py` steuern die
Fensterbestimmung:

| Konstante | Standard | Wirkung | Anpassung |
|---|---|---|---|
| `_HALB_MAX` | `0.4` T | obere Grenze der halben Fensterbreite | verkleinern bei generell schmalen Resonanzen; vergrößern bei sehr breiten |
| `_PROMINENZ_MIN` | `4.0` | Mindest-Prominenz, ab der ein Kandidat als verlässlich gilt | erhöhen bei verrauschten Daten (strengere Auswahl); senken bei sehr schwachen Resonanzen |

Weitere wirksame Größen sind innerhalb der Funktionen festgelegt:

- **Fenster der gleitenden Geraden** (`_glatte_lokale_trasse`, Argument
  `fenster_punkte`, Standard 31). Ein größeres Fenster glättet stärker und ist
  robuster gegen Ausreißer, folgt aber einer rasch wandernden Dispersion träger.
- **Konsistenztoleranz und Suchradius** in `auto_fenster_alle` (`tol`). Sie
  bestimmen, ab welchem Abstand ein lokaler Kandidat als mit der Trasse inkonsistent
  gilt und in welchem Umkreis die Verfeinerung einen Peak sucht. Der Wert ist an den
  Punktabstand gekoppelt.

## Parameter des Fits

In `bbfmr/fit/linescan_fit.py` und `bbfmr/physik/fitmodell.py`:

- Die Parameterschranken (`B_res` im Fenster, `alpha`, `phi`) ergeben sich aus den
  Konstanten in `bbfmr/fit/kriterien.py` (siehe unten).
- Die Startwertschätzung (`schaetze_startwerte`) ist datengetrieben; bei
  systematisch schwieriger Konvergenz können einzelne Linescans mit expliziten
  Startwerten über `fitte_neu` erneut angepasst werden.

## Bewertungsschwellen

Die Schwellwerte der Einstufung sind in `bbfmr/fit/kriterien.py` zusammengefasst und
im Kapitel [Bewertung der Fits](bewertung.md) tabelliert. Die für die Praxis
relevantesten:

- `RMSE_NORM_SCHWELLE` (`0.35`) – Grenze des normierten Residuums. Senken für eine
  strengere, Erhöhen für eine nachsichtigere Einstufung.
- `ALPHA_PLAUSIBEL_MAX` (`0.05`) – obere Plausibilitätsgrenze der Dämpfung.
- `B_RES_REL_UNSICHERHEIT_MAX` (`0.02`) – maximale relative Unsicherheit des
  Resonanzfeldes.

## Empfehlungen nach Probentyp

- **Schmale Resonanzen, geringe Dämpfung** (z. B. YIG): `_HALB_MAX` gegebenenfalls
  reduzieren; die Einstufung „alpha an Grenze" ist hier zu erwarten, sofern die
  Dämpfung an die untere Schranke stößt, und kein Hinweis auf einen Fehler.
- **Verrauschte oder schwache Signale** (z. B. nahe In-plane): `_PROMINENZ_MIN`
  erhöhen, um Fehldetektionen an Störfeatures zu vermeiden; bei nicht
  lokalisierbarer Resonanz ist eine manuelle Dispersionsvorgabe (`zentren` /
  `fenster_aus_trasse`) vorzuziehen.
- **Periodische Untergrundstruktur** (z. B. Gitter-Proben): der feldstationäre
  Untergrundabzug greift automatisch bei unsortierten Daten; bei verbleibenden
  Fehlplatzierungen empfiehlt sich die manuelle Dispersionsvorgabe.
- **Sehr hochauflösende Feld-Sweeps**: Die Rechenzeit des Fits steigt mit der
  Punktzahl je Linescan stark an (siehe [Troubleshooting](troubleshooting.md#timeout)).
