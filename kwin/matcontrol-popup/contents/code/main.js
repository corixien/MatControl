// Places the MatControl popup flush under the top panel (where the tray icon lives),
// top-right, even on multi-screen setups where only one screen has a panel.
const MARGIN_RIGHT = 6;

function topPanel() {
    for (const w of workspace.windowList()) {
        if (!w.dock || String(w.resourceClass) !== "plasmashell") {
            continue;
        }
        const g = w.frameGeometry;
        const screenTop = w.output && w.output.geometry ? w.output.geometry.y : 0;
        if (g.y <= screenTop + 1 && g.width > g.height) {
            return g;
        }
    }
    return null;
}

function place(win) {
    const geo = win.frameGeometry;
    if (geo.width <= 0 || geo.height <= 0) {
        return false;
    }
    const panel = topPanel();
    let x;
    let y;
    if (panel) {
        x = panel.x + panel.width - geo.width - MARGIN_RIGHT;
        y = panel.y + panel.height;
    } else {
        const area = workspace.clientArea(KWin.MaximizeArea, win);
        x = area.x + area.width - geo.width - MARGIN_RIGHT;
        y = area.y;
    }
    win.frameGeometry = { x: x, y: y, width: geo.width, height: geo.height };
    return true;
}

function handle(win) {
    if (String(win.resourceClass) !== "matcontrol") {
        return;
    }
    win.skipTaskbar = true;
    win.skipPager = true;
    win.skipSwitcher = true;
    win.keepAbove = true;
    if (!place(win)) {
        // size is not known before the first commit: place once it is
        const onGeometry = () => {
            if (place(win)) {
                win.frameGeometryChanged.disconnect(onGeometry);
            }
        };
        win.frameGeometryChanged.connect(onGeometry);
    }
}

workspace.windowAdded.connect(handle);
workspace.windowList().forEach(handle);
