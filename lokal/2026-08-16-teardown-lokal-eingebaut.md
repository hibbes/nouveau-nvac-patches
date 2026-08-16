# Teardown-Serie lokal eingebaut, 16.08.2026

## Anlass

Beim Nachziehen der Ueberwachung fiel auf: die Teardown-Fehler, die upstream
gemeldet und behoben wurden, waren auf **genau der Maschine noch aktiv**, auf
der sie gefunden wurden. Spur 1 lief lokal (und in der aktuellen Fassung),
die Teardown-Serie gar nicht.

Belegt vor dem Umbau, im Baubaum und unabhaengig davon im geladenen Modul:

    nouveau_fence_context_del:   cancel_work_sync        <- 1/3 v2 fehlte
    nouveau_connector_destroy:   nur nvif_event_dtor()   <- 2/3 fehlte
    nouveau_dp_irq:              nouveau_drm(outp->...)
                                 if (!outp) return;      <- 3/3 fehlte

`nm -u` auf dem laufenden Modul zeigte `cancel_work_sync`, nicht
`disable_work_sync`.

## Was gemacht wurde

Drei Patches in den aktiven Bausatz `/etc/kernel/nouveau-patches/`, damit
19 -> 22:

| neu | Quelle |
|---|---|
| `0025-teardown-fence-uevent-disable-work-sync.patch` | v2 von 1/3, wie am 16.08. gesendet |
| `0026-teardown-connector-cancel-dp-irq-work.patch` | 2/3, wie am 15.08. gesendet |
| `0027-teardown-dp-irq-check-outp-first.patch` | 3/3, wie am 15.08. gesendet |

Vorher Trockenprobe gegen den lokalen Baum (der die 19 schon trug): alle drei
passen sauber.

Sicherungen: Bausatz nach `/root/nouveau-patches-backup-20260816-153228`,
laufendes Modul nach `/root/nouveau.ko.bak-20260816-vor-teardown`
(als byteidentisch zum geladenen Modul verifiziert).

Rebuild nach der Runbook-Kur, weil ein Reinstall auf bereits gepatchte
Quellen an `0010` scheitert:

    rm -rf /usr/src/linux-7.1.8-gentoo
    emerge -1 =sys-kernel/gentoo-sources-7.1.8
    emerge -1 =sys-kernel/gentoo-kernel-bin-7.1.8

Skript `~/nvac-v2-qa/teardown-rebuild-20260816.sh`, Log daneben.

## Abnahme

Dem emerge-Exit-Code wurde nicht getraut (Runbook: ein `die` im postinst-Hook
liefert trotzdem 0). Stattdessen `~/nvac-v2-qa/teardown-abnahme-20260816.sh`,
**0 Beanstandungen**:

- Modul neu (16:09), `vermagic 7.1.8-gentoo-dist-bin`
- `0025`: Modul referenziert `disable_work_sync`, Quelle ebenso
- `0026`: `nouveau_connector_destroy` drainiert die irq_work
- `0027`: der `if (!outp)`-Test steht jetzt bei Z.12, der Zugriff bei Z.15,
  also Test **vor** Dereferenzierung
- alle 16 Parameter des bestehenden Stacks im neuen Modul
- `mcp79_pci_func` (Spur 1) weiterhin vorhanden

Der Hook meldete alle 22 Patches als `applied`, in Reihenfolge, ohne
Fehlermeldung und ohne Fuzz-Hinweis.

## Stand und offener Punkt

**Ein Neustart steht aus.** Das neue Modul liegt auf Platte, im Speicher
laeuft weiter das alte:

    auf Platte:  cancel_work_sync UND disable_work_sync
    im Speicher: nur cancel_work_sync

Erst nach dem Reboot sind die drei Patches wirksam. Damit **startet der Soak
neu**, der seit dem 25.07. auf `0019-0022` lief. Laufzeit vor dem Umbau:
3 Tage 4 Stunden seit dem 13.08., ohne Wedge.

Rueckfallebene, falls der neue Stand Aerger macht: das gesicherte Modul
zurueckkopieren und `depmod` laufen lassen, oder im GRUB-Advanced-Menu 7.1.7
waehlen.

## Zwei eigene Fehlgriffe beim Pruefen, zur Warnung

1. `cat` auf Modulparameter meldet "fehlt", wenn der Parameter nicht lesbar
   ist. Fuer die Existenzpruefung `ls` oder `modinfo -p` nehmen, nicht `cat`.
   Ich hatte deshalb kurzzeitig fehlende Patches gemeldet, die da waren.
2. `nm` auf eine Datei in `/root` liefert als normaler Nutzer stumm nichts,
   der Test sah nach "Symbol fehlt" aus. Mit `sudo` gegenpruefen.
