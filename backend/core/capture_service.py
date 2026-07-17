"""异步抓包服务（带进度跟踪）。

把阻塞的 capture_live 放到后台线程执行，前端通过任务 ID 轮询进度。
进度通过「输出文件大小增长 + 已用时间」估算。
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from config.settings import CAPTURES_DIR
from core.pyshark_analyzer import capture_live, PysharkAnalyzerError

logger = logging.getLogger(__name__)


class CaptureTask:
    def __init__(self, task_id: str, interface: str, duration: int,
                 packet_count: int, bpf_filter: str | None):
        self.task_id = task_id
        self.interface = interface
        self.duration = duration
        self.packet_count = packet_count
        self.bpf_filter = bpf_filter
        self.status = "running"          # running | done | error
        self.error = ""
        self.file = ""
        self.filename = ""
        self.start_time = time.time()
        self.output_path = CAPTURES_DIR / f"capture_{int(self.start_time)}.pcapng"


_TASKS: dict[str, CaptureTask] = {}
_LOCK = threading.Lock()


def _run_capture(task: CaptureTask) -> None:
    try:
        path = capture_live(
            interface=task.interface,
            duration=task.duration,
            packet_count=task.packet_count,
            bpf_filter=task.bpf_filter,
            output_filename=task.output_path.name,
        )
        task.file = path
        task.filename = Path(path).name
        task.status = "done"
    except Exception as e:
        logger.exception("后台抓包失败")
        task.error = str(e)
        task.status = "error"


def start_capture_task(interface: str, duration: int = 10,
                       packet_count: int = 0, bpf_filter: str | None = None) -> str:
    """启动后台抓包任务，返回任务 ID。"""
    task_id = uuid.uuid4().hex[:12]
    task = CaptureTask(task_id, interface, duration, packet_count, bpf_filter)
    with _LOCK:
        _TASKS[task_id] = task
    t = threading.Thread(target=_run_capture, args=(task,), daemon=True)
    t.start()
    logger.info("启动抓包任务 %s: interface=%s duration=%s", task_id, interface, duration)
    return task_id


def get_capture_status(task_id: str) -> dict[str, Any]:
    """查询抓包任务状态与进度。"""
    with _LOCK:
        task = _TASKS.get(task_id)
    if task is None:
        raise PysharkAnalyzerError(f"任务不存在: {task_id}")

    elapsed = time.time() - task.start_time
    # 进度估算：时间维度为主
    if task.duration > 0:
        progress = min(0.99, elapsed / task.duration)
    else:
        progress = 0.5
    if task.status == "done":
        progress = 1.0

    size_kb = 0.0
    if task.output_path.exists():
        size_kb = round(task.output_path.stat().st_size / 1024, 2)

    return {
        "task_id": task_id,
        "status": task.status,
        "progress": round(progress, 3),
        "elapsed": round(elapsed, 1),
        "duration": task.duration,
        "size_kb": size_kb,
        "file": task.file,
        "filename": task.filename,
        "error": task.error,
    }
