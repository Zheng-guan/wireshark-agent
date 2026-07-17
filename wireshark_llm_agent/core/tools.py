"""Agent 工具链。

使用 LangChain 的 @tool 装饰器，将 PyShark/Tshark 的底层能力封装为
Agent 可调用的工具函数。每个工具的 docstring 即是给 LLM 的工具说明，
必须清晰描述参数含义与返回内容，以便 Agent 正确决策调用。

工具清单：
- list_interfaces        : 列出可用网卡
- capture_packets        : 实时抓包并保存为 pcap
- analyze_pcap           : 分析 pcap 文件，提取协议关键字段
- get_tshark_stats       : 获取宏观统计信息
- inspect_packet         : 查看单个数据包详情
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from langchain_core.tools import tool

from core import pyshark_analyzer
from core.pyshark_analyzer import TSHARK_STAT_TYPES

logger = logging.getLogger(__name__)


@tool
def list_interfaces() -> str:
    """列出当前系统中所有可用于抓包的网络接口（网卡）。

    在需要知道有哪些网卡、或用户想抓某个网卡但不确定名称时调用。
    返回 JSON 字符串，每项包含 index(序号)、name(接口标识，用于抓包时传入)、display(展示名)。
    """
    interfaces = pyshark_analyzer.list_interfaces()
    return json.dumps(interfaces, ensure_ascii=False, indent=2)


@tool
def capture_packets(
    interface: str,
    duration: int = 10,
    packet_count: int = 0,
    bpf_filter: Optional[str] = None,
) -> str:
    """在指定网卡上实时抓包，并保存为 .pcapng 文件。

    参数：
    - interface: 网卡标识（来自 list_interfaces 的 name 字段，例如 "\\Device\\NPF_{...}" 或 "WLAN"）
    - duration: 抓包持续时间（秒），默认 10。到达后自动停止。
    - packet_count: 最多抓取的包数，0 表示不限（仅受 duration 控制），默认 0。
    - bpf_filter: 可选的 BPF 捕获过滤器，如 "tcp port 80" 或 "host 192.168.1.1"。默认无。

    返回：保存的 pcapng 文件绝对路径；若抓包失败返回错误信息。
    注意：抓包是阻塞操作，duration 越长等待越久，请按用户需求合理设置。
    """
    try:
        path = pyshark_analyzer.capture_live(
            interface=interface,
            duration=duration,
            packet_count=packet_count,
            bpf_filter=bpf_filter,
        )
        return f"抓包完成，文件已保存至：{path}"
    except Exception as e:
        return f"抓包失败：{e}"


@tool
def analyze_pcap(
    pcap_path: str,
    display_filter: Optional[str] = None,
    max_packets: int = 200,
) -> str:
    """分析 pcap/pcapng 文件，提取数据包摘要与各协议关键字段。

    参数：
    - pcap_path: pcap 文件路径（通常由 capture_packets 返回）
    - display_filter: 可选的 Wireshark 显示过滤器，如 "http.response.code >= 400" 或 "tcp.analysis.retransmission"。
                      用于聚焦特定流量，留空则分析全部。
    - max_packets: 最多解析的包数，默认 200（防止超大文件拖慢）。建议聚焦分析时配合 display_filter。

    返回：JSON 字符串，包含 total_returned(包数)、protocol_distribution(协议分布)、packets(每包摘要与字段)。
    字段示例：IP/TCP/HTTP/DNS/TLS 等层的 src/dst/port/状态码/标志位等。
    """
    try:
        result = pyshark_analyzer.analyze_pcap(
            pcap_path=pcap_path,
            display_filter=display_filter,
            max_packets=max_packets,
        )
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return f"分析失败：{e}"


@tool
def get_tshark_stats(pcap_path: str, stat_type: str = "protocol_hierarchy") -> str:
    """获取 pcap 文件的宏观统计信息（基于 tshark -z）。

    参数：
    - pcap_path: pcap 文件路径
    - stat_type: 统计类型，可选值：
        "protocol_hierarchy" - 协议层级树（默认，推荐先看整体概览）
        "io_stat"            - IO 统计（吞吐量等）
        "conv_ip"/"conv_tcp"/"conv_udp" - IP/TCP/UDP 端到端对话统计
        "endpoints_ip"/"endpoints_tcp"/"endpoints_udp" - 各端点统计
        "http_tree"          - HTTP 请求/响应树
        "dns_tree"           - DNS 查询树

    返回：tshark 输出的统计文本。
    """
    if stat_type not in TSHARK_STAT_TYPES:
        valid = ", ".join(TSHARK_STAT_TYPES.keys())
        return f"不支持的统计类型 '{stat_type}'。可选值：{valid}"
    try:
        return pyshark_analyzer.get_tshark_stats(pcap_path, stat_type)
    except Exception as e:
        return f"统计失败：{e}"


@tool
def inspect_packet(pcap_path: str, packet_number: int) -> str:
    """查看 pcap 文件中指定序号数据包的完整分层详情（用于深入排查单个包）。

    参数：
    - pcap_path: pcap 文件路径
    - packet_number: 数据包序号（从 1 开始，可先通过 analyze_pcap 获知）

    返回：该包的逐层字段详情文本。
    """
    try:
        return pyshark_analyzer.get_packet_details(pcap_path, packet_number)
    except Exception as e:
        return f"获取数据包详情失败：{e}"


# 导出全部工具列表，供 agent.py 使用
ALL_TOOLS = [
    list_interfaces,
    capture_packets,
    analyze_pcap,
    get_tshark_stats,
    inspect_packet,
]
