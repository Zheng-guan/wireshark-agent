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

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config.settings import CAPTURES_DIR
from core import capture_service, nic_monitor, stream_service
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


@router.get("/files/download")
def download_file(
    file: str = Query(..., description="pcap 文件路径"),
    filter: str = Query("", description="可选：按显示过滤器导出匹配包"),
):
    """下载 pcap 文件；带 filter 时用 tshark 导出过滤后的子集。"""
    src = Path(file)
    if not src.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file}")

    if not filter:
        return FileResponse(
            path=str(src),
            filename=src.name,
            media_type="application/vnd.tcpdump.pcap",
        )

    # 过滤导出：写到临时文件再返回
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pcapng", delete=False, dir=str(CAPTURES_DIR),
        ) as tmp:
            tmp_path = tmp.name
        stream_service.export_filtered_pcap(str(src), filter, tmp_path)
        stem = src.stem
        return FileResponse(
            path=tmp_path,
            filename=f"{stem}_filtered.pcapng",
            media_type="application/vnd.tcpdump.pcap",
            background=None,  # 临时文件保留在 captures 目录，便于复用/排查
        )
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("过滤导出失败")
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")


# ---------------------------------------------------------------------
# 导出对象（HTTP 等协议传输的文件提取）
# ---------------------------------------------------------------------
@router.get("/files/export-objects")
def export_objects(
    file: str = Query(..., description="pcap 文件路径"),
    proto: str = Query("http", description="协议：http / smb / imf 等"),
):
    """列出 pcap 中可提取的协议对象（HTTP 下载的文件等）。"""
    try:
        return stream_service.list_exported_objects(file, proto)
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("导出对象列表失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


@router.get("/files/export-objects/{session_id}/{filename}")
def download_exported_object(session_id: str, filename: str):
    """下载单个导出对象。"""
    try:
        p = stream_service.get_exported_object_path(session_id, filename)
        return FileResponse(path=str(p), filename=filename)
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=404, detail=str(e))
