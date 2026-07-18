"""LLM 语义服务。

提供两类能力：
1. 自然语言 -> Wireshark 显示过滤表达式（结构化输出，供前端应用）
2. 对选中数据包的自然语言总结 / 诊断

复用 agent.py 中的 _FastChatZhipuAI（关闭深度思考）与配置。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage

from core.agent import _build_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# 意图识别 + 过滤表达式生成
# ---------------------------------------------------------------------
_FILTER_PROMPT = """你是一名 Wireshark 显示过滤器专家。用户会用自然语言描述想看的网络流量，
你的任务是判断用户意图，并（如适用）生成对应的 Wireshark 显示过滤表达式。

请严格按以下 JSON 格式输出（不要输出任何其他文字、不要用 markdown 代码块包裹）：
{{
  "intent": "filter" | "chat",
  "filter": "<Wireshark 显示过滤表达式，若 intent 为 chat 则为空字符串>",
  "explanation": "<一句话中文说明这个过滤器的含义，若 chat 则为你的回答>"
}}

判断规则：
- 若用户想"过滤/筛选/找出/显示/只看"某些包，intent 为 "filter"，并给出合法的 Wireshark 显示过滤语法。
- 若用户只是聊天、提问、要求解释或总结，intent 为 "chat"，filter 留空。

常用过滤语法参考：
- HTTP 错误: http.response.code >= 400
- 指定状态码: http.response.code == 500
- TCP 重传: tcp.analysis.retransmission
- SYN 无 ACK（握手失败）: tcp.flags.syn==1 and tcp.flags.ack==0
- 指定 IP: ip.addr == 192.168.1.1
- 指定端口: tcp.port == 80
- DNS: dns
- TLS 握手: tls.handshake.type == 1
- HTTP 请求: http.request

用户输入：{user_input}
"""


def parse_semantic_filter(user_input: str) -> dict[str, Any]:
    """把自然语言解析为过滤意图。

    :return: {"intent": "filter"|"chat", "filter": str, "explanation": str}
    """
    llm = _build_llm()
    prompt = _FILTER_PROMPT.format(user_input=user_input)
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = (resp.content or "").strip()
        # 去掉可能的 markdown 代码块包裹
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        # 提取第一个 JSON 对象
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            return {
                "intent": data.get("intent", "chat"),
                "filter": data.get("filter", "") or "",
                "explanation": data.get("explanation", "") or "",
            }
    except Exception as e:
        logger.exception("语义过滤解析失败")
        return {"intent": "chat", "filter": "", "explanation": f"解析失败：{e}"}
    return {"intent": "chat", "filter": "", "explanation": "未能理解您的意图，请换个说法。"}


# ---------------------------------------------------------------------
# 数据包总结
# ---------------------------------------------------------------------
_SUMMARY_PROMPT = """你是一名资深网络分析工程师。下面是用户从抓包文件中选中的若干数据包的摘要信息
（JSON 格式，包含序号、时间、源/目的地址、协议、长度、Info 等）。

请你用中文对这些数据包进行分析，输出一份简洁的诊断报告，包括：
1. 这些包在做什么（通信双方、协议、行为）。
2. 是否有异常（错误状态码、重传、握手失败、可疑流量等）。
3. 简要结论与建议。

数据包摘要：
{packets_json}
"""


def summarize_packets(packets: list[dict]) -> str:
    """对选中的数据包摘要列表进行 LLM 总结。"""
    if not packets:
        return "未提供任何数据包。"
    llm = _build_llm()
    packets_json = json.dumps(packets, ensure_ascii=False, indent=2, default=str)
    # 截断防止超长
    if len(packets_json) > 6000:
        packets_json = packets_json[:6000] + "\n...(已截断)"
    prompt = _SUMMARY_PROMPT.format(packets_json=packets_json)
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        return resp.content or "（LLM 未返回总结）"
    except Exception as e:
        logger.exception("数据包总结失败")
        return f"总结失败：{e}"


# ---------------------------------------------------------------------
# 通用聊天（带上下文）
# ---------------------------------------------------------------------
_CHAT_PROMPT = """你是「Wireshark 智能助手」，一名资深网络分析工程师。
用户正在一个 Web 版 Wireshark 界面上分析抓包文件。请用中文简洁、专业地回答用户的问题。
如果用户的问题涉及过滤流量，请提示用户可以让我帮忙过滤（例如说"帮我过滤 HTTP 错误"）。

当前上下文：
- 打开的抓包文件：{pcap_file}
- 当前应用的过滤器：{current_filter}

用户问题：{user_input}
"""


def chat(user_input: str, pcap_file: str = "", current_filter: str = "") -> str:
    """通用对话（非过滤意图时使用）。"""
    llm = _build_llm()
    prompt = _CHAT_PROMPT.format(
        pcap_file=pcap_file or "(未打开)",
        current_filter=current_filter or "(无)",
        user_input=user_input,
    )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        return resp.content or "（LLM 未返回回答）"
    except Exception as e:
        logger.exception("聊天失败")
        return f"对话失败：{e}"


# ---------------------------------------------------------------------
# 协议字段解释（Explain This Field）
# ---------------------------------------------------------------------
_FIELD_PROMPT = """你是一名网络协议专家，正在帮助用户理解 Wireshark 协议树中的一个字段。

请用中文简洁解释（150 字以内，可用简短 markdown）：
1. 这个字段在该协议中的含义/作用。
2. 当前这个值说明什么（是否正常、典型取值范围、是否值得关注）。

所属协议层：{layer}
字段路径：{field_path}
字段显示名：{field_name}
当前值：{field_value}

只输出解释正文，不要输出标题或客套话。"""


def explain_field(layer: str, field_path: str, field_name: str, field_value: str) -> str:
    """AI 解释协议树中的单个字段。"""
    llm = _build_llm()
    prompt = _FIELD_PROMPT.format(
        layer=layer or "(未知)",
        field_path=field_path or field_name,
        field_name=field_name,
        field_value=(field_value or "(空)")[:500],
    )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        return resp.content or "（LLM 未返回解释）"
    except Exception as e:
        logger.exception("字段解释失败")
        return f"解释失败：{e}"


# ---------------------------------------------------------------------
# 流级 AI 诊断（Analyze TCP/UDP Stream）
# ---------------------------------------------------------------------
_STREAM_PROMPT = """你是一名资深网络安全分析工程师。下面是从抓包文件中提取的一条完整 {proto} 流
的双向通信内容（ASCII 形式，不可打印字符以 . 代替）。

通信节点：{nodes}
共 {seg_count} 个数据段。

流内容（可能已截断）：
------
{stream_text}
------

请用中文输出一份会话级诊断报告（markdown 格式），包括：
1. **会话概要**：这是什么协议的会话？双方在做什么（如 HTTP 下载、API 调用、登录等）？
2. **是否正常**：通信是否成功完成？有无错误码、重试、异常中断、握手问题？
3. **安全观察**：是否存在可疑特征（明文凭证、注入尝试、异常 User-Agent、敏感信息泄露等）？
4. **结论建议**：一句话结论 + 是否值得深入排查。

若内容为空或无法识别，请如实说明。"""


def analyze_stream(proto: str, nodes: list[str], segments: list[dict]) -> str:
    """对完整 TCP/UDP 流进行 AI 会话级诊断。"""
    if not segments:
        return "该流没有可分析的数据内容。"
    llm = _build_llm()

    # 拼接流文本（标注方向），并截断防超长
    parts: list[str] = []
    node0 = nodes[0] if len(nodes) > 0 else "Node0"
    node1 = nodes[1] if len(nodes) > 1 else "Node1"
    total = 0
    for seg in segments:
        src, dst = (node0, node1) if seg["direction"] == 0 else (node1, node0)
        chunk = f"[{src} -> {dst}]\n{seg['data']}\n"
        if total + len(chunk) > 8000:
            parts.append("\n...(后续内容已截断)\n")
            break
        parts.append(chunk)
        total += len(chunk)
    stream_text = "\n".join(parts)

    prompt = _STREAM_PROMPT.format(
        proto=proto.upper(),
        nodes=" ↔ ".join(nodes) if nodes else "(未知)",
        seg_count=len(segments),
        stream_text=stream_text,
    )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        return resp.content or "（LLM 未返回诊断）"
    except Exception as e:
        logger.exception("流诊断失败")
        return f"诊断失败：{e}"
