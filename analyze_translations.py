#!/usr/bin/env python3
"""
Analyseur de qualité des traductions : détecte les mots appartenant
à une langue étrangère dans les fichiers de traduction cibles.

Approche heuristique basée sur :
- Dictionnaires de mots-outils caractéristiques par langue
- Détection de caractères spécifiques (umlauts, accents, caractères arabes, etc.)
- Analyse de mots entiers non traduits
- Comparaison optionnelle avec le texte source anglais
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

BASE_DIR = Path("/Users/michaelboitin/Documents/02_Dev/COP_translations")
EXPORT_DIR = BASE_DIR / "translator/output/2026_06_11_Export"
SOURCE_FILE = BASE_DIR / "translator/source/2026_06_11_Import/en 7.json"

FILES = {
    "translation_en_cz.json": {"lang": "cs", "label": "Tchèque (cs)"},
    "translation_en_de.json": {"lang": "de", "label": "Allemand (de)"},
    "translation_en_fr.json": {"lang": "fr", "label": "Français (fr)"},
    "translation_en_it.json": {"lang": "it", "label": "Italien (it)"},
    "translation_en_sk.json": {"lang": "sk", "label": "Slovaque (sk)"},
    "translation_en_ar.json": {"lang": "ar", "label": "Arabe (ar)"},
}

# ═══════════════════════════════════════════════════════════════════════
# TERMES TECHNIQUES À IGNORER (communs à toutes les langues)
# ═══════════════════════════════════════════════════════════════════════

TECH_TERMS = {
    # Acronymes & codes techniques
    "cop",
    "id",
    "srs",
    "api",
    "url",
    "uri",
    "http",
    "https",
    "ftp",
    "ssh",
    "ip",
    "vpn",
    "lan",
    "wan",
    "dns",
    "ssl",
    "tls",
    "cpu",
    "ram",
    "gpu",
    "csv",
    "xml",
    "json",
    "pdf",
    "html",
    "css",
    "sql",
    "pdf",
    "doc",
    "xls",
    "ok",
    "ko",
    "n/a",
    "na",
    "gps",
    "rfid",
    "erp",
    "crm",
    "sap",
    # Mots latins/borrowings universels en informatique
    "status",
    "error",
    "warning",
    "info",
    "success",
    "cancel",
    "reset",
    "version",
    "admin",
    "login",
    "logout",
    "online",
    "offline",
    "upload",
    "download",
    "email",
    "web",
    "internet",
    "browser",
    "server",
    "client",
    "database",
    "password",
    "username",
    "default",
    "menu",
    "tab",
    # Formats de date
    "dd",
    "mm",
    "yyyy",
    "jj",
    "mmaa",
    "rrrr",
    "gg",
    "aaaa",
    "tt",
    "jjjj",
    # Mots courts ambigus (conjonctions/prépositions qui existent dans
    # plusieurs langues et ne peuvent pas être attribués à une seule)
    "pro",
    "para",
    "per",
    "auto",
    "via",
    "mini",
    "max",
    "plus",
    "mega",
    "super",
    "extra",
    "top",
    "net",
    "key",
    "mode",
    "base",
    "code",
    # Noms propres / marques communs
    "coca-cola",
    "google",
    "microsoft",
    # Codes et abréviations français/EU spécifiques au domaine COP
    "siren",
    "siret",
    "insee",
    "tva",
    "nsc",
    "dms",
    "ape",
    "xxx",
    # Balises HTML et variables de template
    "strong",
    "br",
    "em",
    "p",
    "div",
    "span",
    "href",
    "src",
    "alt",
    "class",
    "style",
    "title",
    # Mots partagés FR/EN (existants dans les deux langues)
    "point",
    "page",
    "correct",
    "confirmation",
    "transport",
    "direction",
    "question",
    "action",
    "information",
    "identification",
    "national",
    "option",
    "situation",
    "position",
    "operation",
    "attention",
    "communication",
    "construction",
    "production",
    "reference",
    "facteur",
    "possible",
    "principal",
    "condition",
    "version",
    "centre",
    "general",
    "partenaire",
    "objet",
    "mobile",
    "actif",
    "activer",
    "desactiver",
    "terminer",
    "service",
    "local",
    "reseau",
    "administrateur",
    # Termes métier COP qui restent souvent en anglais
    "role",
    "transfer",
    "report",
    "business",
    "access",
    "logistic",
    "us",
    # Mots partagés DE/EN
    "name",
    "hand",
    "ring",
    "gold",
    "wolf",
    "haus",
    # Mots partagés IT/FR/EN
    "concerto",
    "studio",
    "radio",
    "piano",
    "banco",
    "control",
    "table",
    "machine",
    "force",
    "nature",
    "chance",
    "face",
    "place",
    "tour",
    "jour",
    "soir",
    "mer",
    "air",
    # Mots partagés EN/FR/DE/IT/etc. (cognats ou emprunts)
    "date",
    "total",
    "details",
    "attribute",
    "identifier",
    "legal",
    "location",
    "commercial",
    "company",
    "created",
    "show",
}

# Mots anglais très courts qui sont souvent des faux positifs car ils
# existent aussi dans d'autres langues ou sont des fragments
IGNORE_EN_SHORT = {
    "a",
    "an",
    "i",
    "o",
    "u",
    "e",  # Lettres seules
    "de",
    "le",
    "la",
    "un",
    "et",  # Sont aussi des mots FR
    "in",
    "on",
    "at",
    "to",
    "by",  # Prépositions ambiguës
    "or",
    "as",
    "no",  # Existent dans d'autres langues
    "da",
    "do",  # Existent en italien/portugais etc.
}

# ═══════════════════════════════════════════════════════════════════════
# DICTIONNAIRES DE MOTS CARACTÉRISTIQUES PAR LANGUE
# ═══════════════════════════════════════════════════════════════════════

ENGLISH_WORDS = {
    # Articles & déterminants
    "the",
    "a",
    "an",
    # Pronoms
    "i",
    "me",
    "my",
    "mine",
    "you",
    "your",
    "yours",
    "he",
    "him",
    "his",
    "she",
    "her",
    "hers",
    "it",
    "its",
    "we",
    "us",
    "our",
    "ours",
    "they",
    "them",
    "their",
    "theirs",
    "this",
    "that",
    "these",
    "those",
    "who",
    "whom",
    "whose",
    "which",
    "what",
    # Auxiliaires & verbes modaux
    "is",
    "am",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "will",
    "would",
    "shall",
    "should",
    "can",
    "could",
    "may",
    "might",
    "must",
    # Conjonctions
    "and",
    "but",
    "or",
    "nor",
    "so",
    "yet",
    "for",
    # Prépositions fréquentes
    "of",
    "in",
    "to",
    "for",
    "with",
    "on",
    "at",
    "from",
    "by",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "over",
    "without",
    "within",
    "along",
    "across",
    # Adverbes & mots-outils
    "not",
    "very",
    "also",
    "just",
    "only",
    "still",
    "already",
    "never",
    "always",
    "here",
    "there",
    "now",
    "then",
    "again",
    "too",
    "even",
    # Verbes fréquents
    "make",
    "get",
    "go",
    "come",
    "take",
    "see",
    "know",
    "think",
    "want",
    "give",
    "use",
    "find",
    "tell",
    "ask",
    "seem",
    "try",
    "leave",
    "call",
    "need",
    "become",
    "keep",
    "begin",
    "show",
    "hear",
    "play",
    "run",
    "move",
    "live",
    "believe",
    "bring",
    "happen",
    "write",
    "provide",
    "sit",
    "stand",
    "lose",
    "pay",
    "meet",
    "include",
    "continue",
    "set",
    "learn",
    "change",
    "lead",
    "understand",
    "watch",
    "follow",
    "stop",
    "create",
    "speak",
    "read",
    "allow",
    "add",
    "spend",
    "grow",
    "open",
    "walk",
    "win",
    "offer",
    "remember",
    "love",
    "consider",
    "appear",
    "buy",
    "wait",
    "serve",
    "die",
    "send",
    "expect",
    "build",
    "stay",
    "fall",
    "cut",
    "reach",
    "kill",
    "remain",
    "suggest",
    "raise",
    "pass",
    "sell",
    "require",
    "report",
    "decide",
    "pull",
    "develop",
    "update",
    "remove",
    "return",
    "search",
    "select",
    "view",
    "edit",
    "save",
    "delete",
    "submit",
    "apply",
    "cancel",
    "confirm",
    "transfer",
    "add",
    "deactivate",
    "rollback",
    "affiliate",
    "monitor",
    "manage",
    "manage",
    # Substantifs fréquents
    "the",
    "company",
    "organization",
    "location",
    "name",
    "type",
    "date",
    "identifier",
    "period",
    "activity",
    "details",
    "territory",
    "hub",
    "commercial",
    "network",
    "structure",
    "partner",
    "profile",
    "setting",
    "help",
    "center",
    "parameter",
    "restructuring",
    "page",
    "items",
    "effective",
    "until",
    "created",
    "updated",
    "last",
    "legal",
    "usual",
    "trade",
    "role",
    "access",
    "point",
    "logistic",
    "link",
    "attribute",
    "confirmation",
    "removal",
    "affiliation",
    "part",
    "information",
    "correct",
    "everything",
    "click",
    "finalize",
    "thank",
    "review",
    "please",
    # Adjectifs fréquents
    "all",
    "each",
    "every",
    "both",
    "few",
    "many",
    "much",
    "more",
    "most",
    "other",
    "some",
    "any",
    "new",
    "old",
    "first",
    "last",
    "next",
    "previous",
    "following",
    "same",
    "different",
    "important",
    # Mots fréquents dans les interfaces
    "please",
    "required",
    "invalid",
    "enter",
    "select",
    "choose",
    "close",
    "open",
    "back",
    "next",
    "previous",
    "finish",
    "start",
    "end",
    "loading",
    "error",
    "success",
    "warning",
    "info",
    "no",
    "yes",
    "true",
    "false",
    "none",
    "null",
    "empty",
    "total",
    "count",
}

FRENCH_WORDS = {
    # Articles
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "au",
    "aux",
    "l'",
    # Pronoms
    "je",
    "tu",
    "il",
    "elle",
    "nous",
    "vous",
    "ils",
    "elles",
    "me",
    "te",
    "se",
    "lui",
    "leur",
    "lequel",
    "laquelle",
    "lesquels",
    "celui",
    "celle",
    "ceux",
    "celles",
    "qui",
    "que",
    "quoi",
    "dont",
    "ce",
    "cette",
    "ces",
    "cet",
    # Prépositions
    "de",
    "à",
    "dans",
    "pour",
    "sur",
    "avec",
    "par",
    "sans",
    "sous",
    "entre",
    "vers",
    "chez",
    "en",
    "chez",
    # Conjonctions
    "et",
    "ou",
    "mais",
    "donc",
    "car",
    "ni",
    "que",
    "si",
    "quand",
    "lorsque",
    "puisque",
    # Auxiliaires & verbes
    "est",
    "sont",
    "sont",
    "a",
    "as",
    "ont",
    "ai",
    "ont",
    "suis",
    "es",
    "été",
    "être",
    "avoir",
    "fait",
    "fait",
    "sera",
    "seront",
    "serait",
    "seraient",
    "peut",
    "peuvent",
    "doit",
    "doivent",
    "faut",
    # Adverbes
    "ne",
    "pas",
    "plus",
    "moins",
    "très",
    "bien",
    "aussi",
    "encore",
    "déjà",
    "jamais",
    "toujours",
    "souvent",
    "parfois",
    "peut-être",
    "beaucoup",
    "trop",
    "peu",
    "tout",
    "tous",
    "toute",
    "toutes",
    "rien",
    "quelque",
    "quelques",
    "certain",
    "certains",
    # Mots-outils fréquents
    "non",
    "oui",
    "merci",
    "s'il",
    "plaît",
    "bonjour",
    "aujourd'hui",
    # Verbes fréquents UI
    "créer",
    "modifier",
    "supprimer",
    "afficher",
    "rechercher",
    "sauvegarder",
    "annuler",
    "confirmer",
    "ajouter",
    "retirer",
    "soumettre",
    "appliquer",
    "désactiver",
    "restaurer",
    "transférer",
    "sélectionner",
    "valider",
    "vider",
    # Noms fréquents UI
    "identifiant",
    "organisation",
    "entreprise",
    "emplacement",
    "nom",
    "prénom",
    "type",
    "date",
    "période",
    "activité",
    "détails",
    "territoire",
    "pôle",
    "commercial",
    "réseau",
    "paramètre",
    "profil",
    "partenaire",
    "structure",
}

GERMAN_WORDS = {
    # Articles
    "der",
    "die",
    "das",
    "ein",
    "eine",
    "einer",
    "eines",
    "einem",
    "einen",
    # Pronoms
    "ich",
    "du",
    "er",
    "sie",
    "es",
    "wir",
    "ihr",
    "Sie",
    "mein",
    "dein",
    "sein",
    "ihr",
    "unser",
    "euer",
    "dieser",
    "diese",
    "dieses",
    "jener",
    "jene",
    "jenes",
    "wer",
    "was",
    "welcher",
    "welche",
    "welches",
    # Prépositions
    "in",
    "an",
    "auf",
    "unter",
    "über",
    "vor",
    "hinter",
    "neben",
    "zwischen",
    "mit",
    "ohne",
    "für",
    "von",
    "zu",
    "nach",
    "bei",
    "aus",
    "durch",
    "gegen",
    "um",
    "bis",
    "seit",
    "während",
    # Conjonctions
    "und",
    "oder",
    "aber",
    "denn",
    "weil",
    "dass",
    "ob",
    "wenn",
    "als",
    "sobald",
    "sodass",
    "entweder",
    "weder",
    # Auxiliaires & verbes fréquents
    "ist",
    "sind",
    "war",
    "waren",
    "sein",
    "haben",
    "hat",
    "haben",
    "wird",
    "werden",
    "wurde",
    "wurden",
    "kann",
    "können",
    "muss",
    "müssen",
    "soll",
    "sollen",
    "darf",
    "dürfen",
    "möchte",
    "will",
    # Adverbes
    "nicht",
    "auch",
    "noch",
    "schon",
    "immer",
    "nie",
    "oft",
    "gern",
    "sehr",
    "viel",
    "wenig",
    "hier",
    "dort",
    "jetzt",
    "dann",
    "heute",
    "morgen",
    "gestern",
    "nur",
    "gerade",
    "etwa",
    # Mots fréquents UI
    "erstellen",
    "bearbeiten",
    "löschen",
    "suchen",
    "speichern",
    "abbrechen",
    "bestätigen",
    "hinzufügen",
    "entfernen",
    "einreichen",
    "anwenden",
    "deaktivieren",
    "aktualisieren",
    "zurückkehren",
    "anmelden",
    "abmelden",
    "auswählen",
    "anzeigen",
    # Noms fréquents
    "name",
    "typ",
    "datum",
    "identifikator",
    "kennung",
    "ausweis",
    "unternehmen",
    "organisation",
    "standort",
    "netzwerk",
    "struktur",
    "parameter",
    "profil",
    "partner",
    "hilfe",
    "zentrum",
}

ITALIAN_WORDS = {
    # Articles
    "il",
    "lo",
    "la",
    "i",
    "gli",
    "le",
    "un",
    "uno",
    "una",
    # Pronoms
    "io",
    "tu",
    "lui",
    "lei",
    "noi",
    "voi",
    "loro",
    "mi",
    "ti",
    "si",
    "ci",
    "vi",
    "questo",
    "questa",
    "questi",
    "queste",
    "quello",
    "quella",
    "che",
    "chi",
    "cui",
    "quale",
    # Prépositions
    "di",
    "a",
    "da",
    "in",
    "con",
    "su",
    "per",
    "tra",
    "fra",
    # Conjonctions
    "e",
    "o",
    "ma",
    "perché",
    "quando",
    "se",
    "anche",
    "dunque",
    "anzi",
    "pertanto",
    "cioè",
    "quindi",
    # Auxiliaires & verbes
    "è",
    "sono",
    "era",
    "erano",
    "essere",
    "avere",
    "ha",
    "hanno",
    "fare",
    "può",
    "possono",
    "deve",
    "devono",
    # Adverbes
    "non",
    "più",
    "molto",
    "poco",
    "bene",
    "male",
    "anche",
    "ancora",
    "già",
    "mai",
    "sempre",
    "spesso",
    "qui",
    "là",
    "ora",
    "poi",
    "sì",
    "no",
    # Mots fréquents UI
    "creare",
    "modificare",
    "eliminare",
    "cercare",
    "salvare",
    "cancellare",
    "confermare",
    "aggiungere",
    "rimuovere",
    "inviare",
    "applicare",
    "disattivare",
    "aggiornare",
    "ritorno",
    "selezionare",
    "visualizzare",
    "mostrare",
    # Noms fréquents
    "nome",
    "tipo",
    "data",
    "identificatore",
    "identificativo",
    "azienda",
    "organizzazione",
    "posizione",
    "rete",
    "struttura",
    "parametro",
    "profilo",
    "partner",
    "centro",
    "aiuto",
}

CZECH_WORDS = {
    # Articles (pas d'articles en tchèque, mais des pronoms)
    "ten",
    "ta",
    "to",
    "ti",
    "ty",
    "ti",
    # Pronoms
    "já",
    "ty",
    "on",
    "ona",
    "ono",
    "my",
    "vy",
    "oni",
    "můj",
    "tvůj",
    "jeho",
    "její",
    "náš",
    "váš",
    "kdo",
    "co",
    "který",
    "která",
    "které",
    "jaký",
    "čí",
    # Prépositions
    "v",
    "na",
    "do",
    "z",
    "ze",
    "k",
    "ke",
    "od",
    "pro",
    "s",
    "se",
    "o",
    "při",
    "podle",
    "kromě",
    "místo",
    "před",
    "za",
    "pod",
    "nad",
    "mezi",
    "při",
    "bez",
    # Conjonctions
    "a",
    "ale",
    "nebo",
    "protože",
    "pokud",
    "když",
    "i",
    "tudíž",
    # Verbes fréquents
    "je",
    "jsou",
    "byl",
    "byla",
    "byli",
    "být",
    "mít",
    "může",
    "mohou",
    "muset",
    "můžete",
    "byl",
    "bude",
    "budou",
    # Adverbes
    "ne",
    "ano",
    "také",
    "ještě",
    "už",
    "vždy",
    "nikdy",
    "často",
    "zde",
    "tam",
    "teď",
    "potom",
    "velmi",
    "více",
    "méně",
    # Mots fréquents UI
    "vytvořit",
    "upravit",
    "smazat",
    "odstranit",
    "hledat",
    "uložit",
    "zrušit",
    "potvrdit",
    "přidat",
    "odebrat",
    "odeslat",
    "předložit",
    "použít",
    "deaktivovat",
    "aktualizovat",
    "vrátit",
    "zobrazit",
    "vybrat",
    "zobrazit",
    # Noms fréquents
    "jméno",
    "název",
    "typ",
    "datum",
    "identifikátor",
    "společnost",
    "organizace",
    "místo",
    "síť",
    "struktura",
    "parametr",
    "profil",
    "partner",
    "centrum",
    "nápověda",
}

SLOVAK_WORDS = {
    # Pronoms
    "ja",
    "ty",
    "on",
    "ona",
    "my",
    "vy",
    "oni",
    "môj",
    "tvoj",
    "jeho",
    "jej",
    "náš",
    "váš",
    "kto",
    "čo",
    "ktorý",
    "ktorá",
    "ktoré",
    "aký",
    # Prépositions
    "v",
    "na",
    "do",
    "z",
    "zo",
    "k",
    "ku",
    "od",
    "pre",
    "s",
    "so",
    "o",
    "pri",
    "podľa",
    "okrem",
    "miesto",
    "pred",
    "za",
    "pod",
    "nad",
    "medzi",
    "bez",
    # Conjonctions
    "a",
    "ale",
    "alebo",
    "pretože",
    "ak",
    "keď",
    "lebo",
    # Verbes fréquents
    "je",
    "sú",
    "bol",
    "bola",
    "boli",
    "byť",
    "mať",
    "môže",
    "môžu",
    "musieť",
    "budem",
    "budú",
    # Adverbes
    "nie",
    "áno",
    "tiež",
    "ešte",
    "už",
    "vždy",
    "nikdy",
    "často",
    "tu",
    "tam",
    "teraz",
    "potom",
    "veľmi",
    "viac",
    "menej",
    # Mots fréquents UI
    "vytvoriť",
    "upraviť",
    "zmazať",
    "odstrániť",
    "hľadať",
    "uložiť",
    "zrušiť",
    "potvrdiť",
    "pridať",
    "odoslať",
    "použiť",
    "deaktivovať",
    "aktualizovať",
    "vrátiť",
    "zobraziť",
    "vybrať",
    # Noms fréquents
    "meno",
    "názov",
    "typ",
    "dátum",
    "identifikátor",
    "spoločnosť",
    "organizácia",
    "miesto",
    "sieť",
    "štruktúra",
    "parameter",
    "profil",
    "partner",
    "centrum",
    "pomoc",
}

# ═══════════════════════════════════════════════════════════════════════
# MOTS DE LANGUE ÉTRANGÈRE À DÉTECTER POUR CHAQUE LANGUE CIBLE
# ═══════════════════════════════════════════════════════════════════════

FOREIGN_WORDS_FOR_LANG = {
    "cs": {
        "fr": FRENCH_WORDS,
        "en": ENGLISH_WORDS,
        "de": GERMAN_WORDS,
        "it": ITALIAN_WORDS,
    },
    "de": {
        "fr": FRENCH_WORDS,
        "en": ENGLISH_WORDS,
        "it": ITALIAN_WORDS,
    },
    "fr": {
        "en": ENGLISH_WORDS,
        "de": GERMAN_WORDS,
        "it": ITALIAN_WORDS,
    },
    "it": {
        "en": ENGLISH_WORDS,
        "fr": FRENCH_WORDS,
        "de": GERMAN_WORDS,
    },
    "sk": {
        "fr": FRENCH_WORDS,
        "en": ENGLISH_WORDS,
        "de": GERMAN_WORDS,
        "it": ITALIAN_WORDS,
    },
    "ar": {
        "en": ENGLISH_WORDS,
        "fr": FRENCH_WORDS,
        "de": GERMAN_WORDS,
        "it": ITALIAN_WORDS,
    },
}

# Langues qui partagent des mots courts (ex: "de" = FR mais aussi préposition EN)
AMBIGUOUS_WORDS = {
    "de",  # FR préposition vs EN/ES/PT etc.
    "le",  # FR article vs IT article
    "la",  # FR article vs IT/ES article
    "un",  # FR article vs EN/ES article
    "et",  # FR conjonction vs IT "e"
    "di",  # IT préposition vs divers
    "a",  # Universel
    "o",  # PT/ES/IT vs EN interjection
    "in",  # EN préposition vs DE/IT
    "an",  # EN article vs DE article
    "da",  # IT/PT/ES vs DE
    "per",  # IT/Latin vs EN
    "con",  # IT/ES/PT vs EN "con"
    "name",  # EN vs DE (Name)
    "type",  # EN vs DE (Typ)
    "profil",  # FR/DE vs EN
    "par",  # FR vs ES
    "qui",  # FR vs IT
    "non",  # FR/IT universel
    "il",  # FR pronoun vs IT article
    "a",  # IT/FR/EN préposition
    "una",  # IT/ES article
    "uno",  # IT/ES article
    "date",  # EN vs FR/DE/IT
    "total",  # EN/FR/DE
}

# ═══════════════════════════════════════════════════════════════════════
# PATTERNS DE CARACTÈRES PAR LANGUE
# ═══════════════════════════════════════════════════════════════════════


def has_arabic_chars(text):
    """Détecte les caractères arabes."""
    return bool(re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text))


def has_cjk_chars(text):
    """Détecte les caractères CJK."""
    return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))


def has_cyrillic_chars(text):
    """Détecte les caractères cyrilliques."""
    return bool(re.search(r"[\u0400-\u04FF]", text))


def has_german_chars(text):
    """Détecte les umlauts allemands (ä, ö, ü, ß) et ligatures."""
    return bool(re.search(r"[äöüßÄÖÜ]", text))


def has_french_accent_chars(text):
    """Détecte les accents spécifiquement français (é, è, ê, ë, ù, û, ç, à, â, î, ô)."""
    return bool(re.search(r"[éèêëùûçàâîôÉÈÊËÙÛÇÀÂÎÔ]", text))


def has_czech_diacritics(text):
    """Détecte les diacritiques tchèques spécifiques (á, é, í, ó, ú, ý, č, ď, ě, ň, ř, š, ť, ů, ž)."""
    return bool(re.search(r"[áéíóúýčďěňřšťůžÁÉÍÓÚÝČĎĚŇŘŠŤŮŽ]", text))


def has_slovak_diacritics(text):
    """Détecte les diacritiques slovaques (comme tchèque + ĺ, ŕ, ô, ä)."""
    return bool(re.search(r"[ĺŕôäĹŔÔÄ]", text))


def has_italian_chars(text):
    """Détecte les accents/graves italiens (à, è, é, ì, ò, ù)."""
    return bool(re.search(r"[àèìòùÀÈÌÒÙ]", text))


# ═══════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════


def tokenize(text):
    """Tokenize le texte en mots, en ignorant la ponctuation, les balises HTML et les variables de template."""
    if not text:
        return []
    # Supprimer les balises HTML
    text = re.sub(r"<[^>]+>", " ", text)
    # Supprimer les variables de template {{...}}
    text = re.sub(r"\{\{[^}]+\}\}", " ", text)
    # Conserver les apostrophes internes (ex: l'homme, d'accord)
    # mais séparer les ponctuations de fin
    words = re.findall(r"[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u0600-\u06FF']+|[^\s]", text)
    return [w for w in words if re.search(r"[a-zA-Z\u00C0-\u024F]", w)]


def is_tech_term(word):
    """Vérifie si un mot est un terme technique à ignorer."""
    w = word.lower().strip("'\"-.,;:!?()[]{}")
    return w in TECH_TERMS


def is_ambiguous(word):
    """Vérifie si un mot est ambigu (existe dans plusieurs langues)."""
    w = word.lower().strip("'\"-.,;:!?()[]{}")
    return w in AMBIGUOUS_WORDS


def normalize_word(word):
    """Normalise un mot pour comparaison."""
    return word.lower().strip("'\"-.,;:!?()[]{}").strip()


# ═══════════════════════════════════════════════════════════════════════
# ANALYSE PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════


def detect_foreign_words(key, value, target_lang, source_value=None):
    """
    Détecte les mots étrangers dans une valeur traduite.
    Retourne une liste de problèmes : [(severity, foreign_lang, foreign_words, explanation)]
    """
    if not value or not value.strip():
        return []

    problems = []
    target_lang_data = FOREIGN_WORDS_FOR_LANG.get(target_lang, {})

    # ─── Vérification des caractères inattendus ───
    char_issues = detect_charset_issues(value, target_lang, key)
    problems.extend(char_issues)

    # ─── Détection de mots étrangers ───
    tokens = tokenize(value)
    if not tokens:
        return problems

    # Vérification spéciale pour l'arabe : texte latin dans un contexte arabe
    if target_lang == "ar":
        latin_tokens = [t for t in tokens if re.search(r"[a-zA-Z]", t)]
        if latin_tokens:
            # Vérifier si les mots latins sont des termes techniques
            non_tech_latin = []
            for t in latin_tokens:
                norm = normalize_word(t)
                if norm and norm not in TECH_TERMS and len(norm) > 1:
                    non_tech_latin.append(t)
            if non_tech_latin:
                severity = "CRITIQUE" if len(non_tech_latin) >= 3 else "MODÉRÉ"
                problems.append(
                    (
                        severity,
                        "latin",
                        non_tech_latin,
                        f"Mots en script latin dans un texte arabe : {', '.join(non_tech_latin)}",
                    )
                )
        return (
            problems  # Pour l'arabe, l'analyse mot-par-mot latin n'est pas pertinente
        )

    # Pour les langues latines, vérifier chaque mot
    foreign_detected = defaultdict(list)  # lang -> [word_list]

    for token in tokens:
        norm = normalize_word(token)
        if not norm or len(norm) <= 1:
            continue
        if is_tech_term(token):
            continue
        if norm in TECH_TERMS:
            continue

        # Vérifier si le mot correspond à une langue étrangère
        for foreign_lang, word_set in target_lang_data.items():
            if norm in word_set:
                # Vérifier si ce mot est ambigu
                if norm in AMBIGUOUS_WORDS:
                    # Les mots ambigus sont marqués mineurs
                    foreign_detected[foreign_lang].append((token, "MINEUR"))
                else:
                    # Les mots clairement étrangers sont marqués modérés
                    foreign_detected[foreign_lang].append((token, "MODÉRÉ"))

    # ─── Vérification : texte non traduit (phrase entière en anglais) ───
    if source_value and len(tokens) >= 3:
        en_word_count = 0
        for token in tokens:
            norm = normalize_word(token)
            if (
                norm in ENGLISH_WORDS
                and not is_tech_term(token)
                and norm not in AMBIGUOUS_WORDS
            ):
                en_word_count += 1

        # Si plus de 60% des mots sont des mots anglais forts, c'est probablement
        # un texte non traduit
        ratio = en_word_count / len(tokens) if len(tokens) > 0 else 0
        if ratio >= 0.6 and target_lang != "en":
            # Vérifier que ce n'est pas juste des mots courts
            en_words_found = [
                normalize_word(t)
                for t in tokens
                if normalize_word(t) in ENGLISH_WORDS
                and not is_tech_term(t)
                and normalize_word(t) not in AMBIGUOUS_WORDS
            ]
            problems.append(
                (
                    "CRITIQUE",
                    "en",
                    en_words_found,
                    f"Texte probablement non traduit (ratio anglais {ratio:.0%}) : « {value} »",
                )
            )

    # ─── Vérification : phrase entière dans une autre langue (non anglais) ───
    if len(tokens) >= 3:
        for foreign_lang, word_set in target_lang_data.items():
            if foreign_lang == "en":
                continue  # Déjà géré ci-dessus
            matches = 0
            matched_words = []
            for token in tokens:
                norm = normalize_word(token)
                if (
                    norm in word_set
                    and not is_tech_term(token)
                    and norm not in AMBIGUOUS_WORDS
                ):
                    matches += 1
                    matched_words.append(token)
            ratio = matches / len(tokens) if len(tokens) > 0 else 0
            if ratio >= 0.4 and matches >= 3:
                problems.append(
                    (
                        "CRITIQUE",
                        foreign_lang,
                        matched_words,
                        f"Phrase possiblement en {foreign_lang.upper()} ({ratio:.0%} des mots) : « {value} »",
                    )
                )

    # ─── Ajouter les mots étrangers isolés ───
    for foreign_lang, words_with_severity in foreign_detected.items():
        if foreign_lang == "en" and target_lang != "en":
            # Ne pas double-signaler si on a déjà signalé comme texte non traduit
            has_critique = any(p[0] == "CRITIQUE" and p[1] == "en" for p in problems)
            if has_critique:
                continue
        for word, severity in words_with_severity:
            # Ne pas signaler les mots ambigus isolés (seulement en contexte)
            if severity == "MINEUR":
                # Ne signaler que si le mot ambigu apparaît dans un contexte
                # qui renforce la suspicion
                continue  # Les mots ambigus isolés sont ignorés

    # ─── Vérification spéciale : mots qui sont identiques à la source EN ───
    if source_value:
        source_tokens = set(normalize_word(t) for t in tokenize(source_value))
        value_tokens = set(normalize_word(t) for t in tokenize(value))
        # Chercher des mots anglais communs qui n'ont pas été traduits
        untranslated = []
        for t in tokens:
            norm = normalize_word(t)
            # Dictionnaire des mots de la langue cible pour éviter les faux positifs
            target_native_words = {
                "cs": CZECH_WORDS,
                "de": GERMAN_WORDS,
                "fr": FRENCH_WORDS,
                "it": ITALIAN_WORDS,
                "sk": SLOVAK_WORDS,
            }.get(target_lang, set())
            if (
                norm in source_tokens
                and norm in ENGLISH_WORDS
                and len(norm) >= 4  # Mots de 4+ lettres pour réduire les faux positifs
                and not is_tech_term(norm)
                and norm not in AMBIGUOUS_WORDS
                and norm not in target_native_words
            ):
                untranslated.append(t)
        if untranslated:
            severity = "MODÉRÉ" if len(untranslated) == 1 else "CRITIQUE"
            # Ne pas dupliquer avec le signalement "texte non traduit"
            has_full_en = any(p[0] == "CRITIQUE" and p[1] == "en" for p in problems)
            if not has_full_en:
                problems.append(
                    (
                        severity,
                        "en",
                        untranslated,
                        f"Mots probablement non traduits de l'anglais : {', '.join(untranslated)}",
                    )
                )

    return problems


def detect_charset_issues(value, target_lang, key):
    """Détecte les caractères qui ne devraient pas être dans la langue cible."""
    issues = []

    if target_lang == "ar":
        # L'arabe ne devrait pas contenir de texte latin (sauf termes tech)
        if re.search(r"[a-zA-Z]{3,}", value):
            latin_words = re.findall(r"[a-zA-Z]+", value)
            non_tech = [
                w for w in latin_words if w.lower() not in TECH_TERMS and len(w) >= 3
            ]
            if non_tech:
                issues.append(
                    (
                        "MODÉRÉ",
                        "latin",
                        non_tech,
                        f"Caractères latins dans un texte arabe : {', '.join(non_tech)}",
                    )
                )

    elif target_lang in ("cs", "sk"):
        # Le tchèque n'utilise pas ä, ö, ü, ß - le slovaque utilise ä légitimement
        # Signalons ö, ü, ß comme allemands, et ä seulement pour le tchèque
        if target_lang == "sk" and re.search(r"[öüßÖÜ]", value):
            umlaut_words = [w for w in value.split() if re.search(r"[öüßÖÜ]", w)]
            issues.append(
                (
                    "MODÉRÉ",
                    "de",
                    umlaut_words,
                    f"Umlauts allemands (ö, ü, ß) détectés en slovaque : {', '.join(umlaut_words)}",
                )
            )
        elif target_lang == "cs" and has_german_chars(value):
            umlaut_words = [w for w in value.split() if re.search(r"[äöüßÄÖÜ]", w)]
            issues.append(
                (
                    "MODÉRÉ",
                    "de",
                    umlaut_words,
                    f"Umlauts allemands (ä, ö, ü, ß) détectés en tchèque : {', '.join(umlaut_words)}",
                )
            )
        # Pas de caractères arabes
        if has_arabic_chars(value):
            issues.append(
                (
                    "CRITIQUE",
                    "ar",
                    [],
                    f"Caractères arabes détectés dans un texte {target_lang}",
                )
            )

    elif target_lang == "de":
        # L'allemand ne devrait pas avoir d'accents français typiques (é, è, ù, ç)
        # sauf dans les emprunts. Mais è et ç sont rares en allemand.
        if re.search(r"[èùçêîô]", value):
            fr_chars = [w for w in value.split() if re.search(r"[èùçêîô]", w)]
            issues.append(
                (
                    "MINEUR",
                    "fr",
                    fr_chars,
                    f"Accents français atypiques en allemand (è, ù, ç) : {', '.join(fr_chars)}",
                )
            )
        if has_arabic_chars(value):
            issues.append(
                (
                    "CRITIQUE",
                    "ar",
                    [],
                    f"Caractères arabes détectés dans un texte allemand",
                )
            )

    elif target_lang == "fr":
        # Le français ne devrait pas avoir d'umlauts allemands
        if has_german_chars(value):
            umlaut_words = [w for w in value.split() if re.search(r"[äöüßÄÖÜ]", w)]
            issues.append(
                (
                    "MODÉRÉ",
                    "de",
                    umlaut_words,
                    f"Umlauts allemands détectés en français : {', '.join(umlaut_words)}",
                )
            )
        if has_arabic_chars(value):
            issues.append(
                (
                    "CRITIQUE",
                    "ar",
                    [],
                    f"Caractères arabes détectés dans un texte français",
                )
            )

    elif target_lang == "it":
        # L'italien ne devrait pas avoir d'umlauts allemands
        if has_german_chars(value):
            umlaut_words = [w for w in value.split() if re.search(r"[äöüßÄÖÜ]", w)]
            issues.append(
                (
                    "MODÉRÉ",
                    "de",
                    umlaut_words,
                    f"Umlauts allemands détectés en italien : {', '.join(umlaut_words)}",
                )
            )
        if has_arabic_chars(value):
            issues.append(
                (
                    "CRITIQUE",
                    "ar",
                    [],
                    f"Caractères arabes détectés dans un texte italien",
                )
            )

    return issues


def analyze_file(filepath, target_lang, source_data):
    """Analyse un fichier de traduction complet."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = {
        "CRITIQUE": [],
        "MODÉRÉ": [],
        "MINEUR": [],
    }

    stats = {
        "total_keys": len(data),
        "empty_keys": 0,
        "issues_found": 0,
        "by_foreign_lang": defaultdict(int),
    }

    for key, value in data.items():
        if not value or not value.strip():
            stats["empty_keys"] += 1
            continue

        source_value = source_data.get(key, "")
        problems = detect_foreign_words(key, value, target_lang, source_value)

        for severity, foreign_lang, foreign_words, explanation in problems:
            results[severity].append(
                {
                    "key": key,
                    "value": value,
                    "source": source_value,
                    "foreign_lang": foreign_lang,
                    "foreign_words": foreign_words,
                    "explanation": explanation,
                }
            )
            stats["issues_found"] += 1
            stats["by_foreign_lang"][foreign_lang] += 1

    return results, stats


# ═══════════════════════════════════════════════════════════════════════
# AFFICHAGE DES RÉSULTATS
# ═══════════════════════════════════════════════════════════════════════

SEVERITY_ICONS = {
    "CRITIQUE": "🔴",
    "MODÉRÉ": "🟡",
    "MINEUR": "🟢",
}

SEVERITY_ORDER = {"CRITIQUE": 0, "MODÉRÉ": 1, "MINEUR": 2}


def print_results(filename, lang_label, results, stats):
    """Affiche les résultats pour un fichier."""
    print(f"\n{'═' * 80}")
    print(f"📁 {filename} → {lang_label}")
    print(f"{'═' * 80}")
    print(f"  Clés totales : {stats['total_keys']}")
    print(f"  Clés vides   : {stats['empty_keys']}")
    print(f"  Problèmes    : {stats['issues_found']}")

    if stats["by_foreign_lang"]:
        print(f"\n  📊 Par langue étrangère détectée :")
        for fl, count in sorted(stats["by_foreign_lang"].items(), key=lambda x: -x[1]):
            lang_names = {
                "en": "Anglais",
                "fr": "Français",
                "de": "Allemand",
                "it": "Italien",
                "cs": "Tchèque",
                "sk": "Slovaque",
                "ar": "Arabe",
                "latin": "Latin",
            }
            print(f"     • {lang_names.get(fl, fl.upper())} : {count} problème(s)")

    for severity in ["CRITIQUE", "MODÉRÉ", "MINEUR"]:
        items = results[severity]
        if not items:
            continue

        icon = SEVERITY_ICONS[severity]
        print(f"\n  {icon} {severity} ({len(items)} occurrence(s))")
        print(f"  {'─' * 76}")

        # Limiter l'affichage à 20 exemples par sévérité
        displayed = items[:20]
        for i, item in enumerate(displayed, 1):
            print(f"\n  {i}. Clé : `{item['key']}`")
            print(
                f"     Valeur      : « {item['value'][:100]}{'...' if len(item['value']) > 100 else ''} »"
            )
            if item["source"]:
                src_display = item["source"][:80] + (
                    "..." if len(item["source"]) > 80 else ""
                )
                print(f"     Source (EN) : « {src_display} »")
            lang_names = {
                "en": "Anglais",
                "fr": "Français",
                "de": "Allemand",
                "it": "Italien",
                "cs": "Tchèque",
                "sk": "Slovaque",
                "ar": "Arabe",
                "latin": "Latin",
            }
            print(
                f"     Langue étrangère : {lang_names.get(item['foreign_lang'], item['foreign_lang'].upper())}"
            )
            if item["foreign_words"]:
                words_display = ", ".join(str(w) for w in item["foreign_words"][:10])
                print(f"     Mots suspects   : {words_display}")
            print(f"     ℹ️  {item['explanation']}")

        if len(items) > 20:
            print(
                f"\n  ... et {len(items) - 20} autres problèmes {severity.lower()}s (non affichés)"
            )


def print_summary(all_stats, all_results):
    """Affiche un résumé global."""
    print(f"\n\n{'═' * 80}")
    print(f"📋 RÉSUMÉ GLOBAL")
    print(f"{'═' * 80}")

    total_issues = 0
    total_critique = 0
    total_moderer = 0
    total_mineur = 0

    print(
        f"\n  {'Fichier':<35} {'🔴 Crit':>8} {'🟡 Mod':>8} {'🟢 Min':>8} {'Total':>8}"
    )
    print(f"  {'─' * 70}")

    for filename, info in FILES.items():
        results = all_results[filename]
        stats = all_stats[filename]
        c = len(results["CRITIQUE"])
        m = len(results["MODÉRÉ"])
        mi = len(results["MINEUR"])
        t = c + m + mi
        total_critique += c
        total_moderer += m
        total_mineur += mi
        total_issues += t
        label = info["label"]
        print(f"  {label:<35} {c:>8} {m:>8} {mi:>8} {t:>8}")

    print(f"  {'─' * 70}")
    print(
        f"  {'TOTAL':<35} {total_critique:>8} {total_moderer:>8} {total_mineur:>8} {total_issues:>8}"
    )

    # Top des problèmes par langue étrangère
    print(f"\n  📊 Problèmes par langue étrangère détectée :")
    global_foreign = defaultdict(int)
    for filename in FILES:
        for fl, count in all_stats[filename]["by_foreign_lang"].items():
            global_foreign[fl] += count
    lang_names = {
        "en": "Anglais",
        "fr": "Français",
        "de": "Allemand",
        "it": "Italien",
        "cs": "Tchèque",
        "sk": "Slovaque",
        "ar": "Arabe",
        "latin": "Latin",
    }
    for fl, count in sorted(global_foreign.items(), key=lambda x: -x[1]):
        print(f"     • {lang_names.get(fl, fl.upper())} : {count}")


# ═══════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════


def main():
    # Charger le fichier source anglais
    print("Chargement du fichier source anglais...")
    try:
        with open(SOURCE_FILE, "r", encoding="utf-8") as f:
            source_data = json.load(f)
        print(f"  ✓ {len(source_data)} clés chargées depuis la source EN")
    except Exception as e:
        print(f"  ⚠ Erreur lors du chargement de la source EN : {e}")
        source_data = {}

    all_results = {}
    all_stats = {}

    for filename, info in FILES.items():
        filepath = EXPORT_DIR / filename
        target_lang = info["lang"]
        label = info["label"]

        print(f"\nAnalyse de {filename} ({label})...")
        try:
            results, stats = analyze_file(filepath, target_lang, source_data)
            all_results[filename] = results
            all_stats[filename] = stats
            print(f"  ✓ {stats['issues_found']} problème(s) détecté(s)")
        except Exception as e:
            print(f"  ✗ Erreur : {e}")
            all_results[filename] = {"CRITIQUE": [], "MODÉRÉ": [], "MINEUR": []}
            all_stats[filename] = {
                "total_keys": 0,
                "empty_keys": 0,
                "issues_found": 0,
                "by_foreign_lang": defaultdict(int),
            }

    # Afficher les résultats détaillés
    for filename, info in FILES.items():
        print_results(
            filename, info["label"], all_results[filename], all_stats[filename]
        )

    # Afficher le résumé global
    print_summary(all_stats, all_results)

    # Sauvegarder les résultats en JSON pour analyse ultérieure
    output_file = BASE_DIR / "translation_analysis_results.json"
    output_data = {}
    for filename, info in FILES.items():
        results = all_results[filename]
        stats = all_stats[filename]
        output_data[filename] = {
            "target_lang": info["lang"],
            "label": info["label"],
            "stats": {
                k: (dict(v) if isinstance(v, defaultdict) else v)
                for k, v in stats.items()
            },
            "critique": results["CRITIQUE"],
            "modere": results["MODÉRÉ"],
            "mineur": results["MINEUR"],
        }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n\n💾 Résultats sauvegardés dans : {output_file}")


if __name__ == "__main__":
    main()
