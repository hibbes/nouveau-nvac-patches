# Plan-Triage 2026-07-19 (Nachzuegler)

Diese Repos fehlten in der Haupt-Triage vom selben Tag; der neue
Repo-Drift-Check hat sie am ersten Lauf gefunden. Verfahren identisch:
Klassifikation gegen den CODE, jedes DONE adversarial gegengeprueft.

## docs/plans/2026-05-04-nv04-fifo-recovery-implementation.md

**Urteil: PARTIAL** (Konfidenz high)

Plan zur Implementierung der zweistufigen nv04_fifo-Recovery (Patch 0006: Tier-1 Channel-Kill, Tier-2 drm_dev_wedged_event, Tracepoints, Module-Params). Die gesamte Implementierung inkl. Fault-Injector-Branch und Validierung Phasen 1-5 ist geliefert und lokal deployt; nur die im Plan vorgesehene ML-Submission des 6-Patch-Bundles fand nie statt, 0006 blieb "local only".

Belege: Commits auf v2-prep: 04ef5ab (Plan) -> 1aaa6f1 "0006: full nv04_fifo recovery (Tier-1+Tier-2, tracepoints, module params)", danach 9acb9ba (Rebase 7.0.4) und f547e23 (NULL-Deref-Fix aus realem Test). Patch 0006-drm-nouveau-fifo-add-recovery-path-for-Tesla-cache_e.patch enthaelt alle versprochenen Symbole: recover.c/nv04_fifo_recover, struct nvkm_fifo_wedge, trace_nouveau_fifo_chan_killed/dev_wedged, CREATE_TRACE_POINTS, module_param fifo_wedge_count/fifo_wedge_window_ms inkl. Range-Clamping; deployt in /etc/kernel/nouveau-patches/. Branch dev-fault-injector (lokal+origin) mit 0099-DO-NOT-MERGE-fifo-fault-injector.patch (Commit 001beec). README.md Zeile 61: "debugfs fault-injector validation Phases 1-5 done, Phase 6 soak in progress"; realer WEDGED=rebind-Uevent 2026-05-05 dokumentiert. Gegenbeweis fuer Task 19: die tatsaechlich gesendete v2-Serie (Commit 8f25f26, v2/send/) enthaelt nur 0001+0002; README fuehrt 0006 als "local only".

Offen:
- Task 19: Upstream-/Mailinglisten-Submission von Patch 0006 (die als v2 gesendete Serie vom 11.06. umfasst nur 0001+0002; 0006 ist laut README "local only")
- Task 20: formaler Abschluss von Phase 6 (Soak laut README noch "in progress", kein dokumentiertes Soak-Ende)

## docs/plans/2026-06-03-disp-evo-recovery-implementation.md

**Urteil: DONE** (Konfidenz high)

Implementierungsplan fuer Patch 0010 (reaktive EVO-Display-Channel-Recovery). Refutationsversuch gescheitert: alle substanziellen Deliverables existieren im Code oder wurden nachweisbar evidenzbasiert verworfen. Der Patch wurde gebaut, committet, installiert, per Injector und am echten Wedge validiert; das Ergebnis (Re-Arm heilt den Wedge nicht, Core-State 0x0e nicht heilbar) ist dokumentiert und die Linie durch den validierten, live laufenden Patch 0011 abgeloest. Kein offener Rest.

Belege: Repo /home/neo/projects/nouveau-nvac-patches, Branch v2-prep. Tasks 1-4 komplett in 0010-drm-nouveau-disp-reactive-evo-channel-recovery.patch: NVIF_DISP_CHAN_V0_RECOVER, nvkm_disp_chan_recover mit 0x610200/0x640000-Logging (Zeile 99-101), disp_recover-Param, dispnv50/recover.c (nv50_dmac_recover/_schedule/_work). Task 0: scripts/nouveau-rebuild.sh. Task 6: Patch in Repo und /etc/kernel/nouveau-patches/. Task 7: Injector abweichend vom Plan in 0010 selbst (nv50_disp_recover_inject_set, debugfs-File nouveau_disp_inject_recover) statt als 0099 auf dev-fault-injector; benutzt in Commit 899384e, verworfen in 1ce1dcd. Task 5 (optionaler Unstick) bewusst nicht geshippt: Bedingung aus docs/specs/2026-06-03-p2-decision-injector-invalid.md (Stuck-Pattern 0x02/0x03) trat nicht ein, echter Wedge zeigt State 0x0e (docs/specs/2026-06-06-REAL-wedge-analysis.md); Commit 5d6e41e (nicht 5d6e716 wie im ersten Pass) beweist, dass kein Re-Arm hilft. Task 8: B=899384e, C=59d712e+5d6e41e, D=Doku in docs/specs/ statt docs/investigations/ (Pfadabweichung, Inhalt vorhanden). Nachfolger 0011 validiert (b4d927f), live in /etc/kernel/nouveau-patches/.
