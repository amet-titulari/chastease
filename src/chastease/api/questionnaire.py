QUESTIONNAIRE_VERSION = "setup-q-v2.5"
SUPPORTED_LANGUAGES = {"de", "en"}

TRANSLATIONS = {
    "de": {
        "not_found": "Setup-Session nicht gefunden.",
        "not_editable": "Setup-Session ist nicht mehr bearbeitbar.",
        "cannot_complete": "Setup-Session kann nicht abgeschlossen werden.",
        "not_enough_answers": "Zu wenige Antworten zum Abschliessen des Setups.",
        "unknown_question": "Unbekannte Frage-ID",
        "action_required": "Feld 'action' ist erforderlich.",
        "story_prefix": "Du versuchst",
        "demo_title": "Setup Prototype Demo",
        "demo_hint": "Teste hier den Setup-Flow vor der DB-Persistenz.",
        "summary_template": "Struktur {structure}, Strenge {strictness}, Kontrolle {accountability}.",
        "recalibration_done": "Psychogramm wurde aktualisiert.",
    },
    "en": {
        "not_found": "Setup session not found.",
        "not_editable": "Setup session is not editable.",
        "cannot_complete": "Setup session cannot be completed.",
        "not_enough_answers": "Not enough answers to complete setup.",
        "unknown_question": "Unknown question_id",
        "action_required": "Field 'action' is required.",
        "story_prefix": "You attempt",
        "demo_title": "Setup Prototype Demo",
        "demo_hint": "Use this page to test the setup flow before DB persistence.",
        "summary_template": "Structure {structure}, strictness {strictness}, accountability {accountability}.",
        "recalibration_done": "Psychogram has been updated.",
    },
}

# Inspired by psychometric preference tests; intentionally authored, not copied.
QUESTION_BANK = [
    {
        "id": "q1_rule_structure",
        "type": "scale_100",
        "texts": {
            "de": "Wie wichtig sind dir klare, schriftliche Regeln und genau definierte Erwartungen?",
            "en": "How important are clear written rules and well-defined expectations to you?",
        },
        "default_values": {"de": 60, "en": 60},
        "weights": {"structure_need": 1.0, "protocol_affinity": 0.4},
    },
    {
        "id": "q2_strictness_authority",
        "type": "scale_100",
        "texts": {
            "de": "Wie stark moechtest du in dieser Session Strenge, Konsequenz und Autoritaet erleben?",
            "en": "How strongly do you want to experience strictness, consequences, and authority in this session?",
        },
        "default_values": {"de": 60, "en": 60},
        "weights": {"strictness_affinity": 1.0, "accountability_need": 0.3},
    },
    {
        "id": "q3_control_need",
        "type": "scale_100",
        "texts": {
            "de": "Wie sehr brauchst du das Gefuehl, wirklich kontrolliert und ueberwacht zu werden?",
            "en": "How much do you need to feel genuinely controlled and monitored?",
        },
        "default_values": {"de": 65, "en": 65},
        "weights": {"accountability_need": 1.0, "structure_need": 0.3},
    },
    {
        "id": "q4_praise_importance",
        "type": "scale_100",
        "texts": {
            "de": "Wie wichtig ist positives Feedback/Anerkennung fuer gutes Verhalten?",
            "en": "How important is positive feedback/recognition for good behavior?",
        },
        "default_values": {"de": 50, "en": 50},
        "weights": {"praise_affinity": 1.0},
    },
    {
        "id": "q5_novelty_challenge",
        "type": "scale_100",
        "texts": {
            "de": "Wie sehr suchst du Abwechslung, neue Aufgaben und ungewohnte Herausforderungen?",
            "en": "How much are you looking for variety, new tasks, and unfamiliar challenges?",
        },
        "default_values": {"de": 80, "en": 80},
        "weights": {"novelty_affinity": 0.7, "challenge_affinity": 0.7},
    },
    {
        "id": "q6_intensity_1_5",
        "type": "scale_100",
        "texts": {
            "de": "Welche Intensitaet passt aktuell am besten?",
            "en": "What intensity fits best right now?",
        },
        "default_values": {"de": 30, "en": 30},
        "weights": {"strictness_affinity": 0.8, "challenge_affinity": 0.6},
    },
    {
        "id": "q8_instruction_style",
        "type": "choice",
        "texts": {
            "de": "Wie sollen Anweisungen am liebsten gegeben werden?",
            "en": "How should instructions preferably be delivered?",
        },
        "options": [
            {"value": "direct_command", "de": "direkt & befehlsartig", "en": "direct & command-like"},
            {"value": "polite_authoritative", "de": "hoeflich-autoritaer", "en": "polite-authoritative"},
            {"value": "suggestive", "de": "suggestiv/verfuehrerisch", "en": "suggestive/seductive"},
            {"value": "mixed", "de": "gemischt je nach Situation", "en": "mixed depending on situation"},
        ],
        "default_values": {"de": "polite_authoritative", "en": "polite_authoritative"},
        "weights": {},
    },
    {
        "id": "q11_escalation_mode",
        "type": "choice",
        "texts": {
            "de": "Wie schnell soll Intensitaet eskalieren?",
            "en": "How quickly should intensity escalate?",
        },
        "options": [
            {"value": "very_slow", "de": "sehr langsam", "en": "very slow"},
            {"value": "slow", "de": "langsam", "en": "slow"},
            {"value": "moderate", "de": "moderat", "en": "moderate"},
            {"value": "strong", "de": "stark", "en": "strong"},
            {"value": "aggressive", "de": "aggressiv", "en": "aggressive"},
        ],
        "default_values": {"de": "strong", "en": "strong"},
        "weights": {},
    },
    {
        "id": "q12_grooming_preference",
        "type": "choice",
        "texts": {
            "de": "Welche Intimrasur-Praeferenz soll beachtet werden?",
            "en": "Which grooming preference should be respected?",
        },
        "options": [
            {"value": "no_preference", "de": "keine Praeferenz", "en": "no preference"},
            {"value": "clean_shaven", "de": "glatt rasiert", "en": "clean shaven"},
            {"value": "trimmed", "de": "getrimmt", "en": "trimmed"},
            {"value": "natural", "de": "natuerlich", "en": "natural"},
        ],
        "default_values": {"de": "clean_shaven", "en": "clean_shaven"},
        "weights": {},
    },
    {
        "id": "q14_hard_limits_text",
        "type": "text",
        "texts": {
            "de": "Welche harten Grenzen sollen verbindlich gelten? (hard_limits_text)",
            "en": "Which hard limits must be treated as binding? (hard_limits_text)",
        },
        "default_values": {
            "de": "Jegliche Form von Scat, Koprophilie und Watersports sowie Urolagnie",
            "en": "Any form of scat, coprophilia, watersports, and urolagnia.",
        },
        "weights": {},
    },
    {
        "id": "q15_soft_limits_text",
        "type": "text",
        "texts": {
            "de": "Soft Limits (fix):",
            "en": "Soft limits (fixed):",
        },
        "default_values": {
            "de": "Dynamisch waehrend der Sitzung durch sichere Kommunikation.",
            "en": "Dynamic during the session via safe communication.",
        },
        "read_only": True,
        "weights": {},
    },
    {
        "id": "q7_taboo_text",
        "type": "text",
        "texts": {
            "de": "Gibt es Themen/Handlungen/Worte/Szenarien, die komplett tabu sind? (Freitext)",
            "en": "Are there topics/actions/words/scenarios that are completely taboo? (Free text)",
        },
        "weights": {},
    },
    {
        "id": "q10_safety_mode",
        "type": "choice",
        "texts": {
            "de": "Welches Sicherheitssystem soll verwendet werden?",
            "en": "Which safety system should be used?",
        },
        "options": [
            {"value": "safeword", "de": "Safeword", "en": "Safeword"},
            {"value": "traffic_light", "de": "Ampelsystem", "en": "Traffic light"},
        ],
        "default_values": {"de": "traffic_light", "en": "traffic_light"},
        "weights": {},
    },
    {
        "id": "q10_safeword",
        "type": "text",
        "texts": {
            "de": "Safeword (nur bei safety_mode=safeword)",
            "en": "Safeword (only when safety_mode=safeword)",
        },
        "weights": {},
    },
    {
        "id": "q13_experience_level",
        "type": "scale_100",
        "texts": {
            "de": "Wie erfahren bist du in diesem Kontext?",
            "en": "How experienced are you in this context?",
        },
        "default_values": {"de": 40, "en": 40},
        "weights": {},
    },
    {
        "id": "q9_open_context",
        "type": "text",
        "texts": {
            "de": "Gibt es etwas, das ich unbedingt wissen sollte, bevor wir starten? (Offen)",
            "en": "Is there anything I should absolutely know before we start? (Open)",
        },
        "default_values": {
            "de": "Ich haette echt Lust, irgendwann mal von dir zu lernen, wie man eine Frau so ruhig und bestimmt dominiert, dass sie es richtig spuert.",
            "en": "I would really like to learn from you one day how to dominate a woman calmly and firmly so she truly feels it.",
        },
        "weights": {},
    },
]

QUESTION_IDS = [q["id"] for q in QUESTION_BANK]
TRAIT_KEYS = [
    "structure_need",
    "strictness_affinity",
    "challenge_affinity",
    "praise_affinity",
    "accountability_need",
    "novelty_affinity",
    "service_orientation",
    "protocol_affinity",
]
