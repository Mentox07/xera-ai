from .common import COMMON_RULES

AGENT = {
    "id": "web_search",
    "name": "Web Search Agent",
    "icon": "🌐",
    "color": "#0ea5e9",
    "brain": "big",
    "tab": "both",
    "description": "Schnelle Web-Suche mit Quellen-Links — direkte Antworten aus aktuellen Web-Ergebnissen.",
    "keywords": [
        # Direct search intent — DE
        "suche im web", "suche online", "google das", "such mal", "im internet suchen",
        "such im internet", "was steht im web", "online suchen", "web suche",
        "suche nach", "such nach", "finde heraus was",
        # Time-sensitive / live data — DE
        "aktuelle nachrichten", "neueste news", "was ist heute", "was passiert gerade",
        "aktueller kurs", "aktueller preis", "aktuelle version", "neueste version",
        "wetter", "news", "nachrichten", "aktuelle infos",
        "morgen", "heute abend", "heute nacht", "jetzt gerade", "anstehend",
        "nächste spiele", "nächsten spiele", "nächste matches", "nächsten matches",
        "spielplan", "spieltag", "tabelle", "ergebnis", "live score",
        # Sports / events — DE
        "wm", "em", "champions league", "bundesliga", "weltmeisterschaft",
        "match", "matches", "spiel heute", "spiel morgen",
        # Direct search intent — EN
        "search the web", "google it", "look it up", "find online", "search online",
        "search for", "look up", "find me",
        # Time-sensitive / live data — EN
        "current news", "latest news", "what's happening", "current price",
        "current version", "latest version", "weather", "what is the latest",
        "tomorrow", "tonight", "right now", "upcoming", "schedule",
        "next games", "next matches", "standings", "live results",
        # Sports — EN
        "world cup", "champions league", "premier league", "match today", "match tomorrow",
    ],
    "tools": ["web_search", "delegate_to_agent"],
    "system_prompt": """Du bist der Web Search Agent — schnell, präzise, quellenbasiert.

DEIN PRINZIP: 1-3 gezielte Suchanfragen, dann direkte Antwort mit Quellen.

ABLAUF:
1. Frage analysieren: Was genau sucht der User?
2. 1-3 Suchanfragen absetzen (nicht mehr — Geschwindigkeit ist Priorität)
3. Ergebnisse zusammenfassen: Fakten, keine Meinungen
4. Quellen IMMER am Ende auflisten

SUCHSTRATEGIE — So formulierst du Suchanfragen:
- Kurz und präzise: "arch linux gaming controller 2025" statt lange Sätze
- Englisch oft besser für technische Themen
- Für aktuelle Infos: Jahr dazuhängen ("...2025")
- Für Preise/Kurse: "current price [produkt]"
- Für Nachrichten: "[thema] news today"

AUSGABEFORMAT:
**[Direkte Antwort in 1-3 Sätzen]**

Details:
- [Kernfakt 1]
- [Kernfakt 2]
- [Kernfakt 3]

Quellen:
- [URL 1]
- [URL 2]

GRENZEN:
- Tiefe Analyse / Vergleiche → delegate_to_agent("research", ...)
- Code / Scripts → delegate_to_agent("code", ...)
- Homelab-Infos → delegate_to_agent("knowledge", ...)

WICHTIG: Niemals Information erfinden wenn Suche nichts findet — sag es klar.
""" + COMMON_RULES,
}
