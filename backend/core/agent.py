"""LangChain/LangGraph Agent 定义、Prompt 设计与编排。

本模块构建一个 ReAct 风格的智能体，能够根据用户的自然语言指令，
自主调用工具链（抓包 / 列网卡 / 分析 pcap / 统计 / 查看单包），
最终将结构化结果总结为人类易读的网络诊断报告。

适配 LangChain 1.x / LangGraph：使用 langgraph.prebuilt.create_react_agent，
而非已移除的 AgentExecutor + create_tool_calling_agent。

模型：智谱 GLM-4.7（通过 langchain_community.chat_models.ChatZhipuAI）。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from config.settings import (
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    OLLAMA_BASE_URL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    ZHIPUAI_API_KEY,
)
from core.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------
SYSTEM_PROMPT = """你是一名资深的网络分析工程师，名叫「Wireshark 智能助手」。
你可以通过一组工具控制 Wireshark/Tshark 进行抓包与协议分析，并用自然语言向用户汇报结果。

你的核心职责：
1. 理解用户的网络分析意图（抓包、排查、统计、协议分析等）。
2. 规划并调用合适的工具完成操作。可多步调用：例如先 list_interfaces 确认网卡，再 capture_packets 抓包，然后 analyze_pcap 或 get_tshark_stats 分析。
3. 将工具返回的结构化数据（JSON / 文本）翻译成清晰、人类易读的网络诊断报告。

【最重要】行动优先原则：
- 当用户的请求需要获取数据（网卡列表、抓包、分析、统计等）时，你**必须实际调用对应工具**，而不是仅用文字说"我来帮你查看"。
- 禁止只说不做：不要回复"让我现在就帮你查看"之类的话却不发起工具调用。要么调用工具，要么向用户提一个澄清问题。
- 一次回复中可以只包含工具调用（不带任何解释文字），这是完全可以接受的。

工作准则：
- 抓包前：若用户未明确指定网卡，先用 list_interfaces 查看可用网卡，并向用户确认或自行选择最可能的一个（如 WLAN / 以太网）。注意 list_interfaces 返回的 name 字段才是要传给 capture_packets 的 interface 参数。
- 抓包参数：默认 duration 取 10 秒，除非用户指定。若用户要求特定协议，应设置相应的 bpf_filter（如 "tcp port 80"）或事后用 display_filter 过滤。
- 分析时：优先用 get_tshark_stats 的 "protocol_hierarchy" 了解整体概览，再针对具体问题用 analyze_pcap 配合 display_filter 聚焦。
- 报告要求：突出关键发现（异常状态码、重传、DNS 问题、可疑流量等），给出可能的成因与建议，而不是简单罗列原始数据。如果抓到的包很少，如实说明。
- 工具返回的错误信息要如实转达给用户，并给出排查建议。
- 所有回复使用中文。

你可以多次调用工具，直到收集到足够信息再给出最终结论。
"""


def _build_zhipu_llm():
    """构建智谱 GLM Chat 模型（关闭深度思考以加速）。"""
    if not ZHIPUAI_API_KEY:
        raise ValueError(
            "未配置智谱 API Key。请在 backend/.env 中设置 ZHIPUAI_API_KEY=你的key。"
        )
    try:
        from langchain_community.chat_models import ChatZhipuAI
    except ImportError as e:
        raise ImportError("无法导入 ChatZhipuAI，请安装 langchain-community 与 zhipuai。") from e

    import os as _os
    thinking_enabled = _os.getenv("LLM_THINKING", "disabled").lower() in (
        "enabled", "true", "1", "on"
    )
    thinking_param = {"type": "enabled"} if thinking_enabled else {"type": "disabled"}

    class _FastChatZhipuAI(ChatZhipuAI):
        @property
        def _default_params(self):
            params = super()._default_params
            params["thinking"] = thinking_param
            return params

    kwargs: dict[str, Any] = dict(
        model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=ZHIPUAI_API_KEY,
    )
    if LLM_MAX_TOKENS:
        kwargs["max_tokens"] = LLM_MAX_TOKENS
    llm = _FastChatZhipuAI(**kwargs)
    logger.info("LLM(zhipu) 构建完成: model=%s thinking=%s",
                LLM_MODEL, "enabled" if thinking_enabled else "disabled")
    return llm


def _build_openai_llm():
    """构建 OpenAI 兼容 Chat 模型。"""
    if not OPENAI_API_KEY:
        raise ValueError("未配置 OpenAI API Key。请设置 OPENAI_API_KEY。")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise ImportError("无法导入 ChatOpenAI，请安装 langchain-openai。") from e
    kwargs: dict[str, Any] = dict(
        model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=OPENAI_API_KEY,
    )
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    if LLM_MAX_TOKENS:
        kwargs["max_tokens"] = LLM_MAX_TOKENS
    llm = ChatOpenAI(**kwargs)
    logger.info("LLM(openai) 构建完成: model=%s base=%s", LLM_MODEL, OPENAI_BASE_URL or "default")
    return llm


def _build_ollama_llm():
    """构建本地 Ollama Chat 模型。"""
    try:
        from langchain_community.chat_models import ChatOllama
    except ImportError as e:
        raise ImportError("无法导入 ChatOllama，请安装 langchain-community。") from e
    llm = ChatOllama(
        model=LLM_MODEL, temperature=LLM_TEMPERATURE, base_url=OLLAMA_BASE_URL,
    )
    logger.info("LLM(ollama) 构建完成: model=%s base=%s", LLM_MODEL, OLLAMA_BASE_URL)
    return llm


def _build_llm():
    """根据 LLM_PROVIDER 构建对应提供商的 Chat 模型。"""
    provider = (LLM_PROVIDER or "zhipu").lower()
    if provider == "openai":
        return _build_openai_llm()
    if provider == "ollama":
        return _build_ollama_llm()
    return _build_zhipu_llm()


def build_agent():
    """构建并返回一个 LangGraph ReAct Agent（可调用对象）。

    返回的 agent 通过 .invoke({"messages": [...]}) 调用，
    返回 {"messages": [...]}，其中最后一条 AIMessage 为最终回答。
    """
    llm = _build_llm()
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,
    )
    logger.info("Agent 构建完成，使用模型 %s", LLM_MODEL)
    return agent


def _messages_to_lc(history: list) -> list:
    """把简化的对话历史 [{role, content}, ...] 转为 LangChain 消息对象。"""
    msgs = []
    for m in history:
        if isinstance(m, (HumanMessage, AIMessage)):
            msgs.append(m)
            continue
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    return msgs


def extract_final_answer(result: dict) -> str:
    """从 agent.invoke 的返回结果中提取最终回答文本。

    取最后一条 AIMessage 的内容。若为空（GLM 工具调用后有时不输出总结），
    则返回空字符串，由调用方（run_query）决定是否触发兜底总结。
    """
    final_msgs = result.get("messages", [])
    for msg in reversed(final_msgs):
        if isinstance(msg, AIMessage):
            return msg.content or ""
    return ""


def _summarize_if_empty(result: dict, llm) -> str:
    """若 Agent 最终回答为空，用 LLM 对工具返回结果做一次总结兜底。

    GLM-4.7 在 ReAct 工具调用后，最终 AIMessage 的 content 经常为空。
    此函数收集所有 ToolMessage 内容，让 LLM 基于工具结果生成人类易读的总结。
    """
    answer = extract_final_answer(result)
    if answer.strip():
        return answer

    from langchain_core.messages import ToolMessage
    tool_outputs = []
    for msg in result.get("messages", []):
        if isinstance(msg, ToolMessage) and msg.content:
            tool_outputs.append(msg.content)
    if not tool_outputs:
        return "（Agent 未返回有效回答，请重试或调整问题。）"

    material = "\n\n".join(tool_outputs)[-4000:]  # 截断防止超长
    summary_prompt = (
        "以下是网络分析工具返回的原始数据。请基于这些数据，用中文给用户一份"
        "简洁、人类易读的分析报告，突出关键发现并给出建议：\n\n" + material
    )
    try:
        resp = llm.invoke([HumanMessage(content=summary_prompt)])
        return resp.content or "（工具已执行，但未能生成总结，以下是原始数据）\n\n" + material
    except Exception:
        return "（工具已执行，以下是原始结果）\n\n" + material


def run_query(query: str, chat_history: list | None = None) -> str:
    """便捷函数：单次运行 Agent 查询并返回最终回答文本。

    :param query: 用户的自然语言指令
    :param chat_history: 可选的对话历史（[{role, content}] 或 LangChain message 列表）
    :return: Agent 的最终回答文本
    """
    agent = build_agent()
    messages = _messages_to_lc(chat_history or [])
    messages.append(HumanMessage(content=query))

    result = agent.invoke({"messages": messages})
    # GLM 工具调用后最终回答可能为空，用兜底总结
    return _summarize_if_empty(result, _build_llm())
