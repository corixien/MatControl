#!/usr/bin/env bash
# Install (or remove with --uninstall) the KWin script that places the MatControl popup.
# Per-user only, no root. Needs KDE Plasma 6 (kpackagetool6, kwriteconfig6).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pkg="$here/matcontrol-popup"
id="matcontrol-popup"

reload() {
    busctl --user call org.kde.KWin /KWin org.kde.KWin reconfigure >/dev/null || true
}

# KWin keeps running the old code after an upgrade: swap the running script for the installed one.
restart_script() {
    local main="${XDG_DATA_HOME:-$HOME/.local/share}/kwin/scripts/$id/contents/code/main.js" script_id
    busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting unloadScript s "$id" >/dev/null 2>&1 || return 0
    script_id=$(busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting loadScript ss "$main" "$id" 2>/dev/null | awk '{print $2}') || return 0
    [[ -n "$script_id" ]] && busctl --user call org.kde.KWin "/Scripting/Script$script_id" org.kde.kwin.Script run >/dev/null 2>&1 || true
}

if [[ "${1:-}" == "--uninstall" ]]; then
    kwriteconfig6 --file kwinrc --group Plugins --key "${id}Enabled" false
    kpackagetool6 --type=KWin/Script --remove "$id" || true
    reload
    echo "removed $id"
    exit 0
fi

if kpackagetool6 --type=KWin/Script --list | grep -qx "$id"; then
    kpackagetool6 --type=KWin/Script --upgrade "$pkg"
else
    kpackagetool6 --type=KWin/Script --install "$pkg"
fi
kwriteconfig6 --file kwinrc --group Plugins --key "${id}Enabled" true
reload
restart_script
echo "installed $id"
