from __future__ import annotations

import os
import queue
import threading
import time
import hashlib
import json
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
from PIL import Image

from src.app_discovery import DiscoveredTarget, _group_for_name, discover_targets, normalized_target_key
from src.appx_manager import AppxShortcutError, create_managed_appx_shortcut
from src.folder_manager import FolderIconError, read_folder_icon
from src.icon_pipeline import (
    discover_pngs,
    discover_png_entries,
    icon_group_for,
    migrate_legacy_icons,
    output_path_for,
    png_output_path_for,
    process_icon,
    processed_outputs_current,
    remove_edge_white_background,
    snapshot_pngs,
    soften_corner_marks,
)
from src.icon_preview import preview_for_icon_location
from src.mapping_store import AppMapping, MappingStore
from src.perf_logger import PerfLogger
from src.reapply_service import apply_mapping, capture_original_icon, reapply_changed, restore_mapping
from src.shortcut_manager import ShortcutError
from src.startup_manager import StartupError, disable_startup_reapply, enable_startup_reapply, is_startup_reapply_enabled
from src.theme_manager import ThemeImportError, delete_theme, import_theme
from src.windows_native import apply_native_window_style


DISCOVERED_IDLE_LIMIT = 120
DISCOVERED_SEARCH_LIMIT = 70
DISCOVERED_SEARCH_DEBOUNCE_MS = 180
ICON_IMAGE_CACHE_LIMIT = 512

ImageCacheSignature = tuple[int, int] | None
ImageCacheKey = tuple[Path, int, ImageCacheSignature]


@dataclass(frozen=True)
class GalleryEntry:
    item_path: Path
    generated_path: Path
    group: str
    relative_text: str
    search_text: str
    is_png: bool
    ready: bool


def remember_icon_image(
    cache: OrderedDict[ImageCacheKey, ctk.CTkImage],
    key: ImageCacheKey,
    image: ctk.CTkImage,
    *,
    limit: int = ICON_IMAGE_CACHE_LIMIT,
) -> None:
    stale_keys = [existing for existing in cache if existing[:2] == key[:2] and existing != key]
    for stale_key in stale_keys:
        del cache[stale_key]
    cache[key] = image
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)


def discover_gallery_icons(source_pngs: list[Path], output_dir: Path) -> list[Path]:
    if source_pngs:
        return []
    return sorted((output_dir / "ico").rglob("*.ico"), key=lambda path: path.stat().st_mtime, reverse=True)


def gallery_icon_ready(source_path: Path, generated_path: Path) -> bool:
    if source_path.suffix.lower() != ".png":
        return generated_path.exists()
    try:
        return generated_path.exists() and source_path.stat().st_mtime <= generated_path.stat().st_mtime
    except OSError:
        return False


def _gallery_group_for_ico(output_dir: Path, ico_path: Path) -> str:
    try:
        relative = ico_path.relative_to(output_dir / "ico")
    except ValueError:
        return "default"
    if len(relative.parts) <= 1:
        return "default"
    return str(Path(*relative.parts[:-1]))


def build_gallery_entries(input_dir: Path, output_dir: Path, gallery_items: list[Path]) -> list[GalleryEntry]:
    entries: list[GalleryEntry] = []
    for item in gallery_items:
        is_png = item.suffix.lower() == ".png"
        base = input_dir if is_png else output_dir / "ico"
        try:
            relative = str(item.relative_to(base))
        except ValueError:
            relative = item.name
        generated = output_path_for(input_dir, output_dir, item) if is_png else item
        entries.append(
            GalleryEntry(
                item_path=item,
                generated_path=generated,
                group=icon_group_for(input_dir, item) if is_png else _gallery_group_for_ico(output_dir, item),
                relative_text=relative,
                search_text=relative.casefold(),
                is_png=is_png,
                ready=gallery_icon_ready(item, generated),
            )
        )
    return entries


def discovered_search_text(target: DiscoveredTarget) -> str:
    return f"{target.name} {target.group} {target.path}".casefold()


def filter_discovered_targets(
    targets: list[DiscoveredTarget],
    index: dict[str, str],
    query: str,
) -> list[DiscoveredTarget]:
    terms = query.casefold().split()
    if not terms:
        return targets
    matched = []
    for target in targets:
        text = index.get(target.key) or discovered_search_text(target)
        if all(term in text for term in terms):
            matched.append(target)
    return matched


class IconMapperApp(ctk.CTk):
    def __init__(self, base_dir: Path) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.input_dir = base_dir / "icons-in"
        self.output_dir = base_dir / "icons-out"
        self.store = MappingStore(base_dir / "config" / "mappings.json")
        self.icon_cache_dir = base_dir / "config" / "icon-cache"
        self.perf = PerfLogger(base_dir / "config" / "performance.log")

        self.selected_mapping: AppMapping | None = None
        self.selected_icon: Path | None = None
        self.selected_png: Path | None = None
        self.source_pngs: list[Path] = []
        self.available_icons: list[Path] = []
        self.gallery_entries: list[GalleryEntry] = []
        self.discovered_targets: list[DiscoveredTarget] = []
        self.discovered_search_index: dict[str, str] = {}
        self.icon_images: OrderedDict[ImageCacheKey, ctk.CTkImage] = OrderedDict()
        self.process_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.processing = False
        self._icons_snapshot: tuple[tuple[str, int], ...] = ()
        self._discovered_render_after: str | None = None

        migrate_legacy_icons(self.output_dir)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self.title("Lab Icons Windows")
        self.geometry("1420x820")
        self.minsize(1180, 700)
        self.configure(fg_color="#0f1b34")

        with self.perf.measure("ui.build_layout"):
            self._build_layout()
        with self.perf.measure("ui.refresh_icons"):
            self.refresh_icons()
        with self.perf.measure("ui.refresh_mapping_list"):
            self.refresh_mapping_list()
        self.refresh_discovered_async()
        self._sync_global_settings()
        self._ensure_startup_reapply()
        self.after(80, lambda: apply_native_window_style(self))
        self.after(2000, self._poll_icon_folder)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1, minsize=560)
        self.grid_columnconfigure(2, weight=0, minsize=316)
        self.grid_rowconfigure(0, weight=1)
        self._build_targets_panel()
        self._build_editor_panel()
        self._build_icon_gallery()

    def _build_targets_panel(self) -> None:
        panel = ctk.CTkFrame(self, corner_radius=26, fg_color="#243553", border_width=1, border_color="#53627a")
        panel.grid(row=0, column=0, padx=(22, 0), pady=28, sticky="nsew")
        panel.grid_rowconfigure(4, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        title = ctk.CTkFrame(panel, fg_color="transparent")
        title.grid(row=0, column=0, padx=16, pady=(22, 12), sticky="ew")
        ctk.CTkLabel(title, text="◇", text_color="#60a5fa", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, rowspan=2, padx=(0, 8), sticky="w"
        )
        ctk.CTkLabel(title, text="Lab Icons", text_color="#f8fafc", font=ctk.CTkFont(size=21, weight="bold")).grid(
            row=0, column=1, sticky="w"
        )
        ctk.CTkLabel(title, text="Gerencie icones de atalhos e pastas", text_color="#a8b3c7", font=ctk.CTkFont(size=12)).grid(
            row=1, column=1, sticky="w"
        )
        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions,
            text="+   Adicionar App",
            height=32,
            anchor="w",
            fg_color="#34476b",
            hover_color="#40577f",
            text_color="#e5edf8",
            command=self.add_shortcut_mapping,
        ).grid(row=0, column=0, pady=(0, 8), sticky="ew")
        ctk.CTkButton(
            actions,
            text="▣   Adicionar Pasta",
            height=32,
            anchor="w",
            fg_color="#34476b",
            hover_color="#40577f",
            text_color="#e5edf8",
            command=self.add_folder_mapping,
        ).grid(row=1, column=0, sticky="ew")

        self.target_tabs = ctk.CTkSegmentedButton(
            panel,
            values=["Customizados", "Detectados"],
            fg_color="#192842",
            selected_color="#394c70",
            selected_hover_color="#445a82",
            unselected_color="#192842",
            unselected_hover_color="#263957",
            text_color="#dbe7f7",
            command=self._switch_target_tab,
        )
        self.target_tabs.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.target_tabs.set("Customizados")

        self.target_filter = ctk.CTkSegmentedButton(
            panel,
            values=["Todos", "Atalhos", "Pastas"],
            fg_color="#1d2d49",
            selected_color="#2f65a8",
            selected_hover_color="#3976bf",
            unselected_color="#2a3b5b",
            unselected_hover_color="#34496d",
            text_color="#d9e6f7",
            command=lambda _: self.refresh_mapping_list(),
        )
        self.target_filter.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.target_filter.set("Todos")

        self.list_stack = ctk.CTkFrame(panel, fg_color="transparent")
        self.list_stack.grid(row=4, column=0, padx=0, pady=(0, 14), sticky="nsew")
        self.list_stack.grid_columnconfigure(0, weight=1)
        self.list_stack.grid_rowconfigure(1, weight=1)

        self.discovered_filter = ctk.CTkEntry(
            self.list_stack,
            placeholder_text="Filtrar detectados...",
            fg_color="#1d2d49",
            border_color="#4a5b78",
            text_color="#e8f0fb",
            placeholder_text_color="#98a6ba",
        )
        self.discovered_filter.grid(row=0, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.discovered_filter.bind("<KeyRelease>", self._schedule_discovered_filter)
        self.mapping_list = ctk.CTkScrollableFrame(self.list_stack, fg_color="transparent", label_text="")
        self.discovered_list = ctk.CTkScrollableFrame(self.list_stack, fg_color="transparent", label_text="")
        self.mapping_list.grid(row=1, column=0, padx=8, pady=0, sticky="nsew")
        self.discovered_filter.grid_remove()

    def _build_editor_panel(self) -> None:
        panel = ctk.CTkFrame(self, corner_radius=22, fg_color="#293a5a", border_width=1, border_color="#465979")
        panel.grid(row=0, column=1, padx=12, pady=28, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)

        topbar = ctk.CTkFrame(panel, fg_color="#263756", height=34, corner_radius=20)
        topbar.grid(row=0, column=0, padx=12, pady=(10, 0), sticky="ew")
        topbar.grid_columnconfigure(1, weight=1)

        self.global_auto = ctk.CTkCheckBox(
            topbar,
            text="Reaplicar no boot",
            checkbox_width=34,
            checkbox_height=18,
            corner_radius=10,
            fg_color="#3b82f6",
            hover_color="#60a5fa",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.global_auto.grid(row=0, column=0, padx=(24, 8), pady=6, sticky="w")
        ctk.CTkButton(
            topbar,
            text="Salvar boot",
            width=76,
            height=28,
            fg_color="transparent",
            hover_color="#34486e",
            text_color="#cbd5e1",
            command=self.save_global_settings,
        ).grid(row=0, column=2, padx=(0, 8), pady=3, sticky="e")
        ctk.CTkButton(
            topbar,
            text="Ver config",
            width=76,
            height=28,
            fg_color="transparent",
            hover_color="#34486e",
            text_color="#cbd5e1",
            command=self.view_config_file,
        ).grid(row=0, column=3, padx=(0, 18), pady=3, sticky="e")

        self.status_label = ctk.CTkLabel(panel, text="Pronto.", anchor="w", text_color="#aab7cc", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=1, column=0, padx=32, pady=(12, 0), sticky="ew")

        preview_stage = ctk.CTkFrame(panel, fg_color="#334665", border_width=1, border_color="#52627c", corner_radius=24)
        preview_stage.grid(row=2, column=0, padx=32, pady=(18, 20), sticky="ew")
        preview_stage.grid_columnconfigure((0, 1, 2), weight=1)
        self.original_preview = ctk.CTkLabel(
            preview_stage,
            text="Original",
            text_color="#aab7cc",
            compound="top",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=152,
            height=168,
        )
        arrow = ctk.CTkLabel(preview_stage, text="->", text_color="#7b8aa1", font=ctk.CTkFont(size=34))
        self.custom_preview = ctk.CTkLabel(
            preview_stage,
            text="Novo icone",
            text_color="#f8fafc",
            compound="top",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=208,
            height=208,
            fg_color="#263551",
            corner_radius=24,
        )
        self.original_preview.grid(row=0, column=0, padx=(36, 8), pady=34)
        arrow.grid(row=0, column=1, padx=8, pady=34)
        self.custom_preview.grid(row=0, column=2, padx=(8, 36), pady=34)

        form = ctk.CTkFrame(panel, fg_color="transparent")
        form.grid(row=3, column=0, padx=32, pady=(0, 24), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(2, weight=0, minsize=158)
        form.grid_columnconfigure(3, weight=0, minsize=180)

        entry_style = {
            "fg_color": "#32435f",
            "border_color": "#53647e",
            "text_color": "#f8fafc",
            "placeholder_text_color": "#9aa8bc",
            "corner_radius": 14,
            "height": 34,
        }
        segment_style = {
            "fg_color": "#151f33",
            "selected_color": "#334866",
            "selected_hover_color": "#3d5478",
            "unselected_color": "#151f33",
            "unselected_hover_color": "#253752",
            "text_color": "#f8fafc",
        }
        self.target_path = ctk.CTkEntry(form, placeholder_text="Caminho do atalho ou pasta", **entry_style)
        self.program_name = ctk.CTkEntry(form, placeholder_text="Nome do destino", **entry_style)
        self.program_group = ctk.CTkEntry(form, placeholder_text="Tema ou grupo", **entry_style)
        self.icon_group = ctk.CTkEntry(form, placeholder_text="Grupo do icone", **entry_style)
        self.asset_choice = ctk.CTkSegmentedButton(form, values=["ICO", "PNG limpo"], **segment_style)
        self.asset_choice.set("ICO")
        self.kind_choice = ctk.CTkSegmentedButton(
            form,
            values=["Atalho", "Pasta"],
            command=lambda value: self.asset_choice.set(self._recommended_asset(value)),
            **segment_style,
        )
        self.kind_choice.set("Atalho")

        ctk.CTkLabel(form, text="Destino", text_color="#aab7cc", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=(0, 12), pady=(0, 6), sticky="w"
        )
        self.target_path.grid(row=1, column=0, columnspan=2, padx=(0, 12), pady=(0, 18), sticky="ew")
        self.program_name.configure(state="disabled")
        ctk.CTkButton(
            form,
            text="Localizar",
            height=34,
            fg_color="#3a4b69",
            hover_color="#465b7f",
            text_color="#f8fafc",
            corner_radius=14,
            command=self.pick_target,
        ).grid(row=1, column=2, padx=(0, 12), pady=(0, 18), sticky="ew")

        ctk.CTkLabel(form, text="Tipo", text_color="#aab7cc", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=3, padx=(0, 0), pady=(0, 6), sticky="w"
        )
        self.kind_choice.grid(row=1, column=3, padx=(0, 0), pady=(0, 18), sticky="ew")

        ctk.CTkLabel(form, text="Nome", text_color="#aab7cc", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, padx=(0, 12), pady=(0, 6), sticky="w"
        )
        self.program_name.grid(row=3, column=0, padx=(0, 12), pady=(0, 18), sticky="ew")

        ctk.CTkLabel(form, text="Tema (Agrupamento)", text_color="#aab7cc", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=1, padx=(0, 12), pady=(0, 6), sticky="w"
        )
        self.program_group.grid(row=3, column=1, columnspan=2, padx=(0, 12), pady=(0, 18), sticky="ew")

        ctk.CTkLabel(form, text="Asset preferido", text_color="#aab7cc", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=3, padx=(0, 0), pady=(0, 6), sticky="w"
        )
        self.asset_choice.grid(row=3, column=3, padx=(0, 0), pady=(0, 18), sticky="ew")

        self.selected_icon_label = ctk.CTkLabel(
            form,
            text="Nenhum icone selecionado.",
            anchor="w",
            text_color="#aab7cc",
            font=ctk.CTkFont(size=12),
        )
        self.selected_icon_label.grid(row=4, column=0, columnspan=4, pady=(2, 18), sticky="ew")

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=5, column=0, columnspan=4, pady=(0, 18), sticky="ew")
        actions.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(
            actions,
            text="Salvar e aplicar",
            width=200,
            height=48,
            fg_color="#2f80ff",
            hover_color="#1f6ee8",
            text_color="#ffffff",
            corner_radius=14,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.apply_selected_icon,
        ).grid(row=0, column=0, padx=(0, 12), sticky="w")
        ctk.CTkButton(
            actions,
            text="Verificar agora",
            width=150,
            height=48,
            fg_color="#354661",
            hover_color="#425876",
            text_color="#f8fafc",
            corner_radius=14,
            command=self.check_and_reapply,
        ).grid(row=0, column=1, padx=(0, 12), sticky="w")
        ctk.CTkButton(
            actions,
            text="Remover customizacao",
            width=180,
            height=48,
            fg_color="transparent",
            hover_color="#4a2632",
            text_color="#f87171",
            corner_radius=14,
            command=self.remove_selected,
        ).grid(row=0, column=3, sticky="e")

        bulk = ctk.CTkFrame(form, fg_color="transparent")
        bulk.grid(row=6, column=0, columnspan=4, sticky="ew")
        bulk.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkButton(
            bulk,
            text="Carregar grupo de icones",
            height=36,
            fg_color="#34476b",
            hover_color="#40577f",
            text_color="#e5edf8",
            corner_radius=12,
            command=self.load_icon_group,
        ).grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(
            bulk,
            text="Importar tema",
            height=36,
            fg_color="#34476b",
            hover_color="#40577f",
            text_color="#e5edf8",
            corner_radius=12,
            command=self.import_theme_package,
        ).grid(row=0, column=1, padx=(0, 8), sticky="ew")
        ctk.CTkButton(
            bulk,
            text="Excluir tema",
            height=36,
            fg_color="#34476b",
            hover_color="#40577f",
            text_color="#e5edf8",
            corner_radius=12,
            command=self.delete_theme_package,
        ).grid(row=0, column=2, padx=(0, 8), sticky="ew")
        ctk.CTkButton(
            bulk,
            text="Remover todos customizados",
            height=36,
            fg_color="#5f2430",
            hover_color="#7f1d1d",
            text_color="#fee2e2",
            corner_radius=12,
            command=self.remove_all_customized,
        ).grid(row=0, column=3, sticky="ew")

        ctk.CTkLabel(
            form,
            text="Selecione um PNG na biblioteca para preparar apenas aquele icone. O pacote roda em segundo plano no rodape da biblioteca.",
            text_color="#9aa8bc",
            wraplength=620,
            justify="left",
            font=ctk.CTkFont(size=12),
        ).grid(row=7, column=0, columnspan=4, pady=(18, 0), sticky="w")

    def _build_icon_gallery(self) -> None:
        panel = ctk.CTkFrame(self, corner_radius=26, fg_color="#2b3b5d", border_width=1, border_color="#53627a")
        panel.grid(row=0, column=2, padx=(0, 22), pady=28, sticky="nsew")
        panel.grid_rowconfigure(3, weight=1)
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text="Biblioteca Visual",
            text_color="#f8fafc",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(18, 2), sticky="w")
        ctk.CTkLabel(
            panel,
            text="assets disponiveis em icons-in/",
            text_color="#9aa8bc",
            font=ctk.CTkFont(size=10),
        ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        search_wrap = ctk.CTkFrame(panel, fg_color="transparent")
        search_wrap.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        search_wrap.grid_columnconfigure(0, weight=1)
        self.icon_filter = ctk.CTkEntry(
            search_wrap,
            placeholder_text="Filtrar por nome...",
            fg_color="#32415c",
            border_color="#59687f",
            text_color="#f8fafc",
            placeholder_text_color="#9aa8bc",
            corner_radius=14,
            height=36,
        )
        self.icon_filter.grid(row=0, column=0, sticky="ew")
        self.icon_filter.bind("<KeyRelease>", lambda _: self.refresh_icon_gallery())
        self.icon_gallery = ctk.CTkScrollableFrame(panel, fg_color="transparent", label_text="")
        self.icon_gallery.grid(row=3, column=0, padx=12, pady=(0, 10), sticky="nsew")

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.grid(row=4, column=0, padx=16, pady=(0, 18), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self.process_button = ctk.CTkButton(
            footer,
            text="Processar pacote em background",
            height=40,
            fg_color="#2f80ff",
            hover_color="#1f6ee8",
            text_color="#ffffff",
            corner_radius=14,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.start_processing,
        )
        self.process_button.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        ctk.CTkButton(
            footer,
            text="Abrir pasta icons-out",
            height=36,
            fg_color="transparent",
            hover_color="#3a4d70",
            text_color="#cbd5e1",
            corner_radius=14,
            command=self.open_generated_icons_folder,
        ).grid(row=1, column=0, sticky="ew")

    def refresh_icons(self) -> None:
        # Reuse one directory walk for sorting and change detection to trim startup and refresh IO.
        png_entries = discover_png_entries(self.input_dir)
        self.source_pngs = [path for path, _mtime_ns in sorted(png_entries, key=lambda item: item[1], reverse=True)]
        # Skip the fallback ICO tree walk when the source PNG library is already available.
        self.available_icons = discover_gallery_icons(self.source_pngs, self.output_dir)
        self.gallery_entries = build_gallery_entries(self.input_dir, self.output_dir, self.source_pngs or self.available_icons)
        self._icons_snapshot = snapshot_pngs(png_entries)
        self.refresh_icon_gallery()

    def _poll_icon_folder(self) -> None:
        current = self._snapshot_icons()
        if current != self._icons_snapshot:
            self.refresh_icons()
            self.set_status("Biblioteca atualizada.")
        self.after(2000, self._poll_icon_folder)

    def _snapshot_icons(self) -> tuple[tuple[str, int], ...]:
        return snapshot_pngs(discover_png_entries(self.input_dir))

    def refresh_icon_gallery(self) -> None:
        started = time.perf_counter()
        for child in self.icon_gallery.winfo_children():
            child.destroy()
        needle = self.icon_filter.get().strip().lower() if hasattr(self, "icon_filter") else ""
        grouped: dict[str, list[GalleryEntry]] = defaultdict(list)
        gallery_items = self.gallery_entries
        for entry in gallery_items:
            if needle and needle not in entry.search_text:
                continue
            grouped[entry.group].append(entry)
        if not grouped:
            ctk.CTkLabel(
                self.icon_gallery,
                text="Coloque PNGs em icons-in para montar a biblioteca.",
                text_color="#aab7cc",
            ).pack(anchor="w", padx=10, pady=10)
            return
        for group, icons in sorted(grouped.items()):
            ctk.CTkLabel(
                self.icon_gallery,
                text=group.upper(),
                text_color="#9aa8bc",
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(anchor="w", padx=10, pady=(12, 4))
            grid = ctk.CTkFrame(self.icon_gallery, fg_color="transparent")
            grid.pack(fill="x", padx=6, pady=(0, 6))
            grid.grid_columnconfigure((0, 1), weight=1, uniform="icons")
            for index, entry in enumerate(icons):
                item = entry.item_path
                preview_path = self._gallery_preview_for_source(item) if entry.is_png else self._png_for_ico(item)
                button = ctk.CTkButton(
                    grid,
                    text=f"{item.stem}\n{'pronto' if entry.ready else 'novo'}",
                    image=self._icon_image(preview_path or item),
                    compound="top",
                    width=92,
                    height=104,
                    fg_color=self._icon_button_color(entry.generated_path),
                    hover_color="#465a7d",
                    text_color="#d8e3f3",
                    corner_radius=18,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    command=lambda source=item: self.select_source_icon(source),
                )
                button.grid(row=index // 2, column=index % 2, padx=5, pady=5, sticky="nsew")
        self.perf.log("ui.refresh_icon_gallery", (time.perf_counter() - started) * 1000, items=len(gallery_items))

    def refresh_mapping_list(self) -> None:
        started = time.perf_counter()
        for child in self.mapping_list.winfo_children():
            child.destroy()
        selected_filter = self.target_filter.get() if hasattr(self, "target_filter") else "Todos"
        grouped: dict[str, list[AppMapping]] = defaultdict(list)
        for mapping in self.store.mappings:
            if selected_filter == "Atalhos" and mapping.target_type != "shortcut":
                continue
            if selected_filter == "Pastas" and mapping.target_type != "folder":
                continue
            grouped[mapping.program_group or "Sem grupo"].append(mapping)
        if not grouped:
            ctk.CTkLabel(self.mapping_list, text="Nenhum customizado ainda.", text_color="#aab7cc").pack(anchor="w", padx=10, pady=10)
            return
        for group, mappings in sorted(grouped.items()):
            ctk.CTkLabel(
                self.mapping_list,
                text=group.upper(),
                text_color="#9aa8bc",
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(anchor="w", padx=10, pady=(12, 4))
            for mapping in sorted(mappings, key=lambda item: item.program_name.lower()):
                self._render_mapping_row(mapping)
        self.perf.log("ui.refresh_mapping_list.render", (time.perf_counter() - started) * 1000, items=len(self.store.mappings))

    def _switch_target_tab(self, value: str) -> None:
        if value == "Detectados":
            self.mapping_list.grid_remove()
            self.target_filter.grid_remove()
            self.discovered_filter.grid()
            self.discovered_list.grid(row=1, column=0, padx=8, pady=0, sticky="nsew")
            self.refresh_discovered_list()
        else:
            self.discovered_list.grid_remove()
            self.discovered_filter.grid_remove()
            self.target_filter.grid()
            self.mapping_list.grid(row=1, column=0, padx=8, pady=0, sticky="nsew")
            self.refresh_mapping_list()

    def refresh_discovered_async(self) -> None:
        threading.Thread(target=self._discover_worker, daemon=True).start()

    def _discover_worker(self) -> None:
        started = time.perf_counter()
        targets = discover_targets()
        index = {target.key: discovered_search_text(target) for target in targets}
        self.discovered_targets = targets
        self.discovered_search_index = index
        self.perf.log("discovery.targets", (time.perf_counter() - started) * 1000, items=len(targets))
        try:
            self.after(0, self.refresh_discovered_list)
        except RuntimeError:
            return

    def _schedule_discovered_filter(self, _event: object | None = None) -> None:
        if hasattr(self, "target_tabs") and self.target_tabs.get() != "Detectados":
            return
        if self._discovered_render_after:
            self.after_cancel(self._discovered_render_after)
        self._discovered_render_after = self.after(DISCOVERED_SEARCH_DEBOUNCE_MS, self._run_scheduled_discovered_filter)

    def _run_scheduled_discovered_filter(self) -> None:
        self._discovered_render_after = None
        self.refresh_discovered_list()

    def refresh_discovered_list(self) -> None:
        if hasattr(self, "target_tabs") and self.target_tabs.get() != "Detectados":
            return
        started = time.perf_counter()
        for child in self.discovered_list.winfo_children():
            child.destroy()
        needle = self.discovered_filter.get().strip() if hasattr(self, "discovered_filter") else ""
        custom_keys = {mapping.known_key for mapping in self.store.mappings if mapping.known_key}
        grouped: dict[str, list[DiscoveredTarget]] = defaultdict(list)
        matched_targets = filter_discovered_targets(self.discovered_targets, self.discovered_search_index, needle)
        limit = DISCOVERED_SEARCH_LIMIT if needle else DISCOVERED_IDLE_LIMIT
        visible_targets = matched_targets[:limit]
        for target in visible_targets:
            grouped[target.group].append(target)
        if not grouped:
            ctk.CTkLabel(self.discovered_list, text="Nenhum item encontrado nesse filtro.", text_color="#aab7cc").pack(anchor="w", padx=10, pady=10)
            return
        if len(matched_targets) > len(visible_targets):
            ctk.CTkLabel(
                self.discovered_list,
                text=f"Mostrando {len(visible_targets)} de {len(matched_targets)}. Refine o filtro para ver menos itens.",
                text_color="#9aa8bc",
                wraplength=250,
                justify="left",
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=10, pady=(0, 8))
        for group, targets in sorted(grouped.items()):
            ctk.CTkLabel(
                self.discovered_list,
                text=group.upper(),
                text_color="#9aa8bc",
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(anchor="w", padx=10, pady=(12, 4))
            for target in targets:
                self._render_discovered_row(target, "customizado" if target.key in custom_keys else "disponivel", target.key in custom_keys)
        self.perf.log(
            "ui.refresh_discovered_list.render",
            (time.perf_counter() - started) * 1000,
            items=len(visible_targets),
            matches=len(matched_targets),
            query=bool(needle),
        )

    def start_processing(self) -> None:
        if self.processing:
            return
        pngs = list(self.source_pngs) if self.source_pngs else discover_pngs(self.input_dir)
        if not pngs:
            self.set_status("Nenhum PNG encontrado em icons-in.")
            return
        self.processing = True
        self.process_button.configure(state="disabled", text="Processando...")
        threading.Thread(target=self._process_worker, args=(pngs,), daemon=True).start()
        self.after(80, self._drain_process_queue)

    def _process_worker(self, pngs: list[Path]) -> None:
        started = time.perf_counter()
        pending = [png for png in pngs if not processed_outputs_current(self.input_dir, self.output_dir, png)]
        if not pending:
            self.perf.log("icons.process_batch", (time.perf_counter() - started) * 1000, items=0, skipped=len(pngs), workers=0)
            self.process_queue.put(("finished", 0))
            return
        workers = min(4, max(1, (os.cpu_count() or 2) - 1), len(pending))
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_icon, self.input_dir, self.output_dir, png): png for png in pending}
            for future in as_completed(futures):
                png_path = futures[future]
                try:
                    processed = future.result()
                except Exception as exc:
                    self.process_queue.put(("error", (png_path, str(exc))))
                else:
                    self.process_queue.put(("done", processed))
                done += 1
                if done % 8 == 0:
                    self.process_queue.put(("progress", done))
        self.perf.log(
            "icons.process_batch",
            (time.perf_counter() - started) * 1000,
            items=len(pending),
            skipped=len(pngs) - len(pending),
            workers=workers,
        )
        self.process_queue.put(("finished", len(pending)))

    def _drain_process_queue(self) -> None:
        events = 0
        while events < 40:
            try:
                event, payload = self.process_queue.get_nowait()
            except queue.Empty:
                break
            events += 1
            if event == "done":
                self.set_status(f"Processado: {payload.source_path.name}")
            elif event == "error":
                path, error = payload
                self.set_status(f"Erro em {path.name}: {error[:80]}")
            elif event == "progress":
                self.set_status(f"Processados {payload} PNGs...")
            elif event == "finished":
                self.processing = False
                self.process_button.configure(state="normal", text="Processar pacote")
                self.refresh_icons()
                self.set_status(f"Pacote concluido: {payload} arquivo(s).")
        if self.processing:
            self.after(80, self._drain_process_queue)

    def add_shortcut_mapping(self) -> None:
        path = filedialog.askopenfilename(title="Selecione um atalho", filetypes=[("Atalhos", "*.lnk")])
        if path:
            self._create_mapping(
                Path(path),
                "shortcut",
                known_key=f"shortcut:{normalized_target_key(Path(path))}",
                original_icon=str(Path(path)),
            )

    def add_folder_mapping(self) -> None:
        path = filedialog.askdirectory(title="Selecione uma pasta")
        if path:
            folder = Path(path)
            self._create_mapping(
                folder,
                "folder",
                known_key=f"folder:{normalized_target_key(folder)}",
                original_icon=read_folder_icon(folder),
            )

    def create_from_discovered(self, target: DiscoveredTarget) -> None:
        existing = next((mapping for mapping in self.store.mappings if mapping.known_key == target.key), None)
        if existing:
            self.select_mapping(existing)
            self.target_tabs.set("Customizados")
            return
        if target.target_type == "appx":
            try:
                shortcut = create_managed_appx_shortcut(target.path, target.name, self.base_dir / "config" / "managed-shortcuts")
            except AppxShortcutError as exc:
                messagebox.showerror("App do Windows", str(exc))
                return
            self._create_mapping(
                shortcut,
                "shortcut",
                group=target.group,
                known_key=target.key,
                display_name=target.name,
                original_icon=str(shortcut),
            )
        else:
            self._create_mapping(
                Path(target.path),
                target.target_type,
                group=target.group,
                known_key=target.key,
                original_icon=target.original_icon or target.current_icon,
            )
        self.target_tabs.set("Customizados")

    def _create_mapping(
        self,
        target: Path,
        target_type: str,
        group: str = "Sem grupo",
        known_key: str = "",
        display_name: str = "",
        original_icon: str = "",
    ) -> None:
        existing = self._find_existing_mapping(target, known_key)
        if existing:
            self.select_mapping(existing)
            return
        if target_type == "folder" and not original_icon:
            original_icon = read_folder_icon(target)
        icon_path = None
        mapping = self.store.add_mapping(
            program_name=display_name or target.stem or target.name,
            program_group=group,
            shortcut_path=str(target),
            icon_group=self._group_for_ico(icon_path) if icon_path else "default",
            source_icon=self._source_for_ico(icon_path) if icon_path else "",
            ico_path=str(icon_path) if icon_path else "",
            png_path=str(self._png_for_ico(icon_path)) if icon_path and self._png_for_ico(icon_path) else "",
            auto_reapply=False,
            target_type=target_type,
            known_key=known_key,
            original_icon=original_icon,
            preferred_asset=self._recommended_asset("Pasta" if target_type == "folder" else "Atalho").lower().replace(" limpo", ""),
        )
        self.refresh_mapping_list()
        self.refresh_discovered_list()
        self.select_mapping(mapping)

    def select_mapping(self, mapping: AppMapping) -> None:
        self.selected_mapping = mapping
        if mapping.target_type == "folder" and not mapping.original_icon:
            folder_icon = read_folder_icon(Path(mapping.shortcut_path))
            if folder_icon:
                mapping.original_icon = folder_icon
                self.store.update_mapping(mapping)
        self.kind_choice.set("Pasta" if mapping.target_type == "folder" else "Atalho")
        self._set_disabled_entry(self.program_name, mapping.program_name)
        self._set_entry(self.program_group, mapping.program_group)
        self._set_entry(self.target_path, mapping.shortcut_path)
        self._set_entry(self.icon_group, mapping.icon_group)
        self.asset_choice.set("PNG limpo" if mapping.preferred_asset == "png" else "ICO")
        if mapping.ico_path:
            self.select_icon(Path(mapping.ico_path), update_gallery=False)
        else:
            self._clear_selected_icon()
        self._refresh_previews(mapping)
        self.set_status(f"Selecionado: {mapping.program_name}")

    def select_source_icon(self, source: Path) -> None:
        if source.suffix.lower() != ".png":
            self.select_icon(source)
            return
        generated = output_path_for(self.input_dir, self.output_dir, source)
        if self._needs_processing(source, generated):
            self.set_status(f"Preparando {source.name}...")
            threading.Thread(target=self._process_single_icon_worker, args=(source,), daemon=True).start()
            return
        self.select_icon(generated)

    def _process_single_icon_worker(self, source: Path) -> None:
        started = time.perf_counter()
        try:
            processed = process_icon(self.input_dir, self.output_dir, source)
        except Exception as exc:
            self.after(0, lambda: self.set_status(f"Erro ao preparar {source.name}: {exc}"))
            return
        self.perf.log("icons.process_single", (time.perf_counter() - started) * 1000, icon=source.name)
        self.after(0, lambda: self._finish_single_icon(processed.output_path))

    def _finish_single_icon(self, icon: Path) -> None:
        self.refresh_icons()
        self.select_icon(icon)
        self.set_status(f"Icone preparado: {icon.name}")

    def select_icon(self, icon: Path, update_gallery: bool = True) -> None:
        self.selected_icon = icon
        self.selected_png = self._png_for_ico(icon)
        detail = f"Icone selecionado: {self._relative_output(str(icon))}"
        if self.selected_png:
            detail += " | PNG limpo disponivel"
        self.selected_icon_label.configure(text=detail)
        self._set_entry(self.icon_group, self._group_for_ico(icon))
        self.custom_preview.configure(image=self._preview_image(self.selected_png or icon), text="Novo")
        if update_gallery:
            self.refresh_icon_gallery()

    def save_selected(self) -> bool:
        if not self.selected_mapping:
            messagebox.showinfo("Lab Icons Windows", "Selecione ou adicione um destino primeiro.")
            return False
        if self.selected_icon is None:
            messagebox.showinfo("Lab Icons Windows", "Importe ou selecione um icone primeiro.")
            return False
        self.selected_mapping.program_name = self.program_name.get().strip() or self._derive_name(Path(self.target_path.get()))
        self.selected_mapping.program_group = self.program_group.get().strip() or "Sem grupo"
        self.selected_mapping.shortcut_path = self.target_path.get().strip()
        self.selected_mapping.target_type = "folder" if self.kind_choice.get() == "Pasta" else "shortcut"
        self.selected_mapping.icon_group = self.icon_group.get().strip() or self._group_for_ico(self.selected_icon)
        self.selected_mapping.ico_path = str(self.selected_icon)
        self.selected_mapping.png_path = str(self.selected_png or "")
        self.selected_mapping.source_icon = self._source_for_ico(self.selected_icon)
        self.selected_mapping.preferred_asset = "png" if self.asset_choice.get() == "PNG limpo" else "ico"
        self.selected_mapping.auto_reapply = True
        self.store.update_mapping(self.selected_mapping)
        self.refresh_mapping_list()
        self.refresh_discovered_list()
        self.set_status("Mapeamento salvo.")
        return True

    def apply_selected_icon(self) -> None:
        if not self.save_selected():
            return
        assert self.selected_mapping is not None
        try:
            capture_original_icon(self.selected_mapping)
            apply_mapping(self.selected_mapping)
        except (ShortcutError, FolderIconError) as exc:
            messagebox.showerror("Nao foi possivel aplicar", str(exc))
            return
        self.selected_mapping.is_customized = True
        self.selected_mapping.auto_reapply = True
        self.store.update_mapping(self.selected_mapping)
        self._refresh_previews(self.selected_mapping)
        self.refresh_mapping_list()
        self.refresh_discovered_list()
        self.set_status("Icone aplicado.")

    def check_and_reapply(self) -> None:
        applied, errors = reapply_changed(self.store)
        detail = f"{applied} reaplicado(s)"
        if errors:
            detail += f", {errors} erro(s)"
        self.set_status(f"Verificacao concluida: {detail}.")

    def save_global_settings(self) -> None:
        enabled = bool(self.global_auto.get())
        self.store.settings["global_auto_reapply"] = enabled
        self.store.settings["startup_reapply_enabled"] = enabled
        try:
            if enabled:
                enable_startup_reapply(self.base_dir / "app.py")
            else:
                disable_startup_reapply()
        except StartupError as exc:
            messagebox.showerror("Inicializacao automatica", str(exc))
            return
        self.store.save()
        self.set_status("Configuracao global salva.")

    def _ensure_startup_reapply(self) -> None:
        if not self.store.settings.get("startup_reapply_enabled", True):
            return
        try:
            enable_startup_reapply(self.base_dir / "app.py")
        except StartupError as exc:
            self.store.settings["startup_reapply_enabled"] = False
            self.store.save()
            self.set_status(f"Reaplicacao no boot desativada: {exc}")

    def view_config_file(self) -> None:
        self.store.save()
        try:
            content = self.store.path.read_text(encoding="utf-8")
            parsed = json.loads(content)
            content = json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            content = self.store.path.read_text(encoding="utf-8", errors="replace")

        window = ctk.CTkToplevel(self)
        window.title("mappings.json")
        window.geometry("900x640")
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            window,
            text=str(self.store.path),
            anchor="w",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        text = ctk.CTkTextbox(window, fg_color="#111827", text_color="#e5edf8", wrap="none")
        text.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        text.insert("1.0", content)
        text.configure(state="disabled")

    def import_theme_package(self) -> None:
        choice = messagebox.askyesno("Importar tema", "Importar de ZIP?\n\nEscolha 'Nao' para selecionar uma pasta.")
        if choice:
            source = filedialog.askopenfilename(title="Selecione o ZIP do tema", filetypes=[("Temas ZIP", "*.zip")])
        else:
            source = filedialog.askdirectory(title="Selecione a pasta do tema")
        if not source:
            return
        started = time.perf_counter()
        try:
            result = import_theme(Path(source), self.input_dir)
        except ThemeImportError as exc:
            messagebox.showerror("Importar tema", str(exc))
            return
        self.refresh_icons()
        created = self._create_theme_mappings(result.theme_name, result.associations)
        self.perf.log("themes.import", (time.perf_counter() - started) * 1000, items=len(result.png_paths), mappings=created)
        self.set_status(f"Tema '{result.theme_name}' importado: {len(result.png_paths)} PNG(s), {created} associacao(oes).")

    def delete_theme_package(self) -> None:
        theme = simpledialog.askstring("Excluir tema", "Nome do tema importado:")
        if not theme:
            return
        if not messagebox.askyesno("Excluir tema", f"Excluir arquivos do tema '{theme}' e seus mapeamentos?"):
            return
        try:
            delete_theme(theme, self.input_dir)
        except ThemeImportError as exc:
            messagebox.showerror("Excluir tema", str(exc))
            return
        kept = []
        errors = 0
        for mapping in self.store.mappings:
            if mapping.theme_name.casefold() != theme.casefold():
                kept.append(mapping)
                continue
            if mapping.is_customized:
                try:
                    restore_mapping(mapping)
                except (ShortcutError, FolderIconError):
                    errors += 1
        self.store.mappings = kept
        self.store.save()
        self.refresh_icons()
        self.refresh_mapping_list()
        self.set_status(f"Tema '{theme}' excluido. Erros ao restaurar: {errors}.")

    def _create_theme_mappings(self, theme_name: str, associations: object) -> int:
        created = 0
        targets = {target.key: target for target in self.discovered_targets}
        for association in associations:
            generated = output_path_for(self.input_dir, self.output_dir, association.icon_path)
            if self._needs_processing(association.icon_path, generated):
                try:
                    process_icon(self.input_dir, self.output_dir, association.icon_path)
                except Exception:
                    continue
            target = self._match_theme_target(association.program_name, association.target_path, association.target_type, targets)
            if not target:
                continue
            if target.target_type == "appx":
                try:
                    target_path = create_managed_appx_shortcut(
                        target.path,
                        target.name,
                        self.base_dir / "config" / "managed-shortcuts",
                    )
                except AppxShortcutError:
                    continue
                target_type = "shortcut"
            else:
                target_path = Path(target.path)
                target_type = target.target_type
            mapping = self._find_existing_mapping(target_path, target.key)
            if not mapping:
                self._create_mapping(
                    target_path,
                    target_type,
                    group=association.program_group or target.group,
                    known_key=target.key,
                    display_name=target.name,
                    original_icon=target.original_icon or target.current_icon,
                )
                mapping = self.selected_mapping
            if not mapping:
                continue
            mapping.ico_path = str(generated)
            mapping.png_path = str(png_output_path_for(self.input_dir, self.output_dir, association.icon_path))
            mapping.source_icon = str(association.icon_path)
            mapping.icon_group = icon_group_for(self.input_dir, association.icon_path)
            mapping.program_group = association.program_group or mapping.program_group
            mapping.theme_name = theme_name
            mapping.auto_reapply = True
            self.store.update_mapping(mapping)
            created += 1
        self.refresh_mapping_list()
        self.refresh_discovered_list()
        return created

    def _match_theme_target(
        self,
        program_name: str,
        target_path: str,
        target_type: str,
        targets: dict[str, DiscoveredTarget],
    ) -> DiscoveredTarget | None:
        if target_path:
            normalized = normalized_target_key(Path(target_path))
            return next((target for target in targets.values() if normalized_target_key(Path(target.path)) == normalized), None)
        terms = program_name.casefold().split()
        if not terms:
            return None
        return next(
            (
                target
                for target in targets.values()
                if target.target_type == target_type or target_type == "shortcut"
                if all(term in target.name.casefold() for term in terms)
            ),
            None,
        )

    def remove_selected(self) -> None:
        if not self.selected_mapping:
            return
        if self.selected_mapping.is_customized:
            if not messagebox.askyesno("Remover customizacao", "Restaurar/remover a customizacao deste item?"):
                return
            try:
                restore_mapping(self.selected_mapping)
            except (ShortcutError, FolderIconError) as exc:
                messagebox.showerror("Nao foi possivel restaurar", str(exc))
                return
        self.store.remove_mapping(self.selected_mapping.id)
        self.selected_mapping = None
        self.refresh_mapping_list()
        self.refresh_discovered_list()
        self.set_status("Item removido.")

    def remove_all_customized(self) -> None:
        if not messagebox.askyesno(
            "Remover todos customizados",
            "Isso tentara restaurar atalhos e remover desktop.ini criado pelo app nas pastas. Continuar?",
        ):
            return
        errors = 0
        for mapping in list(self.store.mappings):
            if mapping.is_customized:
                try:
                    restore_mapping(mapping)
                except (ShortcutError, FolderIconError):
                    errors += 1
        self.store.mappings = [mapping for mapping in self.store.mappings if not mapping.is_customized]
        self.store.save()
        self.selected_mapping = None
        self.refresh_mapping_list()
        self.refresh_discovered_list()
        self.set_status(f"Customizacoes removidas. Erros: {errors}.")

    def load_icon_group(self) -> None:
        folder = filedialog.askdirectory(title="Escolha um grupo dentro de icons-out/ico", initialdir=str(self.output_dir / "ico"))
        if not folder:
            return
        icons = sorted(Path(folder).rglob("*.ico"))
        if not icons:
            messagebox.showinfo("Carregar grupo", "Nenhum .ico encontrado nesse grupo.")
            return
        targets = {target.key: target for target in self.discovered_targets}
        applied = 0
        for icon in icons:
            stem = icon.stem.lower()
            match = next((target for target in targets.values() if stem in target.name.lower()), None)
            if not match:
                continue
            mapping = next((item for item in self.store.mappings if item.known_key == match.key), None)
            if not mapping:
                self._create_mapping(Path(match.path), match.target_type, group=match.group, known_key=match.key)
                mapping = self.selected_mapping
            if not mapping:
                continue
            mapping.ico_path = str(icon)
            mapping.png_path = str(self._png_for_ico(icon) or "")
            mapping.icon_group = self._group_for_ico(icon)
            try:
                capture_original_icon(mapping)
                apply_mapping(mapping)
            except (ShortcutError, FolderIconError):
                continue
            mapping.is_customized = True
            self.store.update_mapping(mapping)
            applied += 1
        self.refresh_mapping_list()
        self.refresh_discovered_list()
        self.set_status(f"Grupo carregado: {applied} item(ns) aplicados.")

    def pick_target(self) -> None:
        if self.kind_choice.get() == "Pasta":
            path = filedialog.askdirectory(title="Selecione uma pasta")
        else:
            path = filedialog.askopenfilename(title="Selecione um atalho", filetypes=[("Atalhos", "*.lnk")])
        if path:
            target = Path(path)
            self._set_entry(self.target_path, path)
            self._set_disabled_entry(self.program_name, self._derive_name(target))
            if self.kind_choice.get() == "Atalho":
                self._set_entry(self.program_group, _group_for_name(target.stem, target))
            elif not self.program_group.get().strip():
                self._set_entry(self.program_group, "Pastas do usuario")
            self.asset_choice.set(self._recommended_asset(self.kind_choice.get()))
            if self.selected_mapping and self.kind_choice.get() == "Pasta":
                self.selected_mapping.original_icon = read_folder_icon(target)
                self._refresh_previews(self.selected_mapping)

    def open_generated_icons_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.output_dir)

    def _render_mapping_row(self, mapping: AppMapping) -> None:
        kind = "Pasta" if mapping.target_type == "folder" else "App"
        status = "customizado" if mapping.is_customized else "mapeado"
        row = ctk.CTkFrame(self.mapping_list, fg_color=self._mapping_button_color(mapping), corner_radius=14)
        row.pack(fill="x", padx=6, pady=4)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, image=self._mapping_image(mapping), text="", width=42, height=42, fg_color="#1c2b45", corner_radius=10).grid(
            row=0, column=0, padx=8, pady=8
        )
        button = ctk.CTkButton(
            row,
            text=f"{mapping.program_name}\n{kind} - {status}",
            anchor="w",
            fg_color="transparent",
            hover_color="#3b4f73",
            text_color="#e8f0fb",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda item=mapping: self.select_mapping(item),
        )
        button.grid(row=0, column=1, padx=(0, 8), pady=5, sticky="ew")

    def _render_discovered_row(self, target: DiscoveredTarget, state: str, is_custom: bool) -> None:
        row = ctk.CTkFrame(
            self.discovered_list,
            fg_color="#244f3c" if is_custom else "#263958",
            corner_radius=14,
        )
        row.pack(fill="x", padx=6, pady=4)
        row.grid_columnconfigure(2, weight=1)
        original = self._icon_location_image(target.original_icon, eager=False)
        current = self._icon_location_image(target.current_icon, eager=False)
        ctk.CTkLabel(row, text="", image=original, width=28, height=36).grid(row=0, column=0, rowspan=2, padx=(8, 3), pady=8)
        ctk.CTkLabel(row, text="", image=current, width=28, height=36).grid(row=0, column=1, rowspan=2, padx=3, pady=8)
        button = ctk.CTkButton(
            row,
            text=f"{target.name}\n{state} - {target.group}{' - App do Windows' if target.target_type == 'appx' else ''}",
            anchor="w",
            fg_color="transparent",
            hover_color="#3b4f73",
            text_color="#e8f0fb",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda item=target: self.create_from_discovered(item),
        )
        button.grid(row=0, column=2, rowspan=2, padx=(3, 8), pady=5, sticky="ew")

    def _sync_global_settings(self) -> None:
        if self.store.settings.get("global_auto_reapply", False) or is_startup_reapply_enabled():
            self.global_auto.select()
        else:
            self.global_auto.deselect()

    def _mapping_image(self, mapping: AppMapping) -> ctk.CTkImage | None:
        path = Path(mapping.png_path) if mapping.png_path else Path(mapping.ico_path) if mapping.ico_path else None
        return self._icon_image(path) if path else None

    def _icon_location_image(self, icon_location: str, *, eager: bool = True) -> ctk.CTkImage | None:
        if not eager:
            raw_path = icon_location.split(",", 1)[0].strip('"') if icon_location else ""
            if Path(raw_path).suffix.lower() not in {".png", ".ico"}:
                return None
        preview = preview_for_icon_location(icon_location, self.icon_cache_dir)
        return self._icon_image(preview) if preview else None

    def _icon_image(self, path: Path) -> ctk.CTkImage:
        return self._sized_icon_image(path, 44)

    def _preview_image(self, path: Path) -> ctk.CTkImage:
        return self._sized_icon_image(path, 128)

    def _sized_icon_image(self, path: Path, size: int) -> ctk.CTkImage:
        key = (path, size, self._image_cache_signature(path))
        cached = self.icon_images.get(key)
        if cached:
            self.icon_images.move_to_end(key)
            return cached
        try:
            image = Image.open(path).convert("RGBA")
        except Exception:
            image = Image.new("RGBA", (size, size), (148, 163, 184, 255))
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
        # Bound the in-memory thumbnail cache because preview file fingerprints can churn over long sessions.
        remember_icon_image(self.icon_images, key, ctk_image)
        return ctk_image

    def _image_cache_signature(self, path: Path) -> ImageCacheSignature:
        try:
            stat = path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def _icon_button_color(self, icon: Path) -> str | tuple[str, str]:
        if self.selected_icon and icon == self.selected_icon:
            return "#244f86"
        return "#34435f"

    def _mapping_button_color(self, mapping: AppMapping) -> str | tuple[str, str]:
        if self.selected_mapping and mapping.id == self.selected_mapping.id:
            return "#344d78"
        if mapping.is_customized:
            return "#243f55"
        return "#263958"

    def _png_for_ico(self, ico_path: Path | None) -> Path | None:
        if not ico_path:
            return None
        try:
            relative = ico_path.relative_to(self.output_dir / "ico").with_suffix(".png")
        except ValueError:
            return None
        png = self.output_dir / "png" / relative
        return png if png.exists() else None

    def _clean_png_for_source(self, source_path: Path) -> Path | None:
        try:
            png = png_output_path_for(self.input_dir, self.output_dir, source_path)
        except ValueError:
            return None
        return png if png.exists() else None

    def _gallery_preview_for_source(self, source_path: Path) -> Path | None:
        clean = self._clean_png_for_source(source_path)
        if clean:
            return clean
        try:
            stat = source_path.stat()
        except OSError:
            return None
        key = hashlib.sha1(f"{source_path}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8", errors="ignore")).hexdigest()
        preview = self.icon_cache_dir / "gallery" / f"{key}.png"
        if preview.exists():
            return preview
        try:
            self.icon_cache_dir.joinpath("gallery").mkdir(parents=True, exist_ok=True)
            image = Image.open(source_path).convert("RGBA")
            image.thumbnail((160, 160), Image.Resampling.LANCZOS)
            image = soften_corner_marks(remove_edge_white_background(image))
            side = max(image.size)
            canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
            canvas.alpha_composite(image, ((side - image.width) // 2, (side - image.height) // 2))
            canvas.thumbnail((128, 128), Image.Resampling.LANCZOS)
            canvas.save(preview, format="PNG", optimize=True)
        except Exception:
            return None
        return preview

    def _source_for_ico(self, ico_path: Path | None) -> str:
        if not ico_path:
            return ""
        try:
            relative = ico_path.relative_to(self.output_dir / "ico").with_suffix(".png")
        except ValueError:
            return ""
        source = self.input_dir / relative
        return str(source) if source.exists() else ""

    def _group_for_ico(self, ico_path: Path | None) -> str:
        if not ico_path:
            return "default"
        try:
            source = self.input_dir / ico_path.relative_to(self.output_dir / "ico").with_suffix(".png")
            return icon_group_for(self.input_dir, source)
        except ValueError:
            return "default"

    def _group_for_source(self, path: Path) -> str:
        if path.suffix.lower() == ".png":
            try:
                return icon_group_for(self.input_dir, path)
            except ValueError:
                return "default"
        return self._group_for_ico(path)

    def _needs_processing(self, source: Path, generated: Path) -> bool:
        return not processed_outputs_current(self.input_dir, self.output_dir, source)

    def _find_existing_mapping(self, target: Path, known_key: str) -> AppMapping | None:
        normalized = normalized_target_key(target)
        for mapping in self.store.mappings:
            if known_key and mapping.known_key == known_key:
                return mapping
            try:
                if normalized_target_key(Path(mapping.shortcut_path)) == normalized:
                    return mapping
            except OSError:
                if mapping.shortcut_path.lower() == str(target).lower():
                    return mapping
        return None

    def _clear_selected_icon(self) -> None:
        self.selected_icon = None
        self.selected_png = None
        self.selected_icon_label.configure(text="Nenhum icone selecionado.")
        self.custom_preview.configure(image=None, text="Novo")

    def _refresh_previews(self, mapping: AppMapping) -> None:
        original = self._icon_location_image(mapping.original_icon, eager=True) if mapping.original_icon else None
        current_path = Path(mapping.png_path) if mapping.png_path else Path(mapping.ico_path) if mapping.ico_path else None
        current = self._preview_image(current_path) if current_path and current_path.exists() else None
        self.original_preview.configure(image=original, text="Original")
        self.custom_preview.configure(image=current or original, text="Novo/Atual" if current else "Atual")

    def _derive_name(self, path: Path) -> str:
        return path.stem or path.name or "Sem nome"

    def _recommended_asset(self, kind: str) -> str:
        return "ICO"

    def _relative_output(self, ico_path: str) -> str:
        if not ico_path:
            return ""
        try:
            return str(Path(ico_path).relative_to(self.output_dir))
        except ValueError:
            return Path(ico_path).name

    def _set_entry(self, entry: ctk.CTkEntry, value: str) -> None:
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)

    def _set_disabled_entry(self, entry: ctk.CTkEntry, value: str) -> None:
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)
        entry.configure(state="disabled")

    def set_status(self, text: str) -> None:
        self.status_label.configure(text=text)
