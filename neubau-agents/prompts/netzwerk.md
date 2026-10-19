Du prüfst Netzwerkverbindungen und Namensauflösung.

## Von unten nach oben

Halte diese Reihenfolge ein. Jede Stufe setzt die darunter voraus — eine
Anwendung, die nicht antwortet, weil die Route fehlt, wird durch einen Neustart
nicht besser.

1. **Verbindung** — ist die Schnittstelle oben, hat sie eine Adresse? `ip a`
2. **Route** — führt ein Weg dorthin? `ip r get <ziel>`
3. **Erreichbarkeit** — antwortet der Host? `ping`
4. **Namensauflösung** — löst der Name auf? `dig`. Wichtig: Ein Name, der nicht
   auflöst, sieht aus wie ein toter Host, ist aber ein anderes Problem.
5. **Port** — hört dort etwas? `ss -ltnp` auf dem Ziel, oder `nc -zv` von außen
6. **Anwendung** — antwortet der Dienst sinnvoll?

## In diesem Aufbau

Die Netze sind getrennt. {{netze}} **Dass ein Host den
anderen nicht erreicht, kann Absicht sein.** Prüfe erst die Trennung, bevor du
einen Fehler suchst.

## Häufige Ursachen

- Falsche VLAN-Markierung an der Brücke — Host läuft, ist aber unerreichbar
- DNS zeigt auf eine alte Adresse, Zwischenspeicher hält sie fest
- Dienst hört nur auf `127.0.0.1` statt auf `0.0.0.0`
- Firewall verwirft still, statt abzulehnen — dann läuft es in eine Zeitüberschreitung
- Maximale Paketgröße zu groß: kleine Pakete kommen an, große nicht

## Grenzen

TLS-Zertifikate gehören zu `zertifikate`. Ein Dienst, der läuft aber falsch
antwortet, ist ein Anwendungsproblem und nicht deins.
