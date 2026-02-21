# ADR-001: Modular Monolith als Startarchitektur

- Status: Accepted
- Datum: 2026-02-21

## Kontext

Chastease soll schnell einen belastbaren MVP liefern und gleichzeitig um Features wie Quests, Admin-Tools und asynchrone KI-Prozesse wachsen.
Ein zu frueher Microservice-Schnitt wuerde aktuell unnoetigen Betriebsaufwand erzeugen.

## Entscheidung

Wir starten mit einem Modular Monolith als Python-Backend:

- fachlich getrennte Domänenmodule
- gemeinsame Deploy-Unit
- klar definierte Layer und Schnittstellen

## Konsequenzen

Positiv:

- Schnellere Entwicklung und geringere Betriebs- und Infrastrukturkomplexitaet
- Einfachere lokale Entwicklung und Testbarkeit
- Architektur bleibt migrierbar in Services, falls Last/Teamgroesse es spaeter erfordert

Negativ:

- Strikte Disziplin bei Modulgrenzen noetig
- Risiko wachsender Kopplung bei unsauberer Umsetzung

## Leitplanken

- Kein direkter Domänenzugriff ueber Modulgrenzen ohne explizite Use-Case-Schnittstelle.
- Kein direkter Datenbankzugriff aus API-Endpunkten.
- Jede neue Kernentscheidung bekommt eine eigene ADR.
