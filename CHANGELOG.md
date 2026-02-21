# Changelog

## 0.0.10 - 2026-02-21

- Neue dedizierte Seite `/chat` mit modernem Chat-Layout eingefuehrt (inspiriert von ChatGPT/Perplexity/Gemini-Flow).
- Chat-Features auf `/chat`:
  - Text-Chat
  - Bild-/Datei-Upload (inkl. Screenshots/Anhänge)
  - Voice-Diktat im Browser (Web Speech API, falls verfuegbar)
  - Export letzter Antwort als TXT/JSON
  - Download von durch KI gelieferten Dateiantworten (`generated_files`)
- API Chat-Responses erweitert:
  - `generated_files` wird in `/api/v1/chat/turn` und `/api/v1/setup/sessions/{id}/chat-preview` mitgeliefert.
  - Marker-Parsing fuer Dateiantworten unterstuetzt (`[[FILE|{...}]]`).
- Psychogramm-Form korrigiert:
  - Skalen wieder als Slider statt Textfelder (kompatibel fuer `scale_100`, `scale_10`, `scale_5`).
  - Ampelsystem ohne Eingabefelder umgesetzt (nur feste Anzeige mit Gruen/Gelb/Rot-Definition).
- Landingpage und App-Topbar um direkten Link auf `/chat` erweitert.

## 0.0.9 - 2026-02-21

- Complete-Setup-Bestaetigung verhaelt sich nun final: `Start Setup`, `Psychogram`, `AI Configuration` und `Complete Setup` werden sofort gesperrt.
- `AI Chat`, `Psychogram Brief` und `Response` bleiben nach der Bestaetigung fuer Analyse/Debug offen.
- Nach Bestaetigung wird direkt in den `Psychogram Brief` gewechselt und waehrend Verarbeitung `Analyse in arbeit` angezeigt.
- Session-Kill-Flow bleibt testbar: nach Loeschen wird wieder ein `draft`-Setup bereitgestellt.
- Dokumentation auf Implementierungsstand 0.0.9 synchronisiert (Flow, Auth-Stand, Psychogramm-Schema, Backlog-Erweiterungen).

## 0.0.8 - 2026-02-21

- App-Flow auf Accordion umgestellt: Start Setup, Psychogram, AI Configuration, Complete Setup, AI Chat, Psychogram Brief, Response.
- Nur eine Karte gleichzeitig offen; Folgekarten bis erfolgreichem Setup-Start gesperrt.
- Auto-Navigation im Setup-Flow: Start -> Psychogram, Submit Answers -> AI Configuration, Save LLM Profile -> Complete Setup.
- Dashboard/Chat entkoppelt, Home/Dashboard/Logout oben rechts konsolidiert.
- Setup-Form verbessert: Penalty-Felder werden bei deaktivierten Caps ausgeblendet.
- Datumslogik bidirektional synchronisiert (Start, Max End, Max Duration), inklusive `0 Tage = KI entscheidet Enddatum`.
- UI-Texte für DE/EN zentralisiert und breit übersetzt.
- Psychogramm v2.4 erweitert:
  - `interaction_preferences`: `escalation_mode`, `experience_level`, `experience_profile`
  - `safety_profile`: `mode`, optional `safeword`, optional `traffic_light_words`
  - `personal_preferences`: `grooming_preference`
- Safety-Validierung ergänzt: abhängige Pflichtfelder werden über `q10_safety_mode` erzwungen.
- Questionnaire um Sicherheits-/Eskalations-/Grooming-/Erfahrungsfelder erweitert.
- Psychogramm-UI zeigt je nach `safety_mode` nur relevante Sicherheitsfelder.

## 0.0.6 - 2026-02-21

- Auth-Flow auf Username/Password fokussiert, Registrierung mit Pflichtfeld E-Mail.
- Aktive Session erzwingt Dashboard statt neuem Setup; Setup-Guard gegen parallele aktive Sessions.
- Session-Vertrag im Setup erweitert (Startdatum, KI-gesteuertes Enddatum mit optionalem Max-Enddatum, Limits/Opening-Period).
- Psychogramm-/Setup-UI verbessert: kompakteres responsives Layout, bessere Mobil-Darstellung, i18n fuer Dropdown-Werte.
- Session-Kill als Feature-Flag eingefuehrt (`ENABLE_SESSION_KILL`), inklusive API-Endpoint und Dashboard-Button.
- Frontend-Flow verfeinert: Login-Karte ausblendbar nach Login, Logout oben rechts, Session-KILL fuer erneuten Setup-Durchlauf.

## 0.0.5 - 2026-02-21

- User-First Setup eingefuehrt (`/users`, `/users/{id}`, `/users/{id}/characters`).
- Setup-Start auf `user_id` umgestellt, optional mit `character_id`.
- Persistente Sessiondaten auf `user_id`/`character_id` angepasst.
- Landingpage (`/`) und App-Shell (`/app`) eingefuehrt.
- Alte Demo-Route als Redirect auf `/app` weitergefuehrt.
- Tests fuer User-Setup und Web-Seiten erweitert.

## 0.0.4 - 2026-02-21

- Psychogramm-Feedback umgesetzt: dynamische Updates, `update_reason`, `autonomy_profile`, `autonomy_bias`, `praise_timing`.
- Sicherheits- und Filterfelder erweitert (`blocked_trigger_words`, `forbidden_topics`, Challenge-Kategorien).
- Konservative Defaults bei niedriger Psychogramm-Confidence explizit implementiert.
- Fragebogen auf Session-Setup v2.1 (8 Hauptfragen + offene Abschlussfrage) umgestellt.
- Kurzauswertung `psychogram_brief` in API-Responses und Demo-UI integriert.

## 0.0.3 - 2026-02-21

- Setup-Prototyp funktional ausgebaut (Start, Fragebogen, Preview, Abschluss).
- BDSM-test-inspirierter Fragebogen mit Psychogramm-Ableitung integriert.
- Mehrsprachigkeit im Prototyp erweitert (`de`/`en`) fuer Setup und Story-Turn.
- Fragebogenskala auf `1-10` umgestellt, inklusive Slider-UI in der Demo.
- Datei-basierte Persistenz fuer Setup-Sessions (`data/setup_sessions.json`) eingefuehrt.
- Tests fuer Setup-Flow, i18n und Demo erweitert.

## 0.0.2 - 2026-02-21

- Produkt-, Architektur- und SRS-Dokumente konsolidiert und sprachlich/fachlich geschärft.
- Domains `world` und `combat` vollständig aus allen Dokumenten entfernt.
- `GameSession` konsistent auf `ChastitySession` umgestellt.
- Setup/Initialisierung in Priorität P0 aufgenommen.
- Psychologischer Setup-Fragebogen und Psychogramm-Konzept ergänzt.
- Neues Architekturartefakt: `docs/architecture/PSYCHOGRAM_SCHEMA.md`.

## 0.0.1 - 2026-02-21

- Initiale Projektgrundlage mit API, Tests und Dokumentationsstruktur.
- Architektur- und Anforderungsdokumentation mit C4, UML, Action-Matrix und ADRs.
- Migration des API-Scaffolds von Flask auf FastAPI.
- UI/UX-Anforderungsschicht fuer responsive, geraeteuebergreifende Nutzung.
