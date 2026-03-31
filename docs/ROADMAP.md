# Roadmap – Chastease

Abgeschlossene Punkte wurden nach [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md) ausgelagert.

## Offener Fokus (März 2026)

- Rollen-/Identity-Konzept weiter schärfen
- Session-State für Roleplay dramaturgisch weiter nutzen
- Szenario-/Phasen-Tools weiter verfeinern
- Rate-Limits und Abuse-Protection ergänzen
- At-Rest-Verschluesselung fuer Session-State und gespeicherte API-Keys vor Beta wieder einfuehren
- Offene API-/Games-Nacharbeiten bei Postures bereinigen
- Device-Integration stabilisieren und erweitern
- Gamification vorerst nach hinten schieben
- Remote-Keyholder-Funktionen vorerst nach hinten schieben

---

## Backlog (Post-MVP)

### v0.6 – Gamification
- [ ] Achievements / Abzeichen
- [ ] Streak-Tracking
- [ ] Statistiken-Dashboard (Gesamtdauer, Aufgaben-Rate, etc.)
- [ ] Punkte-System

### v0.6.x – Weitere Schnittstellen
- [ ] Extensions TTLock für Tresor
- [ ] Extensions Chaster für Session

### Alpha-Hardening Rueckbau
- [ ] Temporär entfernte At-Rest-Verschluesselung fuer `Session.llm_api_key`, `LlmProfile.api_key` sowie Session-State-JSONs vor Beta wieder einfuehren
- [ ] Migrationsstrategie fuer bestehende Klartextdaten nach Rueckkehr der Verschluesselung festlegen
- [ ] Betriebsdoku fuer Key-Rotation und Secret-Recovery nach Wiedereinbau der Verschluesselung aktualisieren

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
| Roleplay-State / Scene Engine | MUSS | Mittel | laufend |
| Rate-Limits / Abuse-Protection | MUSS | Mittel | Sicherheit |
| Games-/Posture-API bereinigen | SOLL | Mittel | v0.3.1 |
| Device-Integrationen | SOLL | Hoch | laufend nach v0.4 |
| Gamification | KANN | Mittel bis hoch | v0.6 |
| Remote-Keyholder | KANN | Sehr hoch | v0.7 |
