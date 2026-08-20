# A) ZUSAMMENFASSUNG

## Trägt der Patch?

Ja, mit einer offenen Frage, die kein Korrektheitsfehler ist, und einem Blocker, den nur du selbst schließen kannst (Signed-off-by, DCO).

Die Angriffe haben den Entwurf an einer Stelle getroffen, die ich nicht erwartet hatte: nicht auf der Plane-State-Ebene (dort hält die Symmetrie, das haben drei Angreifer unabhängig bestätigt), sondern eine Ebene tiefer, im neu eingeführten Zähler auf `nvbo->kmap`. Der Entwurf hat einen Cache gebaut und ihn ungeprüft weitergereicht. Genau dieselbe Klasse wie beim ersten Entwurf: stille Verfälschung statt Absturz.

## Kernidee der Neufassung

Zwei Patches, zwei Ebenen, jede mit genau einem Besitzer.

**1/2, `nouveau_bo`/`nouveau_gem`.** Die CPU-Abbildung eines nouveau-Puffers ist ein geteiltes Einzelstück, kein Privatbesitz. Belegt: `ttm_mem_io_reserve()` kehrt sofort zurück, sobald `ttm_resource.bus` gesetzt ist (`ttm_bo_util.c:52-53`), aber `ttm_mem_io_free()` gibt bedingungslos frei (`:62-76`), und `nouveau_ttm_io_mem_free_locked()` zieht das BAR1-Fenster ohne Rückfrage ein (`nouveau_bo.c:1240-1246`). Die zweite Abbildung ist also kein zweiter Besitz, sondern Miteigentum am ersten, und der erste Abbau enteignet alle anderen. `drm_fbdev_ttm_damage_blit()` läuft bei jedem Konsolen-Update genau da hinein (`drm_fbdev_ttm.c:126` und `:133`). Der Patch bündelt alle Kernel-Abbildungen in `nvbo->kmap` und zählt sie, mit eigenen `->vmap`/`->vunmap` statt der `drm_gem_ttm`-Helfer, so wie qxl, loongson und `drm_gem_vram_helper` es schon tun.

**2/2, `dispnv50`.** Eine Marke `panic_map` im `nv50_wndw_atom` sagt, welcher Plane-State eine Referenz hält. `prepare_fb` nimmt sie, `cleanup_fb` gibt sie. Keine Kopplung an `bo->pin_count`.

## Welche Angriffe trafen

| Angriff | Verdikt nach eigener Nachprüfung | Was daraus wurde |
|---|---|---|
| **besitz** (hoch) | **BESTÄTIGT.** `nouveau_bo_map_locked()` gab bei `kmap_count != 0` die vorhandene Abbildung heraus, ohne zu prüfen, ob sie noch zur aktuellen `ttm_resource` gehört. | Schnellweg prüft jetzt `nvbo->kmap.virtual`, und `nouveau_bo_move_ntfy()` reißt die Abbildung bei **jedem** Ressourcenwechsel ab. Damit gilt: `kmap.virtual != NULL` heißt "bildet die aktuelle Ressource ab". |
| **veralteter-zeiger** (hoch) | **BESTÄTIGT**, gleiche Wurzel. | Dieselbe Behebung. Zusätzlich prüft `get_scanout_buffer()` jetzt `nvbo->kmap.virtual` und nicht nur die Marke. |
| **regression 2**, io_reserve_lru läuft leer (hoch) | **BESTÄTIGT.** `nouveau_bo_add_io_reserve_lru()` hat genau einen Aufrufer, `nouveau_ttm_fault` (`nouveau_gem.c:62`); per grep über den ganzen Treiber geprüft. Nichts hängt einen entnommenen Puffer zurück. | `nouveau_bo_unmap_locked()` hängt beim Übergang auf 0 zurück, und der Fehlerausgang von `ttm_bo_kmap()` ebenfalls. Die Sperre in `add_io_reserve_lru()` läuft jetzt über `kmap.virtual` statt über den Zähler, damit ein nach einem Umzug abgeräumter Puffer wieder listenfähig wird. |
| **regression 1**, Abbildung pro Seitenwechsel (hoch) | **BESTÄTIGT als real.** Kette nachgerechnet: `ttm_bo_kmap` → `nvif_object_map_handle` → `nv50_mem_map` mit `nvkm_vmm_get`+`nvkm_memory_map` (`memnv50.c:56-62`), Flush unter geräteweitem `mmu->mutex` (`vmmnv50.c:181-222`), dazu `ioremap_wc` über die volle Puffergröße. | **Nicht behoben, nur begrenzt.** Gattert mit `IS_ENABLED(CONFIG_DRM_PANIC)` und im Änderungstext offen ausgeschrieben. Siehe D. |
| **form** (Blocker) | **BESTÄTIGT**, alle sechs Punkte. | Serie in 1/2 und 2/2 geteilt, `Fixes:` nur auf 2/2, `Cc: stable` ganz gestrichen, die falsche Changelog-Behauptung ersetzt, die drei stillen Hunks im Changelog von 1/2 benannt, `WARN_ON` kommentiert, Betreff-Präfix `drm/nouveau/kms` für den KMS-Teil. **Signed-off-by fehlt weiter, siehe D.** |
| **panic-verletzung** | kein Treffer, geprüft und bestätigt. | Beide Nebenhinweise aufgenommen (Laufzeit-Suspend nach D, Fehlerwert bleibt `-ENODEV`). |
| **verklemmung** | kein Treffer, geprüft und bestätigt. | Beide Randbeobachtungen aufgenommen, siehe unten. |

## Was ich verworfen habe, und warum

**Der im Auftrag bevorzugte Weg, privates `ttm_bo_kmap_obj` oder `iosys_map` im Plane-State.** Trägt nicht. `drm_fbdev_ttm_damage_blit()` vmapt und vunmapt denselben Scanout-Puffer bei jedem Konsolen-Update (`drm_fbdev_ttm.c:126`, `:133`) über `drm_client_buffer_vmap_local()` (`drm_client.c:290-310`), und `ttm_bo_vunmap()` zieht das gemeinsame BAR1-Fenster ein (`ttm_bo_util.c:579`). Eine private Abbildung im State wäre vom ersten fbcon-Blit entkernt. Deshalb ist die Zählung in `struct nouveau_bo` nicht Kür, sondern Voraussetzung.

**Empfehlung 1 der Angreifer "besitz" und "veralteter-zeiger": `.vmap` soll pinnen.** Verworfen. Erstens ist die Vorlage falsch zitiert: `drm_gem_vram_vmap()` pinnt trotz seines Doku-Kommentars **nicht** (`drm_gem_vram_helper.c:347-374`, kein `ttm_bo_pin`), es zählt nur und räumt in `move_notify` ab (`:488-496`). Zweitens ändert ein Pin in `->vmap` die Semantik für jeden dma-buf-Importeur und für fbcon, und er braucht eine Domain: `nouveau_bo_pin_locked()` gibt `-EBUSY`, wenn die gewählte Domain nicht zur bestehenden Anheftung passt (`nouveau_bo.c:566-580`). Die Abräumung im Umzug erreicht dasselbe Ziel ohne diese Nebenwirkungen und ist die tatsächliche in-tree-Vorlage.

**Empfehlung 3 derselben Angreifer: `kmap_res` merken und vergleichen.** Verworfen, weil ein Zeigervergleich nach `ttm_resource_free()` einem ABA-Fehler durch Slab-Wiederverwendung offensteht. Die Abräumung im Umzug macht den Vergleich überflüssig.

**Faktische Korrektur an "veralteter-zeiger":** die Behauptung, `contig = true` erzwinge bei **jedem** `nv50_wndw_prepare_fb()` zwei Umzüge, stimmt nicht. Der Block bei `nouveau_bo.c:553-560` steht unter `if (!nvbo->contig)`, und `nvbo->contig` bleibt gesetzt. Betroffen ist nur die erste Anheftung eines Puffers. Der geschilderte Ablauf bleibt trotzdem gültig, er braucht diesen Umzug nur einmal.

**Faktische Korrektur an "regression 2":** ein Teil der verlorenen Listeneinträge war ohnehin wertlos, weil `ttm_bo_kunmap()` über `ttm_mem_io_free()` das Fenster des Opfers schon zerstört hatte (`ttm_bo_util.c:478`). Der SIGBUS-Schluss bleibt richtig, die Menge der wirklich verlorenen brauchbaren Opfer ist kleiner als behauptet. Behoben ist es trotzdem, und zwar so, dass die Listenmitgliedschaft exakt dem Stand vor dem Patch entspricht.

**Zwei Randbeobachtungen der Nicht-Treffer, beide übernommen:**
- Die Begründung für `WARN_ON` im alten Entwurf war falsch. `drm_atomic_helper_resume()` ruft `drm_mode_config_reset()` (`drm_atomic_helper.c:3917`). Sie trägt trotzdem, aber aus einem anderen Grund: `disp->suspend` ist nur beim Nicht-Laufzeit-Suspend gesetzt (`nouveau_display.c:769-777`), und der läuft vorher durch `drm_atomic_helper_suspend()`, das alle Planes abschaltet und dabei per `cleanup_fb` aufräumt. Der Quelltextkommentar sagt jetzt genau das.
- `WARN_ON(ret)` in `nouveau_bo_unmap()` war toter Code (`ttm_bo_reserve(bo, false, false, NULL)` landet in `ww_mutex_lock` mit NULL-Kontext und liefert immer 0). Entfernt, die Funktion folgt jetzt dem Stil ihrer Nachbarn `nouveau_bo_pin`/`nouveau_bo_unpin`.

## Prüfstand

- `make W=1 M=drivers/gpu/drm/nouveau` gegen die reale `.config` der Zielmaschine (`CONFIG_DRM_PANIC=y`, `CONFIG_DRM_NOUVEAU=m`): Exit 0, null Warnungen, `nouveau.ko` gelinkt.
- Bisect-Probe: **nur 1/2** angewandt, gleicher Build, Exit 0, null Warnungen. Die Serie ist bisect-fest.
- `scripts/checkpatch.pl --strict --no-signoff` auf beiden versandfertigen `.patch`-Dateien (Kopf + Changelog + `---` + Diff, nicht auf dem nackten Diff): je **0 errors, 0 warnings, 0 checks**. Mit Signoff-Prüfung meldet 1/2 erwartungsgemäß `ERROR: Missing Signed-off-by`.
- Basis geprüft: die fünf Dateien sind zwischen `c21bb4193868` und dem lokalen HEAD `72a21ddc97d9` unverändert (`git diff --stat` leer). Die beiden lokalen Fremdcommits (MCP79-MSI-Rearm, `nv50_sor` NULL-crtc) sind aus den Diffs sauber ausgeschlossen, das war im ersten Anlauf ein echter Fehler in meiner Diff-Erzeugung und ist behoben.

Dateien:
- `/home/neo/projects/nouveau-nvac-patches/drm-panic-report/v1-0001.patch`
- `/home/neo/projects/nouveau-nvac-patches/drm-panic-report/v1-0002.patch`
- Der verworfene erste Entwurf liegt jetzt als `REJECTED-v0-panic-map.patch.diff` und `REJECTED-v0-commit-message.txt` daneben.

---

# B) COMMIT-TEXT

## Patch 1/2

```
drm/nouveau: reference count the kernel CPU mapping of a buffer object

nouveau maps a buffer object for the CPU in four places: nouveau_bo_map()
for the driver's own objects, the pushbuf relocation path and the pushbuf
suffix fixup in nouveau_gem.c, and &drm_gem_object_funcs.vmap, which is
drm_gem_ttm_vmap().  Each of them assumes it gets a mapping of its own.
It does not.

TTM asks the driver to set up the aperture only for the first mapping of
a resource, ttm_mem_io_reserve() returns early once ttm_resource.bus is
populated, but it asks the driver to tear it down on every
ttm_bo_kunmap() and ttm_bo_vunmap(), and nouveau_ttm_io_mem_free_locked()
then releases the BAR1 window unconditionally.  A second mapping of the
same buffer object is therefore not a second mapping, it is a second user
of the first one, and the first teardown leaves the others pointing into
BAR1 space that has since been handed to somebody else.

drm_fbdev_ttm_damage_blit() walks into this on every console update: it
vmaps and vunmaps the scanout buffer object through drm_gem_ttm_vmap(),
so any other kernel mapping of that object dies with the next console
print.

Funnel all of them through nvbo->kmap and count the users.  This is the
shape qxl, loongson and drm_gem_vram_helper already use, and like them
nouveau now needs its own ->vmap and ->vunmap instead of the
drm_gem_ttm helpers.

Two more holes come with the counter and are closed here as well.  A
mapped object is kept off the io_reserve_lru, so that the -ENOSPC path of
nouveau_ttm_io_mem_reserve() cannot revoke a window that is still in use,
and it goes back on the list as soon as the last user is gone.  And
nouveau_bo_move_ntfy() now drops the mapping, because
ttm_bo_handle_move_mem() has just revoked the aperture window it points
into; the next nouveau_bo_map_locked() creates a fresh one.

The pushbuf paths keyed their mapping off nvbo->kmap.virtual and unmapped
only what they had mapped themselves.  They now key off
nvbo->validate_mapped, which they already maintain, and take a counted
reference in either case.

nouveau_bo_unmap() takes the reservation, which it always should have:
ttm_bo_kunmap() reaches nouveau_ttm_io_mem_free() and the io_reserve_mutex
from there.  None of its four callers holds the reservation.
```

## Patch 2/2

```
drm/nouveau/kms: don't map the scanout buffer in panic context

nv50_wndw_get_scanout_buffer() calls nouveau_bo_map(), which takes the
buffer object reservation and ends in ioremap() for VRAM.  drm_panic
calls ->get_scanout_buffer() under drm_panic_trylock(), which is a
raw_spin_trylock_irqsave(), so neither is allowed there: the reservation
is a sleeping lock, and ioremap() reaches __get_vm_area_node(), which
BUG()s when called from interrupt context.

On a Mac mini 3,1 (MCP79, GeForce 9400M) this turns every panic into a
second oops inside panic(), and no panic screen is drawn.

drm_panic documents the way out: anything set up by
&drm_plane_helper_funcs.prepare_fb and torn down by ->cleanup_fb may be
used from panic context, and for that window the framebuffer is pinned.
Map it there, and let ->get_scanout_buffer() hand out only what is
already mapped.

A flag in the plane state records which state holds the reference.
->prepare_fb() runs once per new plane state and ->cleanup_fb() once for
every state it succeeded on, but not for the plane whose ->prepare_fb()
failed: drm_atomic_helper_prepare_planes() skips exactly that one on its
error path.  The mapping is therefore the last thing ->prepare_fb() does,
behind every error return, so nothing has to be unwound by hand.  The
flag must not be inherited by nv50_wndw_atomic_duplicate_state(), which
allocates with kmalloc_obj() and copies field by field.

Deliberately not tied to bo->pin_count.  Cursor and overlay planes share
this ->prepare_fb()/->cleanup_fb() pair without having
->get_scanout_buffer(), and dma-buf importers pin the same buffer object
too, so the last unpin is not the last unmap.

The cost is one ttm_bo_kmap()/ttm_bo_kunmap() pair per page flip whenever
the framebuffer changes, which for VRAM means a BAR1 window and an
ioremap_wc() of the framebuffer.  A framebuffer that stays put, such as
an fbdev console, is mapped once.  CONFIG_DRM_PANIC=n pays nothing.

Fixes: 1d26c846f3ff ("drm/nouveau: Add drm_panic support for nv50+")
```

`1d26c846f3ff` verifiziert: "drm/nouveau: Add drm_panic support for nv50+", Jocelyn Falempe, 2024-10-22, `git describe --contains` gibt `v6.13-rc1~122^2~2^2~17`. Kein `Fixes:` auf 1/2, kein `Cc: stable` auf der Serie, Begründung in Abschnitt D.

---

# C) DIFF gegen c21bb4193868

## Patch 1/2

```diff
diff --git a/drivers/gpu/drm/nouveau/nouveau_bo.c b/drivers/gpu/drm/nouveau/nouveau_bo.c
index 0e8de6d4b36f..2c1bd3591e7f 100644
--- a/drivers/gpu/drm/nouveau/nouveau_bo.c
+++ b/drivers/gpu/drm/nouveau/nouveau_bo.c
@@ -141,6 +141,7 @@ nouveau_bo_del_ttm(struct ttm_buffer_object *bo)
 	struct nouveau_bo *nvbo = nouveau_bo(bo);
 
 	WARN_ON(nvbo->bo.pin_count > 0);
+	WARN_ON(nvbo->kmap_count > 0);
 	nouveau_bo_del_io_reserve_lru(bo);
 	nv10_bo_put_tile_region(dev, nvbo->tile, NULL);
 
@@ -664,6 +665,64 @@ int nouveau_bo_unpin(struct nouveau_bo *nvbo)
 	return 0;
 }
 
+/* The kernel CPU mapping of a buffer object is a shared singleton, not a
+ * private mapping per user.  TTM asks the driver to set up the aperture only
+ * for the first mapping of a resource, ttm_mem_io_reserve() returns early once
+ * ttm_resource.bus is populated, but it asks the driver to tear it down on
+ * every ttm_bo_kunmap() and ttm_bo_vunmap(), and
+ * nouveau_ttm_io_mem_free_locked() then releases the BAR1 window
+ * unconditionally.  A second mapping of the same buffer object is therefore
+ * not a second mapping, it is a second user of the first one, and the first
+ * teardown leaves the others pointing into BAR1 space that has since been
+ * handed to somebody else.
+ *
+ * Funnel every kernel mapping of a nouveau buffer object through nvbo->kmap
+ * and count the users.  The caller must hold the buffer object reservation.
+ */
+int
+nouveau_bo_map_locked(struct nouveau_bo *nvbo)
+{
+	int ret;
+
+	dma_resv_assert_held(nvbo->bo.base.resv);
+
+	if (nvbo->kmap.virtual) {
+		nvbo->kmap_count++;
+		return 0;
+	}
+
+	/* nouveau_ttm_io_mem_reserve() reclaims BAR1 space by revoking the io
+	 * mapping of whatever sits at the head of the io_reserve_lru, without
+	 * asking the users of that mapping.  Keep this object off the list for
+	 * as long as it is mapped.
+	 */
+	nouveau_bo_del_io_reserve_lru(&nvbo->bo);
+
+	ret = ttm_bo_kmap(&nvbo->bo, 0, PFN_UP(nvbo->bo.base.size), &nvbo->kmap);
+	if (ret) {
+		nouveau_bo_add_io_reserve_lru(&nvbo->bo);
+		return ret;
+	}
+
+	nvbo->kmap_count++;
+	return 0;
+}
+
+void
+nouveau_bo_unmap_locked(struct nouveau_bo *nvbo)
+{
+	dma_resv_assert_held(nvbo->bo.base.resv);
+
+	/* Tolerate an unmap of an object that is not mapped: ttm_bo_kunmap()
+	 * did the same, and nv04_display_fini() relies on it.
+	 */
+	if (!nvbo->kmap_count || --nvbo->kmap_count)
+		return;
+
+	ttm_bo_kunmap(&nvbo->kmap);
+	nouveau_bo_add_io_reserve_lru(&nvbo->bo);
+}
+
 int
 nouveau_bo_map(struct nouveau_bo *nvbo)
 {
@@ -673,7 +732,7 @@ nouveau_bo_map(struct nouveau_bo *nvbo)
 	if (ret)
 		return ret;
 
-	ret = ttm_bo_kmap(&nvbo->bo, 0, PFN_UP(nvbo->bo.base.size), &nvbo->kmap);
+	ret = nouveau_bo_map_locked(nvbo);
 
 	ttm_bo_unreserve(&nvbo->bo);
 	return ret;
@@ -682,10 +741,18 @@ nouveau_bo_map(struct nouveau_bo *nvbo)
 void
 nouveau_bo_unmap(struct nouveau_bo *nvbo)
 {
+	int ret;
+
 	if (!nvbo)
 		return;
 
-	ttm_bo_kunmap(&nvbo->kmap);
+	ret = ttm_bo_reserve(&nvbo->bo, false, false, NULL);
+	if (ret)
+		return;
+
+	nouveau_bo_unmap_locked(nvbo);
+
+	ttm_bo_unreserve(&nvbo->bo);
 }
 
 void
@@ -766,7 +833,11 @@ void nouveau_bo_add_io_reserve_lru(struct ttm_buffer_object *bo)
 	struct nouveau_bo *nvbo = nouveau_bo(bo);
 
 	mutex_lock(&drm->ttm.io_reserve_mutex);
-	list_move_tail(&nvbo->io_reserve_lru, &drm->ttm.io_reserve_lru);
+	/* A kernel mapping of this object is live, it must not be picked as a
+	 * victim by the -ENOSPC path of nouveau_ttm_io_mem_reserve().
+	 */
+	if (!nvbo->kmap.virtual)
+		list_move_tail(&nvbo->io_reserve_lru, &drm->ttm.io_reserve_lru);
 	mutex_unlock(&drm->ttm.io_reserve_mutex);
 }
 
@@ -1077,6 +1148,16 @@ static void nouveau_bo_move_ntfy(struct ttm_buffer_object *bo,
 
 	nouveau_bo_del_io_reserve_lru(bo);
 
+	/* The kernel mapping is about to become invalid.  For an io mapping
+	 * ttm_bo_handle_move_mem() has already revoked the aperture window it
+	 * points into, and the pages behind a system memory mapping are about
+	 * to be freed.  Drop it here, while the reservation is held and the
+	 * old resource is still around; nouveau_bo_map_locked() creates a
+	 * fresh one on demand.  Users that still hold a reference keep a copy
+	 * of the old address, exactly as they did with ttm_bo_vmap() before.
+	 */
+	ttm_bo_kunmap(&nvbo->kmap);
+
 	if (mem && new_reg->mem_type != TTM_PL_SYSTEM &&
 	    mem->mem.page == nvbo->page) {
 		list_for_each_entry(vma, &nvbo->vma_list, head) {
diff --git a/drivers/gpu/drm/nouveau/nouveau_bo.h b/drivers/gpu/drm/nouveau/nouveau_bo.h
index 6c26beeb427f..611202a16e10 100644
--- a/drivers/gpu/drm/nouveau/nouveau_bo.h
+++ b/drivers/gpu/drm/nouveau/nouveau_bo.h
@@ -17,7 +17,14 @@ struct nouveau_bo {
 	u32 valid_domains;
 	struct ttm_place placements[3];
 	bool force_coherent;
+
+	/* The single kernel CPU mapping of this buffer object, and the number
+	 * of users of it.  Both are protected by the buffer object
+	 * reservation.
+	 */
 	struct ttm_bo_kmap_obj kmap;
+	unsigned int kmap_count;
+
 	struct list_head head;
 	struct list_head io_reserve_lru;
 
@@ -75,6 +82,8 @@ int  nouveau_bo_pin_locked(struct nouveau_bo *nvbo, uint32_t domain, bool contig
 void nouveau_bo_unpin_locked(struct nouveau_bo *nvbo);
 int  nouveau_bo_pin(struct nouveau_bo *, u32 flags, bool contig);
 int  nouveau_bo_unpin(struct nouveau_bo *);
+int  nouveau_bo_map_locked(struct nouveau_bo *nvbo);
+void nouveau_bo_unmap_locked(struct nouveau_bo *nvbo);
 int  nouveau_bo_map(struct nouveau_bo *);
 void nouveau_bo_unmap(struct nouveau_bo *);
 void nouveau_bo_placement_set(struct nouveau_bo *, u32 type, u32 busy);
diff --git a/drivers/gpu/drm/nouveau/nouveau_gem.c b/drivers/gpu/drm/nouveau/nouveau_gem.c
index 20dba02d6175..42e866c9544e 100644
--- a/drivers/gpu/drm/nouveau/nouveau_gem.c
+++ b/drivers/gpu/drm/nouveau/nouveau_gem.c
@@ -24,6 +24,8 @@
  *
  */
 
+#include <linux/iosys-map.h>
+
 #include <drm/drm_gem_ttm_helper.h>
 
 #include "nouveau_drv.h"
@@ -214,6 +216,34 @@ nouveau_gem_object_close(struct drm_gem_object *gem, struct drm_file *file_priv)
 	ttm_bo_unreserve(&nvbo->bo);
 }
 
+static int
+nouveau_gem_object_vmap(struct drm_gem_object *obj, struct iosys_map *map)
+{
+	struct nouveau_bo *nvbo = nouveau_gem_object(obj);
+	bool is_iomem;
+	void *vaddr;
+	int ret;
+
+	ret = nouveau_bo_map_locked(nvbo);
+	if (ret)
+		return ret;
+
+	vaddr = ttm_kmap_obj_virtual(&nvbo->kmap, &is_iomem);
+	if (is_iomem)
+		iosys_map_set_vaddr_iomem(map, (void __force __iomem *)vaddr);
+	else
+		iosys_map_set_vaddr(map, vaddr);
+
+	return 0;
+}
+
+static void
+nouveau_gem_object_vunmap(struct drm_gem_object *obj, struct iosys_map *map)
+{
+	nouveau_bo_unmap_locked(nouveau_gem_object(obj));
+	iosys_map_clear(map);
+}
+
 const struct drm_gem_object_funcs nouveau_gem_object_funcs = {
 	.free = nouveau_gem_object_del,
 	.open = nouveau_gem_object_open,
@@ -222,8 +252,8 @@ const struct drm_gem_object_funcs nouveau_gem_object_funcs = {
 	.pin = nouveau_gem_prime_pin,
 	.unpin = nouveau_gem_prime_unpin,
 	.get_sg_table = nouveau_gem_prime_get_sg_table,
-	.vmap = drm_gem_ttm_vmap,
-	.vunmap = drm_gem_ttm_vunmap,
+	.vmap = nouveau_gem_object_vmap,
+	.vunmap = nouveau_gem_object_vunmap,
 	.mmap = drm_gem_ttm_mmap,
 	.vm_ops = &nouveau_ttm_vm_ops,
 };
@@ -432,7 +462,7 @@ validate_fini_no_ticket(struct validate_op *op, struct nouveau_channel *chan,
 		}
 
 		if (unlikely(nvbo->validate_mapped)) {
-			ttm_bo_kunmap(&nvbo->kmap);
+			nouveau_bo_unmap_locked(nvbo);
 			nvbo->validate_mapped = false;
 		}
 
@@ -693,9 +723,8 @@ nouveau_gem_pushbuf_reloc_apply(struct nouveau_cli *cli,
 			break;
 		}
 
-		if (!nvbo->kmap.virtual) {
-			ret = ttm_bo_kmap(&nvbo->bo, 0, PFN_UP(nvbo->bo.base.size),
-					  &nvbo->kmap);
+		if (!nvbo->validate_mapped) {
+			ret = nouveau_bo_map_locked(nvbo);
 			if (ret) {
 				NV_PRINTK(err, cli, "failed kmap for reloc\n");
 				break;
@@ -898,10 +927,8 @@ nouveau_gem_ioctl_pushbuf(struct drm_device *dev, void *data,
 			cmd = chan->push.addr + ((chan->dma.cur + 2) << 2);
 			cmd |= 0x20000000;
 			if (unlikely(cmd != req->suffix0)) {
-				if (!nvbo->kmap.virtual) {
-					ret = ttm_bo_kmap(&nvbo->bo, 0,
-							  PFN_UP(nvbo->bo.base.size),
-							  &nvbo->kmap);
+				if (!nvbo->validate_mapped) {
+					ret = nouveau_bo_map_locked(nvbo);
 					if (ret) {
 						WIND_RING(chan);
 						goto out;
```

## Patch 2/2

```diff
diff --git a/drivers/gpu/drm/nouveau/dispnv50/atom.h b/drivers/gpu/drm/nouveau/dispnv50/atom.h
index c34a42ea9ac4..16c93d5c6e8c 100644
--- a/drivers/gpu/drm/nouveau/dispnv50/atom.h
+++ b/drivers/gpu/drm/nouveau/dispnv50/atom.h
@@ -191,6 +191,12 @@ struct nv50_wndw_atom {
 	struct drm_property_blob *ilut;
 	bool visible;
 
+	/* Set while this plane state holds a reference on the CPU mapping of
+	 * its framebuffer, for drm_panic.  Must not be inherited by a
+	 * duplicated state.
+	 */
+	bool panic_map;
+
 	struct {
 		u32  handle;
 		u16  offset:12;
diff --git a/drivers/gpu/drm/nouveau/dispnv50/wndw.c b/drivers/gpu/drm/nouveau/dispnv50/wndw.c
index 2635458d52ac..8d7b0c6f47bd 100644
--- a/drivers/gpu/drm/nouveau/dispnv50/wndw.c
+++ b/drivers/gpu/drm/nouveau/dispnv50/wndw.c
@@ -524,6 +524,7 @@ static void
 nv50_wndw_cleanup_fb(struct drm_plane *plane, struct drm_plane_state *old_state)
 {
 	struct nouveau_drm *drm = nouveau_drm(plane->dev);
+	struct nv50_wndw_atom *armw = nv50_wndw_atom(old_state);
 	struct nouveau_bo *nvbo;
 
 	NV_ATOMIC(drm, "%s cleanup: %p\n", plane->name, old_state->fb);
@@ -531,6 +532,10 @@ nv50_wndw_cleanup_fb(struct drm_plane *plane, struct drm_plane_state *old_state)
 		return;
 
 	nvbo = nouveau_gem_object(old_state->fb->obj[0]);
+	if (armw->panic_map) {
+		armw->panic_map = false;
+		nouveau_bo_unmap(nvbo);
+	}
 	nouveau_bo_unpin(nvbo);
 }
 
@@ -590,6 +595,24 @@ nv50_wndw_prepare_fb(struct drm_plane *plane, struct drm_plane_state *state)
 		wndw->func->prepare(wndw, asyh, asyw);
 	}
 
+	/* drm_panic runs ->get_scanout_buffer() from panic context, under a raw
+	 * spinlock, so that callback cannot map anything.  Map the framebuffer
+	 * here instead: anything set up between ->prepare_fb() and
+	 * ->cleanup_fb() may be used from panic context, and the framebuffer is
+	 * pinned for exactly that window.
+	 *
+	 * This has to stay behind the last error return of this function.
+	 * drm_atomic_helper_prepare_planes() does not call ->cleanup_fb() for
+	 * the plane whose ->prepare_fb() failed, so anything taken before an
+	 * error return would have to be released by hand.
+	 *
+	 * Best effort: without a mapping there is simply no panic screen.
+	 */
+	if (IS_ENABLED(CONFIG_DRM_PANIC) &&
+	    plane->helper_private->get_scanout_buffer &&
+	    !nouveau_bo_map(nvbo))
+		asyw->panic_map = true;
+
 	return 0;
 }
 
@@ -651,6 +674,7 @@ static int
 nv50_wndw_get_scanout_buffer(struct drm_plane *plane, struct drm_scanout_buffer *sb)
 {
 	struct drm_framebuffer *fb;
+	struct nv50_wndw_atom *armw;
 	struct nouveau_bo *nvbo;
 	struct nouveau_drm *drm = nouveau_drm(plane->dev);
 	u16 chipset = drm->client.device.info.chipset;
@@ -661,6 +685,7 @@ nv50_wndw_get_scanout_buffer(struct drm_plane *plane, struct drm_scanout_buffer
 	if (!plane->state || !plane->state->fb)
 		return -EINVAL;
 
+	armw = nv50_wndw_atom(plane->state);
 	fb = plane->state->fb;
 	nvbo = nouveau_gem_object(fb->obj[0]);
 
@@ -668,10 +693,12 @@ nv50_wndw_get_scanout_buffer(struct drm_plane *plane, struct drm_scanout_buffer
 	if (nvbo->comp || fb->format->num_planes != 1)
 		return -EOPNOTSUPP;
 
-	if (nouveau_bo_map(nvbo)) {
-		drm_warn(plane->dev, "nouveau bo map failed, panic won't be displayed\n");
-		return -ENOMEM;
-	}
+	/* Mapping the framebuffer here would sleep and ioremap(), both
+	 * forbidden in panic context.  nv50_wndw_prepare_fb() has done it for
+	 * this plane state, or there is no panic screen for this framebuffer.
+	 */
+	if (!armw->panic_map || !nvbo->kmap.virtual)
+		return -ENODEV;
 
 	if (nvbo->kmap.bo_kmap_type & TTM_BO_MAP_IOMEM_MASK)
 		iosys_map_set_vaddr_iomem(&sb->map[0], (void __iomem *)nvbo->kmap.virtual);
@@ -721,6 +748,16 @@ nv50_wndw_atomic_destroy_state(struct drm_plane *plane,
 			       struct drm_plane_state *state)
 {
 	struct nv50_wndw_atom *asyw = nv50_wndw_atom(state);
+
+	/* Every state that ever held the mapping went through ->cleanup_fb()
+	 * first: nv50_wndw_reset() only runs from drm_mode_config_reset(),
+	 * which nouveau reaches either with plane->state still NULL, or from
+	 * drm_atomic_helper_resume() after drm_atomic_helper_suspend() has
+	 * disabled all planes, and drm_plane_cleanup() only runs after
+	 * nouveau_display_fini() has called drm_atomic_helper_shutdown().
+	 */
+	WARN_ON(asyw->panic_map);
+
 	__drm_atomic_helper_plane_destroy_state(&asyw->state);
 	kfree(asyw);
 }
@@ -736,6 +773,7 @@ nv50_wndw_atomic_duplicate_state(struct drm_plane *plane)
 	asyw->sema = armw->sema;
 	asyw->ntfy = armw->ntfy;
 	asyw->ilut = NULL;
+	asyw->panic_map = false;
 	asyw->xlut = armw->xlut;
 	asyw->csc  = armw->csc;
 	asyw->image = armw->image;
```

---

# D) OFFENE RISIKEN UND WAS VOR DEM EINREICHEN NOCH ZU TUN IST

## Der Blocker, den nur du schließen kannst

**Signed-off-by fehlt.** Der Auftrag schließt es ausdrücklich aus, und die DCO-Zeile darf ohnehin nur der Autor selbst setzen. Ohne sie ist die Serie nicht einreichbar, `checkpatch.pl` meldet `ERROR: Missing Signed-off-by: line(s)`, und `git am` nimmt sie nicht. Zwei Zeilen sind vor dem Versand zu ergänzen, in jedem der beiden Patches:

```
Link: https://lore.kernel.org/all/178681005908.3524476.7115000150741026287@gmail.com/
Signed-off-by: Marek Czernohous <mczernohous@gmail.com>
```

Und die Serie ist mit `git format-patch --cover-letter -2` zu erzeugen, nicht als `git diff`. Ich habe die beiden `.patch`-Dateien nur mit `Subject:`-Kopf und `---`-Trenner gebaut, damit checkpatch sie realistisch prüfen kann, sie tragen keinen `From:` und kein `Date:`.

Kein weiterer Blocker bleibt stehen.

## Das eine ungelöste Sachproblem: die Abbildung pro Seitenwechsel

Der Angriff "regression" hat recht, und ich habe es nicht wegbekommen. Bei echtem Doppelpuffer wechselt der Framebuffer bei jedem Flip, also nimmt `prepare_fb` eine echte Abbildung von B (Zähler 0 auf 1) und `cleanup_fb` gibt die von A (1 auf 0). Pro Flip kommt dazu:

- `nvkm_vmm_get` plus `nvkm_memory_map` für ein BAR1-Fenster in Puffergröße (`memnv50.c:56-62`), bei 1080p rund 2000 BAR1-PTEs, bei 4K rund 8000,
- eine Hardware-MMU-Invalidierung unter dem **geräteweiten** `mmu->mutex` mit Registerabfrage (`vmmnv50.c:181-222`, `vmmgf100.c:188-201`), derselbe Mutex, der auch Userspace-GPU-VA-Operationen serialisiert,
- `ioremap_wc` über die volle Puffergröße (`ttm_bo_util.c:327-329`) und beim Aufräumen `iounmap` plus `nvkm_vmm_put`.

Was ich getan habe: `IS_ENABLED(CONFIG_DRM_PANIC)` davor, damit Konfigurationen ohne Panikschirm nichts zahlen, und den Preis im Änderungstext von 2/2 offen hingeschrieben. Was ich **nicht** getan habe: ihn verstecken. Ein Maintainer, der ihn nicht will, soll ihn im Review sehen und benennen können.

Was auf echter Hardware zu messen ist, bevor die Serie rausgeht:
- Flip-Latenz und Haltezeit von `mmu->mutex` mit und ohne Patch, bei 1080p und bei 4K, unter einem echten Wayland-Compositor.
- Rate der globalen TLB-Flushes aus dem `iounmap`-Nachlauf.
- Der Panikfall selbst zeigt diesen Preis **nicht**. Wenn Jocelyn nur den Panikschirm testet, bleibt die Regression unentdeckt. Das gehört ins Anschreiben.

Falls die Messung den Preis als untragbar ausweist, ist die Vorlage für den Ausweg schon im Baum: `drm_gem_vram_helper` baut die Abbildung beim letzten `vunmap` **nicht** ab, sondern erst im `move_notify` (`drm_gem_vram_helper.c:396-404` und `:488-496`). Für nouveau hieße das, eine unreferenzierte Abbildung stehen zu lassen. Der Preis dafür ist, dass ein solcher Puffer dauerhaft von der `io_reserve_lru` fernbleiben muss, weil der `-ENOSPC`-Pfad (`nouveau_bo.c:1411-1427`) keine Reservierung hält und deshalb kein `ttm_bo_kunmap()` machen kann, ohne sich am `io_reserve_mutex` selbst zu verklemmen. Das ist ein eigener Entwurf mit eigener Testmatrix, nicht ein Feilen an Zeilen.

## Risiken, die ich am Quelltext geprüft und stehen gelassen habe

**`ttm_bo_pipeline_gutting()` umgeht `->move`.** Es gibt `bo->resource` frei, ohne `nouveau_bo_move_ntfy()` zu rufen (`ttm_bo_util.c:763-783`, gerufen aus `ttm_bo.c:382` und `:833`). Danach wäre `nvbo->kmap.virtual` verwaist. In nouveau ist das heute unerreichbar: `nouveau_bo_evict_flags()` setzt immer mindestens eine Platzierung, und `nouveau_gem_set_domain()` gibt `-EINVAL` bevor `pref_domains` leer wäre (`nouveau_gem.c:415-425`). Für den Panikpfad ist es zusätzlich durch die Anheftung gedeckt. Es bleibt eine Annahme über TTM-Interna, die im Anschreiben genannt werden sollte.

**Laufzeit-Suspend nach D3cold.** `nouveau_display_suspend()` überspringt bei `runtime == true` das `drm_atomic_helper_suspend()` (`nouveau_display.c:769-777`), also überleben Plane-State, Anheftung und jetzt auch die Abbildung bis in `pci_set_power_state(pdev, PCI_D3cold)`. Ein Panic in diesem Zustand schreibt in die BAR eines abgeschalteten Geräts. Die Klasse ist nicht neu (die alte Fassung hätte dieselbe tote BAR zu ioremappen versucht), der stehende Zeiger ist neu. Der saubere Ort wäre ein unter `drm_panic_lock()` geleertes `panic_map` in `nouveau_display_suspend()`. Bewusst nicht in dieser Serie, eigene Frage, eigener Test.

**Abbildungsart wechselt für einseitige, cached abgelegte Systemspeicher-Puffer.** `ttm_bo_vmap` vmapt immer (`ttm_bo_util.c:544-548`), `ttm_bo_kmap` nimmt bei `num_pages == 1` und `ttm_cached` stattdessen `kmap()` (`:358-368`). Betrifft jeden dma-buf-Importeur eines einseitigen nouveau-Puffers. Unter `CONFIG_HIGHMEM` belegt ein langlebiges `->vmap` damit einen `LAST_PKMAP`-Platz statt vmalloc-Adressraum. Auf x86-64 folgenlos, auf 32-Bit-Konfigurationen theoretisch nicht. Nicht behoben, im Changelog von 1/2 als API-Wechsel benannt.

**`ttm_bo_kunmap()` zieht das BAR1-Fenster ein, ohne die Userspace-PTEs zu zappen.** Es ruft `ttm_mem_io_free()` (`ttm_bo_util.c:478`), aber kein `drm_vma_node_unmap()`. Hat ein Prozess denselben Puffer per mmap eingeblendet, zeigen seine PTEs danach in ein Fenster, das inzwischen jemand anderem gehört. Das ist **vorbestehend**, heute über den Pushbuf-Reloc-Pfad erreichbar, und der Patch fasst es nicht an. Er macht es aber häufiger, weil er `nouveau_bo_unmap()` jetzt auch auf Scanout-Puffern ausführt. Gehört in einen eigenen Vorpatch und ins Anschreiben.

**Zwei Anheftungs-Lecks in `nv50_wndw_prepare_fb`.** Bei Fehlschlag von `drm_gem_plane_helper_prepare_fb()` (`wndw.c:585-586`) und von `nv50_head_atom_get_new()` (`:592-593`) kehrt die Funktion ohne `nouveau_bo_unpin()` zurück, und `fail_prepare_fb` holt das nicht nach (`drm_atomic_helper.c:2876-2886`). Der Patch legt seine Abbildung bewusst hinter diese Stellen und fügt darum kein neues Leck hinzu, behebt die alten aber auch nicht. Eigener kleiner Vorpatch.

**Fehlende `visible`-Prüfung.** `nv50_wndw_atomic_check()` lässt bei abgeschaltetem CRTC `state->fb` stehen, `get_scanout_buffer()` prüft das nicht, drm_panic kann also in einen Puffer malen, den kein Kopf ausgibt. Eigenständige kleine Verbesserung, eigener Patch, nicht hier hineingemischt.

**amdgpu hat dieselbe Verletzung.** `amdgpu_display_get_scanout_buffer()` ruft `ttm_bo_kmap()` mitten im Panikpfad (`amdgpu_display.c:1907-1911`) und nimmt dabei nicht einmal eine Reservierung. Gehört ins Anschreiben an Jocelyn, nicht in diese Serie.

## Zu Fixes und stable

Auf 1/2 steht **kein** `Fixes:`. Ich konnte keinen einzelnen einführenden Commit belegen. `.vmap = drm_gem_ttm_vmap` steht seit `49a3f51dfeee` (v5.11-rc1, 2020-11-03) in `nouveau_gem.c`, aber der routinemäßig auslösende Verbraucher, `drm_fbdev_ttm`, kam erst mit `ef350898ae22` ("drm/nouveau: Run DRM default client setup", v6.13). Welcher von beiden der ehrliche Fixes ist, hängt daran, ob nouveau vor `ef350898ae22` einen Nutzer hatte, der den Scanout-Puffer im Betrieb vmapt. Das ist eine Archäologie-Aufgabe über die alte `nouveau_fbcon.c`, die ich nicht am Quelltext dieses Baums entscheiden kann. Lieber kein Tag als ein falscher.

`Cc: stable` steht auf **keinem** der beiden Patches. Begründung nach `Documentation/process/stable-kernel-rules.rst:10-11`: die Serie hat 178 hinzugefügte Zeilen und liegt weit über der 100-Zeilen-Grenze, und sie ist nicht getestet. Wenn das Stable-Team den zweiten Oops trotzdem loswerden will, gibt es einen minimalen Rückfall, der ihn verhindert und den Panikschirm auf nv50 abschaltet: in `nv50_wndw_get_scanout_buffer()` das `nouveau_bo_map()` durch `if (!nvbo->kmap.virtual) return -ENODEV;` ersetzen, vier Zeilen. Das ist eine Kapitulation, keine Lösung, aber es ist stable-tauglich, und es sollte als separater Patch angeboten und nicht in diese Serie gemischt werden.

## Was nur auf echter Hardware klärbar ist

1. **Der Panikschirm selbst** auf dem Macmini3,1: erscheint er, und bleibt der zweite Oops aus. Das ist genau das, was Jocelyn zu testen angeboten hat.
2. **Flip-Kosten**, siehe oben. Ohne diese Zahl ist die Serie unvollständig begründet.
3. **`CONFIG_PROVE_LOCKING` plus `CONFIG_DEBUG_WW_MUTEX_SLOWPATH` plus `CONFIG_DEBUG_ATOMIC_SLEEP`** über einen Suspend/Resume-Zyklus, fbcon-Betrieb und einen GEM-Pushbuf-Lastlauf. Dort laufen `dma_resv`, `io_reserve_mutex` und `fb_helper->lock` gleichzeitig. Ich habe die Sperrreihenfolge am Quelltext geprüft (`dma_resv` vor `io_reserve_mutex`, keine Gegenrichtung, weil der `-ENOSPC`-Opferpfad bei `nouveau_bo.c:1411-1427` das Opfer ohne dessen Reservierung anfasst), aber gelesen ist nicht gemessen.
4. **Klonbetrieb**, ein Framebuffer auf zwei Primary-Planes über zwei Köpfe. Dort wird `kmap_count` zweimal genommen und zweimal gegeben, und dort wäre der Fehler des ersten Entwurfs aufgeschlagen.
5. **Eine Karte mit VRAM größer BAR1** (Fermi ohne Resizable BAR), um die `io_reserve_lru`-Rückgewinnung unter Druck zu sehen. Auf dem Macmini3,1 ist BAR1 gleich VRAM gleich 256 MB, dort kann `-ENOSPC` gar nicht eintreten, also ist der ganze Zweig auf der Zielmaschine untestbar.
6. **dma-buf-Export mit Prime**, weil `->vmap` jetzt der treibereigene Pfad ist und die Abbildungsart für einseitige Puffer wechselt.

## Ehrlich zum Schluss

Kein Treiber im Baum hält heute eine dauerhafte TTM-Abbildung für einen Scanout-Puffer über einen dynamisch verwalteten Aperture-Ausschnitt. ast reicht einen Dauer-ioremap der VRAM-Blende durch (`ast/ast_mode.c:635`), i915 ein vorhandenes fbdev-vma, mgag200 `mdev->vram`. nouveaus BAR1 ist eine bezahlte, knappe Ressource mit bedingungslosem Abbau, und genau daran hängen alle Restrisiken oben. Dieser Patch betritt Neuland. Das gehört ins Anschreiben, und deshalb ist Jocelyns Angebot, ihn zu reviewen und zu testen, der richtige nächste Schritt.