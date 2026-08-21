# v5, vorbereitet 22.08.2026, NICHT GESENDET

Antwort auf den Sashiko-Befund zur v4 (chan->fence plain veroeffentlicht,
Acquire auf ready deckt das kzalloc-Nullen nicht).

Loesung b: die Marke wandert aus dem Fence-Kontext in den Kanal, als
Zeiger `chan->fence_armed`, den NUR nouveau_fence_context_arm() schreibt
(release) und NUR nouveau_channel_kill() liest (acquire). Das bool ready
entfaellt. Kein Backend beruehrt. 42 Zeilen in vier Dateien.

Verschraenkungsbeweis identisch zur v4 (Struktur unveraendert, nur die
Marke ist ein Zeiger). Ein Schreiber, ein Leser, kein Plain-Store
dazwischen.

Branch: v5-respin in ~/linux-nouveau-patches, auf 1/3 der v4 aufgesetzt,
3/3 per cherry-pick unveraendert.

Warten auf Lyudes Review der v4. Moeglich ist auch, dass sie a) (Release
in den Backends, eigener Patch) oder "Nachtrag" bevorzugt. Dann faellt
diese v5 anders aus.
