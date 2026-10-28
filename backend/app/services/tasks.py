"""Background task execution."""

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)


class TaskRunner:
    """Runs long operations such as downloads, agent turns and scoring off the request thread."""

    def __init__(self, max_workers: int = 8) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bhb-task")

    def submit(self, function: Callable[..., Any], *args: Any) -> Future[None]:
        return self._executor.submit(_run_logged, function, *args)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class InlineTaskRunner(TaskRunner):
    """Executes tasks synchronously. Intended for tests and scripted use."""

    def __init__(self) -> None:
        pass

    def submit(self, function: Callable[..., Any], *args: Any) -> Future[None]:
        future: Future[None] = Future()
        _run_logged(function, *args)
        future.set_result(None)
        return future

    def shutdown(self) -> None:
        pass


def _run_logged(function: Callable[..., Any], *args: Any) -> None:
    try:
        function(*args)
    except Exception:
        logger.exception("Background task %s failed", getattr(function, "__qualname__", function))
