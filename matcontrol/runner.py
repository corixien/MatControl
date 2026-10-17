"""Run a shell command as root through pkexec (Polkit dialog) and stream its output."""

from PySide6.QtCore import QObject, QProcess, Signal

from .updates import clean_output

POLKIT_DISMISSED = (126, 127)  # pkexec exit codes: dialog cancelled / not authorized


def privileged_argv(command: str) -> list[str]:
    return ["pkexec", "sh", "-c", command]


class CommandRunner(QObject):
    """Runs a command as root (pkexec) in a QProcess and streams cleaned output lines."""

    started = Signal()
    line = Signal(str)
    finished = Signal(int)  # exit code, -1 when it could not start

    def __init__(self) -> None:
        super().__init__()
        self._process: QProcess | None = None
        self._partial = ""

    @property
    def running(self) -> bool:
        return self._process is not None

    def start(self, command: str) -> None:
        self._partial = ""
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read)
        process.finished.connect(lambda code, _status: self._done(code))
        process.errorOccurred.connect(lambda error: self._failed(error))
        self._process = process
        argv = privileged_argv(command)
        process.start(argv[0], argv[1:])

    def _read(self) -> None:
        if self._process is None:
            return
        chunk = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        lines = clean_output(self._partial + chunk)
        self._partial = lines.pop()
        for text in lines:
            self.line.emit(text)

    def _done(self, code: int) -> None:
        self._read()
        if self._partial.strip():
            self.line.emit(clean_output(self._partial)[-1])
        self._partial = ""
        self._process, process = None, self._process
        if process is not None:
            process.deleteLater()
        self.finished.emit(code)

    def _failed(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and self._process is not None:
            self.line.emit("pkexec konnte nicht gestartet werden.")
            self._process, process = None, self._process
            process.deleteLater()
            self.finished.emit(-1)
