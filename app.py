from pathlib import Path
import sys
import time

from src.ui import IconMapperApp
from src.mapping_store import MappingStore
from src.perf_logger import PerfLogger
from src.reapply_service import reapply_changed


BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def ensure_project_folders() -> None:
    for folder in ("icons-in", "icons-out", "config"):
        (BASE_DIR / folder).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_project_folders()
    if "--reapply-once" in sys.argv:
        store = MappingStore(BASE_DIR / "config" / "mappings.json")
        reapply_changed(store, only_global=True)
        raise SystemExit(0)
    if "--perf-smoke" in sys.argv:
        perf = PerfLogger(BASE_DIR / "config" / "performance.log")
        started = time.perf_counter()
        app = IconMapperApp(BASE_DIR)
        app.update_idletasks()
        app.update()
        elapsed_ms = (time.perf_counter() - started) * 1000
        perf.log("app.perf_smoke", elapsed_ms)
        print(f"app.perf_smoke elapsed_ms={elapsed_ms:.2f}")
        app.destroy()
        raise SystemExit(0)
    app = IconMapperApp(BASE_DIR)
    app.mainloop()
