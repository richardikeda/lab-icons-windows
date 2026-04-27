## 2026-04-27 - Reused squared icon canvas
**Learning:** The icon pipeline was preparing the same squared RGBA canvas twice per PNG, once for the clean preview and again for ICO generation.
**Action:** Keep future batch-processing changes reusing shared image intermediates before considering heavier optimizations.
