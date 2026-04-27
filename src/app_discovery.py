from __future__ import annotations

import os
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.folder_manager import read_folder_icon


DEFAULT_GROUPS = {
    "Browsers": ("chrome", "edge", "firefox", "brave", "opera", "vivaldi", "tor browser", "waterfox"),
    "Dev": (
        "visual studio",
        "developer command prompt",
        "developer powershell",
        "native tools command prompt",
        "cross tools command prompt",
        "git ",
        "git bash",
        "git cmd",
        "github desktop",
        "python",
        "pydoc",
        "idle",
        "node.js",
        "npm",
        "yarn",
        "pnpm",
        "postman",
        "insomnia",
        "dbeaver",
        "datagrip",
        "intellij",
        "pycharm",
        "webstorm",
        "android studio",
        "eclipse",
        "fiddler",
        "docker",
        "wsl",
        "ubuntu",
        "windows kits",
        "software development kit",
        "application verifier",
        "sample desktop apps",
        "sample uwp apps",
        "tools for desktop apps",
        "tools for uwp apps",
        "documentation for desktop apps",
        "documentation for uwp apps",
    ),
    "Editores": (
        "visual studio code",
        "notepad++",
        "obsidian",
        "notion",
        "sublime text",
        "atom",
        "typora",
        "joplin",
        "evernote",
    ),
    "Office": (
        "word",
        "excel",
        "powerpoint",
        "outlook",
        "onenote",
        "microsoft access",
        "libreoffice",
        "openoffice",
        "wps office",
        "foxit",
        "adobe acrobat",
        "pdf",
        "publisher",
        "enviar para o onenote",
    ),
    "Design": (
        "figma",
        "photoshop",
        "illustrator",
        "lightroom",
        "premiere",
        "after effects",
        "gimp",
        "inkscape",
        "canva",
        "krita",
        "blender",
        "davinci resolve",
    ),
    "Media": (
        "spotify",
        "itunes",
        "apple music",
        "vlc",
        "plex",
        "audacity",
        "handbrake",
        "netflix",
        "prime video",
        "music",
        "photos",
        "fotos",
        "camera",
        "obs ",
        "media player",
        "mpc-hc",
        "qbittorrent",
    ),
    "Games": (
        "steam",
        "epic",
        "xbox",
        "battle.net",
        "riot",
        "ea app",
        "ubisoft",
        "gog",
        "minecraft",
        "roblox",
        "valorant",
        "league of legends",
        "modrinth",
        "gamingcenter",
    ),
    "Comunicacao": (
        "discord",
        "teams",
        "slack",
        "zoom",
        "telegram",
        "whatsapp",
        "messenger",
        "signal",
        "skype",
    ),
    "Arquivos e busca": (
        "7-zip",
        "winrar",
        "winzip",
        "nanazip",
        "agent ransack",
        "everything",
        "filezilla",
        "winscp",
        "onedrive",
        "dropbox",
        "google drive",
        "mega",
    ),
    "Seguranca e senhas": (
        "kaspersky",
        "keepassxc",
        "1password",
        "bitwarden",
        "nordpass",
        "proton pass",
        "malwarebytes",
        "windows defender",
        "security configuration",
    ),
    "VPN e rede": (
        "openvpn",
        "forticlient",
        "sophos connect",
        "putty",
        "puttygen",
        "psftp",
        "pageant",
        "remote desktop",
        "protonvpn",
        "nordvpn",
        "tailscale",
        "wireguard",
        "iscsi",
        "odbc",
    ),
    "Hardware e drivers": (
        "nvidia",
        "amd",
        "intel driver",
        "driver & support",
        "msi afterburner",
        "hwmonitor",
        "cpuid",
        "3dmark",
        "logitech",
        "razer",
        "corsair",
    ),
    "Acessibilidade": ("voiceaccess", "livecaptions", "magnify", "narrator", "on-screen keyboard"),
    "Sistema Windows": (
        "administrative tools",
        "character map",
        "command prompt",
        "component services",
        "computer management",
        "control panel",
        "dfrgui",
        "disk cleanup",
        "event viewer",
        "file explorer",
        "hyper-v manager",
        "memory diagnostics",
        "performance monitor",
        "print management",
        "recoverydrive",
        "registry editor",
        "resource monitor",
        "run",
        "services",
        "steps recorder",
        "system configuration",
        "system information",
        "task manager",
        "task scheduler",
        "vmcreate",
        "windows app cert kit",
        "windows powershell",
    ),
}


PUBLIC_PATH_HINTS = (
    "\\programdata\\microsoft\\windows\\start menu\\programs\\",
    "\\users\\public\\desktop\\",
)


PERSONAL_PATH_HINTS = (
    "\\firefox web apps\\",
    "\\startup\\",
)


PERSONAL_NAME_HINTS = (
    "bem!",
    "antigravity",
    "uninstall",
    "desinstalar",
    "manual",
    "help",
    "user guide",
    "getting started",
    "release notes",
    "web site",
    "documentation",
    "online documentation",
    "sample desktop apps",
    "sample uwp apps",
)


COMMON_FOLDERS = (
    ("Desktop", "Pastas do usuario", "Desktop"),
    ("Documents", "Pastas do usuario", "Documents"),
    ("Downloads", "Pastas do usuario", "Downloads"),
    ("Music", "Pastas do usuario", "Music"),
    ("Pictures", "Pastas do usuario", "Pictures"),
    ("Videos", "Pastas do usuario", "Videos"),
    ("Workspace", "Trabalho", "D:\\WorkSpace"),
)


@dataclass(frozen=True)
class DiscoveredTarget:
    key: str
    name: str
    group: str
    path: str
    target_type: str
    original_icon: str = ""
    current_icon: str = ""


def discover_targets() -> list[DiscoveredTarget]:
    targets = _discover_common_folders()
    targets.extend(_discover_shortcuts())
    targets.extend(_discover_start_apps())
    unique: dict[str, DiscoveredTarget] = {}
    for target in targets:
        unique.setdefault(target.key, target)
    return sorted(unique.values(), key=lambda item: (item.group.lower(), item.name.lower()))


def _discover_common_folders() -> list[DiscoveredTarget]:
    home = Path.home()
    found: list[DiscoveredTarget] = []
    for name, group, raw_path in COMMON_FOLDERS:
        path = Path(raw_path) if ":" in raw_path else home / raw_path
        if path.exists():
            found.append(
                DiscoveredTarget(
                    key=f"folder:{path.resolve()}",
                    name=name,
                    group=group,
                    path=str(path),
                    target_type="folder",
                    current_icon=_folder_current_icon(path),
                )
            )
    return found


def _discover_start_apps() -> list[DiscoveredTarget]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12)
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    found: list[DiscoveredTarget] = []
    for item in data:
        name = str(item.get("Name", "")).strip()
        app_id = str(item.get("AppID", "")).strip()
        if not name or not app_id:
            continue
        found.append(
            DiscoveredTarget(
                key=f"appx:{app_id}",
                name=name,
                group=_group_for_name(name),
                path=app_id,
                target_type="appx",
            )
        )
    return found


def _discover_shortcuts() -> list[DiscoveredTarget]:
    folders = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path.home() / "Desktop",
        Path(os.environ.get("PUBLIC", "C:\\Users\\Public")) / "Desktop",
    ]
    found: list[DiscoveredTarget] = []
    for folder in folders:
        if not folder.exists():
            continue
        for shortcut in folder.rglob("*.lnk"):
            name = shortcut.stem
            found.append(
                DiscoveredTarget(
                    key=f"shortcut:{shortcut.resolve()}",
                    name=name,
                    group=_group_for_name(name, shortcut),
                    path=str(shortcut),
                    target_type="shortcut",
                    original_icon=str(shortcut),
                    current_icon=str(shortcut),
                )
            )
    return found


def _group_for_name(name: str, path: Path | None = None) -> str:
    lowered = name.lower()
    lowered_path = str(path).lower() if path else ""
    if any(term in lowered for term in PERSONAL_NAME_HINTS):
        return "Pessoal"
    if any(term in lowered_path for term in PERSONAL_PATH_HINTS):
        return "Pessoal"
    if "vpn" in lowered or "tap-windows" in lowered or "dco-win" in lowered:
        return "VPN e rede"
    if "sticky notes" in lowered:
        return "Editores"
    if lowered.strip() == "access":
        return "Office"
    for group, terms in DEFAULT_GROUPS.items():
        if any(term in lowered for term in terms):
            return group
    if any(hint in lowered_path for hint in PUBLIC_PATH_HINTS):
        return "Utilitarios"
    return "Pessoal"


def _folder_current_icon(folder: Path) -> str:
    return read_folder_icon(folder)

