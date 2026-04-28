## 2026-04-27 - Reused squared icon canvas
**Learning:** The icon pipeline was preparing the same squared RGBA canvas twice per PNG, once for the clean preview and again for ICO generation.
**Action:** Keep future batch-processing changes reusing shared image intermediates before considering heavier optimizations.

## 2026-04-27 - Removed duplicate PNG tree walk
**Learning:** Refreshing the icon library was scanning `icons-in/` twice in succession, once to sort PNGs and again to build the change snapshot used by polling.
**Action:** Keep future gallery and startup work reusing the same filesystem discovery results before adding heavier caching.

## 2026-04-27 - Skipped fallback ICO scan when PNG library exists
**Learning:** Startup was still walking `icons-out/ico/` recursively even though the gallery already prefers `icons-in/` whenever source PNGs are present.
**Action:** Keep gallery fallback work lazy and only scan generated outputs when the source library is empty.

## 2026-04-27 - Invalidated extracted icon preview cache on source changes
**Learning:** Preview PNGs extracted from Windows icon locations were keyed only by path and index, so app updates or shortcut icon changes could leave stale cached thumbnails visible in the UI.
**Action:** Keep future preview caches fingerprinted by source file metadata so UI state follows Windows file changes without manual cache cleanup.

## 2026-04-27 - Released Win32 handles after preview extraction
**Learning:** Native preview extraction for `.exe`, `.lnk`, and shell-backed icons was not releasing the screen `DC`, which risks handle buildup during repeated preview refreshes on Windows.
**Action:** Keep all Win32 preview paths wrapped in deterministic cleanup and extend cleanup checks when adding new native extraction code.

## 2026-04-27 - Bounded the in-memory thumbnail cache
**Learning:** The UI keeps `CTkImage` previews in memory, and fingerprinted preview filenames from refreshed icons can otherwise make that cache grow for the whole session.
**Action:** Keep future preview/image caches size-bounded and replace stale same-path entries when content fingerprints change.

## 2026-04-27 - Precomputed gallery metadata for rerenders
**Learning:** Filtering or rerendering the icon gallery was repeatedly recomputing each item's relative path, group, and ready state, including extra `stat()` calls for generated ICOs.
**Action:** Keep gallery refresh work centered on cached metadata built during source discovery, and reserve per-render file IO for preview assets only.

## 2026-04-27 - Replaced resolve-based discovery keys
**Learning:** Startup discovery and manual mapping creation were calling `Path.resolve()` only to build dedupe keys, adding unnecessary filesystem resolution work on every discovered `.lnk` and folder.
**Action:** Keep internal target keys based on normalized absolute Windows paths unless symlink-target identity is explicitly required.

## 2026-04-27 - Streamed applied ICO hashing
**Learning:** Applying shortcut and folder icons was loading each ICO fully into memory just to derive the versioned filename used for Explorer cache-busting.
**Action:** Keep future digest-based icon naming on streamed file reads so repeated applies stay content-based without avoidable memory spikes.

## 2026-04-27 - Normalized legacy performance log encoding
**Learning:** `config/performance.log` could become mixed-encoding on Windows when a UTF-16 redaction placeholder was left in place and runtime JSON lines were appended as UTF-8.
**Action:** Keep diagnostic logs normalized to one encoding at startup whenever local placeholder files or legacy mixed headers can appear.

## 2026-04-27 - Skipped unchanged batch icon work
**Learning:** The background package processor was re-encoding every PNG on every run even when both the generated `.ico` and cleaned preview `.png` were already newer than the source asset.
**Action:** Keep future bulk icon work gated by shared output-freshness checks so Windows batch actions skip unchanged files before starting worker threads.

## 2026-04-27 - Parallelized startup target discovery
**Learning:** Startup discovery time is dominated by three independent tasks: common-folder checks, recursive `.lnk` scanning, and `Get-StartApps`, so running them serially adds avoidable wall-clock delay.
**Action:** Keep future discovery expansions isolated enough to run concurrently instead of extending the serial startup path.
