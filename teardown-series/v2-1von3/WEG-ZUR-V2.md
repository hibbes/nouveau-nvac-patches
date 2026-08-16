# Wie die v2 zu einem Einwort-Patch wurde

## Drei Anlaeufe

| | Aenderung | Ergebnis |
|---|---|---|
| v1 (15.08., gesendet) | `dtor` nach vorne | **zurueckgezogen**, fuehrte TOCTOU ein |
| v2, erster Anlauf | `cancel` nach hinten | verworfen, aber aus falschem Grund, siehe unten |
| v2, final | `cancel_work_sync` -> `disable_work_sync` | ein Wort, keine Umstellung |

## Warum der erste v2-Anlauf verworfen wurde, und warum die Begruendung nicht trug

Die Pruefung am 16.08. verwarf den Anlauf mit dem Argument, die Umstellung
lasse `nouveau_fence_uevent_work()` zeitgleich mit `nvif_event_dtor()` laufen,
und die Arbeit rufe ueber `nouveau_fence_update()` selbst
`nvif_event_block(&fctx->event)`.

**Dieses Argument ist falsch, gegen den Quelltext geprueft.**
`nouveau_fence_update()` erreicht `nvif_event_block()` nur bei gesetztem
`drop` (`nouveau_fence.c:138-139`), und `drop` entsteht ausschliesslich in der
Schleife ueber `fctx->pending` (`:130-136`). `nouveau_fence_context_kill()`
leert diese Liste vollstaendig und setzt `fctx->killed` unter `fctx->lock`
(`:85-92`), danach weist `nouveau_fence_emit()` mit `-ENODEV` ab. Nach dem
`kill` ist die Liste dauerhaft leer, der Aufruf findet also gar nicht statt.

Der zweite Drain hinter dem `dtor` waere damit **sicher** und haette zudem
nach 6.6.y zurueckportiert werden koennen. `disable_work_sync()` ist trotzdem
die bessere Wahl fuer mainline, aber aus anderen Gruenden: ein
Synchronisationspunkt statt zwei, die Arbeit wird gar nicht erst eingereiht
statt hinterher aufgeraeumt, und es ist das in drm etablierte Idiom
(`drm/xe`, `drm/panthor`, `drm_pagemap`, sieben Dateien im Baum).

Diese Begruendung steht jetzt so im Commit-Text, samt der Alternative.

## Was die Pruefungen sonst korrigiert haben

- Die Behauptung, das Fenster reiche bis zum `dtor`, war zu weit. Es endet in
  zwei Stufen: der `kill` blockt das Event (`atomic_xchg(&ntfy->allowed, 0)`,
  `event.c:104`), was neue Handler stoppt; nur der `dtor` wartet einen bereits
  laufenden aus (`nvkm_event_ntfy_remove()`, `write_lock_irq`, `event.c:84`),
  weil das Event mit `wait = false` angelegt ist (`nouveau_fence.c:201`).
- Der Beleg `dma-fence.c:707-710` deckte nur **einen** Einstiegspfad ab.
  Tragend ist der Test in `__dma_fence_enable_signaling()` selbst (`:639`),
  der unter der Fence-Sperre laeuft, und die ist `fctx->lock`.
- `nouveau_fence_context_free()` ist ein `kref_put()`, kein unbedingtes
  Freigeben. Emittierte Fences halten eigene Referenzen. Das ist aber **kein
  Schutznetz**: haelt keine mehr eine, faellt der Zaehler sofort auf null.
- **Der Schaden ist der blanke Use-after-free**, nichts weiter.
  `struct work_struct uevent_work` liegt eingebettet in `fctx`
  (`nouveau_fence.h:53`), `nouveau_fence_context_put()` gibt per `kfree()` frei
  (`:114`). Die Workqueue dereferenziert also schon beim Aufgreifen
  freigegebenen Speicher. Mit `CONFIG_DEBUG_OBJECTS_WORK` und
  `CONFIG_DEBUG_OBJECTS_FREE` wird das als Freigabe eines aktiven Objekts
  gemeldet (`mm/slub.c:2608`, `kernel/workqueue.c:680`).

## Korrektur an dieser Datei selbst (16.08.)

Zwei Saetze frueherer Fassungen waren falsch und sind hier ersetzt:

1. *"Der `Link:` zeigte auf die eigene zurueckgezogene 1/3 statt auf den
   Bericht des Bots."* Falsch. Der v1-Verweis zeigte auf
   `sashiko.dev/#/patchset/20260812231330...?part=1`, also sehr wohl auf die
   Bot-Durchsicht der Viererserie. Das echte Problem war ein anderes: es ist
   eine JS-Fragment-URL statt eines dauerhaften Archivverweises. In der v2
   war er dann faelschlich auf die `[Critical]`-Mail **zur zurueckgezogenen
   v1** umgebogen, also auf eine Kritik am eigenen Patch statt auf den
   Fehlerbericht. Jetzt: `Closes:` auf die lore-Thread-URL der Viererserie,
   dieselbe, die schon im Cover der Serie stand.

2. *"Kein Langzeitzweig liegt in dieser Luecke."* Falsch, siehe unten.

## Randbedingung fuer stable

`disable_work_sync()` gibt es seit **v6.10**
(commit `86898fa6b8cd ("workqueue: Implement disable/enable for (delayed)
work items")`, laut `git describe --contains` in `v6.10-rc1~137^2^2~12`).

Der Fehler kam mit
commit `39126abc5e20 ("nouveau: offload fence uevents work to workqueue")`,
und dieser Commit trug selbst `Cc: linux-stable@vger.kernel.org`. Er wurde
zurueckportiert: **CVE-2024-26719**, behoben in **6.6.18** (Backport
`cc0037fa592d`) und **6.7.6** (`985d053f7633`).

Damit liegt **linux-6.6.y** genau in der Luecke: Longterm-Zweig, traegt den
Fehler, hat `disable_work_sync()` nicht. Der Patch wuerde dort sauber
anwenden und dann am unbekannten Symbol scheitern.

Konsequenz im Trailer, Form nach
`Documentation/process/stable-kernel-rules.rst:111-119`:

    Cc: <stable@vger.kernel.org> # 6.10.x

Der Commit-Text nennt zusaetzlich die Form, die eine 6.6.y-Fassung braechte
(der zweite Drain), damit ein stable-Maintainer nicht raten muss.

**Nicht lokal pruefbar:** der Arbeitsbaum hat nur die Remotes `origin`
(torvalds) und `netdev`, keinen stable-Baum. Die Versionsangaben stammen aus
dem CVE-Datensatz (`cveawg.mitre.org/api/cve/CVE-2024-26719`), nicht aus
eigener Anschauung. lore und cgit sind von diesem Host aus durch Anubis
gesperrt, auch mit Chrome headless.

## Stand

Modulbau rc=0, 0 Warnungen (Diff-Hash identisch zur gebauten Fassung,
`908fc2e9bdca…`, daher kein Neubau noetig). checkpatch --strict 0/0/0.
Basis `c21bb4193868`. Zweig `teardown-1von3-v2`. **NICHT GESENDET.**

## Nachtrag 16.08. nach dem Versand: lore ist doch erreichbar, und der Closes: ist falsch

**lore ist von gentoo-neo aus NICHT gesperrt.** Anubis blockt nur die HTML-
und `/raw`-Sichten (403). Der Endpunkt `t.mbox.gz` liefert 200. Das
Morgen-Briefing benutzt ihn seit jeher, mir ist der Widerspruch erst nach dem
Versand aufgefallen.

Damit liess sich die Zuschreibung endlich direkt belegen. Die Bot-Mail
`20260812233022.159301F000E9@smtp.kernel.org` (Antwort auf 1/4 der
Viererserie) sagt woertlich:

> `- [High] Canceling `uevent_work` before destroying `fctx->event` in
> `nouveau_fence_context_del` leaves a window for use-after-free.`

Das ist genau dieser Patch, und der Bot nennt es **use-after-free**, also
genau die Formulierung, auf die der Commit-Text heute korrigiert wurde.
`Reported-by: sashiko-bot` steht zu Recht.

**Aber der `Closes:` ist falsch gezielt.** Gesendet wurde

    Closes: https://lore.kernel.org/nouveau/20260812231330.705425-1-mczernohous@gmail.com/

Das loest auf, zeigt aber auf die **nouveau**-Sicht des Fadens, und dort
existieren die Bot-Mails nicht. Gemessen:

| Sicht der Viererserie | Mails | Bot-Mails |
|---|---|---|
| `/dri-devel/` | 7 | 2 |
| `/nouveau/` | 5 | **0** |
| `/nouveau/<bot-msgid>/` | **HTTP 404** | |

Wer dem Verweis folgt, findet den zitierten Bericht also nicht. Richtig waere

    Closes: https://lore.kernel.org/all/20260812233022.159301F000E9@smtp.kernel.org/

**Lehre:** fuer Verweise auf Fremdmails immer `/all/<message-id>/`, nie die
Serien-Wurzel und nie eine Listensicht ohne Gegenprobe, dass die zitierte Mail
dort existiert. Im Memory als
`reference_lore_mbox_endpoint_umgeht_anubis.md`.
