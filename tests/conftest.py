import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def wait(ms: int) -> None:
    """Spin the event loop while letting worker threads run (QTest.qWait starves them)."""
    import time

    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + ms / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
