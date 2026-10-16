#!/usr/bin/env bash
# Install MatControl for the current user (no root): launcher, app-menu entry, icon, autostart
# and the KWin placement script. Re-run after moving the repo. Remove everything with --uninstall.
#
# Options: --no-autostart  --no-kwin  --no-deps  --uninstall
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$HOME/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icon_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
autostart_dir="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
launcher="$bin_dir/matcontrol"

autostart=1 kwin=1 deps=1 uninstall=0
for arg in "$@"; do
    case "$arg" in
        --no-autostart) autostart=0 ;;
        --no-kwin) kwin=0 ;;
        --no-deps) deps=0 ;;
        --uninstall) uninstall=1 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [[ $uninstall -eq 1 ]]; then
    rm -f "$launcher" "$apps_dir/matcontrol.desktop" "$autostart_dir/matcontrol.desktop" "$icon_dir/matcontrol.svg"
    [[ $kwin -eq 1 ]] && "$here/kwin/install.sh" --uninstall || true
    echo "MatControl removed (config in ~/.config/matcontrol is kept)"
    exit 0
fi

if [[ $deps -eq 1 ]]; then
    [[ -x "$here/.venv/bin/python" ]] || python3 -m venv --system-site-packages "$here/.venv"
    "$here/.venv/bin/pip" install -q -r "$here/requirements.txt"
fi

mkdir -p "$bin_dir" "$apps_dir" "$icon_dir"

cat > "$launcher" <<LAUNCHER
#!/usr/bin/env bash
export PYTHONPATH="$here\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$here/.venv/bin/python" -m matcontrol "\$@"
LAUNCHER
chmod +x "$launcher"

cp "$here/matcontrol/data/matcontrol.svg" "$icon_dir/matcontrol.svg"

write_entry() {  # $1 = target file, $2 = Exec arguments
    cat > "$1" <<ENTRY
[Desktop Entry]
Type=Application
Name=MatControl
Comment=Audio Split, Updates and more in one tray popup
Exec=$launcher $2
Icon=$icon_dir/matcontrol.svg
Terminal=false
Categories=Settings;
StartupWMClass=matcontrol
ENTRY
}

write_entry "$apps_dir/matcontrol.desktop" ""
if [[ $autostart -eq 1 ]]; then
    mkdir -p "$autostart_dir"
    write_entry "$autostart_dir/matcontrol.desktop" "--minimized"
    printf 'X-KDE-autostart-after=panel\n' >> "$autostart_dir/matcontrol.desktop"
else
    rm -f "$autostart_dir/matcontrol.desktop"
fi

[[ $kwin -eq 1 ]] && "$here/kwin/install.sh"

# make a running Plasma pick up the new icon without a re-login (best effort)
busctl --user emit /KIconLoader org.kde.KIconLoader iconChanged i 0 2>/dev/null || true

echo "MatControl installed: start it from the app menu or run 'matcontrol'"
[[ $autostart -eq 1 ]] && echo "It also starts hidden in the tray at login."
exit 0
