"""抓包与文件管理 API 路由。

- GET  /api/capture/interfaces        列出网卡（含实时流量）
- GET  /api/capture/traffic           各网卡实时速率
- POST /api/capture/start             启动异步抓包任务，返回 task_id
- GET  /api/capture/status/{task_id}  查询抓包进度
- GET  /api/files/list                列出 captures 目录下的 pcap 文件
- POST /api/files/upload              上传 pcap 文件
"""
from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from config.settings import CAPTURES_DIR
from core import capture_service, nic_monitor
from core.pyshark_analyzer import (
    PysharkAnalyzerError,
    list_interfaces,
)
from core.packet_service import clear_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["capture"])


class CaptureRequest(BaseModel):
    interface: str
    duration: int = 10
    packet_count: int = 0
    bpf_filter: str | None = None


@router.get("/capture/interfaces")
def get_interfaces(with_traffic: bool = True):
    """列出可用网卡（默认附带实时流量，便于选择）。"""
    try:
        interfaces = list_interfaces()
        if with_traffic:
            interfaces = nic_monitor.match_tshark_to_psutil(interfaces)
        return {"interfaces": interfaces}
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capture/traffic")
def get_traffic():
    """获取各网卡实时速率（用于流量图轮询）。"""
    try:
        return {"nics": nic_monitor.get_nic_rates()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取流量失败: {e}")


@router.post("/capture/start")
def start_capture(req: CaptureRequest):
    """启动异步抓包任务，返回 task_id 供轮询进度。"""
    try:
        task_id = capture_service.start_capture_task(
            interface=req.interface,
            duration=req.duration,
            packet_count=req.packet_count,
            bpf_filter=req.bpf_filter,
        )
        return {"task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动抓包失败: {e}")


@router.get("/capture/status/{task_id}")
def capture_status(task_id: str):
    """查询抓包任务进度。"""
    try:
        status = capture_service.get_capture_status(task_id)
        if status["status"] == "done":
            clear_cache()  # 新文件产生，清缓存
        return status
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/files/list")
def list_files():
    """列出 captures 目录下的 pcap/pcapng 文件。"""
    files = []
    for ext in ("*.pcap", "*.pcapng", "*.cap"):
        for f in sorted(CAPTURES_DIR.glob(ext), key=lambda x: x.stat().st_mtime, reverse=True):
            files.append({
                "filename": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 2),
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime)),
            })
    seen = set()
    unique = []
    for f in files:
        if f["path"] not in seen:
            seen.add(f["path"])
            unique.append(f)
    return {"files": unique, "captures_dir": str(CAPTURES_DIR)}


@router.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 pcap 文件到 captures 目录。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pcap", ".pcapng", ".cap"):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 {suffix}")
    dest = CAPTURES_DIR / Path(file.filename).name
    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")
    clear_cache()
    return {"file": str(dest), "filename": dest.name}
