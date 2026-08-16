# Wie die v2 zu einem Einwort-Patch wurde

## Drei Anlaeufe

| | Aenderung | Ergebnis |
|---|---|---|
| v1 (15.08., gesendet) | `dtor` nach vorne | **zurueckgezogen**, fuehrte TOCTOU ein |
| v2, erster Anlauf | `cancel` nach hinten | verworfen, siehe unten |
| v2, final | `cancel_work_sync` -> `disable_work_sync` | eine Zeile, keine Umstellung |

## Warum der erste v2-Anlauf verworfen wurde

Die adversariale Pruefung am 16.08. (20 Agenten, eine Linse rein destruktiv)
lieferte 16 Befunde, **alle bestaetigt, keiner widerlegt**. Vier davon
kreisten um dasselbe: die Umstellung liess `nouveau_fence_uevent_work()`
erstmals zeitgleich mit `nvif_event_dtor()` laufen, und die Arbeit ruft ueber
`nouveau_fence_update()` selbst `nvif_event_block(&fctx->event)`. Das ist
derselbe ungeschuetzte Zugriff, den v1 zu Fall gebracht hatte, nur ueber
einen anderen Aufrufer.

Ein weiterer Befund nannte die Loesung: **`disable_work_sync()`**. Laut
Kerneldoc erhoeht sie den disable-Zaehler, und "as long as the disable count
is non-zero, any attempt to queue @work will fail and return %false". Sie
leert also wie `cancel_work_sync()` UND verhindert das Neueinreihen.

Damit bleibt die Mainline-Reihenfolge unangetastet, und die ganze
Reihenfolgefrage stellt sich nicht mehr.

## Was die Pruefung sonst noch korrigiert hat

- Die Behauptung, das Fenster reiche bis zum `dtor`, war zu weit. Es endet in
  zwei Stufen: der `kill` blockt das Event (`atomic_xchg(&ntfy->allowed, 0)`,
  `event.c:104`), was neue Handler stoppt; nur der `dtor` wartet einen bereits
  laufenden aus (`nvkm_event_ntfy_remove()`, `write_lock_irq`, `event.c:84`),
  weil das Event mit `wait = false` angelegt ist (`nouveau_fence.c:201`).
- Der Beleg `dma-fence.c:707-710` deckte nur **einen** Einstiegspfad ab.
  Tragend ist der Test in `__dma_fence_enable_signaling()` selbst (`:639`),
  der unter der Fence-Sperre laeuft, und die ist `fctx->lock`.
- `nouveau_fence_context_free()` ist ein `kref_put()`, kein unbedingtes
  Freigeben. Emittierte Fences halten eigene Referenzen.
- Der `Link:` zeigte auf die eigene zurueckgezogene 1/3 statt auf den Bericht
  des Bots. Korrigiert.

## Randbedingung fuer stable

`disable_work_sync()` gibt es seit **v6.10** (`86898fa6b8cd`), der Fehler
existiert seit **v6.8** (`39126abc5e20`). Kein Langzeitzweig liegt in dieser
Luecke, aber der Commit-Text sagt es, damit ein stable-Maintainer es nicht
selbst herausfinden muss.

## Stand

Modulbau rc=0, 0 Warnungen. checkpatch 0/0/0. Basis `c21bb4193868`.
Zweig `teardown-1von3-v2`. **NICHT GESENDET.**
