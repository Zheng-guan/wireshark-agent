"""AI 聊天 / 语义分析 API 路由。

- POST /api/chat/message   处理用户自然语言（可能是过滤意图或普通对话）
- POST /api/chat/summarize 对选中的数据包进行 LLM 总结
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from core import llm_service, report_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    pcap_file: str = ""
    current_filter: str = ""


class ChatResponse(BaseModel):
    intent: str            # "filter" | "chat"
    filter: str = ""       # 若 intent=filter，为 Wireshark 过滤表达式
    reply: str             # 给用户看的文字回复


class SummarizeRequest(BaseModel):
    packets: list[dict[str, Any]]


@router.post("/message", response_model=ChatResponse)
def chat_message(req: ChatRequest):
    """处理用户自然语言输入。

    流程：先尝试解析为过滤意图；若为 filter，返回过滤表达式让前端应用；
    否则走通用对话。
    """
    try:
        parsed = llm_service.parse_semantic_filter(req.message)
        if parsed["intent"] == "filter" and parsed["filter"]:
            return ChatResponse(
                intent="filter",
                filter=parsed["filter"],
                reply=parsed["explanation"] or f"已为您生成过滤器：{parsed['filter']}",
            )
        # 普通对话
        reply = llm_service.chat(
            user_input=req.message,
            pcap_file=req.pcap_file,
            current_filter=req.current_filter,
        )
        return ChatResponse(intent="chat", filter="", reply=reply)
    except Exception as e:
        logger.exception("chat_message 失败")
        raise HTTPException(status_code=500, detail=f"对话处理失败: {e}")


@router.post("/summarize")
def summarize(req: SummarizeRequest):
    """对选中的数据包摘要进行 LLM 总结。"""
    try:
        text = llm_service.summarize_packets(req.packets)
        return {"summary": text}
    except Exception as e:
        logger.exception("summarize 失败")
        raise HTTPException(status_code=500, detail=f"总结失败: {e}")


class ReportRequest(BaseModel):
    title: str = "网络分析报告"
    summary: str
    packets: list[dict[str, Any]]
    pcap_file: str = ""
    filter_expr: str = ""


@router.post("/report", response_class=HTMLResponse)
def export_report(req: ReportRequest):
    """把 AI 总结 + 数据包明细导出为自包含 HTML 报告。"""
    try:
        return report_service.render_report_html(
            title=req.title,
            summary_markdown=req.summary,
            packets=req.packets,
            pcap_file=req.pcap_file,
            filter_expr=req.filter_expr,
        )
    except Exception as e:
        logger.exception("export_report 失败")
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")
