"""Qt worker that runs any engine off the UI thread.

Wraps an EngineCallable in a QThread, marshalling the engine's `progress_callback`
and `log_callback` into Qt signals (safe to connect to widgets). Cancellation is
cooperative: `cancel()` sets the shared token the engines poll via check_cancel.

Usage (from a panel):
    worker = EngineWorker(spec.load_engine(), source, options)
    worker.progress.connect(bar.setValue)
    worker.message.connect(log.appendPlainText)
    worker.result_ready.connect(on_done)
    worker.start()
    ...
    worker.cancel()
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

from photo_organizer.engine import OperationCancelled, make_cancel_token


class EngineWorker(QThread):
    progress = Signal(float)          # 0–100
    message = Signal(str)             # log line
    result_ready = Signal(object)     # engine return value (result object)
    failed = Signal(str)              # error string (non-cancel exceptions)
    cancelled = Signal()

    def __init__(self, engine: Callable, source: Any, options: dict | None = None,
                 parent=None):
        super().__init__(parent)
        self._engine = engine
        self._source = source
        self._options = dict(options or {})
        self._cancel_token = make_cancel_token()
        self._options["cancel_event"] = self._cancel_token

    def cancel(self) -> None:
        """Request cooperative cancellation; the engine stops at its next check."""
        self._cancel_token.set()

    def run(self) -> None:  # executes on the worker thread
        try:
            result = self._engine(
                self._source, self._options,
                lambda pct: self.progress.emit(float(pct)),
                lambda msg: self.message.emit(str(msg)),
            )
            if self._cancel_token.is_set():
                self.cancelled.emit()
            self.result_ready.emit(result)
        except OperationCancelled:
            self.cancelled.emit()
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")
