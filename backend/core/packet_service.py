"""数据包解析服务。

在 pyshark_analyzer 的基础上，提供面向 Web 前端的数据结构：
- 分页的数据包列表（类似 Wireshark 主窗口的表格行）
- 单个数据包的协议树（嵌套 dict，可直接渲染为 TreeView）
- 数据包的 Hex 转储（类似 Wireshark 的 Hex 视图）
- 协议分布统计（供图表）

性能优化：
- 对「文件 + 显示过滤器」的行列表做内存缓存（按文件 mtime 失效），
  翻页不再重复扫描整个 pcap。
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from config.settings import TSHARK_PATH
from core.pyshark_analyzer import (
    PysharkAnalyzerError,
    _ensure_event_loop,
    _safe_close,
    _tshark_kwargs,
)

from pyshark import FileCapture

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# 行列表缓存（file+filter -> rows），按文件 mtime 失效
# ---------------------------------------------------------------------
class _RowsCache:
    """线程安全的简单缓存：key=(file, filter)，value=(mtime, rows)。"""

    def __init__(self, max_entries: int = 8):
        self._data: dict[tuple, tuple[float, list[dict]]] = {}
        self._lock = threading.Lock()
        self._max = max_entries

    def get(self, key: tuple, mtime: float) -> list[dict] | None:
        with self._lock:
            entry = self._data.get(key)
            if entry and entry[0] == mtime:
                return entry[1]
            return None

    def set(self, key: tuple, mtime: float, rows: list[dict]) -> None:
        with self._lock:
            if len(self._data) >= self._max:
                # 简单淘汰：删第一个（近似 FIFO）
                self._data.pop(next(iter(self._data)))
            self._data[key] = (mtime, rows)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_ROWS_CACHE = _RowsCache()


def clear_cache() -> None:
    """清空行缓存（抓包/上传新文件后调用）。"""
    _ROWS_CACHE.clear()


# ---------------------------------------------------------------------
# 协议树构建
# ---------------------------------------------------------------------
def _field_to_tree(field) -> dict:
    node: dict[str, Any] = {
        "name": getattr(field, "showname", None) or getattr(field, "name", ""),
        "value": "",
        "children": [],
    }
    show = getattr(field, "show", None)
    raw = getattr(field, "raw_value", None)
    if show:
        node["value"] = str(show)
    elif raw is not None:
        node["value"] = str(raw)

    sub_fields = getattr(field, "_all_fields", None)
    if isinstance(sub_fields, dict) and sub_fields:
        for sub in sub_fields.values():
            if isinstance(sub, list):
                for s in sub:
                    node["children"].append(_field_to_tree(s))
            else:
                node["children"].append(_field_to_tree(sub))
    return node


def _layer_to_tree(layer) -> dict:
    node: dict[str, Any] = {
        "name": layer.layer_name.upper(),
        "value": "",
        "children": [],
    }
    fields = getattr(layer, "_all_fields", {})
    if isinstance(fields, dict):
        for field in fields.values():
            if isinstance(field, list):
                for f in field:
                    node["children"].append(_field_to_tree(f))
            else:
                node["children"].append(_field_to_tree(field))
    return node


def packet_to_tree(packet) -> list[dict]:
    tree: list[dict] = []
    for layer in getattr(packet, "layers", []):
        try:
            tree.append(_layer_to_tree(layer))
        except Exception as e:
            logger.debug("解析层 %s 失败: %s", getattr(layer, "layer_name", "?"), e)
            tree.append({
                "name": getattr(layer, "layer_name", "UNKNOWN").upper(),
                "value": "(解析失败)",
                "children": [],
            })
    return tree


# ---------------------------------------------------------------------
# 列表行构建
# ---------------------------------------------------------------------
def _packet_to_row(packet) -> dict:
    row: dict[str, Any] = {
        "number": getattr(packet, "number", None),
        "time": "",
        "source": "",
        "destination": "",
        "protocol": getattr(packet, "highest_layer", "") or "",
        "length": getattr(packet, "length", None),
        "info": "",
    }
    try:
        st = getattr(packet, "sniff_time", None)
        row["time"] = st.strftime("%H:%M:%S.%f")[:-3] if st else ""
    except Exception:
        row["time"] = str(getattr(packet, "sniff_time", ""))

    for lname in ("ip", "ipv6"):
        layer = getattr(packet, lname, None)
        if layer is not None:
            row["source"] = str(getattr(layer, "src", "") or "")
            row["destination"] = str(getattr(layer, "dst", "") or "")
            break
    if not row["source"]:
        eth = getattr(packet, "eth", None)
        if eth is not None:
            row["source"] = str(getattr(eth, "src", "") or "")
            row["destination"] = str(getattr(eth, "dst", "") or "")

    row["info"] = _build_info(packet)
    return row


def _build_info(packet) -> str:
    try:
        tcp = getattr(packet, "tcp", None)
        if tcp is not None:
            sport = getattr(tcp, "srcport", "?")
            dport = getattr(tcp, "dstport", "?")
            flags = getattr(tcp, "flags_str", None) or getattr(tcp, "flags", "")
            return f"{sport} → {dport} [{flags}]"
        udp = getattr(packet, "udp", None)
        if udp is not None:
            return f"{getattr(udp, 'srcport', '?')} → {getattr(udp, 'dstport', '?')}"
        http = getattr(packet, "http", None)
        if http is not None:
            method = getattr(http, "request_method", None)
            if method:
                return f"{method} {getattr(http, 'request_uri', '')}"
            code = getattr(http, "response_code", None)
            if code:
                return f"Response {code} {getattr(http, 'response_phrase', '')}"
        dns = getattr(packet, "dns", None)
        if dns is not None:
            qname = getattr(dns, "qry_name", None)
            if qname:
                return f"DNS query {qname}"
        arp = getattr(packet, "arp", None)
        if arp is not None:
            return f"Who has {getattr(arp, 'dst_proto_ipv4', '?')}? Tell {getattr(arp, 'src_proto_ipv4', '?')}"
        icmp = getattr(packet, "icmp", None)
        if icmp is not None:
            return f"ICMP type {getattr(icmp, 'type', '?')}"
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------
# 全量行构建（带缓存）
# ---------------------------------------------------------------------
def _build_all_rows(pcap_path: str, display_filter: str | None) -> list[dict]:
    """扫描整个 pcap，构建匹配过滤条件的全部行（带缓存）。"""
    _ensure_event_loop()
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")

    mtime = pcap_file.stat().st_mtime
    key = (str(pcap_file.resolve()), display_filter or "")
    cached = _ROWS_CACHE.get(key, mtime)
    if cached is not None:
        logger.info("命中行缓存: %s (filter=%s, %d 行)", pcap_file.name, display_filter, len(cached))
        return cached

    rows: list[dict] = []
    try:
        cap = FileCapture(
            input_file=str(pcap_file),
            display_filter=display_filter,
            keep_packets=False,
            **_tshark_kwargs(),
        )
        for packet in cap:
            try:
                rows.append(_packet_to_row(packet))
            except Exception as e:
                logger.debug("构建行失败: %s", e)
        _safe_close(cap)
    except Exception as e:
        logger.exception("扫描 pcap 失败")
        raise PysharkAnalyzerError(f"扫描 pcap 失败: {e}") from e

    _ROWS_CACHE.set(key, mtime, rows)
    logger.info("构建行缓存: %s (filter=%s, %d 行)", pcap_file.name, display_filter, len(rows))
    return rows


def get_packets_page(
    pcap_path: str,
    display_filter: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> dict:
    """分页读取数据包列表（基于缓存的全量行切片）。"""
    rows = _build_all_rows(pcap_path, display_filter)
    total = len(rows)
    page_rows = rows[offset:offset + limit]
    return {
        "total_matched": total,
        "has_more": offset + limit < total,
        "offset": offset,
        "limit": limit,
        "packets": page_rows,
    }


def count_packets(pcap_path: str, display_filter: str | None = None) -> int:
    """精确统计匹配过滤条件的包数（基于缓存）。"""
    return len(_build_all_rows(pcap_path, display_filter))


def get_protocol_distribution(pcap_path: str, display_filter: str | None = None) -> dict:
    """基于缓存的行列表统计协议分布（供图表）。"""
    rows = _build_all_rows(pcap_path, display_filter)
    dist: dict[str, int] = {}
    for r in rows:
        proto = (r.get("protocol") or "UNKNOWN").upper()
        dist[proto] = dist.get(proto, 0) + 1
    # 按数量降序
    items = sorted(dist.items(), key=lambda x: x[1], reverse=True)
    return {
        "total": len(rows),
        "distribution": [{"protocol": k, "count": v} for k, v in items],
    }


def get_packet_detail(pcap_path: str, packet_number: int) -> dict:
    """获取指定序号数据包的协议树 + 基本信息 + Hex 转储。"""
    _ensure_event_loop()
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")
    try:
        cap = FileCapture(
            input_file=str(pcap_file),
            keep_packets=False,
            **_tshark_kwargs(),
        )
        for packet in cap:
            if str(getattr(packet, "number", "")) == str(packet_number):
                tree = packet_to_tree(packet)
                row = _packet_to_row(packet)
                raw = str(packet)
                _safe_close(cap)
                hex_dump = get_packet_hex(pcap_path, packet_number)
                return {
                    "number": packet_number,
                    "row": row,
                    "tree": tree,
                    "raw": raw,
                    "hex": hex_dump,
                }
        _safe_close(cap)
        raise PysharkAnalyzerError(f"未找到序号为 {packet_number} 的数据包")
    except PysharkAnalyzerError:
        raise
    except Exception as e:
        raise PysharkAnalyzerError(f"获取数据包详情失败: {e}") from e


# ---------------------------------------------------------------------
# Hex 转储（tshark -x）
# ---------------------------------------------------------------------
def get_packet_hex(pcap_path: str, packet_number: int) -> list[dict]:
    """获取指定数据包的 Hex 转储（仿 Wireshark Hex 视图）。

    通过 `tshark -r file -Y frame.number==N -x` 获取，解析为
    [{offset, hex, ascii}, ...] 的行列表。
    """
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")

    tshark_exe = TSHARK_PATH if (TSHARK_PATH and os.path.isfile(TSHARK_PATH)) else "tshark"
    cmd = [
        tshark_exe, "-r", str(pcap_file),
        "-Y", f"frame.number=={packet_number}",
        "-x",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except Exception as e:
        logger.debug("获取 Hex 失败: %s", e)
        return []

    if proc.returncode != 0:
        return []

    lines: list[dict] = []
    for line in proc.stdout.splitlines():
        # 形如: "0000  c8 68 de c4 78 43 9c 5a 88 63 6f 8a 08 00 45 00   .h..xC.Z.co..E."
        stripped = line.rstrip()
        if not stripped:
            continue
        # 前 4 个字符是 offset（16 进制）
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            continue
        offset = parts[0]
        rest = parts[1]
        # 分离 hex 区与 ascii 区（ascii 区通常以两个以上空格分隔）
        # tshark -x 的 hex 区固定宽度，ascii 在末尾
        # 简单处理：按 2+ 空格切分
        import re as _re
        segs = _re.split(r"\s{2,}", rest, maxsplit=1)
        hex_part = segs[0].strip()
        ascii_part = segs[1].strip() if len(segs) > 1 else ""
        # 过滤非 offset 行（offset 应为 4 位 16 进制）
        if not all(c in "0123456789abcdefABCDEF" for c in offset):
            continue
        lines.append({"offset": offset, "hex": hex_part, "ascii": ascii_part})
    return lines
