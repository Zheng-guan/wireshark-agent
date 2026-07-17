"""配置管理模块。

集中管理以下配置项：
- Tshark / Wireshark 可执行文件路径
- 智谱 GLM API Key 与模型选择
- 抓包文件存储目录
- 日志级别等

配置优先级（从高到低）：
1. 环境变量 / .env 文件
2. 本模块中的默认值
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------
# 项目根目录：wireshark_llm_agent/ 的上一级（即 wireshark-agent/）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = Path(__file__).resolve().parents[1]

# .env 文件查找：项目根目录与包目录均可能存在。
# 先加载根目录 .env，再用包目录 .env 覆盖（override=True），
# 这样包目录里的配置优先级更高。
_ENV_FILES = [PROJECT_ROOT / ".env", PACKAGE_DIR / ".env"]
for _ef in _ENV_FILES:
    if _ef.exists():
        load_dotenv(_ef, override=True)
ENV_FILE = _ENV_FILES[-1] if _ENV_FILES[-1].exists() else _ENV_FILES[0]

# 抓包文件存储目录
CAPTURES_DIR = PACKAGE_DIR / "data" / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Tshark / Wireshark 路径
# ---------------------------------------------------------------------
def _detect_tshark_path() -> str:
    """自动探测 tshark.exe 路径。

    搜索顺序：
    1. 环境变量 TSHARK_PATH
    2. 常见安装路径（Program Files / 各盘符根目录）
    3. 系统 PATH
    """
    # 1. 环境变量
    env_path = os.getenv("TSHARK_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. 常见安装路径
    candidate_dirs: list[str] = []
    for env_var in ("ProgramFiles", "ProgramFiles(x86)"):
        program_files = os.getenv(env_var)
        if program_files:
            candidate_dirs.append(os.path.join(program_files, "Wireshark"))

    # 各盘符根目录下的 Wireshark（如 D:\Wireshark, E:\Wireshark）
    for drive in ("C:", "D:", "E:", "F:"):
        candidate_dirs.append(os.path.join(drive, os.sep, "Wireshark"))

    for dir_path in candidate_dirs:
        exe = os.path.join(dir_path, "tshark.exe")
        if os.path.isfile(exe):
            return exe

    # 3. 退化到让 pyshark 自己在 PATH 中查找（返回 None）
    return os.getenv("TSHARK_PATH", "")


TSHARK_PATH: str = _detect_tshark_path()


# ---------------------------------------------------------------------
# LLM 配置（支持智谱 GLM / OpenAI / Ollama）
# ---------------------------------------------------------------------
# LLM 提供商：zhipu（默认）| openai | ollama
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "zhipu").lower()

# 智谱 API Key，从环境变量 ZHIPUAI_API_KEY 读取
ZHIPUAI_API_KEY: str = os.getenv("ZHIPUAI_API_KEY", "")

# OpenAI 兼容配置（provider=openai 时使用；也可指向兼容网关）
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")  # 可选，自定义网关

# Ollama 配置（provider=ollama 时使用）
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# 默认使用的模型名称。智谱 GLM-4.7 对应 API 名称 glm-4.7，
# 用户可在环境变量 LLM_MODEL 中覆盖。
LLM_MODEL: str = os.getenv("LLM_MODEL", "glm-4.7")

# LLM 采样温度：网络分析需要严谨，使用较低温度
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# 最大输出 token 数
LLM_MAX_TOKENS: int | None = None
_max_tokens_env = os.getenv("LLM_MAX_TOKENS")
if _max_tokens_env:
    LLM_MAX_TOKENS = int(_max_tokens_env)


# ---------------------------------------------------------------------
# 抓包默认参数
# ---------------------------------------------------------------------
DEFAULT_CAPTURE_DURATION: int = int(os.getenv("DEFAULT_CAPTURE_DURATION", "10"))
DEFAULT_PACKET_LIMIT: int = int(os.getenv("DEFAULT_PACKET_LIMIT", "5000"))


# ---------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


def get_settings_summary() -> dict:
    """返回当前配置摘要（隐藏敏感字段），用于启动检查与 UI 展示。"""
    return {
        "tshark_path": TSHARK_PATH or "(未配置，将依赖 PATH)",
        "tshark_found": bool(TSHARK_PATH) and os.path.isfile(TSHARK_PATH),
        "llm_model": LLM_MODEL,
        "llm_api_key_configured": bool(ZHIPUAI_API_KEY),
        "captures_dir": str(CAPTURES_DIR),
        "default_capture_duration": DEFAULT_CAPTURE_DURATION,
        "log_level": LOG_LEVEL,
    }
