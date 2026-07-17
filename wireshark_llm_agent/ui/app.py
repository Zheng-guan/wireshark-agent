"""Streamlit Web 聊天界面。

启动方式：
    streamlit run ui/app.py

功能：
- 侧边栏展示环境配置（tshark 路径、模型、API Key 状态）
- 主区域为聊天对话，用户输入自然语言指令，Agent 调用工具完成抓包/分析
- 显示 Agent 的流式/分步输出与最终诊断报告
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# 确保能导入项目包（streamlit run 的工作目录可能是任意位置）
# app.py 位于 wireshark_llm_agent/ui/，其 parents[1] 即 wireshark_llm_agent/（含 config、core）
PACKAGE_DIR = Path(__file__).resolve().parents[1]
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from config.settings import get_settings_summary  # noqa: E402
from core.tools import ALL_TOOLS  # noqa: E402


# ---------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Wireshark 智能助手",
    page_icon="🦈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------
# 侧边栏：环境配置展示
# ---------------------------------------------------------------------
with st.sidebar:
    st.title("🦈 Wireshark 智能助手")
    st.caption("语义化网络分析 · PyShark + LangChain + GLM")

    st.divider()
    st.subheader("⚙️ 环境配置")
    settings = get_settings_summary()

    status_icon = "✅" if settings["tshark_found"] else "⚠️"
    st.write(f"{status_icon} **Tshark 路径**")
    st.code(settings["tshark_path"], language="text")

    key_icon = "✅" if settings["llm_api_key_configured"] else "⚠️"
    st.write(f"{key_icon} **智谱 API Key**: "
             f"{'已配置' if settings['llm_api_key_configured'] else '未配置'}")
    st.write(f"🤖 **模型**: `{settings['llm_model']}`")
    st.write(f"📁 **抓包目录**: `{settings['captures_dir']}`")

    st.divider()
    if not settings["tshark_found"]:
        st.warning(
            "未检测到 tshark。请在项目根目录的 `.env` 中设置：\n\n"
            "`TSHARK_PATH=E:/Wireshark/tshark.exe`"
        )
    if not settings["llm_api_key_configured"]:
        st.warning(
            "未配置智谱 API Key。请在 `.env` 中设置：\n\n"
            "`ZHIPUAI_API_KEY=你的key`"
        )

    st.divider()
    st.subheader("🛠️ 可用工具")
    for t in ALL_TOOLS:
        st.write(f"• `{t.name}`")
        st.caption(t.description)

    st.divider()
    st.subheader("💡 使用示例")
    st.caption(
        "• 列出所有网卡\n"
        "• 用 WLAN 网卡抓包 15 秒，分析有没有 HTTP 错误\n"
        "• 抓取以太网流量 10 秒并统计协议分布\n"
        "• 分析最近的抓包，找出所有 TCP 重传"
    )


# ---------------------------------------------------------------------
# 主区域：聊天
# ---------------------------------------------------------------------
st.header("💬 网络分析对话")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "你好！我是 Wireshark 智能助手。你可以用自然语言让我抓包、"
                "分析流量或排查网络问题。例如：「用 WLAN 抓包 10 秒，"
                "告诉我有没有 HTTP 错误」。"
            ),
        }
    ]

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 用户输入
if user_input := st.chat_input("输入你的网络分析需求..."):
    # 显示用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 检查前置条件
    preflight = get_settings_summary()
    if not preflight["llm_api_key_configured"]:
        reply = ("⚠️ 尚未配置智谱 API Key，无法启动 AI 分析。"
                 "请在项目根目录的 `.env` 文件中设置 `ZHIPUAI_API_KEY` 后重启。")
    elif not preflight["tshark_found"]:
        reply = ("⚠️ 未检测到 tshark，无法抓包/分析。"
                 "请在 `.env` 中设置 `TSHARK_PATH` 指向 tshark.exe 后重启。")
    else:
        # 构建 Agent 并运行
        with st.chat_message("assistant"):
            with st.spinner("正在思考并调用工具，可能需要抓包，请稍候..."):
                try:
                    from core.agent import build_agent
                    from langchain_core.messages import AIMessage, HumanMessage

                    agent = build_agent()
                    # 将历史对话转为 LangChain 消息格式
                    messages = []
                    for m in st.session_state.messages[:-1]:  # 排除刚加入的 user 消息
                        if m["role"] == "user":
                            messages.append(HumanMessage(content=m["content"]))
                        elif m["role"] == "assistant":
                            messages.append(AIMessage(content=m["content"]))
                    messages.append(HumanMessage(content=user_input))

                    result = agent.invoke({"messages": messages})
                    from core.agent import _summarize_if_empty, _build_llm
                    reply = _summarize_if_empty(result, _build_llm())
                except Exception as e:
                    reply = f"❌ 运行出错：{e}"
            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
