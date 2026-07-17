"""数据包相关 API 路由。

- GET  /api/packets/list     分页获取数据包列表
- GET  /api/packets/count    精确统计匹配包数
- GET  /api/packets/detail   获取单个数据包协议树
- GET  /api/packets/stats    获取 tshark 统计
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from core import packet_service
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
):
    """分页获取数据包列表（Wireshark 主窗口表格）。"""
    try:
        return packet_service.get_packets_page(
            pcap_path=file,
            display_filter=filter or None,
            offset=offset,
            limit=limit,
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
