"""网卡实时流量监控服务。

基于 psutil.net_io_counters(pernic=True) 采样各网卡的收发速率，
供前端在「选择抓包网卡」时展示实时流量图，辅助判断哪个网卡有流量。

关键点：把 psutil 的网卡名（如 "以太网"、"WLAN"）与 tshark -D 的
设备标识（形如 \\Device\\NPF_{GUID}）做尽力而为的匹配。
"""
from __future__ import annotations

import logging
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# 上一次采样：{nic_name: (timestamp, bytes_sent, bytes_recv)}
_last_sample: dict[str, tuple[float, int, int]] = {}


def get_nic_rates() -> list[dict[str, Any]]:
    """采样一次，返回各网卡的实时速率（bytes/s）。

    第一次调用时建立基线（速率为 0），后续调用返回与上次的差值速率。
    """
    now = time.time()
    counters = psutil.net_io_counters(pernic=True)
    result: list[dict[str, Any]] = []

    for name, c in counters.items():
        prev = _last_sample.get(name)
        if prev is None:
            sent_rate = recv_rate = 0.0
        else:
            dt = max(now - prev[0], 1e-6)
            sent_rate = max(0.0, (c.bytes_sent - prev[1]) / dt)
            recv_rate = max(0.0, (c.bytes_recv - prev[2]) / dt)
        _last_sample[name] = (now, c.bytes_sent, c.bytes_recv)
        result.append({
            "name": name,
            "sent_bps": round(sent_rate, 1),
            "recv_bps": round(recv_rate, 1),
            "total_bps": round(sent_rate + recv_rate, 1),
        })
    return result


def match_tshark_to_psutil(tshark_interfaces: list[dict]) -> list[dict]:
    """把 tshark 网卡与 psutil 网卡做名称匹配，返回带流量的网卡列表。

    tshark 项: {"index", "name"(形如 \\Device\\NPF_..), "alias"(如 WLAN), "display"}
    psutil 项: {"name"(如 "WLAN"/"以太网"), "sent_bps", "recv_bps", ...}

    匹配策略：alias 与 psutil name 忽略大小写/空格后互相包含即认为匹配。
    """
    rates = {r["name"]: r for r in get_nic_rates()}
    out: list[dict] = []
    for iface in tshark_interfaces:
        alias = (iface.get("alias") or "").strip().lower()
        matched = None
        for ps_name, r in rates.items():
            ps_l = ps_name.strip().lower()
            if not alias:
                break
            if alias in ps_l or ps_l in alias:
                matched = r
                break
        item = dict(iface)
        if matched:
            item["traffic"] = matched
        else:
            item["traffic"] = None
        out.append(item)
    return out
