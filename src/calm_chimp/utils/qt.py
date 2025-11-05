from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


class TaskSignals(QObject):
    completed = pyqtSignal(object)
    failed = pyqtSignal(Exception)


class _Runnable(QRunnable):
    def __init__(
        self,
        fn: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        signals: TaskSignals,
    ) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = signals

    def run(self) -> None:  # noqa: D401
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(exc)
        else:
            self.signals.completed.emit(result)


@dataclass
class TaskHandle:
    signals: TaskSignals


class TaskRunner:
    def __init__(self, *, max_threads: Optional[int] = None) -> None:
        self.pool = QThreadPool.globalInstance()
        if max_threads is not None:
            self.pool.setMaxThreadCount(max_threads)

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        **kwargs: Any,
    ) -> TaskHandle:
        signals = TaskSignals()
        if on_success:
            signals.completed.connect(on_success)
        if on_error:
            signals.failed.connect(on_error)
        runnable = _Runnable(fn, args, kwargs, signals)
        self.pool.start(runnable)
        return TaskHandle(signals=signals)
