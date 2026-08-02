# 0003 – Wochen-Ratings aus dem v2-Erstrelease zurückgestellt

**Status:** Accepted (2026-08-02)

## Kontext

v1 berechnet in `ratings.py` "Wochen-Ratings" (Rating pro ISO-Kalenderwoche, gewichtet nach Spielplan-Dichte des
Teams in dieser Woche — nützlich für Streaming-/Waiver-Entscheidungen) und speichert sie in `weekly_ratings.csv`.

Beim Review für v2 wurde per Grep über `views.py`, `urls.py` und alle Templates verifiziert: **keine einzige
Stelle in v1 zeigt Wochen-Ratings tatsächlich an.** Das Feature wird berechnet, aber nirgends in der
Weboberfläche verwendet — vermutlich ein begonnenes, nie fertiggestelltes Feature.

## Entscheidung

Wochen-Ratings sind **nicht Teil des ersten v2-Release-Scopes**. Backlog-Notiz statt aktiver Umsetzung — siehe
"Backlog" in `docs/product-spec.md`.

## Verworfene Alternativen

- **Komplett streichen, nie wieder aufgreifen:** verworfen — das Feature ist grundsätzlich sinnvoll (z. B. "welche
  Spieler haben diese Woche viele Spiele"), und die Spielplan-Daten werden für die Verfügbarkeits-Gewichtung
  (`availability_score`, siehe `product-spec.md` Abschnitt 2.3) ohnehin benötigt. Die Überschneidung macht ein
  späteres Nachrüsten günstig — Streichen würde diesen Vorteil verschenken.
- **Jetzt vollständig bauen inkl. sichtbarer UI (z. B. eigene "Streaming-Helfer"-Ansicht):** verworfen für den
  Erstrelease, um dessen Scope nicht unnötig zu vergrößern — kann als eigenständiges Feature nach dem
  Kern-Rebuild ergänzt werden.

## Konsequenzen

- `pipeline/` muss im ersten Release keine Wochen-Spielplan-Aggregation liefern.
- Das Feature bleibt als dokumentierter Backlog-Punkt erhalten, damit es nicht vergessen wird, wird aber nicht
  in die erste Supabase-Schema-Version oder das Next.js-Grundgerüst eingeplant.
