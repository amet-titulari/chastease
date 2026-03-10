# Requirements – Chastease

## Funktionale Anforderungen

---

### FR-01: Session-Management

| ID | Anforderung | Priorität |
|---|---|---|
| FR-01.1 | Der Nutzer kann eine neue Session starten und konfigurieren | Hoch |
| FR-01.2 | Der Nutzer kann eine laufende Session pausieren und fortsetzen | Hoch |
| FR-01.3 | Sessions werden auf dem Backend-Server persistiert und können von jedem Client-Gerät fortgesetzt werden | Hoch |
| FR-01.4 | Sessionverlauf (Chat, Ereignisse) ist einsehbar | Mittel |
| FR-01.5 | Eine Session hat immer genau eine Keyholderin | Hoch |

---

### FR-02: Timer & Sperrdauer

| ID | Anforderung | Priorität |
|---|---|---|
| FR-02.1 | Die Sperrdauer wird beim Sessionstart zufällig innerhalb eines konfigurierten Bereichs festgelegt | Hoch |
| FR-02.2 | Es gibt eine konfigurierbare Mindestdauer; intern als Integer-Sekunden gespeichert, die UI zeigt und akzeptiert menschenlesbare Einheiten (z.B. "30 Min", "2 Std", "3 Tage") | Hoch |
| FR-02.3 | Es gibt eine optionale konfigurierbare Maximaldauer (ebenfalls intern als Integer-Sekunden, `None` = kein Maximum) | Mittel |
| FR-02.10 | Alle Dauern und Timer-Intervalle werden intern als Integer-Sekunden gespeichert (konsistent mit Unix `timedelta`); die KI kommuniziert Zeitaktionen in Minuten, die Schicht konvertiert | Hoch |
| FR-02.4 | Die Keyholderin kann Zeit hinzufügen (Bestrafung) | Hoch |
| FR-02.5 | Die Keyholderin kann Zeit entfernen (Belohnung) | Hoch |
| FR-02.6 | Die Keyholderin kann den Timer einfrieren (Freeze) | Hoch |
| FR-02.7 | Die Keyholderin kann einen eingefrorenen Timer wieder freigeben (Unfreeze) | Hoch |
| FR-02.8 | Der aktuelle Timer-Status ist jederzeit im Dashboard sichtbar | Hoch |
| FR-02.9 | Der Timer läuft auch wenn die App nicht aktiv genutzt wird | Hoch |

---

### FR-03: Bildverifikation

| ID | Anforderung | Priorität |
|---|---|---|
| FR-03.1 | Die Keyholderin kann eine Bildverifikation anfordern | Hoch |
| FR-03.2 | Der Nutzer lädt ein Foto zur Verifikation hoch | Hoch |
| FR-03.3 | Die KI analysiert das Bild und bestätigt oder zweifelt die Integrität an | Hoch |
| FR-03.4 | Optionale Unterstützung für nummerierte Plomben (Seal-Nummern werden in der Anforderung mitgegeben) | Mittel |
| FR-03.5 | Verifikationsanfragen und Ergebnisse werden im Sessionverlauf gespeichert | Mittel |

---

### FR-04: Aufgaben- & Challenge-System

| ID | Anforderung | Priorität |
|---|---|---|
| FR-04.1 | Die Keyholderin kann dem Nutzer Aufgaben/Challenges stellen | Hoch |
| FR-04.2 | Aufgaben können eine Deadline haben | Mittel |
| FR-04.3 | Der Nutzer kann Aufgaben als erledigt markieren (optional mit Bild-/Text-Nachweis) | Hoch |
| FR-04.4 | Nicht erledigte Aufgaben können zu Bestrafungen führen | Hoch |
| FR-04.5 | Erledigt Aufgaben können zu Belohnungen führen | Hoch |
| FR-04.6 | Aufgaben-Bibliothek: vordefinierte Tasks die der Persona zugeordnet werden können | Niedrig |

---

### FR-05: Belohnungs- & Bestrafungssystem

| ID | Anforderung | Priorität |
|---|---|---|
| FR-05.1 | Belohnungen: Zeit entfernen, Sonderrechte | Hoch |
| FR-05.2 | Bestrafungen: Zeit hinzufügen, Timer einfrieren, neue Aufgaben | Hoch |
| FR-05.3 | Belohnungen/Bestrafungen können direkt durch die KI ausgelöst werden | Hoch |
| FR-05.4 | Belohnungen/Bestrafungen können als Ergebnis von Tasks vergeben werden | Hoch |
| FR-05.5 | Alle Belohnungen/Bestrafungen werden im Verlauf dokumentiert | Mittel |

---

### FR-06: Kommunikation & Benachrichtigungen

| ID | Anforderung | Priorität |
|---|---|---|
| FR-06.1 | Chat-Interface zwischen Nutzer und Keyholderin | Hoch |
| FR-06.2 | Die Keyholderin kann proaktiv Nachrichten senden (getriggert durch Timer-Events) | Hoch |
| FR-06.3 | Browser-Push-Benachrichtigungen für wichtige Events (Aufgaben-Deadline, Timer-Änderungen) | Mittel |
| FR-06.4 | Die Keyholderin kann Erinnerungen einplanen | Mittel |

---

### FR-07: Sicherheitssystem

| ID | Anforderung | Priorität |
|---|---|---|
| FR-07.1 | **Safeword**: Sofortiger Abbruch der Session ohne Konsequenzen im Spiel | Hoch |
| FR-07.2 | **Ampelsystem (GYR)**: Nutzer kann Grün/Gelb/Rot signalisieren; die KI reagiert entsprechend | Hoch |
| FR-07.3 | Bei Gelb: KI verlangsamt/reduziert Intensität | Hoch |
| FR-07.4 | Bei Rot: Session wird sofort pausiert | Hoch |
| FR-07.5 | **Emergency Release**: Sofortige Session-Beendigung mit Pflichtbegründung | Hoch |
| FR-07.6 | Emergency Release erfordert eine schriftliche Begründung vor der Ausführung | Hoch |
| FR-07.7 | Emergency Release wird im Protokoll dokumentiert | Hoch |
| FR-07.8 | Safety-Controls sind jederzeit erreichbar (persistent im UI) | Hoch |

---

### FR-08: Keyholderin-Konfiguration

| ID | Anforderung | Priorität |
|---|---|---|
| FR-08.1 | Name, Persönlichkeit und Kommunikationsstil sind konfigurierbar | Hoch |
| FR-08.2 | Mehrere Persona-Profile können gespeichert werden | Mittel |
| FR-08.3 | Die Keyholderin-Persona wird dem KI-System als Kontext mitgegeben (System-Prompt) | Hoch |
| FR-08.4 | Verhaltensregeln und Grenzen der Persona sind definierbar | Mittel |

---

### FR-09: KI-Konfiguration

| ID | Anforderung | Priorität |
|---|---|---|
| FR-09.1 | API-Anbieter ist konfigurierbar (Grok, OpenAI-kompatible APIs, lokale LLMs) | Hoch |
| FR-09.2 | API-Key wird lokal und verschlüsselt gespeichert | Hoch |
| FR-09.3 | Modell ist wählbar (innerhalb des gewählten Anbieters) | Mittel |
| FR-09.4 | Verbindungstest mit Feedback | Mittel |

---

### FR-10: Hygiene-Öffnungen

| ID | Anforderung | Priorität |
|---|---|---|
| FR-10.1 | Die maximale Anzahl erlaubter Hygiene-Öffnungen ist pro Session konfigurierbar (pro Tag / Woche / Monat) | Hoch |
| FR-10.2 | Der Nutzer kann bei der Keyholderin eine Hygiene-Öffnung beantragen | Hoch |
| FR-10.3 | Die Keyholderin entscheidet (KI) ob eine Öffnung gewährt wird, basierend auf dem verbleibenden Kontingent und ihrer Persona | Hoch |
| FR-10.4 | Eine gewährte Öffnung startet einen konfigurierbaren Countdown (z.B. 15–30 Minuten) | Hoch |
| FR-10.5 | Nach Ablauf des Countdowns muss der Käfig wieder verschlossen und bestätigt werden | Hoch |
| FR-10.6 | Verbrauchte und verbleibende Öffnungen des aktuellen Zeitraums sind im Dashboard sichtbar | Mittel |
| FR-10.7 | Alle Hygiene-Öffnungen werden mit Zeitstempel im Session-Verlauf protokolliert | Mittel |
| FR-10.8 | Bei aktiver Plomben-Nutzung: die bestehende Plombe wird beim Start der Öffnung als zerstört markiert | Hoch |
| FR-10.9 | Nach einer Öffnung mit Plombe: der Nutzer muss zwingend eine neue Plombennummer eintragen, bevor die Session weiterläuft | Hoch |
| FR-10.10 | Die neue Plombennummer wird im System gespeichert und gilt ab diesem Zeitpunkt für nachfolgende Verifikationen | Hoch |
| FR-10.11 | Überschreitet der Nutzer das Kontingent und beantragt dennoch eine Öffnung, kann die KI dies ablehnen oder als regelwidrig markieren (Bestrafung möglich) | Mittel |
| FR-10.12 | Wird der Countdown der gewährten Öffnung überschritten ohne Wiedereinschluss-Bestätigung, wird automatisch eine Bestrafung ausgelöst (z.B. Zeit hinzufügen, Timer einfrieren) | Hoch |
| FR-10.13 | Die Art und Schwere der automatischen Bestrafung bei Überschreitung ist pro Persona konfigurierbar | Mittel |
| FR-10.14 | Die Keyholderin kommentiert eine Überschreitung in ihrer Persona (proaktive KI-Nachricht) | Mittel |

---

### FR-11: Spieler-Psychogramm

| ID | Anforderung | Priorität |
|---|---|---|
| FR-11.1 | Der Nutzer kann ein persönliches Psychogramm-Profil anlegen und pflegen | Hoch |
| FR-11.2 | Das Profil erfasst **Vorlieben**: bevorzugte Aufgabentypen, Themen, Reize | Hoch |
| FR-11.3 | Das Profil erfasst **Grenzen**: Hard Limits (niemals) und Soft Limits (ungern / nur mit Ankündigung) | Hoch |
| FR-11.4 | Das Profil erfasst **Reaktionsmuster**: was motiviert, was demotiviert, wie der Nutzer auf Lob/Strenge reagiert | Mittel |
| FR-11.5 | Das Profil erfasst **Bedürfnisse**: z.B. Bedarf nach Bestätigung, Kontrolle, Überraschung, Routine | Mittel |
| FR-11.6 | Das Profil erfasst **Erfahrungsniveau** (Einsteiger / Fortgeschritten / Erfahren) | Mittel |
| FR-11.7 | Das Profil wird über einen geführten Onboarding-Fragebogen initial erstellt | Mittel |
| FR-11.8 | Das Psychogramm kann jederzeit manuell ergänzt und angepasst werden | Hoch |
| FR-11.9 | Das Profil wird als komprimierter Kontext-Block in jeden KI-Prompt eingebettet | Hoch |
| FR-11.10 | Die KI passt Tonalität, Aufgabentypen, Belohnungen und Bestrafungen auf Basis des Profils an | Hoch |
| FR-11.11 | Hard Limits werden als absolute Einschränkungen im System-Prompt verankert – die KI darf diese nie überschreiten | Hoch |
| FR-11.12 | Das Profil ist lokal gespeichert und nicht an eine einzelne Session gebunden (sessionübergreifend) | Hoch |
| FR-11.13 | Optional: Die KI kann nach einer Session Beobachtungen zum Spielerverhalten vorschlagen, die ins Profil übernommen werden können | Niedrig |

---

### FR-12: Keuschheits-Vertrag

| ID | Anforderung | Priorität |
|---|---|
---|
| FR-12.1 | Als letzter Schritt der Session-Erstellung wird automatisch ein Keuschheits-Vertrag generiert | Hoch |
| FR-12.2 | Der Vertrag fasst alle Session-Parameter zusammen: Keyholderin-Persona, Mindest-/Maximaldauer, Hygiene-Regelung, Aufgaben-Regeln, Plomben-Status, Safeword | Hoch |
| FR-12.3 | Der Vertrag wird von der KI in der Sprache und im Stil der Keyholderin-Persona formuliert | Hoch |
| FR-12.4 | Der Nutzer muss den Vertrag durch eine aktive digitale Unterschrift bestätigen (Checkbox + explizite Bestätigungsschaltfläche) | Hoch |
| FR-12.5 | Erst nach Unterzeichnung startet die Session; vorher ist kein Timer-Start möglich | Hoch |
| FR-12.6 | Nach Unterzeichnung kann der Nutzer keine Session-Parameter mehr ändern | Hoch |
| FR-12.7 | Die KI darf Session-Parameter (ausser sicherheitsrelevante) im gegenseitigen Einverständnis anpassen – der Nutzer muss jeder KI-initiierten Änderung aktiv zustimmen | Hoch |
| FR-12.8 | Sicherheitsrelevante Parameter (Safeword, Ampelsystem, Emergency Release) sind unveränderlich und können weder vom Nutzer noch von der KI nach Unterzeichnung geändert werden | Hoch |
| FR-12.9 | Der unterzeichnete Vertrag wird als unveränderliches Dokument (mit Zeitstempel der Unterzeichnung) in der Session gespeichert | Hoch |
| FR-12.10 | Der Vertrag ist jederzeit während der Session einsehbar | Mittel |
| FR-12.11 | KI-initiierte Parameteränderungen werden als Vertrags-Addendum mit Zeitstempel und Zustimmungsprotokoll gespeichert | Mittel |
| FR-12.12 | Nach Abschluss der Session ist der vollständige Vertrag inkl. aller Addenda einsehbar und exportierbar | Niedrig |

---

## Nicht-funktionale Anforderungen

| ID | Anforderung | Priorität |
|---|---|---|
| NFR-01 | **Datenschutz – Server**: Alle Nutzerdaten (DB, Fotos, Konfiguration, Chat) werden ausschliesslich auf dem Backend-Server gespeichert – kein Cloud-Dienst, keine Telemetrie | Hoch |
| NFR-01a | **Datenschutz – Client**: Client-Geräte (Smartphone, Tablet) speichern keinerlei App-Daten lokal – kein LocalStorage, kein IndexedDB, kein Foto-Cache | Hoch |
| NFR-01b | **Foto-Upload**: Verifikationsfotos werden direkt per Stream an das Backend übertragen und nie im Gerätespeicher des Clients abgelegt | Hoch |
| NFR-02 | **Geräteunabhängigkeit**: Läuft auf jedem modernen Browser (Desktop, Tablet, Mobile) ohne Installation | Hoch |
| NFR-03 | **Netzwerk**: Der Backend-Server ist im Heimnetz erreichbar; Fernzugriff erfolgt ausschliesslich über VPN (z.B. WireGuard, Tailscale) | Mittel |
| NFR-04 | **Performance**: Timer-Logik ist präzise auch bei längeren Laufzeiten | Hoch |
| NFR-05 | **Sicherheit**: API-Keys werden nie im Klartext im LocalStorage gespeichert | Hoch |
| NFR-06 | **Usability**: Safety-Controls sind immer innerhalb von 1 Klick/Tap erreichbar | Hoch |
| NFR-07 | **Erweiterbarkeit**: KI-Backend-Abstraktion erlaubt einfaches Hinzufügen neuer Anbieter | Mittel |
