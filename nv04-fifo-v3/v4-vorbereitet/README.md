# v4 der nv04-FIFO-Serie: Stand der Vorbereitung, NICHTS GESENDET

## Ausgangslage nach Lyudes Durchsicht vom 20.08.2026

| Patch | Rueckmeldung | Vorbereitung |
|---|---|---|
| 1/4 unsubscribe kill-event | **Reviewed-by Lyude** | unveraendert uebernehmen |
| 2/4 subscribe after fence context | Entwurfsvorschlag Lyude | **neu gebaut**, `2von4-handschlag.diff` |
| 3/4 CACHE_ERROR-Filter | drei Umbauwuensche | **umgebaut**, `3von4-nach-lyude.diff` |
| 4/4 kill-events auf NV50+ | keine | unveraendert, Begruendung anpassen |

## 2/4: Lyudes Entwurf, plus eine Schranke

### KORREKTUR 20.08. abends: die erste Fassung beruhte auf einer Fehllesung

Eine frueherer Stand dieses Files behauptete, Lyude schlage vor, dass **beide**
Seiten `fctx->lock` nehmen, und verwarf den Entwurf deshalb. Das steht so nicht
in seiner Mail. Woertlich:

> * Have `nouveau_channel_kill()` **check this atomic** after setting the
>   killed bit [...]
> * Back in `nouveau_channel_init()`, [...] **grab the fence context lock**

Die Sperre nimmt nur die **Init-Seite**. Die Kill-Seite prueft bloss das
Atomic. Damit faellt der ganze Einwand ueber die uninitialisierte Sperre weg,
denn die Kill-Seite fasst sie nie an.

### Was wirklich fehlt: eine Schranke auf der Kill-Seite

Sein Entwurf hat genau eine Luecke, und sie ist dokumentiert.
`Documentation/atomic_t.txt:165`:

> non-RMW operations are unordered

`atomic_set()` und `atomic_read()` sind non-RMW. Die Kill-Seite macht

    atomic_set(&chan->killed, 1);      /* Store */
    if (atomic_read(&fctx->ready))     /* Load  */

Store-dann-Load ist die eine Richtung, die weder der Uebersetzer noch x86
erhaelt. Der Store kann im Puffer stehen, waehrend `ready` als 0 gelesen wird,
und `arm()` liest `killed` als 0, bevor er ankommt. Beide tun nichts, der Kill
geht verloren.

Die Init-Seite ist Load-dann-Store. Das bleibt erhalten, und die Sperre
sichert es zusaetzlich.

### Beweis, dass eine Schranke reicht

Angenommen, beide verpassen sich. Dann las kill `ready == 0` und arm
`killed == 0`. Daraus folgt eine Kette:

    arm.LD(killed) -> arm.ST(ready)        Programmordnung, durch die Sperre gedeckt
    arm.ST(ready)  -> kill.LD(ready)       sonst haette kill die 1 gesehen
    kill.LD(ready) -> kill.ST(killed)      rueckwaerts, durch smp_mb() gedeckt
    kill.ST(killed)-> arm.LD(killed)       sonst haette arm die 1 gesehen

Das schliesst sich zu `arm.LD(killed)` vor sich selbst. Widerspruch. Also sieht
mindestens eine Seite die andere.

Dass beide toeten, ist unschaedlich: `nouveau_fence_context_kill()` wird
ohnehin schon zweimal gerufen, im Kill-Pfad und bei `nouveau_fence.c:100` im
Teardown, und der zweite Durchlauf findet `pending` leer.

### Warum die Sperre auf der Init-Seite trotzdem bleibt

Sie tut mehr, als die Marken zu ordnen. `nouveau_fence_context_kill()` nimmt
dieselbe Sperre. Ein Kill, der mitten in den Handschlag faellt, wartet also
dort, statt einen unfertigen Kontext zu durchlaufen. Das ist genau die
Wirkung, die Lyude mit "delay, but not block, any incoming kills" beschrieben
hat.

### Warum `fctx->ready` und nicht `chan->fence != NULL`

Die Fence-Backends veroeffentlichen den Zeiger vor der Initialisierung:

    nv50_fence.c:45       fctx = chan->fence = kzalloc_obj(*fctx);
    nv50_fence.c:49       nouveau_fence_context_new(chan, &fctx->base);
    nouveau_fence.c:183       spin_lock_init(&fctx->lock);

`chan->fence` wird also nicht-NULL, waehrend der Kontext noch unbrauchbar ist.
`kzalloc` nullt allerdings auch `ready`, der Kill-Pfad steigt in diesem Fenster
also korrekt aus, ohne irgendetwas anzufassen.

## Stand der Pruefung

- `checkpatch --strict`: **0 Warnungen, 0 Checks** fuer beide Patches,
  nur der erwartete fehlende `Signed-off-by`.
- Laengste Zeile 2/4: 77 Spalten. 3/4: 100 Spalten (Formatzeichenkette,
  bewusst nicht umbrochen, siehe coding-style.rst).
- **Bautest steht fuer beide aus.** Der 7.2.0-Baum baut noch, der Versuch im
  7.1.9-Baum wurde abgebrochen und der Baum sauber wiederhergestellt.

## Offen

- Bautest beider Patches
- 4/4: Begruendung anpassen, weil 2/4 die Luecke jetzt schliesst statt sie
  zu verschieben. Der Satz "That window does not close here, it moves"
  stimmt nicht mehr.
- Cover-Letter fuer die v4
- `Signed-off-by` setzt Marek
