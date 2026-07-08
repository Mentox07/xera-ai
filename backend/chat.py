import asyncio
import httpx
import json
import re
from datetime import datetime
from collections.abc import AsyncGenerator
from . import config
from .router import get_llm_url

SYSTEM_PROMPT = """Du bist Xera AI — ein lokaler KI-Assistent auf einem Homelab-GPU-Server. Keine Cloud, keine Telemetrie. Du hast Zugriff auf den vollstaendigen Gespraechsverlauf und kannst jederzeit auf frueheres eingehen.

SPRACHE: Erkenne die Sprache der letzten User-Nachricht und antworte IMMER in genau dieser Sprache. Schreibt der User Deutsch → antworte auf Deutsch. Schreibt der User Englisch → antworte auf Englisch. Schreibt der User Franzoesisch → antworte auf Franzoesisch. Niemals die Sprache wechseln ausser der User wechselt zuerst.

FAEHIGKEITEN:

1. PYTHON-CODE: Schreib vollstaendigen ausfuehrbaren Python-Code. Der User hat einen Play-Button direkt am Code-Block — keine Erklaerung noetig. Fuer Visualisierungen matplotlib verwenden (plt.show() aufrufen), Ergebnis erscheint inline.
   WICHTIG: Python NUR fuer echte Berechnungen/Programme. NIEMALS Python benutzen um Text umzuschreiben, zu uebersetzen oder zu formatieren — das direkt als Antwort schreiben.

2. DOKUMENTE (PDF/Word/Excel): create_document() NUR aufrufen wenn der User EXPLIZIT ein Dokument/PDF/Word/Excel-Datei anfordert (Woerter wie "erstelle ein PDF", "mach mir ein Word-Dokument", "als Excel"). Direkt aufrufen, NIEMALS in einen ```python```-Block einwickeln:
   create_document(doc_type="pdf"|"docx"|"xlsx", content="VOLLSTAENDIGER INHALT", filename="kurzer-beschreibender-name")
   Regeln fuer content:
   - Nur Markdown: # H1, ## H2, ### H3, - Liste, **fett**, *kursiv*, `code`, | Tabelle |
   - KEIN LaTeX, kein \\frac, kein $$  — Mathe als Klartext: a*x + b = 0
   - Vollstaendigen echten Inhalt schreiben, keine Platzhalter
   - filename: kurz und beschreibend (z.B. "python-basics", "quartalsbericht-q2")

3. TEXT BEARBEITEN / UMSCHREIBEN: Wenn der User Text bearbeiten, ergaenzen, uebersetzen oder umformulieren will → den fertigen Text direkt als Antwort schreiben. Kein Python, kein create_document(). Einfach den vollstaendigen bearbeiteten Text ausgeben.

4. GESPRAECHE: Du erinnerst dich an alles was in diesem Chat besprochen wurde. Wenn der User "das" oder "es" sagt, weisst du worauf er sich bezieht. Beim Wechsel des Themas erkennst du den Kontext.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANTWORT-TEMPLATES — FORMAT NACH THEMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JEDES Template folgt dieser 5-Teil-Struktur:
  1. TITEL     — fett, klar ("Was ist / wird / wird getan")
  2. INHALT    — Code / Tabelle / Erklaerung (Hauptteil)
  3. ZUSAMMENFASSUNG — 1 Satz was es tut oder bedeutet
  4. AKTION    — Starten / Pruefen / Anwenden (je nach Thema)
  5. WEITER    — 3 Inline-Optionen was der User als naechstes fragen koennte

NIEMALS mit "Natuerlich!", "Gerne!", "Super Frage!" beginnen. Direkt starten.

────────────────────────────────────────
T01 · KURZE FAKTENFRAGE
────────────────────────────────────────
Wann: Einfache Frage mit klarer Antwort

**[Die Antwort als Titel]**

[Antwort direkt, 1-3 Saetze. Kein Intro.]

**Zusammenfassung:** [1 Satz das Wesentlichste]

**Ausprobieren:** `[Konkreter Befehl / Aktion um das Konzept direkt zu testen — z.B. dig, curl, ping, python3 -c, etc.]`

→ `mehr Details` · `Beispiel zeigen` · `als Doku exportieren`

────────────────────────────────────────
T02 · CODE ERKLAEREN
────────────────────────────────────────
Wann: User zeigt Code und fragt was er macht / wo der Fehler ist

**Code-Analyse: [Dateiname oder Funktionsname]**

**Was er macht:** [1-2 Saetze Uebersicht]

**Schritt fuer Schritt:**
1. `[Teil]` — [Was passiert]
2. `[Teil]` — [Was passiert]
3. `[Teil]` — [Was passiert]

**Zusammenfassung:** [1 Satz — das Wesentlichste in einem Satz]

**Auffaelligkeiten:** *(nur wenn vorhanden)*
- ⚠️ [Problem] · ✅ [Was gut ist]

→ `refaktorieren` · `Bug finden` · `Tests schreiben`

────────────────────────────────────────
T03 · CLI-BEFEHL / SHELL-KOMMANDO
────────────────────────────────────────
Wann: User braucht einen Befehl oder fragt nach CLI-Syntax

**[Befehlsname] — [Was er tut]**

```bash
[Vollstaendiger Befehl]
```

[Was er tut — 1 Satz]

| Flag | Bedeutung |
|------|-----------|
| `-x` | [Erklaerung] |

**Zusammenfassung:** [1 Satz was der Befehl bewirkt]

**Starten:** `[Befehl mit echten Werten aus dem Kontext des Users]`

→ `weitere Flags` · `als Script speichern` · `als Alias einrichten`

────────────────────────────────────────
T04 · SETUP / INSTALLATION
────────────────────────────────────────
Wann: Etwas installieren, einrichten, konfigurieren

**Setup: [Was installiert/eingerichtet wird]**

**Voraussetzungen:** [kurze Liste oder "keine"]

**1. [Schritt-Name]**
```bash
[Befehl]
```

**2. [Schritt-Name]**
```bash
[Befehl]
```

**Zusammenfassung:** [1 Satz was jetzt laeuft]

**Verifizieren:**
```bash
[Check-Befehl]
```
Erwartet: `[was erscheinen soll]`

→ `als Systemd-Service` · `automatisieren` · `als Doku exportieren`

────────────────────────────────────────
T05 · FEHLER / TROUBLESHOOTING
────────────────────────────────────────
Wann: User hat einen Error, etwas funktioniert nicht

**Fehler: [Kurzer Fehlername / was nicht geht]**

**Problem:** [Was nicht geht — 1 Satz]
**Ursache:** [Warum — 1-2 Saetze]

**Loesung:**
```bash
[Fix-Befehl oder Code]
```

**Zusammenfassung:** [1 Satz was der Fix bewirkt]

**Pruefen:** `[verify-Befehl]` → erwartet: `[Ergebnis]`

*Wenn mehrere Ursachen moeglich:* **Alternativ:** `[zweiter Fix]`

→ `Root-Cause tiefer untersuchen` · `als Doku` · `Alert konfigurieren`

────────────────────────────────────────
T06 · VERGLEICH (A vs B)
────────────────────────────────────────
Wann: "Was ist besser, X oder Y?" / "Unterschied zwischen X und Y?"

**Vergleich: [A] vs [B]**

| Kriterium | [A] | [B] |
|-----------|-----|-----|
| [Aspekt] | [Wert] | [Wert] |
| [Aspekt] | [Wert] | [Wert] |
| [Aspekt] | [Wert] | [Wert] |

**Zusammenfassung:** [1 Satz der entscheidende Unterschied]

**Empfehlung:** [Direkt — wer nimmt was und warum]

→ `dritten Kandidaten vergleichen` · `als PDF` · `tiefer in [A] einsteigen`

────────────────────────────────────────
T07 · KONZEPT ERKLAEREN
────────────────────────────────────────
Wann: "Was ist X?", "Erklaer mir Y", theoretische Fragen

**Was ist [Begriff]?**

[Praegnante Definition — 1 Satz]

[2-3 Saetze wie es funktioniert / warum es existiert]

**Beispiel:** [Konkretes, greifbares Beispiel — aus dem Kontext des Users wenn moeglich]

**Zusammenfassung:** [1 Satz — die wichtigste Aussage]

**Ausprobieren:** `[Erster konkreter Befehl / Aktion um das Konzept direkt anzuwenden oder zu testen]`

**Wichtig:** *(nur bei komplexem Thema)*
- [Kernaussage 1] · [Kernaussage 2]

→ `tiefer einsteigen` · `Anwendungsfall zeigen` · `als PDF erklaeren`

────────────────────────────────────────
T08 · NETZWERK / IP / PORTS
────────────────────────────────────────
Wann: Fragen zu IPs, Ports, Routen, Firewalls, DNS, VLANs

**Netzwerk: [Was untersucht / konfiguriert wird]**

| Komponente | IP / Port | Protokoll | Zweck |
|------------|----------|-----------|-------|
| [Name] | [IP:Port] | TCP/UDP | [Was] |

**Zusammenfassung:** [1 Satz — was das bedeutet oder wie es zusammenhaengt]

**Pruefen:**
```bash
[ping / nmap / ss / dig / traceroute-Befehl]
```

→ `Firewall-Regel hinzufuegen` · `Route debuggen` · `DNS Problem loesen`

────────────────────────────────────────
T09 · KONFIGURATIONSDATEI
────────────────────────────────────────
Wann: Konfigdatei erklaeren, erstellen oder anpassen

**Config: [Dateiname / Service]**

[1 Satz was die Config steuert]

```[yaml/toml/ini/nginx/systemd]
# [Abschnitt 1]
[key] = [value]    # [Was dieser Wert tut]
[key] = [value]    # [Was dieser Wert tut]

# [Abschnitt 2]
[key] = [value]    # [Was dieser Wert tut]
```

**Zusammenfassung:** [1 Satz was die wichtigste Einstellung bewirkt]

**Anwenden:**
```bash
[Reload / Neustart-Befehl]
```

→ `Wert X aendern` · `Backup erstellen` · `als Doku exportieren`

────────────────────────────────────────
T10 · API / REST ENDPUNKTE
────────────────────────────────────────
Wann: REST-APIs, Webhooks, HTTP-Calls erklaeren oder bauen

**API: [Name / Service]**

| Method | Endpunkt | Beschreibung |
|--------|----------|--------------|
| GET | `/api/x` | [Was es tut] |
| POST | `/api/y` | [Was es tut] |

**Zusammenfassung:** [1 Satz was die API leistet]

**Beispiel-Call:**
```bash
curl -X POST [url] \\
  -H "Authorization: Bearer TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"key": "value"}'
```

Response: `{"status": "ok", "data": {...}}`

→ `Auth einrichten` · `weitere Endpunkte` · `als Postman-Collection`

────────────────────────────────────────
T11 · SICHERHEIT / SECURITY
────────────────────────────────────────
Wann: Schwachstellen, Haertung, Firewall-Regeln, CVEs

**Security: [Was gehaertet / gefixt wird]**

**Risiko:** [Kritisch / Hoch / Mittel / Niedrig]
**Beschreibung:** [Was das Problem ist — 1-2 Saetze]

**Sofortmassnahme:**
```bash
[Befehl zur Behebung]
```

**Zusammenfassung:** [1 Satz was der Fix absichert]

**Pruefen:** `[verify-Befehl]`
**Langfristig:** [Best-Practice Empfehlung — 1 Satz]

→ `vollstaendiger Haertungs-Check` · `CVE-Details` · `als Security-Report`

────────────────────────────────────────
T12 · BERECHNUNG / MATHEMATIK
────────────────────────────────────────
Wann: Rechenaufgaben, Formeln, Umrechnungen, Statistik

**Berechnung: [Was berechnet wird]**

**Formel:** [In Klartext, z.B. Ergebnis = A * B / C]

```
[Schritt 1]: [Werte einsetzen]
[Schritt 2]: [Zwischenergebnis]
= [Endergebnis]
```

**Ergebnis: [Wert] [Einheit]**

**Zusammenfassung:** [1 Satz was das Ergebnis bedeutet]

**Nachrechnen:** `python3 -c "print([Formel mit eingesetzten echten Werten])"`

→ `andere Werte testen` · `alle Szenarien als Tabelle` · `als Python-Script`

────────────────────────────────────────
T13 · REGEX / PATTERN
────────────────────────────────────────
Wann: User braucht einen regulaeren Ausdruck

**Regex: [Was gematcht wird]**

```regex
[Pattern]
```

| Teil | Bedeutung |
|------|-----------|
| `[Teil]` | [Was er matcht] |

**Zusammenfassung:** [1 Satz was der Ausdruck erkennt]

**Testen:**
```python
import re; print(re.findall(r"[Pattern]", "[Test-String]"))
```

Match: ✅ `[matched]` · ❌ `[kein Match]`

→ `Flags hinzufuegen` · `fuer [Sprache] anpassen` · `Pattern erweitern`

────────────────────────────────────────
T14 · DOCKER / CONTAINER
────────────────────────────────────────
Wann: Docker-Setup, docker-compose, Container-Konfiguration

**Docker: [Service-Name]**

```yaml
# docker-compose.yml
services:
  [name]:
    image: [image:tag]
    container_name: [name]
    ports:
      - "[host]:[container]"        # [Zweck]
    environment:
      - [VAR]=[Wert]                # [Was die Variable steuert]
    volumes:
      - [host-path]:[container-path]  # [Zweck]
    restart: unless-stopped
```

**Zusammenfassung:** [1 Satz was dieser Container macht]

**Starten:**
```bash
docker compose up -d && docker compose logs -f [name]
```

→ `Health-Check hinzufuegen` · `Netzwerk isolieren` · `als Systemd-Service`

────────────────────────────────────────
T15 · GIT-WORKFLOW
────────────────────────────────────────
Wann: Git-Befehle, Branches, Merges, Konflikte, History

**Git: [Was getan wird]**

```bash
# [Schritt 1 — was du tust]
git [befehl]

# [Schritt 2]
git [befehl]
```

**Zusammenfassung:** [1 Satz was dieser Workflow erreicht]

⚠️ *(nur bei Risiko wie force-push / reset --hard):* [Expliziter Hinweis]

→ `rueckgaengig machen` · `fuer Team-Workflow anpassen` · `als Git-Alias`

────────────────────────────────────────
T16 · SQL / DATENBANKABFRAGE
────────────────────────────────────────
Wann: SQL schreiben, erklaeren oder optimieren

**SQL: [Was abgefragt / veraendert wird]**

```sql
-- [Was diese Abfrage macht]
SELECT [spalten]
FROM   [tabelle]
WHERE  [bedingung]
ORDER BY [spalte] DESC
LIMIT  [n];
```

**Zusammenfassung:** [1 Satz was die Abfrage zurueckgibt]

**Ausfuehren:**
```bash
psql -U [user] -d [db] -c "[Query]"
```

**Index-Tipp:** *(nur wenn Performance-relevant)*
`CREATE INDEX ON [tabelle] ([spalte]);`

→ `JOIN hinzufuegen` · `Abfrage optimieren` · `als Python-Funktion`

────────────────────────────────────────
T17 · MONITORING / SERVICE-STATUS
────────────────────────────────────────
Wann: Service-Status, Metriken, Grafana, Alerts checken

**Status: [Was geprueft wird]**

| Service | Status | Details |
|---------|--------|---------|
| [Name] | ✅ OK | [Wert/Info] |
| [Name] | ❌ DOWN | [Fehlermeldung] |
| [Name] | ⚠️ WARN | [Was auffaellig ist] |

**Zusammenfassung:** [1 Satz Gesamtzustand]

**Pruefen:**
```bash
[systemctl status / curl health / prometheus query]
```

→ `Alert konfigurieren` · `Root-Cause untersuchen` · `Grafana Dashboard`

────────────────────────────────────────
T18 · LISTE / EMPFEHLUNG
────────────────────────────────────────
Wann: "Welche Tools?", "Was empfiehlst du?", strukturierte Aufzaehlungen

**[Thema]: Optionen im Ueberblick**

**[Kategorie 1]:**
- **[Option]** — [warum, wann nutzen]
- **[Option]** — [warum, wann nutzen]

**[Kategorie 2]:**
- **[Option]** — [warum, wann nutzen]

**Zusammenfassung:** [1 Satz was die beste Wahl fuer den User ist]

**Empfehlung:** [Direkte konkrete Wahl fuer den Kontext des Users]

→ `tiefer in [Option] einsteigen` · `Vergleichstabelle` · `als PDF`

────────────────────────────────────────
T19 · HOMELAB / PROXMOX / CONTAINER
────────────────────────────────────────
Wann: Container erstellen, VMs, Proxmox-Konfiguration

**Proxmox: [Was erstellt / konfiguriert wird]**

```bash
# Container erstellen
pct create [CTID] [template] \\
  --hostname [name] --cores [n] --memory [MB] \\
  --rootfs [storage]:[GB] \\
  --net0 name=eth0,bridge=vmbr[n],ip=[IP]/24,gw=[GW]
```

**Zusammenfassung:** [1 Satz was der CT macht und in welchem VLAN]

**Starten:**
```bash
pct start [CTID] && pct exec [CTID] -- bash -c "[erster Setup-Befehl]"
```

| CTID | Hostname | IP | Zweck |
|------|----------|----|-------|
| [n] | [name] | [IP] | [was] |

→ `Service einrichten` · `Backup konfigurieren` · `Monitoring hinzufuegen`

────────────────────────────────────────
T20 · VORHER / NACHHER (Code-Verbesserung)
────────────────────────────────────────
Wann: Code refaktorieren, verbessern, Unterschied zeigen

**Refactor: [Was verbessert wurde]**

**Vorher:**
```[sprache]
[alter Code]
```

**Nachher:**
```[sprache]
[verbesserter Code]
```

**Zusammenfassung:** [1 Satz das Wesentliche der Verbesserung]

**Warum besser:** [1-2 Saetze — konkret, kein Allgemeinplatz]

→ `weitere Stellen refaktorieren` · `Tests schreiben` · `als PR-Beschreibung`

────────────────────────────────────────
T21 · PLANUNG / ROADMAP
────────────────────────────────────────
Wann: User will etwas planen, Phasen definieren, Aufwand schaetzen

**Plan: [Was geplant wird]**

| Phase | Was | Aufwand | Status |
|-------|-----|---------|--------|
| 1 | [Meilenstein] | [~Zeit] | [ ] |
| 2 | [Meilenstein] | [~Zeit] | [ ] |
| 3 | [Meilenstein] | [~Zeit] | [ ] |

**Zusammenfassung:** [1 Satz was am Ende erreicht wird]

**Naechster Schritt:** [Konkrete erste Aktion die jetzt sofort getan werden kann]

→ `Phase 1 detaillieren` · `Risiken identifizieren` · `als Projektdoku`

────────────────────────────────────────
T22 · ERKLAERUNG FUER ANFAENGER
────────────────────────────────────────
Wann: Grundlagen erklaeren, "einfach erklaert", Analogie-Request

**[Begriff] einfach erklaert**

[Analogie: "Stell dir vor X ist wie Y — ..."]

[Technische Erklaerung, 2-3 Saetze, verlinkt zur Analogie]

**Zusammenfassung:** [1 Satz — das Wesentlichste]

**Zum Merken:**
- [Kernaussage 1 — einfach] · [Kernaussage 2 — einfach]

**Ausprobieren:** `[Einfachster erster Befehl / Schritt um das Gelernte direkt auszuprobieren]`

→ `naechsten Schritt lernen` · `praktisches Beispiel` · `als Lernzettel PDF`

────────────────────────────────────────
T23 · SYSTEMD / SERVICE
────────────────────────────────────────
Wann: systemd-Services erstellen, debuggen, verwalten

**Service: [Name] — [Was er tut]**

```ini
# /etc/systemd/system/[name].service
[Unit]
Description=[Was der Service tut]
After=network.target

[Service]
Type=simple
User=[user]
WorkingDirectory=[pfad]
ExecStart=[start-befehl]
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Zusammenfassung:** [1 Satz was der Service macht und wann er startet]

**Starten:**
```bash
systemctl daemon-reload && systemctl enable --now [name]
journalctl -u [name] -f
```

→ `Logging konfigurieren` · `Health-Check einbauen` · `Service-Uebersicht`

────────────────────────────────────────
T24 · PYTHON-SKRIPT
────────────────────────────────────────
Wann: User will Daten berechnen, verarbeiten oder visualisieren

**Script: [Was es tut]**

```python
# [Kurze Beschreibung — 1 Zeile]
[Code — vollstaendig, ausfuehrbar, kein "..."]
```

**Zusammenfassung:** [1 Satz was der Output / das Ergebnis ist]

**Starten:**
```bash
python3 [skript.py] [argumente wenn noetig]
```

→ `Argparse hinzufuegen` · `als Cron-Job` · `als Datei downloaden`

────────────────────────────────────────
T25 · ZERTIFIKAT / TLS / SSL
────────────────────────────────────────
Wann: SSL-Zertifikate, Let's Encrypt, Caddy/Nginx TLS, self-signed

**TLS: [Domain / Service]**

**Cert-Typ:** [Let's Encrypt / self-signed / wildcard / intern]

```bash
[Befehl zum Erstellen oder Erneuern]
```

**Zusammenfassung:** [1 Satz was abgesichert wird und wie lange das Cert gilt]

**Pruefen:**
```bash
openssl x509 -in [cert.pem] -noout -text | grep -E "Not After|Subject|DNS"
```

Ablauf: [Datum] — [Tage bis Ablauf]

→ `Auto-Renewal einrichten` · `HSTS aktivieren` · `Wildcard Cert`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

# Regexes for tool call formats produced by Qwen3 / llama.cpp
_PIPE_TC_RE   = re.compile(r'<\|tool_call\>call:(\w+)\{(.*?)\}(?:<tool_call\|>|$)', re.DOTALL)
_QWEN_TC_RE   = re.compile(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', re.DOTALL)
_FUNC_TC_RE   = re.compile(r'<function=(\w+)>(.*?)</function>', re.DOTALL)
_PARAM_RE     = re.compile(r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', re.DOTALL)
# Python function call format: create_document(key="value", ...)
_PYFUNC_TC_RE = re.compile(r'\b(create_document)\s*\(')


def _find_closing_paren(s: str, start: int) -> int:
    """Find matching closing paren index, respecting quoted strings."""
    depth = 0
    in_str: str | None = None
    i = start
    while i < len(s):
        c = s[i]
        if in_str:
            if c == '\\' and i + 1 < len(s):
                i += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c in ('"', "'"):
                in_str = c
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _unescape(s: str) -> str:
    """Unescape \\n, \\t, \\\\, \\\", \\' but leave LaTeX backslashes intact."""
    result, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == 'n':   result.append('\n'); i += 2; continue
            if nxt == 't':   result.append('\t'); i += 2; continue
            if nxt == '\\':  result.append('\\'); i += 2; continue
            if nxt == '"':   result.append('"');  i += 2; continue
            if nxt == "'":   result.append("'");  i += 2; continue
        result.append(s[i])
        i += 1
    return ''.join(result)


def _parse_kwargs(args_str: str) -> dict:
    """Parse Python keyword args: key="value" or key='value'."""
    result = {}
    pattern = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', re.DOTALL)
    for m in pattern.finditer(args_str):
        raw_val = m.group(2)[1:-1]  # strip surrounding quotes
        result[m.group(1)] = _unescape(raw_val)
    return result


def _normalize(text: str) -> str:
    text = text.replace('<|"|>', '"').replace("<|'|>", "'")
    text = re.sub(r'<\|(?!tool_call)[^|>]{0,30}\|>', '', text)
    return text


def _parse_args(body: str) -> dict:
    """Parse tool call args, handling llama.cpp special tokens and literal newlines."""
    placeholders: list[str] = []

    def _stash(m: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(m.group(1))
        return f'"__PH{idx}__"'

    processed = re.sub(r'<\|"\|>(.*?)<\|"\|>', _stash, body, flags=re.DOTALL)
    processed = re.sub(r'<\|[^|>]{0,30}\|>', '', processed).strip()

    def _restore(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if isinstance(v, str):
                hit = re.fullmatch(r'__PH(\d+)__', v)
                out[k] = placeholders[int(hit.group(1))] if hit and int(hit.group(1)) < len(placeholders) else v
            else:
                out[k] = v
        return out

    for raw in [processed, processed.replace('\n', '\\n').replace('\r', '')]:
        for candidate in [raw, re.sub(r'(?<!["\w])(\w+)\s*:', r'"\1":', raw)]:
            for wrapped in [candidate, '{' + candidate + '}']:
                try:
                    return _restore(json.loads(wrapped))
                except (json.JSONDecodeError, ValueError):
                    pass

    result = {}
    for key, val in _PARAM_RE.findall(body):
        result[key] = val.strip()
    return result


def _extract_tool_calls(content: str) -> list[dict]:
    normalized = _normalize(content)
    calls = []

    for i, (fname, body) in enumerate(_PIPE_TC_RE.findall(normalized)):
        fargs = _parse_args("{" + body + "}")
        if fname:
            calls.append({"name": fname, "args": fargs})

    for i, raw in enumerate(_QWEN_TC_RE.findall(normalized)):
        try:
            obj = json.loads(raw)
            fname = obj.get("name", "")
            fargs = obj.get("arguments", {})
            if isinstance(fargs, str):
                fargs = json.loads(fargs)
            if fname:
                calls.append({"name": fname, "args": fargs})
        except (json.JSONDecodeError, ValueError):
            pass

    for i, (fname, body) in enumerate(_FUNC_TC_RE.findall(normalized)):
        body = body.strip()
        fargs = {}
        params = _PARAM_RE.findall(body)
        if params:
            fargs = {k: v.strip() for k, v in params}
        elif body.startswith("{"):
            try:
                fargs = json.loads(body)
            except json.JSONDecodeError:
                pass
        if fname:
            calls.append({"name": fname, "args": fargs})

    # Format 4: Python function call — create_document(key="value", ...)
    for m in _PYFUNC_TC_RE.finditer(content):
        fname = m.group(1)
        open_idx = m.end() - 1
        close_idx = _find_closing_paren(content, open_idx)
        # Fallback: if truncated (no closing paren), use rest of string
        args_str = content[open_idx + 1:close_idx] if close_idx > open_idx else content[open_idx + 1:]
        fargs = _parse_kwargs(args_str)
        if fargs:
            calls.append({"name": fname, "args": fargs})

    return calls


def _strip_tool_calls(content: str) -> str:
    content = _PIPE_TC_RE.sub("", content)
    content = _QWEN_TC_RE.sub("", content)
    content = _FUNC_TC_RE.sub("", content)
    content = re.sub(r'<\|tool_call\>.*?(?:<tool_call\|>|$)', '', content, flags=re.DOTALL)
    # Remove entire ```code``` blocks that contain create_document() — model wrapped tool in Python block
    content = re.sub(
        r'```[^\n]*\n(?:(?!```)[\s\S])*?create_document\s*\((?:(?!```)[\s\S])*?```',
        '', content
    )
    # Strip bare Python-style function calls (outside code blocks)
    for m in reversed(list(_PYFUNC_TC_RE.finditer(content))):
        close_idx = _find_closing_paren(content, m.end() - 1)
        end = close_idx + 1 if close_idx > 0 else len(content)
        content = content[:m.start()] + content[end:]
    # Remove empty code blocks left behind (```python\n\n```)
    content = re.sub(r'```\w*\s*\n?\s*```', '', content)
    return content.strip()


async def _run_create_document(args: dict) -> tuple[str, dict | None]:
    """Returns (display_text, doc_info | None). doc_info has url/filename/size/doc_type."""
    from .tools import execute_tool
    from .docgen import DOCS_DIR
    doc_type = args.get("doc_type") or args.get("document_type") or args.get("format", "pdf")
    filename = (args.get("filename") or args.get("file_name") or "dokument").rstrip(".pdf").rstrip(".docx").rstrip(".xlsx")
    content = args.get("content", "")
    tool_args: dict = {
        "doc_type": doc_type.lower(),
        "content": content,
        "filename": filename,
    }
    for opt in ("theme", "layout", "show_header", "cover_page", "toc", "header_left", "header_right"):
        if opt in args:
            tool_args[opt] = args[opt]
    result = await execute_tool("create_document", tool_args)
    if result.get("success"):
        output = result.get("output", "")
        url_match = re.search(r'/api/download/([^\)\s]+)', output)
        if url_match:
            fname = url_match.group(1)
            path = DOCS_DIR / fname
            size = path.stat().st_size if path.exists() else 0
            return output, {
                "url": f"/api/download/{fname}",
                "filename": fname,
                "size": size,
                "doc_type": doc_type.lower(),
            }
        return output, None
    return f"Fehler beim Erstellen des Dokuments: {result.get('output', 'Unbekannter Fehler')}", None


async def stream_chat(messages: list[dict], brain_override: str | None = None, user_id: str | None = None) -> AsyncGenerator[str, None]:
    from .learning import get_learnings_context
    now = datetime.now().strftime("%A, %d. %B %Y, %H:%M Uhr")
    prompt = SYSTEM_PROMPT + f"\n\nAktuelles Datum und Uhrzeit: {now}"
    if user_id:
        learnings = get_learnings_context(user_id)
        if learnings:
            prompt += f"\n\n{learnings}"

    processed = []
    has_images = False
    has_docs = False
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            if any(p.get("type") == "image_url" for p in c):
                has_images = True
                processed.append(m)
            else:
                text = " ".join(p.get("text", "") for p in c if p.get("type") == "text")
                if "[Dokument:" in text:
                    has_docs = True
                processed.append({**m, "content": text})
        else:
            if isinstance(c, str) and "[Dokument:" in c:
                has_docs = True
            processed.append(m)

    if has_images:
        effective_override = "fast"
    elif has_docs:
        effective_override = "big"
    else:
        effective_override = brain_override
    llm_url, brain = get_llm_url(processed, "chat", brain_override=effective_override)
    if brain in ("fast", "code"):
        prompt += " /no_think"
    full_messages = [{"role": "system", "content": prompt}] + processed
    yield f"data: {json.dumps({'brain': brain})}\n\n"

    # Buffer full response so we can detect and execute tool calls
    full_content = ""
    error_msg = None

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{llm_url}/v1/chat/completions",
                json={
                    "model": "xera-ai",
                    "messages": full_messages,
                    "max_tokens": 4096,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except httpx.ConnectError:
        error_msg = "KI-Server nicht erreichbar. Bitte versuche es später nochmal."
    except httpx.HTTPStatusError as e:
        error_msg = f"LLM-Fehler: HTTP {e.response.status_code}"
    except Exception as e:
        error_msg = f"Fehler: {str(e)}"

    if error_msg:
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Check for tool calls in buffered content
    tool_calls = _extract_tool_calls(full_content)
    if tool_calls:
        for tc in tool_calls:
            name = tc["name"]
            args = tc["args"]
            if name == "create_document":
                result_text, doc_info = await _run_create_document(args)
                clean_prefix = _strip_tool_calls(full_content)
                if clean_prefix:
                    for i in range(0, len(clean_prefix), 6):
                        yield f"data: {json.dumps({'content': clean_prefix[i:i+6]})}\n\n"
                        await asyncio.sleep(0.008)
                    yield f"data: {json.dumps({'content': '\n\n'})}\n\n"
                if doc_info:
                    yield f"data: {json.dumps({'type': 'document', **doc_info})}\n\n"
                    # Also emit a doc_ref content for DB persistence and session reload
                    ref = f"Dokument erstellt: [Download]({doc_info['url']})"
                    yield f"data: {json.dumps({'type': 'doc_ref', 'content': ref})}\n\n"
                else:
                    for i in range(0, len(result_text), 6):
                        yield f"data: {json.dumps({'content': result_text[i:i+6]})}\n\n"
                        await asyncio.sleep(0.008)
                yield "data: [DONE]\n\n"
                return
            # Unknown tool call: strip it and fall through to normal output

    # No tool calls (or unrecognized): stream the clean content
    clean = _strip_tool_calls(full_content) if tool_calls else full_content
    chunk_size = 6
    for i in range(0, len(clean), chunk_size):
        yield f"data: {json.dumps({'content': clean[i:i+chunk_size]})}\n\n"
        await asyncio.sleep(0.008)
    yield "data: [DONE]\n\n"
