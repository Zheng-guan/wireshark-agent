"""实时抓包 WebSocket 路由。

- WS /api/live/capture?interface=...&bpf_filter=...
  消息协议（服务端 -> 客户端）：
    {"type": "packet", "packet": {...}, "count": N}
    {"type": "done", "count": N, "file": "...", "elapsed": S}
    {"type": "error", "message": "..."}
  客户端 -> 服务端：
    {"action": "stop"}   停止抓包
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from core import live_capture_service
from core.packet_service import clear_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["live"])


@router.websocket("/capture")
async def live_capture_ws(
    ws: WebSocket,
    interface: str = Query(...),
    bpf_filter: str = Query(""),
):
    await ws.accept()
    sess = None

    async def send(msg: dict):
        await ws.send_text(json.dumps(msg, ensure_ascii=False))

    try:
        sess = live_capture_service.start_session(
            interface=interface,
            bpf_filter=bpf_filter or None,
        )
        await send({"type": "started", "session": sess.session_id, "file": sess.file})

        # 并行：推送数据包 + 监听客户端停止指令
        async def listen_stop():
            try:
                while True:
                    data = await ws.receive_text()
                    try:
                        msg = json.loads(data)
                    except Exception:
                        continue
                    if msg.get("action") == "stop":
                        live_capture_service.stop_session(sess.session_id)
                        break
            except WebSocketDisconnect:
                pass

        push_task = asyncio.create_task(live_capture_service.stream_packets(sess, send))
        stop_task = asyncio.create_task(listen_stop())
        await asyncio.wait(
            [push_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        # 任一完成则清理
        for t in (push_task, stop_task):
            if not t.done():
                t.cancel()
        live_capture_service.stop_session(sess.session_id)
        clear_cache()  # 新文件产生，清行缓存
    except WebSocketDisconnect:
        logger.info("实时抓包 WebSocket 断开")
    except Exception as e:
        logger.exception("实时抓包失败")
        try:
            await send({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if sess:
            live_capture_service.stop_session(sess.session_id)
        try:
            await ws.close()
        except Exception:
            pass
