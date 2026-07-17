"""PyShark 底层调用封装。

本模块对 PyShark 的 LiveCapture / FileCapture 进行二次封装，提供：
- 实时抓包（限时或限包数）
- 读取 pcap/pcapng 文件并提取协议关键字段
- 调用 tshark -z 获取宏观统计信息（协议层级树、端到端对话等）

所有返回值均为可被 LLM 直接消费的「结构化字典 / 字符串」，
避免把复杂的 PyShark Packet 对象暴露给上层 Agent。
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from config.settings import CAPTURES_DIR, TSHARK_PATH

logger = logging.getLogger(__name__)

# PyShark 在不同事件循环下有兼容性问题，按需导入
import pyshark  # noqa: E402
from pyshark import LiveCapture, FileCapture  # noqa: E402


def _ensure_event_loop() -> None:
    """确保当前线程拥有 asyncio 事件循环。

    Streamlit 在 ThreadPoolExecutor 子线程中执行用户代码，而 pyshark 的
    Capture.__init__ 会调用 asyncio.get_event_loop()，子线程中若无事件循环
    会抛出 RuntimeError。此函数在子线程中创建并设置一个新的事件循环。
    """
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        # 当前线程没有事件循环，创建一个新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug("为线程 %s 创建了新的事件循环", threading.current_thread().name)


# ---------------------------------------------------------------------
# 异常定义
# ---------------------------------------------------------------------
class PysharkAnalyzerError(Exception):
    """PyShark 分析器通用异常。"""


def _safe_close(capture) -> None:
    """安全关闭 pyshark capture 对象，吞掉 Windows 下关闭子进程时的清理异常。

    Windows ProactorEventLoop 在关闭 tshark/dumpcap 子进程时，
    可能抛出 "I/O operation on closed pipe" 等异常，这属于清理噪音，
    不影响已完成的抓包/解析结果。
    """
    try:
        capture.close()
    except Exception as e:
        logger.debug("capture.close() 清理异常（可忽略）: %s", e)


# ---------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------
def _tshark_kwargs() -> dict:
    """返回传给 PyShark 各 Capture 类的公共参数。"""
    kwargs: dict[str, Any] = {}
    if TSHARK_PATH and os.path.isfile(TSHARK_PATH):
        kwargs["tshark_path"] = TSHARK_PATH
    return kwargs


def _packet_to_summary(packet) -> dict:
    """将一个 PyShark Packet 转换为精简摘要字典。

    提取帧号、时间、长度、各层名称，以及常见协议关键字段。
    """
    summary: dict[str, Any] = {
        "number": getattr(packet, "number", None),
        "sniff_time": str(getattr(packet, "sniff_time", "")),
        "length": getattr(packet, "length", None),
        "highest_layer": getattr(packet, "highest_layer", None),
        "transport_layer": getattr(packet, "transport_layer", None),
        "layers": [layer.layer_name for layer in getattr(packet, "layers", [])],
        "fields": {},
    }

    # 提取每层中常见的关键字段（容错：字段不存在则跳过）
    interesting_fields = {
        "ip": ["ip.src", "ip.dst", "ip.ttl", "ip.proto"],
        "ipv6": ["ipv6.src", "ipv6.dst"],
        "tcp": ["tcp.srcport", "tcp.dstport", "tcp.flags", "tcp.seq", "tcp.ack",
                "tcp.analysis.retransmission", "tcp.analysis.lost_segment"],
        "udp": ["udp.srcport", "udp.dstport"],
        "http": ["http.request.method", "http.request.uri", "http.host",
                 "http.response.code", "http.response.phrase", "http.content_type"],
        "http2": ["http2.header.value"],
        "dns": ["dns.qry.name", "dns.qry.type", "dns.flags.response",
                "dns.a", "dns.cname"],
        "tls": ["tls.record.content_type", "tls.handshake.type",
                "tls.handshake.extensions_server_name"],
        "ssl": ["tls.record.content_type", "tls.handshake.type"],
        "arp": ["arp.src.proto_ipv4", "arp.dst.proto_ipv4", "arp.opcode"],
        "icmp": ["icmp.type", "icmp.code"],
        "ntp": ["ntp.refid"],
    }

    for layer in getattr(packet, "layers", []):
        layer_name = layer.layer_name.lower()
        field_list = interesting_fields.get(layer_name)
        if not field_list:
            continue
        layer_fields: dict[str, Any] = {}
        for fname in field_list:
            # PyShark layer 属性名是点号转下划线，但也可用 get_field / has_field
            attr = fname.replace(".", "_")
            if hasattr(layer, attr):
                val = getattr(layer, attr)
                if val is not None:
                    layer_fields[fname] = str(val)
            elif layer.has_field(fname):
                layer_fields[fname] = str(layer.get_field(fname))
        if layer_fields:
            summary["fields"][layer_name] = layer_fields

    return summary


def _safe_str(value: Any, max_len: int = 200) -> str:
    """安全转字符串并截断，避免超长字段污染 LLM 上下文。"""
    s = str(value)
    return s if len(s) <= max_len else s[:max_len] + "...(截断)"


# ---------------------------------------------------------------------
# 实时抓包
# ---------------------------------------------------------------------
def capture_live(
    interface: str,
    duration: int = 10,
    packet_count: int = 0,
    bpf_filter: str | None = None,
    output_filename: str | None = None,
) -> str:
    """在指定网卡上实时抓包并保存为 pcapng 文件。

    :param interface: 网卡名称（来自 list_interfaces()）
    :param duration: 抓包持续时间（秒），到达后自动停止
    :param packet_count: 最大抓包数量，0 表示不限
    :param bpf_filter: BPF 捕获过滤表达式，如 "tcp port 80"
    :param output_filename: 输出文件名（不含路径），None 则自动生成
    :return: 保存的 pcapng 文件绝对路径
    """
    _ensure_event_loop()
    if not output_filename:
        output_filename = f"capture_{int(time.time())}.pcapng"
    output_path = CAPTURES_DIR / output_filename

    logger.info(
        "开始抓包: interface=%s, duration=%ss, count=%s, filter=%s -> %s",
        interface, duration, packet_count, bpf_filter, output_path,
    )

    try:
        capture = LiveCapture(
            interface=interface,
            bpf_filter=bpf_filter,
            output_file=str(output_path),
            **_tshark_kwargs(),
        )
        # load_packets 支持 timeout（秒），到点自动停止
        capture.load_packets(packet_count=packet_count, timeout=duration)
        try:
            capture.close()
        except Exception as close_err:
            # Windows ProactorEventLoop 下关闭子进程时可能抛出
            # "I/O operation on closed pipe" 等清理异常，不影响抓包结果
            logger.debug("capture.close() 清理异常（可忽略）: %s", close_err)
    except Exception as e:
        logger.exception("抓包失败")
        raise PysharkAnalyzerError(f"抓包失败: {e}") from e

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise PysharkAnalyzerError(
            f"抓包结束但文件为空或不存在: {output_path}（可能是该网卡无流量或过滤过严）"
        )

    logger.info("抓包完成: %s (%.2f KB)", output_path, output_path.stat().st_size / 1024)
    return str(output_path)


# ---------------------------------------------------------------------
# 读取 / 分析 pcap 文件
# ---------------------------------------------------------------------
def analyze_pcap(
    pcap_path: str,
    display_filter: str | None = None,
    max_packets: int = 200,
    extract_fields: bool = True,
) -> dict:
    """使用 PyShark 读取 pcap 文件，提取数据包摘要与关键字段。

    :param pcap_path: pcap/pcapng 文件路径
    :param display_filter: Wireshark 显示过滤器，如 "http.response.code >= 400"
    :param max_packets: 最多解析的数据包数量（防止超大文件拖慢分析）
    :param extract_fields: 是否提取各协议关键字段
    :return: {"file": ..., "filter": ..., "total_returned": N, "packets": [...], "protocol_distribution": {...}}
    """
    _ensure_event_loop()
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")

    result: dict[str, Any] = {
        "file": str(pcap_file),
        "filter": display_filter,
        "total_returned": 0,
        "packets": [],
        "protocol_distribution": {},
    }

    try:
        cap = FileCapture(
            input_file=str(pcap_file),
            display_filter=display_filter,
            keep_packets=False,
            **_tshark_kwargs(),
        )
        count = 0
        for packet in cap:
            if count >= max_packets:
                break
            summary = _packet_to_summary(packet)
            result["packets"].append(summary)

            # 统计最高层协议分布
            hl = summary.get("highest_layer") or "UNKNOWN"
            result["protocol_distribution"][hl] = (
                result["protocol_distribution"].get(hl, 0) + 1
            )
            count += 1
        try:
            cap.close()
        except Exception as close_err:
            logger.debug("cap.close() 清理异常（可忽略）: %s", close_err)
    except Exception as e:
        logger.exception("分析 pcap 失败")
        raise PysharkAnalyzerError(f"分析 pcap 失败: {e}") from e

    result["total_returned"] = len(result["packets"])
    if not extract_fields:
        # 仅保留每包的元信息，丢弃字段细节
        for p in result["packets"]:
            p.pop("fields", None)

    logger.info("分析完成: %s, 返回 %d 个包", pcap_path, result["total_returned"])
    return result


def get_packet_details(pcap_path: str, packet_number: int) -> str:
    """获取指定序号数据包的完整层结构文本（用于深入排查单个包）。

    :param pcap_path: pcap 文件路径
    :param packet_number: 数据包序号（从 1 开始）
    :return: 该包的 pretty_print 文本
    """
    _ensure_event_loop()
    try:
        cap = FileCapture(
            input_file=str(pcap_path),
            keep_packets=False,
            **_tshark_kwargs(),
        )
        target = packet_number
        for packet in cap:
            if str(getattr(packet, "number", "")) == str(target):
                _safe_close(cap)
                return str(packet)
        _safe_close(cap)
        return f"未找到序号为 {packet_number} 的数据包。"
    except Exception as e:
        raise PysharkAnalyzerError(f"获取数据包详情失败: {e}") from e


# ---------------------------------------------------------------------
# tshark 统计信息（-z）
# ---------------------------------------------------------------------
# 常用统计类型 -> tshark -z 参数
TSHARK_STAT_TYPES = {
    "io_stat": "io,stat,0",
    "protocol_hierarchy": "io,phs",
    "conv_ip": "conv,ip",
    "conv_tcp": "conv,tcp",
    "conv_udp": "conv,udp",
    "endpoints_ip": "endpoints,ip",
    "endpoints_tcp": "endpoints,tcp",
    "endpoints_udp": "endpoints,udp",
    "http_tree": "http,tree",
    "dns_tree": "dns,tree",
}


def get_tshark_stats(pcap_path: str, stat_type: str = "protocol_hierarchy") -> str:
    """利用 tshark -z 命令获取宏观统计信息。

    :param pcap_path: pcap 文件路径
    :param stat_type: 统计类型，见 TSHARK_STAT_TYPES 的 key
    :return: tshark 输出的原始统计文本
    """
    pcap_file = Path(pcap_path)
    if not pcap_file.is_file():
        raise PysharkAnalyzerError(f"pcap 文件不存在: {pcap_path}")

    z_arg = TSHARK_STAT_TYPES.get(stat_type, stat_type)
    tshark_exe = TSHARK_PATH if (TSHARK_PATH and os.path.isfile(TSHARK_PATH)) else "tshark"

    cmd = [tshark_exe, "-r", str(pcap_file), "-q", "-z", z_arg]
    logger.info("执行 tshark 统计: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise PysharkAnalyzerError(
            f"未找到 tshark 可执行文件: {tshark_exe}。请在配置中设置正确的 TSHARK_PATH。"
        ) from None
    except subprocess.TimeoutExpired:
        raise PysharkAnalyzerError("tshark 统计执行超时（>60s）。") from None

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise PysharkAnalyzerError(
            f"tshark 统计执行失败 (返回码 {proc.returncode}): {stderr}"
        )

    output = proc.stdout.strip()
    if not output:
        return f"统计类型 '{stat_type}' 无输出（可能该 pcap 中无相关协议流量）。"
    return output


# ---------------------------------------------------------------------
# 网卡列表
# ---------------------------------------------------------------------
def list_interfaces() -> list[dict]:
    """获取可用网卡列表。

    通过解析 `tshark -D` 的输出，配对出「设备标识（用于抓包）+ 友好别名」。

    :return: [{"index": 1, "name": "\\Device\\NPF_{...}", "alias": "WLAN",
               "display": "1. WLAN (\\Device\\NPF_{...})"}, ...]
    """
    tshark_exe = TSHARK_PATH if (TSHARK_PATH and os.path.isfile(TSHARK_PATH)) else "tshark"
    try:
        proc = subprocess.run(
            [tshark_exe, "-D"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
    except Exception as e:
        raise PysharkAnalyzerError(f"获取网卡列表失败: {e}") from e

    if proc.returncode != 0:
        raise PysharkAnalyzerError(f"tshark -D 执行失败: {proc.stderr.strip()}")

    # 输出形如： 5. \Device\NPF_{...} (WLAN)
    line_re = re.compile(r"^\s*(\d+)\.\s+(\S+)(?:\s+\((.+)\))?\s*$")
    interfaces: list[dict] = []
    for line in proc.stdout.splitlines():
        m = line_re.match(line)
        if not m:
            continue
        idx, name, alias = m.group(1), m.group(2), (m.group(3) or "")
        interfaces.append({
            "index": int(idx),
            "name": name,                       # 用于 capture_packets 的 interface 参数
            "alias": alias,                     # 友好名，如 WLAN / 以太网
            "display": f"{idx}. {alias} ({name})" if alias else f"{idx}. {name}",
        })
    return interfaces


def get_tshark_version() -> str:
    """返回 tshark 版本字符串，用于启动检查。"""
    tshark_exe = TSHARK_PATH if (TSHARK_PATH and os.path.isfile(TSHARK_PATH)) else "tshark"
    try:
        proc = subprocess.run(
            [tshark_exe, "--version"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        return proc.stdout.splitlines()[0] if proc.stdout else "未知"
    except Exception:
        return "未知（无法调用 tshark）"
