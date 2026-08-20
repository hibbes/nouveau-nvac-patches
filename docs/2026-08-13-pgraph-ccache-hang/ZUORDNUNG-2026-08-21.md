# Chrome-Abstuerze mit GPU: nouveau, Mesa oder Chromium?

11 Agenten, 6 Analyselinsen und 4 Angriffe. Die Schlussfassung fiel ans
Sitzungslimit, deshalb hier von Hand synthetisiert, mit eigener Nachpruefung
der beiden folgenreichsten Befunde.

## A) Die Antwort

**Die Unheilbarkeit gehoert vollstaendig nouveau.** Ein einzelner VM-Fault auf
Tesla toetet die Maschine dauerhaft, weil der Fault gemeldet und dann
fallengelassen wird. Das ist belegt und unbestritten.

**Der Ausloeser laesst sich nicht zuordnen.** Das staerkste Argument dafuer,
dass auch der Fault selbst ein nouveau-Fehler ist, wurde im Angriff widerlegt.
Chromium liefert die Last, Mesa die getrappte Methode, aber wessen Fehler der
Fault ist, gibt die Beweislage nicht her.

## B) Was gesichert ist

### Der Fault, dekodiert

    Klasse 0x8397   GT200_TESLA, 3D-Objektklasse
    subc 3          3D-Subchannel
    mthd 0x0f04     CB_DATA(0), Konstantenpuffer-Upload
    client 05/00    CCACHE / CB, die Konstanten-Cache-Einheit
    reason 0x02     PAGE_NOT_PRESENT
    Adresse         0x00201b0000

`PGRAPH_STATUS 0x503` und `PGRAPH_VSTATUS0 0x08` benennen unabhaengig
dieselbe Einheit als die haengende.

### Die Unheilbarkeit, belegt an mehreren Stellen

- `nvkm_chan_error()` wird im ganzen Treiber nur von Fermi, Volta, Ampere,
  der generischen Runlist-Recovery und dem GSP-Pfad gerufen, **von keiner
  einzigen Stelle auf Tesla**.
- Der Funktionszeiger `.mmu_fault` und die Robust-Channel-Maschinerie
  existieren erst ab Fermi.
- Fuer Tesla-GR gibt es kein `gr->func->reset`, ohne das
  `nvkm_engine_reset()` mit `-ENOSYS` abbricht.
- Ohne VM_BIND legt nouveau keinen Scheduler an, also gibt es auch keine
  Hangcheck-Uhr.
- Folge: kein Kanal-Kill, kein Fence-Signal, `ttm_bo_delayed_delete` wartet
  uninterruptibel ohne Zeitgrenze. D-State bis zum Neustart.

**Das Mittel existiert und wird nur nie aufgerufen:**
`nvkm_engine_reset` -> `nvkm_mc_reset` (GR-Maske 0x00201000, NVAC-spezifisch
in `g98_mc_reset`) -> `nv50_gr_init`. Was fehlt, ist die Belegung von
`nvkm_gr_func.reset` fuer nv50. Zusaetzlich hat das PGRAPH-Register 0x400040
ein CCACHE-Reset-Bit, das nouveau fuer M2MF und STRMOUT zwei Zweige weiter
oben bereits benutzt.

### Warum die lokalen Patches nicht griffen

0006, 0020 und 0023 haengen alle an `nv04_fifo_intr`. In diesem Vorfall war
`PFIFO_INTR` = 0. Der Fault kam aus PGRAPH, nicht aus PFIFO.

## C) Was die Angriffe zerlegt haben

**BLOCKER: der einzige kernelseitige Ursachenkandidat ist tot.** Die These, ein
verworfener Rueckgabewert von `nouveau_vma_map` (`nouveau_bo.c:1083`) hinterlasse
still einen residenten Puffer ohne PTE, beruht auf einem invertierten Boolean:
`uvmm.c:281-282` setzt `getref = (type == PTES)` und `mapref = (type == ADDR)`,
LAZY ist 0x02, also weder noch. Die ganze Kette ist unerreichbar.

**Der Reason-Code beweist nichts.** Die Linse schloss aus 0x02
(PAGE_NOT_PRESENT statt 0x00 PT_NOT_PRESENT) auf eine *aufgeloeste* statt nie
existierende Abbildung, und daraus auf einen Kernelanteil. Falsch:
`nouveau_vma_new` nimmt fuer Puffer in TTM_PL_SYSTEM den PTES-Zweig und
schreibt keine einzige PTE (`nouveau_vmm.c:99-115`), und frische Seitentabellen
werden genullt, weil `nv50_vmm_pgt` kein `.invalid` hat (`vmm.c:440,450,457`).
Eine nie hergestellte Abbildung erzeugt denselben Reason.

**Die Chrome-Schalterliste ruht auf einem ungueltigen Test.** Die Linse belegte
"in diesem Build gueltig" mit `strings -a chrome | grep -x`. Dasselbe Binary
enthaelt aber Windows-only- und Android-WebView-only-Schalter. Praesenz eines
Namensliterals sagt nichts. `--force-gpu-mem-available-mb` ist als String da,
aber in keiner zustaendigen Schalterdatei definiert.

## D) Zwei Spuren, selbst nachgeprueft

### mcp79 fehlt .tlb_flush: interessant, aber KEIN fehlender Flush

Gemessen:

    nv50 0 | g84 2 | gt200 1 | gt215 1 | mcp79 0 | mcp89 1

`mcp79_gr` hat keinen `.tlb_flush`, die Schwester-IGP `mcp89` schon. Der
Aufrufer ist aber:

    vmmnv50.c:192   /* unfortunate hw bug workaround... */
    vmmnv50.c:194   int ret = nvkm_gr_tlb_flush(device->gr);
    vmmnv50.c:195   if (ret != -ENODEV) continue;

und `nvkm_gr_tlb_flush()` liefert `-ENODEV` ohne Rueckruf (`gr/base.c:83-85`).
**Ohne Rueckruf wird also der normale Flush-Pfad genommen.** Der Rueckruf ist
eine Umgehung fuer einen Hardwarefehler bestimmter Chips, kein Grundbaustein.

Offen bleibt die legitime Frage, ob NVAC die Umgehung nicht doch braucht, da
die Schwester mcp89 sie hat. Das ist eine Frage an Upstream, kein Befund.

### Der pstate-Boden: Behauptung eingeschraenkt

Ein Angreifer behauptete, der lokale Patch 0016 (`nouveau.pclk_floor=1`) mache
den pstate-Daemon vollstaendig wirkungslos, debugfs zeige `03` als Wunsch und
`0e` als programmiert. Live nachgemessen zeigt debugfs:

    03: core 150 MHz shader 300 MHz vdec 150 MHz AC DC *

Stern und Wunsch stehen auf derselben Zeile, der Daemon wirkt also. Der Boden
greift laut Beschreibung nur, **solange ein Head aktiv ist**. Die Behauptung ist
damit nicht widerlegt, aber sie gilt nicht allgemein und gehoert unter Last
nachgemessen. 19.407 protokollierte Uebergaenge seit April sind kein Beleg
dafuer, dass sie wirkten.

## E) Was Chromium und Mesa beitragen

**Chromium:** Skia-Budget aus dem Arbeitsspeicher abgeleitet (256 MB) auf einer
GPU mit 247 MB. Der eigene Blocklist-Eintrag 30 gegen nouveau prueft
`gl_vendor` gegen `nouveau.*`, Mesa meldet seit Januar 2023 aber `Mesa`, der
Schutz ist also still wirkungslos geworden. Der GPU-Wachhund macht aus einem
Fault fuenf tote GPU-Prozesse in vier Minuten.

**Mesa:** liefert die getrappte Methode (0x0f04 ist der nv50-Uniform-Upload)
und hat keine Erholungsschnittstelle: `device_reset_status_query` ist nicht
gesetzt, `glGetGraphicsResetStatusARB` liefert immer `GL_NO_ERROR`, `PUSH_KICK`
verschluckt Kernelfehler im Release-Build.

Die naheliegende These "Mesa hat den Puffer nicht als resident angemeldet" ist
widerlegt: `screen->uniforms` haengt permanent im Bufctx.

## F) Upstream

Dieselbe Signatur ist seit 2011 dokumentiert und bis heute offen: derselbe
Trap, dieselbe Klasse 0x83xx, dieselbe Methode 0x0f04, dasselbe anschliessende
"failed to idle channel". Drei aktuelle Tesla-Freeze-Tickets im nouveau-Tracker
sind unbeantwortet.

## G) Was sich lohnt

**Meldenswert an nouveau, mit Aussicht:** dass Tesla keinen Erholungspfad hat,
obwohl das Mittel im Baum liegt und nur nicht verdrahtet ist. Das ist dieselbe
Argumentationsform, die bei der Teardown-Serie getragen hat: ein Treiber darf
nicht den ganzen Rechner verklemmen, weil ein Client eine ungueltige Adresse
gelesen hat. Wer den Fault ausloest, ist dafuer gleichgueltig.

**Nicht meldenswert, weil unbelegt:** wessen Fehler der Fault ist.

**Sofort und billig:** Chrome laeuft ohne GPU, das bleibt die wirksame
Massnahme. Die Schalterliste unterhalb davon ist wertlos, solange sie auf dem
`strings`-Test ruht.

## H) Offen

- Greift der pstate-Boden unter Last wirklich? Unter aktivem Head nachmessen.
- Braucht NVAC die tlb_flush-Umgehung, die mcp89 hat? Frage an Upstream.
- Waere ein `nvkm_gr_func.reset` fuer nv50 baubar? Das Mittel existiert,
  gebraucht wird die Verdrahtung plus ein Kanal-Kill fuer die Fences.
