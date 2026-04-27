import sys
import time

from src.app_paths import AppPaths
from src.ui import IconMapperApp
from src.mapping_store import MappingStore
from src.perf_logger import PerfLogger
from src.reapply_service import reapply_changed


APP_PATHS = AppPaths.for_runtime()


def ensure_project_folders() -> None:
    APP_PATHS.ensure_mutable_dirs()


if __name__ == "__main__":
    ensure_project_folders()
    if "--reapply-once" in sys.argv:
        store = MappingStore(APP_PATHS.mappings_file)
        reapply_changed(store, only_global=True)
        raise SystemExit(0)
    if "--perf-smoke" in sys.argv:
        perf = PerfLogger(APP_PATHS.performance_log)
        started = time.perf_counter()
        app = IconMapperApp(APP_PATHS)
        app.update_idletasks()
        app.update()
        elapsed_ms = (time.perf_counter() - started) * 1000
        perf.log("app.perf_smoke", elapsed_ms)
        print(f"app.perf_smoke elapsed_ms={elapsed_ms:.2f}")
        app.destroy()
        raise SystemExit(0)
    app = IconMapperApp(APP_PATHS)
    app.mainloop()
