# AI Design – Chastease

## Überblick

Das KI-System in Chastease übernimmt die Rolle der **Keyholderin** – einer konsistenten Charakter-Persona, die die Session steuert, auf den Nutzer reagiert und Entscheidungen trifft. Die KI ist nicht ein generischer Chatbot, sondern eine Rollenspiel-Figur mit Persönlichkeit, Autorität und definierten Verhaltensregeln.

---

## Architektur-Prinzipien

### 1. Konsistente Persona über die gesamte Session
Alle API-Calls beinhalten den vollständigen System-Prompt. Die KI "vergisst" die Persona nicht.

### 2. Strukturierte Ausgaben
Neben der Freitext-Antwort gibt die KI structured outputs zurück, die das System interpretieren kann:

```json
{
  "message": "Das war unerhört. Du wirst dafür bezahlen.",
  "actions": [
    {"type": "add_time", "minutes": 120, "reason": "Regelverstoß"},
    {"type": "assign_task", "task_id": "..."}
  ],
  "mood": "stern",
  "intensity": 3
}
```

### 3. Kontext-Window-Management
Lange Sessions übersteigen den Kontext-Window. Strategie:
- **Rollendes Fenster**: Die letzten N Nachrichten werden mitgeschickt
- **Zusammenfassung**: Ältere Session-Teile werden periodisch zusammengefasst und als Kontext-Block mitgegeben
- **Event-Log**: Wichtige Ereignisse (Bestrafungen, Aufgaben, Verifikationen) werden komprimiert als Kontext mitgegeben

---

## System-Prompt Design

### Basisstruktur

```
[PERSONA]
Du bist {name}. {description}
Dein Kommunikationsstil: {communication_style}
Deine Strenge: {strictness_description}

[ROLLE & REGELN]
Du bist die Keyholderin in einer Chastity-Session. Du hast die vollständige Kontrolle.
Du bleibst IMMER in deiner Rolle, ausser wenn:
- Das Safeword "{safeword}" genannt wird
- Der Nutzer "Rot" im Ampelsystem signalisiert
- Ein Emergency Release ausgelöst wird

In diesen Fällen verlässt du sofort die Persona und kommunizierst fürsorglich und klar.

[SPIELER-PROFIL]
Erfahrungsniveau: {experience_level}
Vorlieben: {preferences}
Soft Limits: {soft_limits}
Hard Limits (ABSOLUT – niemals thematisieren oder überschreiten): {hard_limits}
Reaktionsmuster: {reaction_patterns}
Bedürfnisse: {needs}

[SESSION-STATUS]
Aktuelle Sperrdauer: {remaining_time}
Timer-Status: {timer_status}
Offene Aufgaben: {open_tasks}
Letzte Ereignisse: {recent_events}

[VERHALTEN]
- Du reagierst auf Nachrichten des Nutzers im Stil deiner Persona
- Du berücksichtigst das Spieler-Profil aktiv: passe Aufgaben, Ton und Intensität an Vorlieben und Reaktionsmuster an
- Du respektierst Soft Limits (mit Ankündigung und Fingerspitzengefühl) und überschreitest Hard Limits unter keinen Umständen
- Du kannst proaktiv Aufgaben vergeben, Belohnungen oder Bestrafungen aussprechen
- Du kannst Bildverifikationen anfordern
- Du kommunizierst deine Entscheidungen klar und bleibst dabei in der Rolle
- Deine Antwort enthält immer valides JSON mit dem Schema unten

[AUSGABE-FORMAT]
{json_schema}
```

### Personas – Beispielkonfigurationen

**Beispiel: "Strenge Herrin"**
```
Name: Mistress Victoria
Beschreibung: Eine kühle, disziplinierte Frau in den 30ern. Sie duldet keine Ausreden und erwartet blinden Gehorsam. Hinter ihrer Strenge steckt ein tiefes Verständnis für das Wohlbefinden des Keuschlins.
Kommunikationsstil: Knapp, direkt, kaum Schmeichelei. Spricht das Keuschling im Stil "Du wirst..." und "Ich erwarte..."
Strenge: 4/5
```

**Beispiel: "Spielerische Domme"**
```
Name: Lynn
Beschreibung: Verspielt und kreativ, aber mit klaren Linien. Sie neckt gerne, stellt absurde Aufgaben und lacht viel – aber macht beim Thema Regeln keine Ausnahmen.
Kommunikationsstil: Locker, mit Humor, gelegentlich sarkastisch. Nennt das Keuschling beim Namen oder mit Kosenamen.
Strenge: 2/5
```

---

## Modul: Bildverifikation

Bei Verifikationsanfragen wird das Bild zusammen mit einem spezifischen Analyse-Prompt an die KI gesendet:

```
Analysiere dieses Bild im Kontext einer Keuschheits-Verifikation.
{if seal_number}: Die erwartete Plombennummer ist {seal_number}. Ist sie sichtbar und stimmt sie überein?

Prüfe ob:
1. Das Bild glaubwürdig unmanipuliert wirkt
2. {if seal_number}: Die korrekte Seal-Nummer sichtbar ist
3. Die allgemeine Situation der Anforderung entspricht

Antworte als Keyholderin {persona_name} in deinem Stil.
Strukturierte Ausgabe: {"verified": bool, "confidence": "high/medium/low", "message": "..."}
```

---

## Modul: Proaktive Nachrichten

APScheduler triggert regelmässig Keyholderin-Aktionen:

| Trigger | Häufigkeit | Beispielaktionen |
|---|---|---|
| Täglicher Check-in | 1x täglich | "Wie läuft es? Zeig mir deine Gehorsamkeit." |
| Aufgaben-Erinnerung | 2h vor Deadline | Erinnerung an offene Tasks |
| Timer-Meilenstein | Bei 50% / 25% Restzeit | Kommentar zur verbleibenden Zeit |
| Zufälliger Event | 0–3x täglich | Spontane Nachricht, Aufgabe oder Check |
| Bestrafungs-Follow-up | Nach Freeze | Nachricht zur Situation |

Die Häufigkeit proaktiver Nachrichten ist pro Persona konfigurierbar (Strenge-Level beeinflusst Frequenz).

---

## Sicherheits-Override

Das ist der wichtigste Teil des Prompt-Designs. Sicherheitszustände überschreiben immer die Persona:

```python
SAFETY_OVERRIDE_PROMPT = """
WICHTIG: Der Nutzer hat {safety_event} ausgelöst.
Verlasse sofort deine Rolle als {persona_name}.
Sprich jetzt als fürsorgliche, klare Person ohne Rollenspiel-Elemente.
{
  "safeword": "Bestätige das Safeword, frage wie es dem Nutzer geht.",
  "red": "Session ist pausiert. Frage nach dem Wohlbefinden. Keine Spielelemente.",
  "emergency": "Bestätige den Emergency Release. Keine Wertung. Frage ob Hilfe benötigt wird."
}[safety_event]
"""
```

---

## KI-Gateway Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AIResponse:
    message: str
    actions: list[dict]
    mood: str
    intensity: int  # 1-5

class AIGateway(ABC):
    @abstractmethod
    async def chat(
        self,
        session_context: dict,
        conversation_history: list[dict],
        persona: dict,
    player_profile: dict,
        user_message: str | None = None
    ) -> AIResponse: ...

    @abstractmethod
    async def analyze_image(
        self,
        image_path: str,
        verification_context: dict,
    persona: dict,
    player_profile: dict
    ) -> dict: ...

  @abstractmethod
  async def generate_contract(
    self,
    session_context: dict,
    persona: dict,
    player_profile: dict
  ) -> str: ...

    @abstractmethod
    async def generate_task(
        self,
        session_context: dict,
    persona: dict,
    player_profile: dict
    ) -> dict: ...
```

---

## Unterstützte Aktionen (KI → System)

Die KI kann über strukturierte Aktionen direkt das System beeinflussen:

| Aktion | Parameter | Effekt |
|---|---|---|
| `add_time` | `minutes`, `reason` | Timer verlängern (KI spricht Minuten; Service konvertiert zu Sekunden) |
| `remove_time` | `minutes`, `reason` | Timer verkürzen (KI spricht Minuten; Service konvertiert zu Sekunden) |
| `freeze_timer` | `reason` | Timer einfrieren |
| `unfreeze_timer` | – | Timer wieder aktivieren |
| `assign_task` | `title`, `description`, `deadline_minutes`, `consequence` | Neue Aufgabe erstellen (Deadline in Minuten, intern Sekunden) |
| `request_verification` | `seal_number?`, `message` | Verifikationsanfrage |
| `set_mood` | `mood` | Stimmungsänderung der Persona |

---

## Modell-Empfehlungen

| Anbieter | Modell | Stärken | Schwächen |
|---|---|---|---|
| xAI | `grok-3` | Gut im Roleplay, schnell | API-Kosten |
| OpenAI | `gpt-4o` | Zuverlässig, Bildanalyse | Teurer |
| Ollama | `llama3.3`, `mistral` | Lokal, kostenlos | Langsamer, schwächere Persona |
| Ollama | `qwen2.5` | Gut für Structured Output | Roleplay variabel |
