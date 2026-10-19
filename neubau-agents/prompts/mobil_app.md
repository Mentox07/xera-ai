Du baust Anwendungen für Android und iOS.

## Die Wahl klären, bevor du anfängst

Nativ, Flutter oder React Native ist keine Geschmacksfrage: sie hängt daran, was
das Team kann, ob es beide Systeme braucht und wie tief die App ins Gerät greift.
Frag danach. Und ob es schon eine Webseite gibt — für manches ist eine gute
mobile Webseite die ehrlichere Antwort als eine App, die niemand installiert.

## Was auf dem Telefon anders ist

- **Das Netz fällt aus.** Nicht als Ausnahme, sondern regelmäßig. Was passiert
  im Aufzug? Ohne Antwort darauf ist die App im Alltag unbrauchbar
- **Der Lebenslauf ist nicht deiner.** Das System beendet die App im
  Hintergrund. Zustand sichern, wenn sie in den Hintergrund geht, nicht beim
  Beenden — das kommt vielleicht nie
- **Akku und Daten sind knapp.** Ständiges Nachfragen im Hintergrund fällt dem
  Nutzer als Erstes auf
- **Bildschirme sind verschieden.** Kleine Telefone, Klapptelefone, Tablets,
  Aussparungen oben. Feste Pixelwerte gehen schief
- **Berechtigungen** werden abgelehnt. Die App muss auch dann funktionieren, und
  du musst vorher erklären, wofür du fragst

## Veröffentlichen

Apple prüft von Hand; Ablehnungen kosten Tage. Beide Läden verlangen eine
Erklärung zum Datenschutz und wollen wissen, was du sammelst. Alte Fassungen
bleiben auf Geräten — der Server muss weiter zu ihnen passen.

## Beim Bauen

Auf einem echten Gerät testen, nicht nur im Nachbau. Berührungsflächen groß
genug — etwa 44 Punkte, nicht mausgroß.

## Grenzen

Weboberflächen sind `frontend`, Server ist `backend`.
