"""数据包相关 API 路由。

- GET  /api/packets/list     分页获取数据包列表
- GET  /api/packets/count    精确统计匹配包数
- GET  /api/packets/detail   获取单个数据包协议树
- GET  /api/packets/stats    获取 tshark 统计
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from core import packet_service, stream_service
from core.pyshark_analyzer import (
    PysharkAnalyzerError,
    get_tshark_stats,
    TSHARK_STAT_TYPES,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/packets", tags=["packets"])


@router.get("/list")
def list_packets(
    file: str = Query(..., description="pcap 文件路径"),
    filter: str = Query("", description="Wireshark 显示过滤器"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    time_format: str = Query("relative", description="时间格式: relative|absolute|delta"),
):
    """分页获取数据包列表（Wireshark 主窗口表格）。"""
    try:
        return packet_service.get_packets_page(
            pcap_path=file,
            display_filter=filter or None,
            offset=offset,
            limit=limit,
            time_format=time_format,
        )
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("list_packets 失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


@router.get("/count")
def count_packets(
    file: str = Query(...),
    filter: str = Query(""),
):
    """精确统计匹配过滤条件的包数。"""
    try:
        n = packet_service.count_packets(pcap_path=file, display_filter=filter or None)
        return {"count": n}
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("count_packets 失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


@router.get("/detail")
def packet_detail(
    file: str = Query(...),
    number: int = Query(..., ge=1),
):
    """获取指定序号数据包的协议树详情。"""
    try:
        return packet_service.get_packet_detail(pcap_path=file, packet_number=number)
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("packet_detail 失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


@router.get("/stats")
def packet_stats(
    file: str = Query(...),
    type: str = Query("protocol_hierarchy"),
):
    """获取 tshark 宏观统计。"""
    if type not in TSHARK_STAT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的统计类型 '{type}'，可选: {list(TSHARK_STAT_TYPES.keys())}",
        )
    try:
        text = get_tshark_stats(file, type)
        return {"type": type, "text": text}
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("packet_stats 失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


@router.get("/distribution")
def protocol_distribution(
    file: str = Query(...),
    filter: str = Query(""),
):
    """获取协议分布（JSON，供图表展示）。"""
    try:
        return packet_service.get_protocol_distribution(
            pcap_path=file, display_filter=filter or None,
        )
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("protocol_distribution 失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


# ---------------------------------------------------------------------
# 追踪流（Follow TCP/UDP Stream）
# ---------------------------------------------------------------------
@router.get("/stream/info")
def stream_info(
    file: str = Query(...),
    number: int = Query(..., ge=1),
):
    """定位指定数据包所属的 TCP/UDP 流（返回协议与流索引）。"""
    try:
        return stream_service.get_stream_info(file, number)
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("stream_info 失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


@router.get("/stream")
def follow_stream(
    file: str = Query(...),
    proto: str = Query("tcp", description="tcp 或 udp"),
    index: int = Query(..., ge=0, description="流索引"),
):
    """提取完整流内容（分段列表，含方向，供客户端/服务端着色）。"""
    try:
        return stream_service.follow_stream(file, proto, index)
    except PysharkAnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("follow_stream 失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


# ---------------------------------------------------------------------
# 过滤器语法校验
# ---------------------------------------------------------------------
@router.get("/validate-filter")
def validate_filter(
    filter: str = Query("", description="Wireshark 显示过滤器"),
):
    """校验显示过滤器语法是否合法。

    原理：tshark 解析过滤器失败时返回码为 4 且 stderr 含语法错误信息；
    合法则返回码为 0。用 captures 目录下任意一个真实文件作为输入
    （-c 1 只读 1 个包，开销极小）；若无文件则跳过实际校验。
    """
    expr = filter.strip()
    if not expr:
        return {"valid": True, "message": ""}
    import subprocess, os
    from config.settings import TSHARK_PATH, CAPTURES_DIR
    tshark = TSHARK_PATH if (TSHARK_PATH and os.path.isfile(TSHARK_PATH)) else "tshark"

    # 找一个真实文件作为校验输入（tshark 需要 -r 参数）
    sample = None
    for ext in ("*.pcapng", "*.pcap", "*.cap"):
        files = sorted(CAPTURES_DIR.glob(ext))
        if files:
            sample = str(files[0])
            break
    if not sample:
        # 没有可用文件，无法校验，假定合法
        return {"valid": True, "message": ""}

    try:
        proc = subprocess.run(
            [tshark, "-Y", expr, "-r", sample, "-c", "1"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        stderr = proc.stderr.strip()
        # 返回码 4 = 过滤器语法错误；含 "Unexpected" / "syntax" 等
        if proc.returncode == 4 or "unexpected" in stderr.lower() \
                or "syntax error" in stderr.lower() or "unable to parse" in stderr.lower():
            msg = stderr.splitlines()[0] if stderr else "过滤器语法错误"
            # 去掉 "tshark: " 前缀更友好
            msg = msg.replace("tshark: ", "")
            return {"valid": False, "message": msg}
        return {"valid": True, "message": ""}
    except subprocess.TimeoutExpired:
        return {"valid": True, "message": "校验超时"}
    except Exception as e:
        return {"valid": True, "message": f"校验不可用: {e}"}
