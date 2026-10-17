"""Run blocking work off the UI thread; the callback runs back on the UI thread."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _Signals(QObject):
    done = Signal(object)


class _Dispatcher(QObject):
    """Lives in the UI thread; the queued connection delivers results there."""

    def __init__(self) -> None:
        super().__init__()
        self._jobs: set[_Job] = set()

    def add(self, job: "_Job") -> None:
        self._jobs.add(job)
        job.signals.done.connect(self._deliver)

    @Slot(object)
    def _deliver(self, payload: tuple) -> None:
        job, result, error = payload
        self._jobs.discard(job)
        job.on_done(result, error)


class _Job(QRunnable):
    def __init__(self, fn: Callable[..., Any], args: tuple, on_done: Callable[[Any, Exception | None], None]):
        super().__init__()
        self.fn, self.args, self.on_done = fn, args, on_done
        self.signals = _Signals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            result, error = self.fn(*self.args), None
        except Exception as exc:  # reported to the callback, never lost in the thread
            result, error = None, exc
        try:
            self.signals.done.emit((self, result, error))
        except RuntimeError:
            pass  # the app quit while the job was running: nobody is left to receive the result


_dispatcher: _Dispatcher | None = None


def run_in_thread(fn: Callable[..., Any], on_done: Callable[[Any, Exception | None], None], *args: Any) -> None:
    """Call fn(*args) in a worker thread, then on_done(result, error) in the UI thread.

    Must be called from the UI thread.
    """
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = _Dispatcher()
    job = _Job(fn, args, on_done)
    _dispatcher.add(job)
    QThreadPool.globalInstance().start(job)
