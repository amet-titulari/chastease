# Roadmap – Chastease

Abgeschlossene Punkte wurden nach [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md) ausgelagert.

## Offener Fokus (März 2026)

- Rollen-/Identity-Konzept weiter schärfen
- Rate-Limits und Abuse-Protection ergänzen
- Offene API-/Games-Nacharbeiten bei Postures bereinigen
- Device-Integrationen vorbereiten
- Gamification aufbauen
- Remote-Keyholder-Funktionen konzipieren

---

## Offene Phasenpunkte

### Phase 0: Fundament

- [ ] HTMX Integration

---

## Backlog (Post-MVP)

### v0.3.1 API Anpassungen
- [ ] API Absicherung durch Login oder Token
- [ ] API /api/games/modules/{module_key}/postures anpassen an Inventar/Postures Logik, nur `available` erforderlich
- [ ] Postures Import und Export

### v0.4 – Gamification
- [ ] Achievements / Abzeichen
- [ ] Streak-Tracking
- [ ] Statistiken-Dashboard (Gesamtdauer, Aufgaben-Rate, etc.)
- [ ] Punkte-System
  
### v0.5 – Erweiterungen - Schnittstellen
- [ ] Lovense für Devices
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
| Rate-Limits / Abuse-Protection | MUSS | Mittel | Sicherheit |
| Games-/Posture-API bereinigen | SOLL | Mittel | v0.3.1 |
| Device-Integrationen | KANN | Hoch | v0.4 |
| Gamification | KANN | Mittel bis hoch | v0.5 |
| Remote-Keyholder | KANN | Sehr hoch | v0.6 |
