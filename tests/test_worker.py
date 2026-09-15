"""Tests for EngineWorker cancellation acknowledgement semantics."""
from __future__ import annotations

from dataclasses import dataclass

from photo_organizer.gui.worker import EngineWorker


def drain(worker: EngineWorker, qapp) -> dict:
    signals: dict = {"cancelled": 0, "result": [], "failed": []}
    worker.cancelled.connect(lambda: signals.__setitem__("cancelled", signals["cancelled"] + 1))
    worker.result_ready.connect(lambda value: signals["result"].append(value))
    worker.failed.connect(lambda message: signals["failed"].append(message))
    worker.run()
    qapp.processEvents()
    return signals


@dataclass
class _Result:
    cancelled: bool = False


def test_engine_that_acknowledges_cancel_emits_cancelled(qapp):
    def engine(source, options, progress_callback, log_callback):
        options["cancel_event"].set()
        return _Result(cancelled=True)

    worker = EngineWorker(engine, "src")
    signals = drain(worker, qapp)

    assert signals["cancelled"] == 1


def test_engine_that_ignores_cancel_is_not_reported_cancelled(qapp):
    def engine(source, options, progress_callback, log_callback):
        options["cancel_event"].set()
        return _Result(cancelled=False)

    worker = EngineWorker(engine, "src")
    signals = drain(worker, qapp)

    assert signals["cancelled"] == 0
    assert signals["result"] == [_Result(cancelled=False)]


def test_result_without_cancelled_attr_falls_back_to_token(qapp):
    def engine(source, options, progress_callback, log_callback):
        options["cancel_event"].set()
        return {"ops": []}

    worker = EngineWorker(engine, "src")
    signals = drain(worker, qapp)

    assert signals["cancelled"] == 1
