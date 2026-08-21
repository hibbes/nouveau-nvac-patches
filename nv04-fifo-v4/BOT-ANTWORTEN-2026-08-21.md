# Sashiko-Bot auf die v4, 21.08. 15:33 bis 15:35 UTC

Drei Mails, je eine pro Patch. Noch keine menschliche Antwort.

## 1/3: zwei Befunde, beide = unsere Teardown-Serie

- cancel_work_sync vs nvif_event_dtor in nouveau_fence_context_del:
  = Teardown 1/3 (disable_work_sync), seit 20.08. in drm-misc-next.
- fehlendes cancel_work_sync fuer irq_work in nouveau_connector_destroy:
  = Teardown 2/3, Lyude Reviewed-by 20.08.
Der Bot sieht nur die Basis c21bb4193868. Antwort: Verweis, zwei Saetze.

## 2/3 (b): Fehlerpfad bei context_new-Fehlschlag

KORREKTUR 22.08.: meine Begruendung "ready bleibt false" haelt nur, wenn
das Nullen sichtbar ist, haengt also am Hauptbefund. Der echte Schutz:
nv84_fence_context_del() setzt chan->fence = NULL VOR dem kfree, dazwischen
synchronize_rcu() in nouveau_fence_context_del(). Der Zeiger geht, bevor
der Speicher geht. Kein UAF erreichbar. Antwort: genau das.

## 2/3 (a) und 3/3: DER ECHTE BEFUND

"chan->fence is published without a release barrier by the backend
allocators [...] READ_ONCE() might observe the pointer before the
allocator's zeroing stores are visible. The smp_load_acquire() on
fctx->ready doesn't prevent reading pre-initialization garbage for the
ready flag itself."

Haelt formal. Acquire ordnet, was NACH dem Load kommt, nicht was VOR dem
Zeiger liegt. SLUB setzt keine Schranke zwischen Nullen und Rueckgabe.
Leseseite ist ein Ereignis, andere CPU moeglich. Auf x86 unerreichbar
(keine Store-Umordnung), auf ARM denkbar. VORBESTEHEND: die Basis las
plain und rief context_kill ohne Pruefung. 2/3 macht es besser, nicht
vollstaendig.

Zwei Loesungen fuer eine v5:
  a) Backends veroeffentlichen chan->fence mit smp_store_release() statt
     plain (5 Stellen: nv04/nv10/nv17/nv50/nv84_fence.c). Dann traegt das
     Acquire auf ready auch das Nullen.
  b) Handschlag ueber einen EIGENEN Zeiger, der erst in arm() gesetzt wird
     (chan->fence_ready o.ae.). Kein Fenster mehr, in dem Zeiger sichtbar
     und Inhalt unfertig ist. Sauberer, aendert aber mehr.

Antwortentwurf: ANTWORT-BOT-ENTWURF.txt. Plan: Lyude abwarten. Sie koennte b) selbst vorschlagen. Eine v5 vor ihrem
Review waere voreilig. Antwort an den Bot: anerkennen, v5 ankuendigen.
