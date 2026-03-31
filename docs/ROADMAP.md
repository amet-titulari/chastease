# Roadmap – Chastease

Abgeschlossene Punkte wurden nach [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md) ausgelagert.

## Offener Fokus (März 2026)

- UI-Struktur und Frontend-Wartbarkeit gezielt verbessern
- Rollen-/Identity-Konzept weiter schärfen
- Session-State für Roleplay dramaturgisch weiter nutzen
- Szenario-/Phasen-Tools weiter verfeinern
- Rate-Limits und Abuse-Protection ergänzen
- Offene API-/Games-Nacharbeiten bei Postures bereinigen
- Device-Integration stabilisieren und erweitern
- Gamification vorerst nach hinten schieben
- Remote-Keyholder-Funktionen vorerst nach hinten schieben

---

## Backlog (Post-MVP)

### v0.5 – UI Refactoring
- [ ] `play.js` und `dashboard.js` in kleinere Module zerlegen
- [ ] Wiederverwendbare UI-Bausteine fuer Meter, Cards, Badges und Panels vereinheitlichen
- [ ] HTMX fuer weitere Admin-Flaechen gezielt ausbauen (`scenarios`, `personas`, `inventory`)
- [ ] Mobile Breakpoints und Formular-Layouts systematisch vereinheitlichen
- [ ] UI-State zwischen Chat, Dashboard und Admin-Flaechen klarer trennen
- [ ] CSS-Tokens, Komponentenklassen und Seitenspezifika konsolidieren

### v0.6 – Gamification
- [ ] Achievements / Abzeichen
- [ ] Streak-Tracking
- [ ] Statistiken-Dashboard (Gesamtdauer, Aufgaben-Rate, etc.)
- [ ] Punkte-System

### v0.6.x – Weitere Schnittstellen
- [ ] Extensions TTLock für Tresor
- [ ] Extensions Chaster für Session

### v0.7 – Remote Keyholder
- [ ] Optionaler Sync-Mechanismus (verschlüsselt, opt-in)
- [ ] Remote-Keyholder-Interface (separater Zugang)
- [ ] Push-Benachrichtigungen für Remote-Keyholder
- [ ] Echtzeit-Kollaboration: Mensch + KI als Co-Keyholder

---

## Priorisierungsmatrix

| Feature | Priorität | Aufwand | Zielbereich |
| --- | --- | --- | --- |
| Rollen-/Identity-Konzept | MUSS | Mittel | Plattformhärtung |
| UI-Refactoring / Frontend-Wartbarkeit | MUSS | Mittel | v0.5 |
| Roleplay-State / Scene Engine | MUSS | Mittel | laufend |
| Rate-Limits / Abuse-Protection | MUSS | Mittel | Sicherheit |
| Games-/Posture-API bereinigen | SOLL | Mittel | v0.3.1 |
| HTMX für weitere Admin-Flächen | SOLL | Niedrig bis mittel | v0.5 |
| Device-Integrationen | SOLL | Hoch | laufend nach v0.4 |
| Gamification | KANN | Mittel bis hoch | v0.6 |
| Remote-Keyholder | KANN | Sehr hoch | v0.7 |
