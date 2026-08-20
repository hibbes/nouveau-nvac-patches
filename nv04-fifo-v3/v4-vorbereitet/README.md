# v4 der nv04-FIFO-Serie: Stand der Vorbereitung, NICHTS GESENDET

## Ausgangslage nach Lyudes Durchsicht vom 20.08.2026

| Patch | Rueckmeldung | Vorbereitung |
|---|---|---|
| 1/4 unsubscribe kill-event | **Reviewed-by Lyude** | unveraendert uebernehmen |
| 2/4 subscribe after fence context | Entwurfsvorschlag Lyude | **neu gebaut**, `2von4-handschlag.diff` |
| 3/4 CACHE_ERROR-Filter | drei Umbauwuensche | **umgebaut**, `3von4-nach-lyude.diff` |
| 4/4 kill-events auf NV50+ | keine | unveraendert, Begruendung anpassen |

## 2/4: warum nicht Lyudes Skizze, sondern eine Schranke

Lyude schlug vor, dass **beide** Seiten `fctx->lock` nehmen. Das geht nicht,
und der Grund ist am Quelltext belegt:

    nv50_fence.c:45   fctx = chan->fence = kzalloc_obj(*fctx);
    nv50_fence.c:49   nouveau_fence_context_new(chan, &fctx->base);
    nouveau_fence.c:183   spin_lock_init(&fctx->lock);

`chan->fence` wird also veroeffentlicht, **bevor** die Sperre existiert.
Der Kill-Pfad darf sie in diesem Fenster nicht nehmen. Mit
`CONFIG_DEBUG_SPINLOCK` waere das sofort ein Befund, ohne es stiller
Vertragsbruch.

Deshalb stattdessen das Speicherpuffer-Muster (Dekker) mit voller Schranke
auf beiden Seiten:

    arm():   WRITE_ONCE(fctx->ready, 1); smp_mb(); if (chan->killed) kill()
    kill():  atomic_set(killed, 1);      smp_mb(); if (fctx && fctx->ready) kill()

Beweis, dass kein Kill verlorengeht: angenommen keiner toetet. Dann las kill
`ready == 0` und arm las `killed == 0`. Beide Seiten haben ihre eigene Marke
vor dem Lesen der fremden geschrieben, mit voller Schranke dazwischen. Nach
Speicherpuffer-Ordnung muss mindestens eine die andere sehen. Widerspruch.

Dass beide toeten, ist unschaedlich: `nouveau_fence_context_kill()` ist
idempotent (die zweite Runde findet `pending` leer) und wird ohnehin schon
zweimal gerufen, im Kill-Pfad und bei `nouveau_fence.c:100` im Teardown.

`ready` braucht kein Atomic, genau wie Lyude selbst vermutete. Es liegt neben
den vorhandenen schlichten Ints `notify_ref, dead, killed`.

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
