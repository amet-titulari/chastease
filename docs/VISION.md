# Vision – Chastease

## Projektziel

Chastease ist eine immersive Rollenspiel-Applikation, die eine möglichst realistische Chastity-Session-Erfahrung ermöglicht. Eine KI übernimmt dabei die Rolle der **Keyholderin** – mit konsistentem Charakter, Entscheidungsgewalt und emotionaler Tiefe.

Das Ziel ist nicht ein einfacher Chatbot, sondern eine strukturierte, spielmechanisch fundierte Erfahrung, die den Nutzenden tatsächlich in eine Rolle versetzt und die Session glaubwürdig lebendig macht.

---

## Zielgruppe

- **Primär**: Einzelpersonen, die Chastity-Sessions solo erleben möchten (mit KI als Keyholderin)
- **Sekundär (spätere Phase)**: Paare oder Gruppen, bei denen eine reale Person remote als Keyholder agiert und die App als Steuerungswerkzeug verwendet

---

## Kernwerte

### 1. Immersion
Die Keyholderin soll sich wie eine echte Person anfühlen – mit Persönlichkeit, Stimmungsschwankungen, Reaktionen auf das Verhalten des Nutzers und einem konsistenten Gesprächsstil. Kein generischer Chatbot.

### 2. Privatsphäre & Datenschutz
Alle persönlichen Daten – Sessionverläufe, Chats, Fotos, Konfigurationen – bleiben **ausschließlich auf dem privaten Backend-Server des Nutzers**. Kein Cloud-Sync, keine Telemetrie, keine externe Datenspeicherung.

Client-Geräte dienen nur als Zugänge zur Anwendung. Die App soll absichtlich keine langlebigen lokalen Daten auf Smartphone, Tablet oder Browser ablegen. Insbesondere sollen Verifikationsbilder nicht in der Galerie des Endgeräts verbleiben, sondern direkt an das Backend übertragen werden. Temporäre Zwischenspeicher des Betriebssystems oder Browsers sollen minimiert, aber nicht als absolut ausgeschlossen versprochen werden.

Die einzige Ausnahme: API-Calls an den gewählten KI-Anbieter (z.B. xAI/Grok). Der Nutzer wählt und konfiguriert diesen selbst und trägt die Verantwortung für dessen Datenschutzbedingungen.

### 3. Sicherheit & Konsens
Das System stellt sicher, dass der Nutzende jederzeit die Kontrolle zurückgewinnen kann. Sicherheitsmechanismen (Ampelsystem, Safeword, Emergency Release) sind erste Klasse-Features – keine Randnotiz.

### 4. Flexibilität & Erweiterbarkeit
- KI-Backend ist austauschbar (Grok → lokales LLM → andere APIs)
- Persona der Keyholderin ist vollständig konfigurierbar
- Das System ist so gebaut, dass spätere Erweiterungen (Remote-Keyholder, Gamification) organisch integriert werden können

### 5. Geräteunabhängigkeit
Als WebApp läuft Chastease auf jedem modernen Gerät (Desktop, Tablet, Smartphone) ohne Installation.

---

## Abgrenzung

| In Scope | Out of Scope (MVP) |
|---|---|
| KI-Keyholderin (solo) | Echter Remote-Keyholder |
| Lokale Datenspeicherung | Cloud-Sync |
| Kernmechaniken der Session | Gamification / Achievements |
| Sicherheitssystem | Social Features |
| Konfigurierbare Persona | Mehrere simultane Sessions |

---

## Erfolgskriterien

- Die Session fühlt sich glaubwürdig und immersiv an
- Alle Safety-Features funktionieren zuverlässig und ohne Umwege
- Das System läuft stabil lokal ohne externe Abhängigkeiten (ausser KI-API)
- Die Keyholderin-Persona ist spürbar im Verhalten und Ton der KI
