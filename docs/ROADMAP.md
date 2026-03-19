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

## Offene Phasenpunkte

### Phase 0: Fundament

- [ ] HTMX/Server-Partials auf weitere Admin-/Backoffice-Seiten ausweiten, wenn der Pflegegewinn klar ist
- [ ] Alpine.js nur ergänzend für kleine lokale UI-Zustände evaluieren, kein Framework-Umbau

---

## Backlog (Post-MVP)

### v0.3.2 Roleplay Engine
- [ ] Roleplay-State aus Games, Task-Fails und Verifikationen automatisch fortschreiben
- [ ] Orders klar von formalen Tasks trennen und im UI konsistent benennen
- [ ] Scene-/Protocol-State im Settings-/Session-Bereich weiter verdichten
- [ ] Langzeit-Beziehungsdynamik zwischen Sessions modellieren

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
| Roleplay-State / Scene Engine | MUSS | Mittel bis hoch | v0.3.2 |
| Rate-Limits / Abuse-Protection | MUSS | Mittel | Sicherheit |
| Games-/Posture-API bereinigen | SOLL | Mittel | v0.3.1 |
| HTMX für weitere Admin-Flächen | SOLL | Niedrig bis mittel | UX / Wartbarkeit |
| Device-Integrationen | KANN | Hoch | v0.4 |
| Gamification | KANN | Mittel bis hoch | v0.5 |
| Remote-Keyholder | KANN | Sehr hoch | v0.6 |
