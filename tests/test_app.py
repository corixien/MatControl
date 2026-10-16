import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from conftest import wait
from matcontrol import app as app_module
from matcontrol.config import Config
from matcontrol.window import MainWindow

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_second_launch_opens_the_running_popup(qapp, tmp_path):
    name = f"matcontrol-test-{os.getpid()}"
    assert not app_module.notify_running_instance(name)  # nothing runs yet
    window = MainWindow(Config(tmp_path / "c.json"), [], [], popup=False)
    server = app_module.serve(qapp, window, name)
    assert not window.isVisible()
    assert app_module.notify_running_instance(name)
    wait(300)
    assert window.isVisible()
    server.close()


def test_app_icon_is_pixmaps_without_a_theme_name(qapp):
    icon = app_module.app_icon()
    assert app_module.ICON_PATH.exists() and not icon.isNull()
    assert icon.name() == ""  # a name would make the tray send it to the panel instead of the pixmaps
    assert {s.width() for s in icon.availableSizes()} >= {16, 32, 48}
    assert not icon.pixmap(48, 48).isNull()


@pytest.fixture
def fake_home(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("XDG_")}
    env["HOME"] = str(tmp_path)
    return tmp_path, env


def run_install(env, *args):
    return subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--no-kwin", "--no-deps", *args],
        env=env, capture_output=True, text=True, cwd=ROOT,
    )


def test_install_creates_launcher_menu_entry_icon_and_autostart(fake_home):
    home, env = fake_home
    result = run_install(env)
    assert result.returncode == 0, result.stderr
    launcher = home / ".local/bin/matcontrol"
    assert os.access(launcher, os.X_OK)
    text = launcher.read_text()
    assert str(ROOT) in text and "-m matcontrol" in text
    menu = home / ".local/share/applications/matcontrol.desktop"
    autostart = home / ".config/autostart/matcontrol.desktop"
    assert f"Exec={launcher}" in menu.read_text()
    icon_file = home / ".local/share/icons/hicolor/scalable/apps/matcontrol.svg"
    assert f"Icon={icon_file}" in menu.read_text()  # absolute path: works whatever the icon theme
    assert f"Exec={launcher} --minimized" in autostart.read_text()
    assert (home / ".local/share/icons/hicolor/scalable/apps/matcontrol.svg").exists()
    if shutil.which("desktop-file-validate"):
        for entry in (menu, autostart):
            check = subprocess.run(["desktop-file-validate", str(entry)], capture_output=True, text=True)
            assert check.returncode == 0, check.stdout + check.stderr


def test_install_without_autostart_and_uninstall(fake_home):
    home, env = fake_home
    assert run_install(env, "--no-autostart").returncode == 0
    assert not (home / ".config/autostart/matcontrol.desktop").exists()
    assert run_install(env).returncode == 0
    assert (home / ".config/autostart/matcontrol.desktop").exists()
    assert run_install(env, "--uninstall").returncode == 0
    for leftover in (".local/bin/matcontrol", ".local/share/applications/matcontrol.desktop", ".config/autostart/matcontrol.desktop"):
        assert not (home / leftover).exists()


def test_install_rejects_unknown_option(fake_home):
    _, env = fake_home
    assert run_install(env, "--bogus").returncode == 2
