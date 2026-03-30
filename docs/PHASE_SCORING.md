# Phase Scoring

## Ziel

Die Gesamtbeurteilung (`relationship_state_json`) bleibt langfristig bestehen.
Jede Phase besitzt zusaetzlich eigene, kurzfristige Phasenpunkte, die pro Kriterium wieder bei `0` starten.

## Datenmodell

Pro Phase koennen direkt in `scenarios.phases_json` folgende Felder definiert werden:

- `score_targets`
- `phase_weight`
- `min_phase_duration_hours`

Beispiel:

```json
{
  "phase_id": "phase_3",
  "title": "Chronische Denial",
  "phase_weight": 1.45,
  "min_phase_duration_hours": 96,
  "score_targets": {
    "trust": 6,
    "obedience": 8,
    "resistance": 5,
    "favor": 5,
    "strictness": 5,
    "frustration": 6,
    "attachment": 5
  }
}
```

## Berechnungsvorschlag

Wenn `score_targets` nicht explizit gesetzt sind, kann eine Phase aus Gewicht und erwarteter Sessiondauer abgeleitet werden.

### 1. Phasengewichte festlegen

Jede Phase bekommt ein relatives Gewicht:

- leichte Einstiegsphase: `0.8` bis `1.1`
- normale Aufbauphase: `1.1` bis `1.4`
- lange Kernphase: `1.4` bis `1.9`
- Reset-/Uebergangsphase: `0.8` bis `1.0`

### 2. Erwartete Sessiondauer bestimmen

Empfohlene Basis:

- `expected_days = max_duration_seconds / 86400`
- falls `max_duration_seconds` leer ist: `min_duration_seconds / 86400`

### 3. Dauerfaktor bilden

```text
pace_factor = clamp(expected_days / 7.0, 0.75, 1.75)
```

Eine etwa einwoechige Session bleibt nahe `1.0`.
Sehr kurze Sessions fallen Richtung `0.75`.
Lange Sessions wachsen bis maximal `1.75`.

### 4. Zielwerte ableiten

```text
target(metric) = round(base_target(metric, phase_index) * pace_factor * phase_weight)
```

Dabei ist `base_target(metric, phase_index)` ein konservativer Grundwert pro Phase.

## Verteilung bei neuer Phase

Wenn eine neue Phase eingefuegt wird:

1. Zwischen welche beiden Phasen faellt sie dramaturgisch?
2. `phase_weight` als Mittelwert der Nachbarphasen setzen.
3. `min_phase_duration_hours` ebenfalls zwischen den Nachbarphasen einordnen.
4. `score_targets` von der vorherigen Phase als Start nehmen.
5. Pro Kriterium nur kleine Anpassungen von `+/- 1` vornehmen.

Empfohlene Faustregel:

- neue Uebergangsphase: Ziele nahe der vorherigen Phase
- neue Eskalationsphase: `obedience`, `frustration`, `strictness`, `resistance` zuerst erhoehen
- neue Bindungsphase: `trust`, `favor`, `attachment` staerker gewichten

## Ametara-Verteilung

Aktuelle Empfehlung fuer `ametara_titulari_devotion_protocol`:

| Phase | Weight | Min Hours | Kernidee |
| --- | ---: | ---: | --- |
| 1 | 1.00 | 48 | Einstieg und Rhythmus |
| 2 | 1.20 | 72 | Tease und erste Verdichtung |
| 3 | 1.45 | 96 | Chronische Denial als Kernbogen |
| 4 | 1.75 | 144 | Spirituelle/absolute Verleugnung |
| 5 | 1.55 | 168 | Integration in Alltag und Identitaet |
| 6 | 0.95 | 72 | Reset und Re-Devotion |

## Empfehlung

Fuer produktive Szenarien sollten `score_targets` explizit an den Phasen gepflegt werden.
Die Berechnungslogik sollte nur als Fallback dienen, nicht als primäre Quelle.
