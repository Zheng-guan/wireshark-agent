"""启动检查与 CLI 入口脚本。

用法：
    python main.py            # 运行环境自检
    python main.py --cli      # 进入命令行交互模式
    python main.py --ui       # 提示如何启动 Streamlit UI

本脚本会：
1. 检查 Python 版本
2. 检查依赖是否已安装（pyshark / langchain / streamlit）
3. 检查 tshark 是否可调用
4. 检查智谱 API Key 是否配置
5. 尝试调用 list_interfaces 验证抓包能力
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ok(msg: str) -> None:
    print(f"  [✅] {msg}")


def _warn(msg: str) -> None:
    print(f"  [⚠️] {msg}")


def _fail(msg: str) -> None:
    print(f"  [❌] {msg}")


def check_environment() -> bool:
    """运行环境自检，返回是否全部通过。"""
    print("=" * 60)
    print("Wireshark 智能助手 - 环境自检")
    print("=" * 60)
    all_good = True

    # 1. Python 版本
    print("\n[1/5] Python 版本")
    if sys.version_info >= (3, 10):
        _ok(f"Python {sys.version.split()[0]}")
    else:
        _fail(f"需要 Python 3.10+，当前为 {sys.version.split()[0]}")
        all_good = False

    # 2. 依赖检查
    print("\n[2/5] Python 依赖")
    required = {
        "pyshark": "pyshark",
        "langchain": "langchain",
        "langchain_community": "langchain-community",
        "streamlit": "streamlit",
        "zhipuai": "zhipuai",
    }
    for module, package in required.items():
        try:
            __import__(module)
            _ok(f"{package}")
        except ImportError:
            _fail(f"{package} 未安装（pip install {package}）")
            all_good = False

    # 3. tshark
    print("\n[3/5] Tshark / Wireshark")
    try:
        from config.settings import TSHARK_PATH
        from core.pyshark_analyzer import get_tshark_version

        if TSHARK_PATH and Path(TSHARK_PATH).is_file():
            _ok(f"tshark 路径: {TSHARK_PATH}")
            _ok(f"版本: {get_tshark_version()}")
        else:
            _warn(f"tshark 路径未配置或不存在: {TSHARK_PATH or '(空)'}")
            _warn("请在 .env 中设置 TSHARK_PATH，或确保 Wireshark 在 PATH 中")
            all_good = False
    except Exception as e:
        _fail(f"tshark 检查异常: {e}")
        all_good = False

    # 4. 智谱 API Key
    print("\n[4/5] 智谱 GLM API Key")
    try:
        from config.settings import ZHIPUAI_API_KEY, LLM_MODEL
        if ZHIPUAI_API_KEY:
            _ok(f"已配置（模型: {LLM_MODEL}）")
        else:
            _warn("未配置 ZHIPUAI_API_KEY，AI 分析功能不可用")
            _warn("请在 .env 中设置: ZHIPUAI_API_KEY=你的key")
            all_good = False
    except Exception as e:
        _fail(f"配置加载异常: {e}")
        all_good = False

    # 5. 网卡列表（抓包能力验证）
    print("\n[5/5] 网卡抓包能力")
    try:
        from core.pyshark_analyzer import list_interfaces
        interfaces = list_interfaces()
        if interfaces:
            _ok(f"检测到 {len(interfaces)} 个网卡：")
            for it in interfaces[:8]:
                print(f"        {it['display']}")
            if len(interfaces) > 8:
                print(f"        ... 共 {len(interfaces)} 个")
        else:
            _warn("未检测到网卡（可能需要管理员权限）")
    except Exception as e:
        _fail(f"网卡列表获取失败: {e}")
        all_good = False

    print("\n" + "=" * 60)
    if all_good:
        print("🎉 环境检查全部通过！可以启动 UI 或进入 CLI 模式。")
    else:
        print("⚠️ 部分检查未通过，请按上述提示修复后重试。")
    print("=" * 60)
    return all_good


def cli_mode() -> None:
    """命令行交互模式。"""
    print("\n进入 CLI 模式（输入 exit 退出，clear 清空历史）\n")
    from core.agent import build_agent, _messages_to_lc
    from langchain_core.messages import AIMessage, HumanMessage

    agent = build_agent()
    history: list = []  # 存放 LangChain message 对象

    while True:
        try:
            user_input = input("🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出"):
            print("再见！")
            break
        if user_input.lower() == "clear":
            history.clear()
            print("（已清空对话历史）\n")
            continue

        try:
            messages = list(history) + [HumanMessage(content=user_input)]
            result = agent.invoke({"messages": messages})
            from core.agent import _summarize_if_empty, _build_llm
            answer = _summarize_if_empty(result, _build_llm())
            print(f"\n🤖 助手: {answer}\n")
            history.append(HumanMessage(content=user_input))
            history.append(AIMessage(content=answer))
        except Exception as e:
            print(f"\n❌ 出错: {e}\n")


def main() -> None:
    args = sys.argv[1:]
    if "--cli" in args:
        if not check_environment():
            print("\n环境检查未通过，但仍尝试进入 CLI（部分功能可能不可用）。\n")
        cli_mode()
    elif "--ui" in args:
        print("启动 Streamlit UI，请运行：")
        print("  streamlit run wireshark_llm_agent/ui/app.py")
        print("或直接双击 run.bat")
    else:
        check_environment()
        print("\n提示：")
        print("  - 启动 Web 界面: 双击 run.bat 或运行 streamlit run wireshark_llm_agent/ui/app.py")
        print("  - 命令行模式:   python main.py --cli")


if __name__ == "__main__":
    main()
