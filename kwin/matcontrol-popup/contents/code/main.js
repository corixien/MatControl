// Places the MatControl popup at the top right of the usable screen area,
// directly under a top panel, and keeps it out of taskbar/switcher.
const MARGIN_RIGHT = 6; // flush with the panel on top so the slide-down emerges from behind it

function place(win) {
    const area = workspace.clientArea(KWin.MaximizeArea, win);
    const geo = win.frameGeometry;
    if (geo.width <= 0 || geo.height <= 0) {
        return false;
    }
    win.frameGeometry = {
        x: area.x + area.width - geo.width - MARGIN_RIGHT,
        y: area.y,
        width: geo.width,
        height: geo.height,
    };
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
