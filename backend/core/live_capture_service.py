"""实时抓包推送服务（WebSocket 瀑布流）。

思路：
1. 用单个 tshark 进程直接抓包：`-i <网卡> -l -T fields ... -w <文件>`
   - `-l` 行缓冲：每抓到一包立即向 stdout 输出一行（供实时推送）
   - `-w` 同时把原始包写入 pcapng 文件（供停止后加载到主界面深入分析）
2. 后端从 stdout 逐行读取，解析后通过 WebSocket 推送给前端
3. 前端实时追加到表格顶部，实现「数据包瀑布流」，可随时停止

关键点：必须用「单进程抓包并输出」，不能用「dumpcap 写文件 + tshark 读文件」
的双进程方案——后者 tshark 读到 EOF 后不会跟随文件增长。
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path

from config.settings import CAPTURES_DIR, TSHARK_PATH

logger = logging.getLogger(__name__)

# 活跃会话：session_id -> LiveSession
_SESSIONS: dict[str, "LiveSession"] = {}


def _tshark_exe() -> str:
    return TSHARK_PATH if (TSHARK_PATH and os.path.isfile(TSHARK_PATH)) else "tshark"


class LiveSession:
    def __init__(self, interface: str, bpf_filter: str | None, session_id: str):
        self.session_id = session_id
        self.interface = interface
        self.bpf_filter = bpf_filter
        self.file = str(CAPTURES_DIR / f"live_{session_id}.pcapng")
        self.proc: subprocess.Popen | None = None  # tshark 抓包+输出进程
        self.status = "running"  # running | stopped | error
        self.packet_count = 0
        self.start_time = time.time()

    def start(self) -> None:
        """启动 tshark 抓包进程：一个进程同时实时输出(-l -T fields)和落盘(-w)。

        -l  行缓冲：每抓到一包立即向 stdout 输出一行
        -w  同时把原始包写入 pcapng 文件（供停止后深入分析）
        -f  BPF 捕获过滤器
        """
        fields = [
            "-T", "fields",
            "-E", "separator=|",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "ip.src",
            "-e", "ip.dst",
            "-e", "ipv6.src",
            "-e", "ipv6.dst",
            "-e", "_ws.col.Protocol",
            "-e", "frame.len",
            "-e", "_ws.col.Info",
        ]
        args = [
            _tshark_exe(),
            "-i", self.interface,
            "-l",                      # 行缓冲：实时输出
            "-w", self.file,           # 同时落盘
            *fields,
        ]
        if self.bpf_filter:
            args += ["-f", self.bpf_filter]
        logger.info("启动实时抓包: %s", " ".join(args))
        self.proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # 行缓冲
        )

    def stop(self) -> None:
        """停止抓包进程。"""
        self.status = "stopped"
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        logger.info("实时抓包会话 %s 已停止，共 %d 包", self.session_id, self.packet_count)


def start_session(interface: str, bpf_filter: str | None = None) -> LiveSession:
    """创建并启动一个实时抓包会话。"""
    session_id = uuid.uuid4().hex[:12]
    sess = LiveSession(interface, bpf_filter, session_id)
    sess.start()
    _SESSIONS[session_id] = sess
    return sess


def get_session(session_id: str) -> LiveSession | None:
    return _SESSIONS.get(session_id)


def stop_session(session_id: str) -> bool:
    sess = _SESSIONS.pop(session_id, None)
    if not sess:
        return False
    sess.stop()
    return True


async def stream_packets(sess: LiveSession, ws_send):
    """从抓包进程 stdout 逐行读包，通过 ws_send 协程推送。"""
    loop = asyncio.get_event_loop()
    assert sess.proc and sess.proc.stdout

    def _read_line():
        return sess.proc.stdout.readline()

    while sess.status == "running":
        try:
            line = await loop.run_in_executor(None, _read_line)
        except Exception as e:
            logger.debug("读取行异常: %s", e)
            break
        if not line:
            # EOF：抓包进程已退出
            break
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 9:
            continue
        sess.packet_count += 1
        src = parts[2] or parts[4] or ""
        dst = parts[3] or parts[5] or ""
        try:
            rel = float(parts[1] or 0)
        except ValueError:
            rel = 0.0
        pkt = {
            "number": parts[0],
            "time": f"{rel:.6f}",
            "source": src,
            "destination": dst,
            "protocol": (parts[6] or "").upper(),
            "length": parts[7],
            "info": parts[8],
        }
        try:
            await ws_send({"type": "packet", "packet": pkt, "count": sess.packet_count})
        except Exception as e:
            logger.debug("WebSocket 发送失败: %s", e)
            break

    # 结束通知
    try:
        await ws_send({
            "type": "done",
            "count": sess.packet_count,
            "file": sess.file,
            "elapsed": round(time.time() - sess.start_time, 1),
        })
    except Exception:
        pass
