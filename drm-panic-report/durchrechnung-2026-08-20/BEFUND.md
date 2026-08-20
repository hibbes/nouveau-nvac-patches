# Durchrechnung 20.08.2026: der naheliegende Patch hat einen Konstruktionsfehler

13 Agenten geplant, 9 gelaufen, 4 am Sitzungslimit gescheitert
(3 Angriffe und die Endfassung). Von 2 gelaufenen Angriffen haben **beide
getroffen, beide mit Schwere hoch, und beide dasselbe**.

## Der Entwurf

Der Entwurf koppelte die Lebensdauer der Panic-Abbildung an `bo->pin_count`:
abbilden beim Pinnen in `prepare_fb`, abbauen, wenn der Pin faellt.

## Warum das bricht

`bo->pin_count` traegt **zwei Bedeutungen**: "gepinnt" und "gepinnt und
abgebildet". Die Entscheidung ABZUBILDEN faellt pro Plane, die Entscheidung
ABZUBAUEN am globalen Zaehler. Es gibt aber Pinner, die nie abbilden:

- **Cursor- und Overlay-Planes** benutzen dasselbe `prepare_fb`/`cleanup_fb`,
  haben aber kein `get_scanout_buffer`.
- dma-buf-Pinner zaehlen ebenfalls mit.

Ablauf, der garantiert eintritt: derselbe BO liegt auf Primary P und Overlay O,
`pin_count == 2`, `kmap` lebt. `drm_atomic_helper_cleanup_planes()` laeuft in
Plane-Index-Reihenfolge, die Primary zuerst. Deren cleanup senkt auf 1, ohne
`ttm_bo_kunmap()`. Der letzte Unpin kommt dann vom Overlay, das nie abbildet
und nie abbaut.

**Ergebnis: `nvbo->kmap.virtual` ueberlebt auf einem UNGEPINNTEN BO.** Der
Puffer darf danach wandern oder freigegeben werden, der Zeiger bleibt stehen,
und im Panic wird genau er benutzt.

Das ist schlimmer als der gemeldete Fehler: stille Verfaelschung statt Absturz.

## Was beide Angreifer empfehlen

Die Abbildung **nicht** an `bo->pin_count` haengen. Zwei Wege:

1. **Eigener Zaehler** `kmap_pin_count` in `struct nouveau_bo`, unter der
   BO-Reservierung gefuehrt, `ttm_bo_kunmap()` erst bei null. Robust gegen
   jede Mischung aus Map- und Nicht-Map-Pinnern.
2. **Privater Zustand in dispnv50** statt `nvbo->kmap`: ein eigenes
   `ttm_bo_kmap_obj` oder ein `iosys_map` im `nv50_wndw_atom` des
   Plane-States. Dann ist die Symmetrie strikt (prepare_fb pro neuem State,
   cleanup_fb pro altem State), ganz ohne Zaehler, und der gemeinsam genutzte
   `nvbo->kmap` bleibt unangetastet.

Weg 2 wirkt sauberer, weil er kein neues Feld im BO braucht und die
Zaehlerfrage gar nicht erst aufwirft.

## Stand

**Der Entwurf ist verworfen.** Er darf so nicht geschrieben werden. Die
Neufassung nach Weg 2 ist noch nicht durchgerechnet, und die drei nicht
gelaufenen Angriffe (Panic-Verletzung, Regression, Form) fehlen weiterhin.

Rohdaten: die sechs Analysen, der verworfene Entwurf und die zwei Angriffe
liegen als Textdateien daneben.
