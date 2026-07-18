"""TCP/UDP 流追踪服务（Follow Stream）。

复刻 Wireshark 的「Follow TCP/UDP Stream」功能：
- 先用 pyshark 定位指定数据包所属的流索引（tcp.stream / udp.stream）
- 再调用 `tshark -q -z follow,<proto>,ascii,<index>` 提取完整双向通信内容
- 解析输出为结构化的分段列表（客户端/服务端着色所需的方向信息）

同时提供「按显示过滤器导出 pcap」能力（配合前端下载过滤后的包）。
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

from config.settings import TSHARK_PATH
from core.pyshark_analyzer import (
    PysharkAnalyzerError,
    _ensure_event_loop,
    _safe_close,
    _tshark_kwargs,
)

from pyshark import FileCapture

logger = logging.getLogger(__name__)

MAX_STREAM_BYTES = 512 * 1024  # 流内容截断阈值（防止超大流撑爆内存/前端）


def _tshark_exe() -> str:
    return TSHARK_PATH if (TSHARK_PATH and os.path.isfile(TSHARK_PATH)) else "tshark"


def _run_tshark(args: list[str], timeout: int = 60) -> str:
    """执行 tshark 并返回 stdout，失败抛 PysharkAnalyzerError。"""
    cmd = [_tshark_exe(), *args]
    logger.info("执行: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise PysharkAnalyzerError(f"未找到 tshark: {cmd[0]}") from None
    except subprocess.TimeoutExpired:
        raise PysharkAnalyzerError(f"tshark 执行超时（>{timeout}s）") from None
    if proc.returncode != 0:
        raise PysharkAnalyzerError(f"tshark 执行失败: {proc.stderr.strip()[:300]}")
    return proc.stdout


def get_stream_info(pcap_path: str, packet_number: int) -> dict:
    """定位指定数据包所属的 TCP/UDP 流。

    :return: {"proto": "tcp"|"udp", "index": int, "src": ..., "dst": ...,
              "sport": ..., "dport": ...}
    """
    _ensure_event_loop()
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")

    try:
        cap = FileCapture(
            input_file=str(pcap_file),
            display_filter=f"frame.number == {packet_number}",
            keep_packets=False,
            **_tshark_kwargs(),
        )
        packet = None
        for p in cap:
            packet = p
            break
        _safe_close(cap)
    except Exception as e:
        raise PysharkAnalyzerError(f"读取数据包失败: {e}") from e

    if packet is None:
        raise PysharkAnalyzerError(f"未找到序号为 {packet_number} 的数据包")

    for proto in ("tcp", "udp"):
        layer = getattr(packet, proto, None)
        if layer is None:
            continue
        stream_idx = getattr(layer, "stream", None)
        if stream_idx is None:
            continue
        info = {
            "proto": proto,
            "index": int(stream_idx),
            "src": "", "dst": "", "sport": "", "dport": "",
        }
        ip = getattr(packet, "ip", None) or getattr(packet, "ipv6", None)
        if ip is not None:
            info["src"] = str(getattr(ip, "src", "") or "")
            info["dst"] = str(getattr(ip, "dst", "") or "")
        info["sport"] = str(getattr(layer, "srcport", "") or "")
        info["dport"] = str(getattr(layer, "dstport", "") or "")
        return info

    raise PysharkAnalyzerError(
        f"数据包 #{packet_number} 不属于任何 TCP/UDP 流（可能是 {getattr(packet, 'highest_layer', '?')}）"
    )


def follow_stream(pcap_path: str, proto: str, stream_index: int) -> dict:
    """提取完整流内容（ASCII 模式），解析为分段列表。

    tshark 输出形如：
        ===================================================================
        Follow: tcp,ascii
        Filter: tcp.stream eq 0
        Node 0: 192.168.1.1:50000
        Node 1: 93.184.216.34:80
        48
        GET / HTTP/1.1...
            （客户端数据，前缀为 1 位十六进制长度）
        ===================================================================
    实际格式：每个数据段以「tab + 十六进制长度」行开头（方向 1），
    或无缩进的长度行（方向 0），随后是该段的原始字节文本。
    """
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")
    if proto not in ("tcp", "udp"):
        raise PysharkAnalyzerError(f"不支持的流协议: {proto}")

    output = _run_tshark([
        "-r", str(pcap_file), "-q", "-z", f"follow,{proto},ascii,{stream_index}",
    ], timeout=120)

    return _parse_follow_output(output, proto, stream_index)


def _parse_follow_output(output: str, proto: str, stream_index: int) -> dict:
    """解析 tshark follow,ascii 输出为结构化分段。"""
    nodes: list[str] = []
    segments: list[dict] = []
    truncated = False

    lines = output.splitlines()
    i = 0
    # 数据段格式：行首（可选 tab）+ 十六进制长度，换行后是该段内容
    len_re = re.compile(r"^(\t?)([0-9a-fA-F]+)$")

    while i < len(lines):
        line = lines[i]
        if line.startswith("Node "):
            # "Node 0: 192.168.1.1:50000"
            m = re.match(r"^Node \d+:\s*(.+)$", line)
            if m:
                nodes.append(m.group(1).strip())
            i += 1
            continue
        m = len_re.match(line)
        if m:
            direction = 1 if m.group(1) else 0
            seg_len = int(m.group(2), 16)
            i += 1
            # 收集该段内容（直到下一个长度行 / 分隔线 / 文件尾）
            buf: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.startswith("===") or len_re.match(nxt) or nxt.startswith("Node "):
                    break
                buf.append(nxt)
                i += 1
            data = "\n".join(buf)
            # tshark 的 ascii 输出中不可打印字符以 . 代替；段尾可能有空行
            data = data.rstrip("\n")
            if len(data.encode("utf-8", errors="replace")) > MAX_STREAM_BYTES:
                data = data[:MAX_STREAM_BYTES]
                truncated = True
            segments.append({
                "direction": direction,   # 0 = Node0->Node1, 1 = Node1->Node0
                "size": seg_len,
                "data": data,
            })
            continue
        i += 1

    return {
        "proto": proto,
        "index": stream_index,
        "nodes": nodes,
        "segments": segments,
        "segment_count": len(segments),
        "truncated": truncated,
    }


def export_filtered_pcap(
    pcap_path: str,
    display_filter: str | None,
    dest_path: str,
) -> str:
    """按显示过滤器导出 pcap（tshark -Y ... -w）。

    :return: 输出文件路径
    """
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")

    args = ["-r", str(pcap_file)]
    if display_filter:
        args += ["-Y", display_filter]
    args += ["-w", dest_path]
    _run_tshark(args, timeout=300)

    out = Path(dest_path)
    if not out.is_file() or out.stat().st_size == 0:
        raise PysharkAnalyzerError("导出失败：输出文件为空（可能过滤器无匹配）")
    return str(out)
