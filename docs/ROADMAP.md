# Roadmap – Chastease

Abgeschlossene Punkte wurden nach [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md) ausgelagert.

## Offener Fokus (März 2026)

- Rollen-/Identity-Konzept weiter schärfen
- Session-State für Roleplay dramaturgisch weiter nutzen
- Rate-Limits und Abuse-Protection ergänzen
- Offene API-/Games-Nacharbeiten bei Postures bereinigen
- Device-Integrationen vorbereiten
- Gamification aufbauen
- Remote-Keyholder-Funktionen konzipieren

---

## Backlog (Post-MVP)

### v0.4 – Device Foundation
- [x] Lovense-Basisintegration fuer Web/Dashboard
- [ ] Toy-Status im Play-Modus sichtbar machen
- [ ] Toy-Kommandos als Session-Actions/Audit-Events persistieren
- [ ] Toy-Simulator fuer lokale Entwicklung
- [ ] Safety-Limits und Freigaberegeln fuer Toy-Steuerung

### v0.5 – Gamification
- [ ] Achievements / Abzeichen
- [ ] Streak-Tracking
- [ ] Statistiken-Dashboard (Gesamtdauer, Aufgaben-Rate, etc.)
- [ ] Punkte-System

### v0.5.x – Weitere Schnittstellen
- [ ] Extensions TTLock für Tresor
- [ ] Extensions Chaster für Session

### v0.6 – Remote Keyholder
- [ ] Optionaler Sync-Mechanismus (verschlüsselt, opt-in)
- [ ] Remote-Keyholder-Interface (separater Zugang)
- [ ] Push-Benachrichtigungen für Remote-Keyholder
- [ ] Echtzeit-Kollaboration: Mensch + KI als Co-Keyholder

---

## Priorisierungsmatrix

| Feature | Priorität | Aufwand | Zielbereich |
| --- | --- | --- | --- |
| Rollen-/Identity-Konzept | MUSS | Mittel | Plattformhärtung |
| Roleplay-State / Scene Engine | MUSS | Mittel | v0.3.2 (Rest) |
| Rate-Limits / Abuse-Protection | MUSS | Mittel | Sicherheit |
| Games-/Posture-API bereinigen | SOLL | Mittel | v0.3.1 |
| HTMX für weitere Admin-Flächen | SOLL | Niedrig bis mittel | UX / Wartbarkeit |
| Device-Integrationen | SOLL | Hoch | v0.4 |
| Gamification | KANN | Mittel bis hoch | v0.5 |
| Remote-Keyholder | KANN | Sehr hoch | v0.6 |
