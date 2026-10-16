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


# Python's cyclic GC can run inside a worker thread (tasks.run_in_thread) and would then destroy
# Qt objects of earlier tests from the wrong thread, crashing the event loop later. So GC only
# runs here, in the main thread, between tests.
import gc  # noqa: E402

import pytest  # noqa: E402


def pytest_sessionstart(session):
    gc.disable()


@pytest.fixture(autouse=True)
def _collect_garbage_in_main_thread():
    yield
    gc.collect()
