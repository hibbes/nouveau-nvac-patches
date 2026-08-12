# Gegenprüfung der nv04-FIFO-v3-Serie vor dem Versand

**Datum:** 2026-08-12  
**Verfahren:** sieben unabhängige Prüflinsen über die 5 Patches und den Cover-Letter, 
danach Entdopplung, danach jedes verbliebene Problem von zwei Skeptikern angegriffen 
(einer am Quelltext, einer an der Relevanz).  
**Zahlen:** 99 Rohbefunde → 30 eindeutige Probleme → 26 überstanden die Gegenprüfung.  
**Empfehlung: `groesserer_umbau`**

## Begründung

Die Patches 1/5 bis 4/5 sind im Kern tragfaehig und brauchen im Wesentlichen Textkorrekturen plus Fixes-Tags. Patch 5/5 ist es nicht: er traegt zwei echte Defekte derselben Klasse, in der der Bot bereits zweimal getroffen hat, und einen Schichtungsfehler, der ohnehin eine Rueckweisung provoziert. Erstens laeuft nv04_fifo_recover() ohne jeden Familien-Check, obwohl nv04_fifo_intr auf sieben Chipfamilien haengt (nv04.c:545, nv10.c:98, nv17.c:127, nv40.c:237, nv50.c:383, g84.c:215, g98.c:54). Auf NV04 bis NV40 legt 4/5 bewusst keinen Kill-Abonnenten an, also erzeugt 5/5 dort genau den Dead-Letter-Haenger, den 4/5 drei Patches vorher als schwerwiegend anklagt. Die Serie widerlegt damit ihre eigene Begruendung, und zwar sichtbar im selben Diff-Hunk. Zweitens zieht recover.c das drm_device bei jedem Fault frisch aus dev_get_drvdata, waehrend nouveau nie drvdata leert und das einzige cancel_work_sync in nvkm_fifo_dtor (base.c:340) erst nach kfree(drm) in nouveau_drm_device_del (nouveau_drm.c:743) laeuft. Ein eingereihtes Wedge-Work liest dort freigegebenen Speicher und uebergibt ihn an dev_info, den Tracepoint und drm_dev_wedged_event. Beides selbst am Quelltext nachgeprueft. Dazu kommt, dass die Serie nach eigener Aussage nie gegen den base-commit uebersetzt wurde, obwohl sie eine neue Datei, einen Kbuild-Eintrag, einen Tracepoint-Header und CREATE_TRACE_POINTS mitbringt.

Praktischer Weg: 1/5 bis 4/5 mit korrigierten Commit-Texten und Fixes-Tags als geschlossene Vierer-Serie senden (3/5 und 4/5 stehen ohne 5/5 sauber fuer sich, 4/5 ist dann ein wohlbegruendetes No-op), und 5/5 fuer v4 umbauen: Tier-2-Politik in die DRM-Schicht heben, dann fallen UAF, Schichtenfrage, die externs in fifo/priv.h und der nv04_-Praefix in generischem Code in einem Zug weg. Wer 5/5 unbedingt jetzt mitschicken will, braucht mindestens den card_type-Guard, einen abgelegten und in nouveau_drm_device_fini genullten drm-Zeiger mit dortigem cancel_work_sync plus Wiedereinreihsperre, und die Struktur per Zeiger statt per Wert.

Unabhaengig davon ist der Cover-Letter in der versandfaehigen Fassung nicht sendbar: v3-0000-cover-letter.patch steht auf 13:44 und traegt die vom Autor selbst widerlegte Behauptung, der Compositor sterbe mit dem Opfer. Das ist die teuerste Einzelzeile der Einreichung.

## Blocker (15)

### 1. nv04_fifo_recover() ohne Familien-Guard: die Recovery feuert auf NV04 bis NV40, wo 4/5 bewusst keinen Kill-Abonnenten anlegt

**Patch:** 5/5 (im Zusammenspiel mit 4/5)  
**Aufwand:** stunde

**Ort:** drivers/gpu/drm/nouveau/nvkm/engine/fifo/recover.c:37-105 (kein card_type-Test, selbst per grep bestaetigt: null Treffer), Aufrufe nv04.c:348 und nv04.c:415, Gate in nouveau_chan.c:488

**Warum:** nv04_fifo_intr ist .intr fuer nv04, nv10, nv17, nv40, nv50, g84 und g98 (nv04.c:545, nv10.c:98, nv17.c:127, nv40.c:237, nv50.c:383, g84.c:215, g98.c:54), selbst nachgeprueft. Das Abo-Gate aus 4/5 steht auf oclass >= NV50_CHANNEL_GPFIFO (0x506f); NV03/NV10/NV17/NV40_CHANNEL_DMA sind 0x006b/0x006e/0x176e/0x406e und liegen darunter. Drei Faults in beliebiger Mischung aus CACHE_ERROR und DMA_PUSHER auf derselben chid binnen 10 s (fifo.h:66-67, beide Typen teilen denselben chfault-Slot) fuehren zu nvkm_chan_error(chan, false). Das Event feuert flankengetriggert (chan.c:232) in eine leere Notifier-Liste, chan->killed bleibt 0, nouveau_fence_context_kill laeuft nie, der Kanal ist ueber nvkm_chan_block_locked dauerhaft gestoppt und keine ausstehende Fence signalisiert je. Damit greifen die Notbremsen in nouveau_gem.c:776 und nouveau_exec.c:186/379 nicht, nouveau_channel_idle sieht killed==0 und busy-wartet 15 s pro Kanal, und dma_resv_wait_timeout in nouveau_bo.c:1136 (gerade der Pre-NV50-Tile-Pfad) sowie nouveau_fence_wait_legacy warten mit MAX_SCHEDULE_TIMEOUT. Betroffen sind vier FIFO-Implementierungen, in device/base.c zusammen 33 Chipsatz-Eintraege. Zweiter Schaden auf denselben Chips: nvkm_chan_error ruft dort nv04_chan_stop (nv04.c:41), das bei nv04.c:87 bedingungslos NV03_PFIFO_CACHES=1 schreibt, mitten in der CACHES-Klammer des Handlers (nv04.c:433 bis :478). Danach schreibt der Handler noch CACHE1_GET=get+4 und die uebrigen Fixups, moeglicherweise auf einen inzwischen eingewechselten Kanal. Zusaetzlich sagen Betreff und Text von 5/5 ausdruecklich nur Tesla, und 4/5 behauptet woertlich 'Pre-NV50 chips keep the old behaviour, so NV04 to NV40 are unaffected'. Betreff gegen Reichweite und Serie gegen sich selbst: das ist eine der zuverlaessigsten Rueckweisungsursachen.

**Fix:** Fruehausstieg am Kopf von nv04_fifo_recover(): if (fifo->engine.subdev.device->card_type != NV_50) return; Damit sind beide Aufrufer und jeder kuenftige mitgeschuetzt, und chan->func->stop ist immer nv50_chan_stop (blosses nvkm_mask auf 0x002600 + id*4). == NV_50 ist >= NV_50 vorzuziehen, weil es die Absicht der Commit-Message woertlich abbildet. Die Datei verzweigt schon bei nv04.c:320, :383 und :459 auf card_type, das ist idiomatisch. Sauberer waere ein Feld in struct nvkm_fifo_func, das nur nv50_fifo, g84_fifo und g98_fifo setzen. Nicht empfohlen: das Gate in 4/5 fallenlassen und klassenneutral abonnieren, das vergroessert die Angriffsflaeche unmittelbar vor der Einreichung. Die tatsaechliche Reichweite gehoert zusaetzlich in den Commit-Text von 5/5.

### 2. Use-after-free von struct nouveau_drm und drm_device: nvkm zieht den DRM-Zeiger bei jedem Fault neu aus drvdata, cancel_work_sync kommt zu spaet

**Patch:** 5/5  
**Aufwand:** mehr

**Ort:** recover.c:28-35 (nv04_fifo_drm_device, dev_get_drvdata in :32, Check nur drm && drm->dev in :34), benutzt in :40, :89, :142, :153, :157, :160; nouveau_drm.c:773 (einziges dev_set_drvdata), :735 drm_dev_put, :743 kfree(drm), :934-945 remove, :926-931 Probe-Fehlerpfad; cancel_work_sync in nvkm/engine/fifo/base.c:340 -> recover.c:175

**Warum:** Selbst nachgeprueft: dev_set_drvdata(parent, drm) steht genau einmal (nouveau_drm.c:773) und wird nirgends auf NULL zurueckgesetzt. Zwei Beine. Bein 1, schmal und konditional: zwischen drm_dev_put (:735) und dem nvkm-Fini in nvif_device_dtor (:738) lebt struct nouveau_drm noch, drm->dev zeigt aber bei letzter Referenz auf freigegebenen Speicher; der Check in recover.c:34 laesst diesen Dangling-Pointer durch, weil er nicht NULL ist. Genau die Fehlerklasse, die der Bot in v2 schon einmal gefunden hat. Bein 2, breit und unbedingt: nouveau_drm_device_remove ruft :942 fini, :943 del (dort kfree(drm) bei :743) und erst :944 nvkm_device_del. Das einzige cancel_work_sync fuer fifo->wedge.work sitzt in nv04_fifo_wedge_fini (recover.c:175), gerufen aus nvkm_fifo_dtor (base.c:340), also erst in Schritt :944. Ein zuvor per schedule_work (recover.c:132) eingereihtes Work liest in recover.c:142 den freigegebenen nouveau_drm, und zwar vor dem atomic_xchg-Fruehausstieg, also bei jedem Lauf, und uebergibt das freigegebene drm_device an dev_info (:153), an trace_nouveau_fifo_dev_wedged (:157, dessen TP_fast_assign dev_name(dev->dev) auswertet) und an drm_dev_wedged_event (:160), das dev->primary->kdev->kobj dereferenziert. Derselbe Ablauf im Probe-Fehlerpfad (fail_drm :929 vor fail_nvkm :931). Besonders bitter: Tier-2 bittet den Userspace mit DRM_WEDGE_RECOVERY_REBIND ausdruecklich um genau das Unbind, das diese Freigabe ausloest, und recover.c:131-132 reiht waehrenddessen weiter ein. Tier-2 ist per Default aktiv (fifo_wedge_count=10). Der ganze Pfad ist neu in 5/5, also kein Altbestand. KASAN und Unbind-Fuzzing treffen das.

**Fix:** Bevorzugt und zugleich Loesung des Schichtenproblems: Tier-2 vollstaendig in die DRM-Schicht heben. nvkm meldet den Fault-Burst per nvkm_event beziehungsweise Callback nach oben (der Mechanismus existiert und wird von 4/5 selbst benutzt), nouveau_drm.c besitzt Work, Modulparameter und drm_dev_wedged_event. Dann fallen nouveau_drv.h, drm_drv.h und drm_device.h aus recover.c weg und die Lebensdauer haengt an der Schicht, die sie ohnehin verwaltet. Minimalvariante, falls 5/5 jetzt mit soll: den Zeiger einmal ablegen (Feld in nvkm_fifo->wedge), erst nach erfolgreichem nouveau_drm_device_init scharf stellen, in nouveau_drm_device_fini vor drm_dev_put wieder auf NULL setzen und dort cancel_work_sync ausfuehren, dazu eine Wiedereinreihsperre (sonst reiht ein Interrupt nach dem Cancel erneut ein), dev_set_drvdata(parent, NULL) in nouveau_drm_device_del, und drm_dev_enter/drm_dev_exit um jede Nutzung. Achtung: der Probe-Fehlerpfad macht kein drm_dev_unplug, dort traegt drm_dev_enter nicht. Sinnvoll abtrennbar waere die DRM-seitige Hygiene (Reihenfolge in fini/del, drvdata-Clear) als kleiner Vorlaeuferpatch analog zu 1/5 und 2/5.

### 3. Die Serie wurde nie gegen den base-commit uebersetzt, und das steht so im Cover

**Patch:** Serie insgesamt, vor allem 5/5  
**Aufwand:** stunde

**Ort:** v3-cover-body.txt, Abschnitt 'Compile coverage, precisely' (Zeilen 209-214); betroffen sind nvkm/engine/fifo/recover.c (neue Datei), nvkm/engine/fifo/Kbuild, include/trace/events/nouveau_fifo.h (neuer Header mit TRACE_INCLUDE_PATH) und CREATE_TRACE_POINTS in nouveau_drm.c:25

**Warum:** Fuenf Patches mit neuer Datei, neuem Kbuild-Eintrag, neuem Tracepoint-Header und CREATE_TRACE_POINTS sind genau der Patchtyp, bei dem Include-Pfade und Buildflags kippen. Dazu kommt Bisect: jeder einzelne Commit muss uebersetzen, nicht nur der Endzustand. Der kernel test robot baut das ohnehin und meldet oeffentlich auf die Liste. Ein Cover, das den fehlenden Bau selbst einraeumt, liefert dem Maintainer die Standardantwort 'build it and resend' frei Haus. Der genannte Referenzbaum existiert zudem nicht mehr: unter /usr/src liegen nur 7.1.7 und 7.1.8, der im Cover benannte 7.1.6-Baum ist weg, die Compile-Aussage ist also nicht einmal nachstellbar.

**Fix:** Vollen Klon anlegen (git worktree oder frischer Klon, der sparse Checkout unter /home/neo/linux-nouveau-patches hat weder scripts/ noch include/ noch Documentation/), allmodconfig, dann jeden der fuenf Commits einzeln bauen, zusaetzlich make C=1 ueber nouveau_drm.c und die neuen Dateien. Danach den Compile-Absatz durch die tatsaechliche Aussage ersetzen.

### 4. 5/5 behauptet 'Tier-2 is fed by every fault', der Filter aus 3/5 kappt aber beide Tiers, und das Praedikat ist vom Userspace steuerbar

**Patch:** 3/5 und 5/5  
**Aufwand:** stunde

**Ort:** nv04.c:328-350 (aeusseres if bei :328-329, Benign-Filter :337-340, Recovery-Aufruf im else bei :348); Commit-Message 972c6840ec7d, Absatz Tier-2

**Warum:** Selbst nachgelesen: der Aufruf von nv04_fifo_recover() steht im else-Zweig des Filters, der wiederum im then-Zweig der swmthd-Bedingung liegt. Ein gefilterter CACHE_ERROR erreicht damit weder Tier-1 noch Tier-2. Die Commit-Message sagt woertlich das Gegenteil. Eine Begruendung, die der eigene Nachbarpatch widerlegt, ist auf den Listen ein sicherer Kommentar. Verschaerfend sind mthd und data der CACHE1-Zustand der fehlschlagenden Methode, also vollstaendig vom Userspace bestimmbar (0xbeef0201/0xbeef0202 sind Mesa-Kanalhandles). Ein Client, der dauerhaft mit (mthd & 0x1ffc)==0x0060 und (data & 0xffffff00)==0xbeef0200 faultet, wird bei Standard-Loglevel nicht sichtbar, von keinem der beiden Tiers gezaehlt und nie gekillt, obwohl jeder dieser Interrupts in nv04_fifo_intr die PFIFO-Caches fuer alle Kanaele stillsetzt. Dritter Punkt: das Praedikat ist nicht am Chip festgemacht, obwohl Kommentar und Message ausdruecklich Tesla nennen, es greift also auf allen sieben .intr-Nutzern. Vierter Punkt: 3/5 ist damit undokumentierte Vorbedingung fuer 5/5, wer 5/5 einzeln backportet, faengt sich Kanal-Kills beim Sitzungsstart ein.

**Fix:** Sauberste und zugleich kleinste Loesung: in 3/5 das Mustermatching ersatzlos durch nvkm_error_ratelimited() ersetzen (Makro in include/nvkm/core/subdev.h:94, etablierte Nutzung in subdev/bus/nv31.c:48, nv50.c:63, gf100.c:40). Dann bleibt dmesg sauber, jeder Fault erreicht Tier-1 und Tier-2, Chip-Gate und Kanalaufloesung eruebrigen sich, und der Tier-2-Satz in 5/5 wird ohne Aenderung wahr. Falls das Muster bleiben soll: device->card_type >= NV_50 ins Praedikat (device liegt vor, siehe nv04.c:320), nvkm_chan_get_chid auch im Debug-Zweig, Satz in 5/5, dass 3/5 Vorbedingung ist, und den Tier-2-Satz korrigieren. NICHT den Tier-2-Aufruf aus dem else herausziehen: das wuerde auch alle von nv04_fifo_swmthd erfolgreich behandelten Methoden und jede Mesa-Bind-Sonde in die Eskalation speisen.

### 5. 2/5 begruendet sich mit einer Aussage, die nach dem eigenen Patch falsch ist

**Patch:** 2/5  
**Aufwand:** minuten

**Ort:** nouveau_chan.c:476 (context_new) bis :501 (nvif_event_allow), Commit 948c1b7eac4b, Absatz 'Nothing is lost by that. The fence context does not exist in that window'

**Warum:** Nach dem Umbau liegt zwischen der Rueckkehr aus context_new (:476) und dem nvif_event_allow (:501) ein Abschnitt, in dem der Fence-Kontext vollstaendig gebaut ist. Fuer diesen Abschnitt ist der Satz nachweislich falsch. 'Nothing is lost by that' ist ohne Einschraenkung unhaltbar: nvkm_chan_error feuert nur auf der 0->1-Flanke (chan.c:232), und weder nvkm_uevent_add noch nvkm_uevent_mthd_allow (core/uevent.c) liefern nach. Ein im Fenster verpasster Kill hinterlaesst einen ueber nvkm_chan_block_locked dauerhaft gestoppten Kanal mit chan->killed==0 und nie signalisierten dma-fences. Zweiter, unabhaengiger Einwand: 2/5 vergroessert allein und ohne 4/5 und 5/5 ein bestehendes Fenster auf Fermi und neuer, wo der Kill-Pfad heute live ist. Der Zwischenzustand der Serie ist dort schlechter als mainline, was gegen die Regel verstoesst, dass jeder Patch fuer sich korrekt ist. Dazu die interne Asymmetrie, die ein Reviewer sofort sieht: 1/5 stuft ein 'real but narrow' Fenster auf derselben Hardware als fixwuerdig ein, 2/5 nennt ein gleich grosses harmlos. Genau diese Argumentfigur ('most of that window is harmless') hat der Bot dem Autor schon einmal widerlegt.

**Fix:** Den Absatz ehrlich fassen: das Fenster bleibt bestehen und wird auf Fermi und neuer groesser; neu ist nur, dass es keinen halbgebauten Kontext mehr trifft; ein dort verpasster Kill hinterlaesst einen gesperrten Kanal mit killed==0; das Fenster existiert schon in mainline, weil nvkm_uchan_init den Kanal bereits beim Kanal-ctor freigibt (nvkm_chan_allow und nvkm_chan_insert, uchan.c:286-299); die vollstaendige Schliessung braucht entweder spaetere chan->fence-Publikation in den Backends (nv10_fence.c:73, nv17_fence.c:86, nv50_fence.c:45, nv84_fence.c:134; nv04_fence.c:85 macht es bereits richtig) oder ein Nachziehen der Flanke beim Abonnieren in nvkm_uchan_uevent, beides ausserhalb dieser Serie. Dazu zwei Zeilen im Cover, damit nicht der Eindruck entsteht, Bot-Befund b sei restlos erledigt.

### 6. 5/5 beschreibt die Platzierung des neuen Aufrufs falsch: 'after the existing logging and reset sequence'

**Patch:** 5/5  
**Aufwand:** minuten

**Ort:** Commit 972c6840ec7d, Zeilen 15-17; Gegenbeleg nv04.c:348 gegen die Reset-Sequenz :353-365 und nv04.c:415 gegen :417-419

**Warum:** Selbst nachgezaehlt: in nv04_fifo_intr_cache_error steht der Aufruf bei :348 VOR der gesamten Reparatursequenz (DMA_PUSH=0 bei :353, Quittung :354, PUSH0-Toggle und CACHE1_GET=get+4 bei :356-360, HASH=0 bei :361, DMA_PUSH|=1 und PULL0=1 bei :363-365). Im dma_pusher-Handler steht er bei :415 nach den Zeiger-Fixups, aber vor 0x003228, 0x003220 und der Quittung 0x002100. Der Satz ist damit fuer einen Handler falsch und fuer den anderen irrefuehrend. Im Diff-Hunk stehen die Reset-Schreibzugriffe als Kontextzeilen unmittelbar unter der eingefuegten Zeile, der Widerspruch ist auf demselben Bildschirm sichtbar. Es ist ausserdem die einzige Stelle der Message, die das Verhaeltnis des neuen Aufrufs zur bestehenden Hardware-Sequenz beschreibt, also genau die Begruendung dafuer, dass er die Fault-Behandlung nicht stoert. Reihenfolge ist die Achse, auf der der Bot bereits zweimal getroffen hat.

**Fix:** Message auf die tatsaechliche Platzierung umschreiben: 'called after the existing logging, before the register reset sequence', plus ein Satz, dass auf NV50/G84/G98 nvkm_chan_error nur nv50_chan_stop ausloest (ein nvkm_mask auf 0x002600 + id*4, ohne Beruehrung von CACHE1 oder NV03_PFIFO_CACHES) und deshalb mit der folgenden Sequenz nicht kollidiert. Fuer pre-NV50 gilt das nicht, das erledigt der Guard aus Blocker 1. Den Aufruf zu verschieben ist die schlechtere Variante, weil genau die jetzige Platzierung downstream laeuft und in den Injektionslaeufen belegt ist.

### 7. 4/5: 'until the fences time out' ist mechanisch unmoeglich und widerspricht dem eigenen Absatz drei Zeilen darueber

**Patch:** 4/5 (plus zwei Cover-Stellen)  
**Aufwand:** minuten

**Ort:** v3-0004-...patch:19 gegen :22 (Commit 2cb7ce2416bb); v3-cover-body.txt:115-116 und :181

**Warum:** Die Message sagt erst korrekt, drm_atomic_helper_wait_for_fences warte 'uninterruptibly and without a timeout', und drei Zeilen spaeter, der Zustand halte 'for minutes until the fences time out'. Beides zugleich geht nicht: drm_atomic_helper.c:1855 ruft dma_fence_wait mit pre_swap=false, ttm_bo.c:240-241 wartet mit MAX_SCHEDULE_TIMEOUT, und nouveau_fence_wait_legacy ueberspringt den Timeout-Zweig bei MAX_SCHEDULE_TIMEOUT ausdruecklich. Der Absatz endet mit 'That is also a dma-fence contract violation', also genau der Aussage, die der erfundene Timeout entwertet. Ein Reviewer muss dafuer nicht in den Code schauen, der Widerspruch steht im Text. Es ist derselbe Ueberzeichnungstyp wie das in v2 bereits gestrichene 'only a reboot clears it', ein Muster, das beim Vergleich v2 gegen v3 auffaellt. Cover:181 ('nothing to do but wait minutes or reboot') widerspricht der eigenen Zeile 180 ('fences that were never signalled').

**Fix:** In 4/5: 'The user sees a frozen desktop on a machine that is otherwise alive, and nothing in the kernel ever ends that state: both waits use MAX_SCHEDULE_TIMEOUT, so the fences cannot time out. They are only signalled when the DRM client owning the channel closes its fd (postclose -> nouveau_channel_del -> nouveau_fence_context_del -> nouveau_fence_context_kill), or the machine is rebooted.' Im Cover beide Stellen analog, und dabei die Kausalitaet richtigstellen: geheilt hat der EXIT des alten labwc mit seinem fd-Teardown, nicht der Respawn durch greetd. Der zweite Vorfall (labwc lebte weiter, Reboot noetig) gehoert mit hinein, sonst schwaecht die Korrektur die Dringlichkeit unnoetig.

### 8. Generischer FIFO-Code ruft nv04_-Helfer und traegt nv04-Zustand per Wert im oeffentlichen Header

**Patch:** 5/5  
**Aufwand:** halber_tag

**Ort:** nvkm/engine/fifo/base.c:340 (nv04_fifo_wedge_fini aus nvkm_fifo_dtor) und :395 (nv04_fifo_wedge_init aus nvkm_fifo_new_); include/nvkm/engine/fifo.h:58-86 (struct nvkm_fifo_wedge) und :119 (per Wert in struct nvkm_fifo); nvkm/engine/fifo/chan.c:294-303

**Warum:** In nvkm ist der Praefix die Schichtungsgrenze. In mainline (c21bb4193868) enthaelt engine/fifo/base.c keinen einzigen nvXX_-Aufruf; diese Serie setzt die ersten zwei, und sie sind beim Ueberfliegen des Diffs sofort sichtbar. Das ist bei Ben Skeggs und Danilo Krummrich eine Rework-Bitte, kein Nit. Gestuetzt wird das durch die Wertsemantik: struct nvkm_fifo_wedge steht im oeffentlichen fifo.h, den 35 Dateien einbinden, obwohl alle drei Nutzer priv.h einbinden, und sie waechst struct nvkm_fifo von rund 408 auf rund 3792 Byte, also von kmalloc-512 auf kmalloc-4096, einmal pro GPU. Das gilt auch fuer Fermi bis Blackwell und die GSP-verwalteten Chips ueber r535_fifo_new -> nvkm_fifo_new_, wo nv04_fifo_recover nie laeuft und die Felder dauerhaft Null bleiben. Nicht als Argument fuehren: den Spinlock in nvkm_chan_del (kalter Pfad, kostet nichts Messbares) und das Modulo (auf allen Chips, wo der Pfad laeuft, ist chid kleiner oder gleich 128, es aliast nie).

**Fix:** Wedge-Zustand per Zeiger in struct nvkm_fifo fuehren, Strukturdefinition nach nvkm/engine/fifo/priv.h verschieben (NVKM_FIFO_WEDGE_RING_MAX muss im oeffentlichen Header bleiben, nouveau_drm.c:1515 klemmt daran), und nur fuer die Chips allozieren, deren .intr nv04_fifo_intr ist. struct nvkm_fifo_func hat keinen .ctor-Haken, praktikabel sind ein Flag beziehungsweise Funktionszeiger in nvkm_fifo_func oder die Allokation in oneinit (dann faellt die feste 128 samt Modulo weg, der dtor muss wedge==NULL vertragen). Helfer in nvkm_fifo_wedge_init/fini umbenennen oder besser hinter einen optionalen func-Hook haengen. Wichtig: mit Zeiger braucht nicht nur nvkm_chan_del einen Guard, sondern auch nv04_fifo_recover (recover.c:48 und :114) ein if (!fifo->wedge) return; der Pfad laeuft im Interrupt. In 5/5 hineinfalten, kein eigener Patch.

### 9. Modulparameter ohne sichtbare Deklaration am Definitionsort: der kernel test robot meldet das per make C=1

**Patch:** 5/5  
**Aufwand:** minuten

**Ort:** Definition nouveau_drm.c:119-129 (Variablen :122 und :128), einzige extern-Deklaration in nvkm/engine/fifo/priv.h:93-94, das nouveau_drm.c nicht einbindet

**Warum:** Selbst geprueft: nouveau_drm.c zieht nouveau_drv.h (:58), <engine/fifo.h> (:79) und den Trace-Header (:80); keiner davon deklariert die beiden Symbole, priv.h wird nicht eingebunden. Am Definitionsort ist damit keine Deklaration sichtbar, es gibt keine Compile-Zeit-Gegenprobe zwischen Definition und der Deklaration, gegen die recover.c gebaut wird, und sparse meldet 'symbol nouveau_fifo_wedge_count was not declared. Should it be static?'. Der kernel test robot faehrt make C=1 auf DRM-Postings und schickt den Text oeffentlich auf die Liste, meist binnen ein bis zwei Tagen. Das ist der einzige Punkt der Serie mit Bot-Gewissheit. Nicht behaupten, GCC oder W=1 schlage an: der Kernel setzt -Wmissing-variable-declarations nirgends, der immer aktive Satz in scripts/Makefile.warn:21-22 betrifft nur Funktionen. Zweiter Teil desselben Hunks: die beiden Parameter sind neue benutzersichtbare ABI, werden aber weder in der Commit-Message von 5/5 noch im Cover mit Name, Default, Wertebereich und Begruendung genannt.

**Fix:** Die beiden externs von nvkm/engine/fifo/priv.h nach drivers/gpu/drm/nouveau/nouveau_drv.h ziehen, dorthin, wo nouveau_modeset steht (Definition nouveau_drm.c:108, extern nouveau_drv.h:368); recover.c bindet nouveau_drv.h ohnehin schon ein. priv.h behaelt nur die Funktionsprototypen. Zusaetzlich fifo_wedge_count und fifo_wedge_window_ms mit Name, Default, Wertebereich und Begruendung im Commit-Text von 5/5 nennen. Faellt komplett weg, wenn Tier-2 in die DRM-Schicht wandert, dann koennen die Parameter static werden.

### 10. 1/5 und 2/5 ohne Fixes: und Cc: stable, obwohl sie sich selbst als Fehlerbehebungen fuer Fermi und neuer beschreiben

**Patch:** 1/5 und 2/5  
**Aufwand:** minuten

**Ort:** v3-0001-...patch:33-34 und v3-0002-...patch:43-44 (jeweils nur Assisted-by und Signed-off-by); grep ueber alle fuenf Patches: null Treffer fuer Fixes, Cc: stable, Link oder Closes

**Warum:** 1/5 sagt woertlich 'On Fermi and newer the window is real but narrow', 2/5 beschreibt den Zugriff auf einen nie initialisierten Spinlock und einen NULL-Listenkopf. Damit behaupten die Patches selbst, in ausgelieferten Kerneln einen Defekt zu beheben. Fuer diese Klasse fragt ein drm-Maintainer verlaesslich nach dem Fixes-Tag, und der einzige Grund, 1/5 und 2/5 als eigenstaendige Vorarbeiten vor 4/5 zu ziehen statt sie einzufalten, ist ihre unabhaengige Anwendbarkeit. Ohne Tag verschenkt die Serie genau den Vorteil, fuer den sie so geschnitten wurde. Die Erreichbarkeit ist ausserdem groesser als die Patches einraeumen: nvkm_runl_rc (runl.c:79-82) ruft nvkm_chan_error fuer jeden Kanal einer geflaggten cgrp, gespeist aus gf100.c:343, gv100.c:158, ga100.c:205/244. Ein Fault eines fremden Kanals trifft also auch den Kanal, der gerade initialisiert oder abgebaut wird. Bei der NVAC-Serie im Juni wurde getagged (Cc: stable # v6.16+), hier nicht.

**Fix:** Ziel im vollen Klon bestimmen und dann setzen. Kandidat ist ea13e5abf807 ('drm/nouveau: signal pending fences when channel has been killed', v5.6), weil erst dieser Commit den Handler chan->fence dereferenzieren laesst; d8cc37d878d6 (2016) setzte nur atomic_set(&chan->killed, 1) und war ungefaehrlich. Nicht ueber 'abi16ChanKilled' suchen, der String stammt erst vom spaeteren nvif_event-Umbau und liefert das falsche Ziel; besser git log -S'nouveau_channel_killed' und git log --follow -p -- nouveau_chan.c. Blankes Cc: stable@vger.kernel.org genuegt bei korrektem Fixes-Tag, die Versionsannotation weglassen. Zusaetzlich ein Satz im Cover, dass 1/5 und 2/5 fuer sich stehen und gern separat ueber drm-misc-fixes gehen koennen, das nimmt der Standardantwort 'schick die Fixes bitte separat' die Spitze. Und im Text von 1/5 und 2/5 den Weg ueber nvkm_runl_rc nennen, damit die Erreichbarkeit belegt statt behauptet ist.

### 11. Cover: die versandfaehige .patch-Datei ist die veraltete Fassung und traegt eine vom Autor selbst widerlegte Behauptung

**Patch:** Cover  
**Aufwand:** minuten

**Ort:** v3-0000-cover-letter.patch (Stand 13:44) gegen v3-cover-body.txt (15:31); Abschnitt Testing, Bullet 'What does not survive is the client', .patch-Zeilen 159-165

**Warum:** Selbst per diff geprueft: die beiden Dateien weichen in genau zwei inhaltlichen Bloecken ab. Die .patch-Fassung behauptet weiterhin 'The killed channel belonged to Xwayland, and in both runs Xwayland and the compositor exited; the session came back about fifteen seconds later. That is the trade this series makes.' Genau das ist widerlegt: /home/neo/nvac-v2-qa/labwc-control-20260812T135529/run.log zeigt labwc mit unveraenderter PID 76849 ueber 100 s, wlopm antwortet durchgehend, fence_wait=0, und die Schlusszeile lautet 'Signale an labwc/Xwayland waehrend des Laufs: 0'. Der Compositor-Abschuss kam vom eigenen Waechter. Wird die .patch per git send-email verschickt (der uebliche Ablauf, sendemail ist im Baum vollstaendig konfiguriert), geht die als falsch erkannte Fassung an nouveau, dri-devel und lkml, und zwar ausgerechnet die Aussage, an der ein Maintainer die Serie kippt oder hinter einen Modulparameter schiebt. lore ist ein dauerhaftes Archiv, eine Richtigstellung braucht spaeter ein v4. Der Pflegeabriss ist punktgenau nachweisbar: Commit ab38de3 pflegte noch beide Dateien, der letzte Korrektur-Commit 2b11611 fasst nur noch den Body an. Verschaerfend behauptet SUBMISSION-STATUS.md in Fettschrift, der Cover sei korrigiert und v3 versandbereit, damit faellt der letzte Schutz, das menschliche Gegenlesen, mit hoher Wahrscheinlichkeit aus.

**Fix:** Minimalinvasiv: die beiden abweichenden Bloecke im vorhandenen v3-0000-cover-letter.patch ersetzen, unterhalb der Header-Zeilen und oberhalb von Shortlog, Diffstat und base-commit. Nicht blind neu generieren: in /home/neo/linux-nouveau-patches ist keine branch.description und keine format.*-Konfiguration gesetzt, ein git format-patch --cover-letter liefert Platzhalter-Betreff und keine base-commit-Zeile. Wer neu generiert, braucht --base=c21bb4193868 und muss die Subject-Zeile von Hand wiederherstellen. Danach Pflichtpruefung: diff der beiden Dateien darf nur noch From/Date/Subject, Shortlog, Diffstat und base-commit uebriglassen, und git send-email --dry-run mit Volltext genau dieser Datei gegenlesen, nicht des Body-Files.

### 12. Cover widerspricht sich selbst: der Abschnitt 'AI assistance' erklaert Patch 1/5 fuer ueberzogen und fallengelassen

**Patch:** Cover  
**Aufwand:** minuten

**Ort:** v3-cover-body.txt:241-247 und v3-0000-cover-letter.patch:224-230, gegen v3-cover-body.txt:9-12, :33-35 und :251

**Warum:** Der Absatz steht wortgleich in beiden Fassungen und ist unveraendert aus nv04-fifo-v2/v2-cover-body-korrigiert-2026-08-04.txt:178-184 uebernommen. Er sagt: 'a first draft of this cover letter described the fence-context teardown ordering in nouveau_channel_del() as a use-after-free worth its own patch. On closer inspection most of that window is harmless ... I dropped that patch rather than send an overstated claim. If you would still like the reordering as a hardening change, I can send it separately.' Genau diese Umsortierung liegt als 1/5 im selben Umschlag (Commit ad3858e00edf), und acht Zeilen weiter unten listet 'Changes since v2' sie als neu. Eine wohlwollende Lesart gibt es nicht, das Angebot 'I can send it separately' schliesst aus, dass 'first draft' den v3-Entwurf meint. Die Rahmung als altes v2-Material traegt ebenfalls nicht, weil derselbe Block fuer v3 punktuell nachgezogen wurde (:124-128, :156-182, und :179 traegt bereits die neue Nummerierung 'Before 2/5'), nur dieser Absatz nicht. Der Ort ist der schlimmstmoegliche: der AI-Abschnitt ist der einzige Teil des Covers, von dem sicher ist, dass er gelesen wird, weil Lyude im v1-Thread danach gefragt hat und coding-assistants.rst dort die Zusicherung verlangt, das Ergebnis geprueft und verstanden zu haben. Ein stehengebliebener Copy-Paste-Block, der der eigenen Serie widerspricht, ist der empirische Gegenbeweis zu dieser Zusicherung. Nebenbei liefert er in der Stimme des Autors das Gegenargument zu 1/5 frei Haus.

**Fix:** Absatz in beiden Fassungen ersatzlos streichen, ohne Ersatzformulierung; die Selbstkorrektur steht in Zeilen 33-35 bereits sauber und an der richtigen Stelle. Weil das Streichen sonst eine Luecke hinterlaesst: die Kurzfassung zu 1/5 in Zeilen 9-12 an die Formulierung der Commit-Message angleichen, also die Enge des Fensters auch im Cover nennen, statt die Behauptung dort in ihrer staerksten Form stehen zu lassen. Ausserdem im selben Zug v3-cover-body.txt:226 aktualisieren, dort steht noch 'claude-opus-4-7 for v1, claude-opus-5 for v2', v3 fehlt.

### 13. Cover: durchgehend die alte Dreier-Nummerierung in einer Fuenfer-Serie, und die eine renummerierte Stelle ist falsch abgebildet

**Patch:** Cover  
**Aufwand:** minuten

**Ort:** v3-cover-body.txt:45, :74, :90, :101, :152, :204, :215, :262-267 (x/3) gegen :179 ('Before 2/5'); in v3-0000-cover-letter.patch dieselben Stellen bei :50, :79, :95, :106, :154, :162, :187, :198

**Warum:** Selbst per grep geprueft. Drei Stellen beziehen sich ausdruecklich auf DIESE Einreichung und loesen auf den falschen vorhandenen Patch auf: :204 'Patch 2/3 as posted does it unconditionally' meint die verbreiterte Subscription, das ist 4/5, zeigt aber auf 2/5 (den Fence-Kontext-Fix); :215 'Patch 3/3 adds a new file recover.c' zeigt auf 3/5, den Log-Filter, der gar keine Datei anlegt; :101 traegt das Abhaengigkeitsargument der Serie, also genau die Stelle, an der ein Maintainer die Reihenfolge nachrechnet. Dazu der Selbstwiderspruch im selben Testing-Block: :152 sagt 'before patch 2/3', :179 'Before 2/5' ueber denselben Patch. Und :179 ist zusaetzlich falsch renummeriert, das Freeze-Verhalten behebt 4/5, nicht 2/5; hier wurde die Nenner-Ziffer stumpf ersetzt, statt auf die neue Position abzubilden. Das ist schlechter als eine durchgehend alte Zaehlung, weil ein Reviewer die Zahl fuer geprueft haelt.

**Fix:** Stellen, die diese Einreichung beschreiben, hart umnummerieren: :152 auf 2/5, :179 auf 4/5, :204 auf 4/5, :215 auf 5/5. Den Zitatblock ab :41 nicht durchnummerieren, sondern uebersetzen ('fixed in 3/3 [now 5/5]', 'new patch 2/3 [now 4/5]'), weil die Ueberschrift :43 'how v2 addresses it' lautet und reine v3-Zahlen darunter einen neuen Widerspruch erzeugen. Block 'Changes since v1' (:262-267) in alter Zaehlung belassen, aber mit dem Halbsatz 'numbering as posted in v2' (nicht v1, die dort gelisteten Patches sind die v2-Patches). Nicht anfassen: :135, :136, :149 ('fault 1/3'), das sind Fehlerzaehler aus dem Log, und v3-thread-reply.txt:38, das ist eine Antwort im v2-Thread. Ausserdem die Rahmenzeile :41 anpassen, sie sagt 'The original v1 report follows', es folgt aber der v2-Cover.

### 14. Cover: die als Beweis zitierten dmesg-Zeilen kann der eingereichte Code nicht erzeugen, und sie stammen aus einem dritten Lauf

**Patch:** Cover (belegt 5/5)  
**Aufwand:** stunde

**Ort:** v3-cover-body.txt:135-138 und :149 (identisch v3-0000-cover-letter.patch:137-140) gegen recover.c:99-102

**Warum:** Selbst verglichen. Das Cover zitiert 'ch 5 fault 1/3 in 10000ms window, skipping method and resuming (Tier-0)'. Der eingereichte Code formatiert an dieser Stelle 'ch %d fault %u/%u within %ums, resuming' (recover.c:99-102), also ohne 'in ... window', ohne 'skipping method' und ohne '(Tier-0)'. Der zitierte Wortlaut stammt aus dem Downstream-Baum. Verschaerfend kennt die Serie gar keinen Tier-0: Commit-Message und Dateikopf sprechen nur von Tier-1 und Tier-2. Zweitens stammen die zitierten PIDs (fbo-stress[13247], Xwayland[4931]) nicht aus den beiden mitgelieferten Protokollen (dort 61942/5660 bzw. 69347/63924), sondern aus injection-proof-2026-07-25.log, und die '18 seconds' in :149 ergeben nur dieser Lauf; im mitgelieferten Lauf vom 06.08. sind es 22 Sekunden. Drittens laesst der Auszug die zweite 1/3-Zeile weg, die den Fensterablauf ueberhaupt erst belegt: der Beleg zeigt nicht, was zwoelf Zeilen darunter behauptet wird, und das ist ohne jeden Logzugriff sichtbar. Bei einer Serie, die zweimal Bot-Befunde kassiert hat und ihre KI-Assistenz offenlegt, ist ein nicht reproduzierbares dmesg-Zitat das billigste Eigentor.

**Fix:** Am saubersten: den Injektionslauf einmal mit dem eingereichten Stand plus lokalem Injektor wiederholen und die echten Zeilen zitieren, mit dem ausdruecklichen Halbsatz, dass nur der Injektor zusaetzlich im Baum liegt (er ist Downstream-only und nicht Teil der Serie, das sagt das Cover an anderer Stelle bereits). Sonst: den Block vollstaendig aus injection-proof-2026-08-06.log uebernehmen (beide 1/3-Zeilen, mit Zeitstempeln), die '18' auf '22' setzen, und die Zeilen unmittelbar am Zitat als Downstream-Ausgabe kennzeichnen mit Angabe des Upstream-Formatstrings. Dieselbe Herkunftspruefung auf alle Beweisbloecke anwenden, auch auf den ftrace-Block und den Kontrolllauf: jede zitierte Zeile mit Datei und Lauf belegen. Beim Kontrolllauf nicht den 'Kernel-Seite'-Block aus run.log uebernehmen, dessen erste Zeile stammt aus dem 13:49-Kill-Lauf.

### 15. Cover: Soak-, Kernel- und Abweichungsangaben sind auf den v2-Versandtag eingefroren, und die einzige relevante Downstream-Abweichung ist nicht genannt

**Patch:** Cover  
**Aufwand:** stunde

**Ort:** v3-cover-body.txt:194-195 ('twelve days as of this posting', '7.1.5 to 7.1.6'), :206 ('for those twelve days'), :210 ('downstream 7.1.6 tree'), :201-207 ('One difference between the soaked code and the diff below'), :155-156 ('the display commit never had to fall back to any timeout')

**Warum:** 25.07. plus zwoelf Tage ergibt den 06.08., also den v2-Versandtag; v3 geht am 12.08. raus, das sind 18 Tage. Die Maschine laeuft auf 7.1.8 (uname, /proc/cmdline und die Kopfzeilen der Laeufe vom 12.08.), die Spanne ist 7.1.5 bis 7.1.8. Einen 7.1.6-Baum gibt es unter /usr/src nicht mehr, die Compile-Aussage ist also nicht nachstellbar. Dieselbe Fehlerklasse stand schon in der v2-Pruefung (COVER-PRUEFUNG-2026-08-04.md, Punkt 6), zum dritten Mal ist es ein Muster im Arbeitsablauf. Schwerer wiegt der Abschnitt 'One difference': er nennt nur das Modulparameter-Gate der Subscription, verschweigt aber die eine Abweichung, die die Argumentation der Serie beruehrt. Die Referenzmaschine traegt nouveau_disp_fence_timeout_ms mit Default 10000, das in dispnv50/disp.c den Fence-Wait im nonblocking Commit-Tail nach 10 s abbricht und trotzdem flippt. Genau dieses unbegrenzte Warten ist die Freeze-Kausalkette der Serie, das lokale Netz haette den Freeze also auch ohne 2/5 und 4/5 abgefangen. Folgerichtig beschreibt der Satz in :155-156 einen Fallback, den Mainline gar nicht hat, und verraet damit den lokalen Patch, statt ihn zu erklaeren. Wer eine Abweichung ausdruecklich aufzaehlt, erzeugt beim Leser die Annahme, die Liste sei vollstaendig.

**Fix:** Absolute statt relativer Angaben: '2026-07-25 to 2026-08-12, across the bumps from 7.1.5 to 7.1.8 with the patch series unchanged', :206 mitziehen, :210 auf 7.1.8. Dabei ehrlich trennen: der v2-Stand laeuft seit 25.07., die v3-Deltas (0023 und 0024, also 2/5 und der Umbau in 5/5) erst seit 06.08. Den 'One difference'-Absatz durch drei Saetze ersetzen: Schwellen liegen downstream als Modulparameter vor, mit denselben Defaults 3 und 10000 wie die eingereichten Konstanten, also verhaltensgleich; die Subscription ist downstream zusaetzlich abschaltbar; die Referenzmaschine traegt ausserdem lokale Display- und Debug-Patches, davon beruehrt nur der begrenzte Plane-Fence-Wait die hier argumentierte Fehlerkette. Den Satz in :155-156 auf das umschreiben, was gemessen wurde (kein Prozess in dma_fence_default_wait an den vier Samples), und 'across two runs', 'TTM worker in D state' und die unbelegte 'twelve' streichen. Optional, aber es macht den schwaechsten Punkt der Evidenz zum staerksten: die Injektion einmal mit nouveau.disp_fence_timeout_ms=0 wiederholen und diesen Lauf zitieren.

## Aufgabenliste vor dem Senden (25)

1. Cover, v3-cover-body.txt:241-247 und v3-0000-cover-letter.patch:224-230: den AI-Absatz mit 'I dropped that patch rather than send an overstated claim' ersatzlos streichen. Sieben Zeilen, null Risiko.

2. Cover, v3-cover-body.txt:226: 'claude-opus-4-7 for v1, claude-opus-5 for v2' um v3 ergaenzen.

3. Cover, v3-cover-body.txt:9-12: Kurzfassung zu 1/5 an die Formulierung der Commit-Message angleichen (Fenster ist real, aber eng), damit Cover und 1/5 nicht auseinanderlaufen.

4. Cover, v3-cover-body.txt:45, :74, :90, :101, :152, :179, :204, :215: Nummerierung geradeziehen. :152 auf 2/5, :179 auf 4/5 (steht heute falsch auf 2/5), :204 auf 4/5, :215 auf 5/5; den Zitatblock ab :41 als '[now x/5]' uebersetzen; :262-267 belassen mit dem Zusatz 'numbering as posted in v2'; Rahmenzeile :41 anpassen ('The original v1 report follows', es folgt aber der v2-Cover). Nicht anfassen: :135, :136, :149 (Fehlerzaehler) und v3-thread-reply.txt.

5. Cover, v3-cover-body.txt:115-116 und :181 sowie 4/5 (v3-0004-...patch:22): 'until the fences time out' streichen. Beide Waiter sind MAX_SCHEDULE_TIMEOUT; signalisiert wird erst beim fd-Teardown des Kanalbesitzers oder beim Reboot. Kausalitaet richtigstellen (der Exit von labwc heilte, nicht der Respawn) und den zweiten Vorfall mit noetigem Reboot nennen.

6. Cover, v3-cover-body.txt:194-195, :206, :210: Soak-Angaben auf absolute Daten ziehen (2026-07-25 bis 2026-08-12, Bumps 7.1.5 bis 7.1.8, downstream 7.1.8 tree). Dabei v2-Stand seit 25.07. von den v3-Deltas seit 06.08. trennen.

7. Cover, v3-cover-body.txt:155-156 und :201-207: den Satz zum 'timeout fallback' streichen (Mainline hat keinen), 'across two runs' und 'TTM worker in D state' auf die tatsaechlich gemessene fence_wait-Reihe zuruecknehmen, die unbelegte 'twelve' entfernen, und den 'One difference'-Absatz um die drei realen Abweichungen ergaenzen, vor allem um nouveau_disp_fence_timeout_ms.

8. 5/5, Commit-Text: 'after the existing logging and reset sequence' ersetzen durch 'after the existing logging, before the register reset sequence', plus Erklaerung fuer nv50_chan_stop.

9. 5/5, Commit-Text: 'Tier-2 is fed by every fault, including those Tier-1 lets pass' korrigieren oder durch die 3/5-Umstellung auf nvkm_error_ratelimited() wieder wahr machen; falls das Muster bleibt, zusaetzlich einen Satz, dass 3/5 Vorbedingung fuer 5/5 ist.

10. 5/5, Commit-Text: fifo_wedge_count und fifo_wedge_window_ms mit Name, Default, Wertebereich und Begruendung nennen; und die Begruendung nachtragen, warum die Tier-1-Schwellen fest statt tunbar sind (der Cache-Puller-Kommentar in fifo.h:57-63 begruendet nur, warum ein Fault nicht reicht).

11. 2/5, Commit-Text: den Absatz 'Nothing is lost by that. The fence context does not exist in that window' durch die ehrliche Fassung ersetzen (Fenster bleibt, wird auf Fermi+ groesser, ein verpasster Kill hinterlaesst einen gesperrten Kanal mit killed==0, Grundproblem liegt in nvkm_uchan_init und in der chan->fence-Publikation der Backends).

12. 5/5, recover.c:145-149: den !drm_dev-Check vor das atomic_xchg ziehen, damit der Ein-Schuss-Schalter nicht ohne Ereignis verbraucht wird, und den Kommentar von 'already wedged this cycle' auf 'one uevent per bind, cleared only in nv04_fifo_wedge_init()' aendern (dito fifo.h:76). NICHT den Rueckgabewert von drm_dev_wedged_event pruefen (nicht __must_check, kein in-tree-Aufrufer tut es) und NICHT das Flag im Fehlerfall freigeben (macht aus dem gewollten Ein-Schuss eine vom Fault-Strom getriebene Wiederholschleife). Nebenbei: fault_count = w->count (recover.c:151) liest den Ringzaehler ohne w->lock.

13. 5/5, nouveau_drm.c:25: CREATE_TRACE_POINTS von ganz oben direkt vor '#include <trace/events/nouveau_fifo.h>' (:80) ziehen. 47 Zwischen-Includes sind der groesste Abstand im ganzen Baum (naechster: mm/cma.c mit 13). Zulaessig, aber es provoziert eine Rueckfrage und kostet eine Zeile Diff. Zuender existiert konkret: nouveau_fence.c:30 zieht bereits <trace/events/dma_fence.h>, und nouveau_drm.c bindet nouveau_fence.h bei :69 ein.

14. 5/5: den Trace-Header aus drivers/gpu/drm/nouveau/include/trace/events/ herausnehmen und flach neben die Quelle legen (Muster drm_trace.h, i915_trace.h, amdgpu_trace.h, xe_trace.h). Es waere sonst das einzige private include/trace/events-Schattenverzeichnis im ganzen Kernel, und das faellt einem Maintainer eher auf als die Define-Position.

15. 5/5, nvkm/engine/fifo/priv.h:93-94: die beiden extern-Deklarationen nach nouveau_drv.h ziehen; priv.h behaelt nur die Funktionsprototypen. Behebt den sicheren sparse-Befund des kernel test robot.

16. 1/5 und 2/5: Fixes-Tag setzen, Ziel im vollen Klon bestimmen (Kandidat ea13e5abf807, v5.6), dazu blankes Cc: stable@vger.kernel.org, und im Text den Erreichbarkeitspfad ueber nvkm_runl_rc (runl.c:79-82, gespeist aus gf100.c:343, gv100.c:158, ga100.c:205/244) nennen. Ein Satz im Cover, dass beide fuer sich stehen und gern separat ueber drm-misc-fixes gehen koennen.

17. 5/5, recover.c am Funktionsanfang: Guard 'if (fifo->engine.subdev.device->card_type != NV_50) return;' einziehen und die tatsaechliche Reichweite in die Commit-Texte von 5/5 und 4/5 schreiben.

18. 5/5: struct nvkm_fifo_wedge nach nvkm/engine/fifo/priv.h verschieben, in struct nvkm_fifo nur einen Zeiger halten, nur fuer die Chips mit .intr = nv04_fifo_intr allozieren, Helfer in nvkm_fifo_wedge_init/fini umbenennen oder hinter einen func-Hook haengen. NVKM_FIFO_WEDGE_RING_MAX bleibt im oeffentlichen Header (nouveau_drm.c:1515). Guards fuer wedge==NULL in nvkm_chan_del UND in nv04_fifo_recover (recover.c:48 und :114), der Pfad laeuft im Interrupt.

19. 5/5: die Lebensdauer des drm_device in Ordnung bringen. Bevorzugt Tier-2 komplett in die DRM-Schicht heben (loest UAF, Schichtenfrage und die externs in einem Zug), sonst mindestens abgelegter Zeiger, Nullen plus cancel_work_sync in nouveau_drm_device_fini vor drm_dev_put, Wiedereinreihsperre, dev_set_drvdata(parent, NULL) in nouveau_drm_device_del und drm_dev_enter/exit um jede Nutzung.

20. 3/5: das Mustermatching durch nvkm_error_ratelimited() ersetzen (include/nvkm/core/subdev.h:94, Praezedenz subdev/bus/nv31.c:48, nv50.c:63, gf100.c:40). Damit entfaellt die userspace-steuerbare Umgehung der Eskalation, das Chip-Gate und die verlorene Kanalaufloesung, und der Tier-2-Satz in 5/5 wird ohne Aenderung wahr. Falls das Muster bleibt: card_type >= NV_50 ins Praedikat und nvkm_chan_get_chid auch im Debug-Zweig. 3/5 zusaetzlich um zwei bis drei echte dmesg-Zeilen ergaenzen; das Material liegt in /home/neo/fab-443-logs/nouveau-full.log und /home/neo/fab-lag-log/, und die Beobachtung gehoert der Tester-Maschine zugeschrieben (mit dessen Einverstaendnis Reported-by beziehungsweise Tested-by), nicht dem eigenen Mac mini.

21. Vollen (nicht sparsen) Klon anlegen, allmodconfig, jeden der fuenf Commits einzeln bauen, dazu make C=1 und checkpatch --strict. Erst danach den Compile-Absatz im Cover neu schreiben.

22. Cover neu erzeugen beziehungsweise die beiden abweichenden Bloecke in v3-0000-cover-letter.patch einsetzen. Abnahme: diff gegen v3-cover-body.txt darf nur From/Date/Subject, Shortlog, Diffstat und base-commit uebriglassen; grep auf 'That is the trade this series makes' und auf '/3' im Messteil muss leer sein; grep auf '82575' muss leer sein, '76295' und '5378' muessen vorkommen.

23. Versand: git send-email zwingend mit --from='Marek Czernohous <mczernohous@gmail.com>' fahren, weil sendemail.from in /home/neo/linux-nouveau-patches/.git/config auf marek@czernohous.de steht und smtpuser das Gmail-Konto ist. Ohne --from unterbleibt die In-Body-From-Zeile, Gmail schreibt den Header trotzdem um, und auf lore stuende ein From, das nicht zum Signed-off-by passt (checkpatch FROM_SIGN_OFF_MISMATCH auf allen fuenf Patches). Nach dem Dry-Run pruefen: Message-Id endet auf '-mczernohous@gmail.com', jede Patch-Mail hat als erste Rumpfzeile 'From: Marek Czernohous <marek@czernohous.de>'.

24. v3-thread-reply.txt NICHT nochmal senden. Die Mail ist am 06.08. um 12:01 raus (Commit 1d26d2e, Result 250) und war damals korrekt; ihr Schlusssatz 'with the remaining three unchanged apart from the rebase' ist inzwischen falsch, weil 5/5 den dritten Fix traegt. Das Cover erledigt die Fortschreibung bereits (:38-39).

25. Nach dem Versand: sendemail.smtppass steht im Klartext in /home/neo/linux-nouveau-patches/.git/config. Entfernen und das App-Passwort im Google-Konto rotieren.

## Von der Gegenprüfung verworfen (12)

Nicht erneut aufgreifen, das kostet nur Zeit.

1. drm_dev_wedged_event dereferenziere vor drm_dev_register einen NULL-kdev: selbst nachgeprueft, minor->kdev entsteht in drm_minor_alloc (drm_drv.c:167), das aus drm_dev_init und damit aus drm_dev_alloc laeuft; drm_minor_register macht nur device_add. kdev ist nie NULL, und nach dem Unplug wird es nur per device_del deaktiviert, nicht genullt.

2. Das Tier-2-Flag sei durch den !drm_dev-Zweig dauerhaft tot: der Zweig ist zur Laufzeit nicht erreichbar, weil dev_set_drvdata (nouveau_drm.c:773) vor jeder nvkm-Device-Init und vor dem Interrupt-Rearm steht und nach dem Teardown der Zeiger nicht NULL, sondern baumelnd ist. Bleibt reine Haertung, siehe Checkliste.

3. Die UAF-Beschreibung in 1/5 sei unhaltbar, weil alle Backends chan->fence vor der Freigabe nullen: 'context_del()' in der Message meint den Backend-Callback, den die Message zwei Zeilen darueber woertlich zitiert, und der ruft nouveau_fence_context_free(), also kfree. Der Text ist richtig; hoechstens ein Halbsatz zur Verschraenkung waere ein Gewinn, die vorgeschlagene Neufassung waere sachlich schwaecher.

4. Die Serie muesse in Fixes-Serie und Feature-Serie aufgeteilt werden: 1/5 und 2/5 stehen bereits am Kopf und sind einzeln entnehmbar. Ein erzwungener Split erzeugt eine Cross-Branch-Abhaengigkeit (4/5 haengt am von 2/5 verschobenen Block, 5/5 am von 3/5 angelegten else-Zweig). Angebot ins Cover schreiben, Reihenfolge 1 bis 5 so lassen.

5. Reported-by fuer den Sashiko-Bot in den Commits: submitting-patches.rst empfiehlt nur, checkpatch verlangt bei gesetztem Reported-by unmittelbar ein Closes: oder Link: mit URL (BAD_REPORTED_BY_LINK), und weder Anzeigename noch Adresse noch eine lore-Message-Id des Bots sind im Material belegt. Fuer 5/5 waere der Tag ohnehin falsch, weil der beanstandete Code nie im Baum stand.

6. Absenderwechsel zwischen v2 und v3 als DKIM-Problem: die From-Zeile der format-patch-Dateien war schon in v2 und in der Juni-Serie czernohous.de, und git send-email setzt bei --from automatisch eine In-Body-From-Zeile (git-send-email:2081). Bleibt allein der Checklistenpunkt, das --from nicht zu vergessen.

7. 3/5 habe keinerlei Artefakt fuer die beef02xx-Sonde: die Zeilen existieren, 99 Stueck, in /home/neo/fab-443-logs/nouveau-full.log (65), kernel-7.0.10-1~bpo13+1.log (21) und /home/neo/fab-lag-log/kernel-6.12.90-...log (13), erhoben auf einer unabhaengigen MCP79/MCP7A-Maschine unter Xorg, kwin_x11, kwin_wayland, plasmashell und ksplashqml. 3/5 nicht zuruecknehmen, nur belegen.

8. Der Soak sei entwertet, weil Chrome mit --disable-gpu laufe: der User-Override wurde am 25.07. um 16:53 geloescht, also exakt zum Soak-Start; im Soak lief Chrome hardwarebeschleunigt und hat nachweislich GR-Traps auf echten Kanaelen erzeugt. Der Satz im Cover stimmt und ist eher zu staerken als zu entschaerfen.

9. Der ftrace-Auszug sei aus zwei Laeufen zusammengesetzt: in v3-cover-body.txt (15:31) bereits behoben, beide Zeilen stammen aus labwc-kill-20260812T134929/trace.txt und der Text sagt es ausdruecklich. Beim Neu-Erzeugen des Covers darf die Korrektur nur nicht verlorengehen.

10. Der Kontrolllauf widerspreche der D-State-Aussage: die aktuelle Fassung sagt fuer den Kontrolllauf nur noch 'no worker in dma_fence_default_wait at any sample', und das ist durch alle sieben Messpunkte gedeckt. Den einen D-State-Treffer bei +5 s NICHT nachtraeglich ins Cover schreiben, er ist Rauschen aus einem systemweiten Zaehler. Offen bleibt nur der Injektionsteil (siehe Checkliste).

11. Die Mesa-Angabe kehre die Beweislage um: in v3-cover-body.txt:123-128 bereits entschaerft, Mesa ist dort ausdruecklich als nicht kontrollierte Variable ausgewiesen. Offen ist nur die Kernelversion im selben Abschnitt.

12. Die vorbereitete Thread-Antwort muesse korrigiert werden: sie ist am 06.08. bereits versendet und nicht mehr aenderbar, und sie war zum Absendezeitpunkt korrekt (der dritte Befund entstand acht Minuten spaeter). Nur nicht nochmal senden.

## Was diese Prüfung NICHT leisten konnte (10)

Hier sitzt das Restrisiko.

1. Kein Bau. /home/neo/linux-nouveau-patches ist ein sparse und shallow Checkout ohne scripts/, include/ und Documentation/. Es gibt daher keine Aussage zur Uebersetzbarkeit der Einreichungsfassung, keinen Bisect-Bau der fuenf Zwischenstaende, keinen sparse- oder W=1-Lauf, keine Pruefung des Kbuild-Eintrags und keine Pruefung, ob der neue Tracepoint-Header in einem echten Mainline-Baum aufloest. Genau dort sitzt das Restrisiko fuer den kernel test robot.

2. Keine Hardware unter der Einreichungsfassung. Alle Messprotokolle stammen vom Downstream-Baum mit 19 lokalen Patches, darunter der begrenzte Plane-Fence-Wait (nouveau_disp_fence_timeout_ms), die EVO-SV-Rescue und der Fault-Injektor, dazu eine Bootzeile mit soft_dpms, pclk_floor und NvForcePost. Der fuer die Einreichung umgebaute errored-Zweig (goto tier2) und die Konstanten statt Modulparameter sind nie unter Last gelaufen.

3. Keine Pre-Tesla-Hardware. Blocker 1 (Recovery ohne Familien-Guard) ist rein statisch belegt: Registerpfade, .intr-Tabellen, Klassenwerte und Aufrufketten wurden gelesen, aber auf NV04 bis NV40 wurde nichts ausgefuehrt. Die Schadensketten (nv04_chan_stop im Interrupt, unsignalisierte Fences) sind hergeleitet, nicht gemessen.

4. Kein Netz. Kein Abgleich mit lore (weder die Bot-Mail noch der v2-Thread), kein aktueller drm-misc-next oder drm-next, kein Rebase-Test gegen den Baum, ueber den nouveau tatsaechlich laeuft. origin/master zeigt lokal auf denselben Commit wie die Basis, Kollisionen mit neuerem Mainline-Code sind also nicht ausgeschlossen. Vor dem Versand fetch und Probe-Rebase noetig.

5. Kein KASAN, kein lockdep, kein Unbind-Fuzzing. Der UAF in Blocker 2 ist aus der Abbaureihenfolge hergeleitet und an jeder Station am Quelltext belegt, aber nicht zur Laufzeit ausgeloest worden. Ebenso ist die Sperrenordnung (wedge.lock als Blatt, cgrp->lock -> chan->lock -> fifo->lock) nur gelesen, nicht von lockdep bestaetigt.

6. Fixes-Ziel nicht endgueltig bestimmt. ea13e5abf807 ist der plausibelste Kandidat und wurde ueber git show <sha>:<pfad> gestuetzt, aber im sparsen Klon liefert git log -- <pfad> keine brauchbare Pfadhistorie. Ein falsches Fixes-Tag ist teurer als keines: im vollen Klon gegenpruefen.

7. Documentation/ fehlt im Serienbaum. Die exakte Syntax von 'Assisted-by: Claude:claude-opus-5' wurde gegen die Downstream-Kopie von coding-assistants.rst geprueft, nicht gegen den Stand des base-commit. get_maintainer.pl liess sich aus demselben Grund nicht ausfuehren, der Empfaengerkreis wurde nur direkt gegen MAINTAINERS abgeglichen.

8. Keine Mesa-Quellen auf der Platte. Die Herkunft von 0xbeef0201/0xbeef0202 als VRAM- und GART-Kanalhandles ist ueber die eigene Testsonde und die Logs des Zweitgeraets plausibel, aber nicht mit Mesa-Datei und -Zeile belegt. Der Satz 'the Mesa userspace driver issues' bleibt insoweit eine Behauptung ueber fremden Code.

9. Der Haeufigkeitsanspruch von 3/5 ('flooding on every X/Wayland session start') ist nur fuer X11-Sitzungen und mit 13 bis 65 Zeilen pro Log belegt, nicht als Flut und nicht auf der eigenen Maschine. Die eigenen persistenten Logs beginnen erst nach Einbau des Filters, ein Beweislauf ohne Filter existiert lokal nicht.

10. Der Bot selbst wurde nicht simuliert. Diese Pruefung hat gelesen und gerechnet; sie kann nicht garantieren, dass sashiko-bot dieselben Punkte findet oder keine weiteren. Die drei Achsen der Vorgeschichte (Lebensdauer, Reihenfolge, Rennen) wurden gezielt abgeklopft, und dort bleibt genau eine Sache halb offen: das Init-Fenster aus 2/5 (nouveau_chan.c:476 bis :501) wird von dieser Serie nicht geschlossen, sondern nur verschoben und auf Fermi und neuer vergroessert. Wenn das nicht ehrlich im Commit-Text steht, ist es der wahrscheinlichste vierte Bot-Befund.
