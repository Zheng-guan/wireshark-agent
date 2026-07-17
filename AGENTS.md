# AGENTS.md

> 本文件为 AI 代理（如 ZCode / Claude Code 等）提供本项目的上下文与操作指引。
> 代理在开始工作前应通读本文件。

## 项目简介

**Web 版智能 Wireshark**：在浏览器中复刻 Wireshark 核心体验（数据包列表 + 协议树），
并融合智谱 GLM 的语义能力（自然语言过滤、AI 总结数据包）。

技术栈：**React + Vite（前端）** + **FastAPI（后端）** + PyShark/Tshark（解析） + 智谱 GLM-4.7（LLM）。

> 历史沿革：项目最初是 Streamlit + LangGraph Agent 的聊天工具（见 `wireshark_llm_agent/`，已保留作参考），
> 2026-07-17 按 `implementation_plan.md` 升级为前后端分离架构。

## 关键架构决策（务必遵守）

1. **不修改 Wireshark C++ 源码**。本项目通过调用系统已安装的 `tshark.exe` 工作。
   `pyshark-master/` 是 pyshark 源码（editable 安装），**不可删除**。

2. **前后端分离**：
   - 前端 `frontend/`（React+Vite，端口 5173），通过 Vite proxy 把 `/api/*` 转发到后端。
   - 后端 `backend/`（FastAPI，端口 8000），入口 `backend/main.py`。
   - 前端不直接碰 pyshark，一切解析通过 HTTP API。

3. **LangChain 版本是 1.x 新版**，已移除 `AgentExecutor`。Agent 用 `langgraph.prebuilt.create_react_agent` 构建
   （保留在 `backend/core/agent.py`，当前 Web 版主要走 `llm_service.py` 的轻量直接调用）。

4. **智谱 GLM-4.7 的两个坑**（已修复，改动时勿破坏）：
   - 默认开启「深度思考」导致响应极慢。通过子类 `_FastChatZhipuAI` 重写 `_default_params`
     注入 `thinking={"type":"disabled"}` 关闭。可用环境变量 `LLM_THINKING=enabled` 重新开启。
   - 工具调用后最终 AIMessage 的 content 经常为空，用 `_summarize_if_empty()` 兜底。

5. **pyshark 需要 asyncio 事件循环**。所有调用 pyshark 的函数开头必须调用 `_ensure_event_loop()`；
   关闭 capture 必须用 `_safe_close()`（吞掉 Windows 下 "I/O operation on closed pipe" 清理异常）。

6. **`.env` 配置加载**：`backend/config/settings.py` 同时加载项目根目录和 `backend/` 的 `.env`，
   后者优先（`override=True`）。当前真实 `.env` 在 `backend/.env`。

## 目录结构与职责

```
backend/                        # FastAPI 后端
├── main.py                     # 应用入口（CORS、路由、/api/health、前端静态托管）
├── api/
│   ├── packets.py              # /api/packets/* 列表/计数/详情/统计/协议分布
│   ├── chat.py                 # /api/chat/* 语义过滤/AI 总结/报告导出
│   └── capture.py              # /api/capture/* 网卡(含流量)/异步抓包 + /api/files/*
├── core/
│   ├── packet_service.py       # 分页列表(带缓存) + 协议树 + Hex 转储
│   ├── llm_service.py          # NL→过滤表达式 + 选中包总结 + 对话
│   ├── nic_monitor.py          # 网卡实时流量（psutil）
│   ├── capture_service.py      # 异步抓包任务 + 进度跟踪
│   ├── report_service.py       # HTML 报告导出
│   ├── pyshark_analyzer.py     # PyShark/Tshark 底层封装
│   ├── agent.py / tools.py     # LangGraph Agent + 多 LLM 提供商构建
├── config/settings.py          # 配置中心：Tshark/LLM 提供商/API Key
├── data/captures/              # pcap 存储（.gitignore 排除）
├── tests/test_services.py      # 单元测试
├── requirements.txt
└── .env                        # 真实配置（含 API Key，.gitignore 排除）

frontend/                       # React + Vite 前端
├── src/App.jsx                 # 整体布局 + 可拖拽状态 + 总结/统计面板
├── src/api.js                  # API 客户端封装
├── src/components/
│   ├── Toolbar.jsx             # 工具栏：文件/上传/抓包(流量图+进度)/过滤器/统计
│   ├── PacketTable.jsx         # 数据包表格（分页/选中/多选/协议着色）
│   ├── PacketDetail.jsx        # 协议树 + Hex + 原始详情 Tab
│   ├── ChatPanel.jsx           # AI 控制台（语义过滤/对话）
│   ├── SummaryPanel.jsx        # AI 总结独立面板（Markdown + 导出）
│   ├── StatsModal.jsx          # 协议分布图表弹窗
│   └── Splitter.jsx            # 可拖拽分隔条
└── src/styles/app.css          # Tokyo Night 深色主题
```

## 环境信息

- **Python**: 3.11.0（需 3.10+）
- **Node.js**: v22.19.0（需 18+）
- **Tshark**: `E:\Wireshark\tshark.exe`（v4.6.4），通过 `.env` 的 `TSHARK_PATH` 指定
- **模型**: `glm-4.7`，API Key 在 `backend/.env` 的 `ZHIPUAI_API_KEY`
- **工作目录**: `E:\计算机实践\wireshark-agent`

## 常用命令

```bash
# 一键启动（推荐，双击 run.bat；抓包需右键管理员运行）
run.bat

# 手动启动后端
cd backend && python main.py          # http://127.0.0.1:8000 （/docs 有交互式 API 文档）

# 手动启动前端
cd frontend && npm run dev            # http://localhost:5173
```

## 开发注意事项

- `run.bat` 必须是**纯 ASCII 英文**（非 GBK/UTF-8），否则 CMD 双击运行会中文乱码。
- 后端路径常量：`backend/config/settings.py` 中 `PROJECT_ROOT=parents[2]`、`PACKAGE_DIR=parents[1]`。
- 新增后端路由：在 `backend/api/` 建文件并在 `main.py` 注册。
- 新增依赖：后端加到 `backend/requirements.txt`，前端加到 `frontend/package.json`。
- 前端改端口或后端改端口，需同步 `frontend/vite.config.js` 的 proxy 与 `backend/main.py` 的 CORS。
- 抓包需**管理员权限**，否则可能无法访问网卡。
- API Key 已在对话中暴露过，建议提醒用户到智谱平台重置。

## 已知限制

- 分页读取是「顺序扫描跳过 offset」，超大 pcap 翻页会有重复扫描开销（教学/中小规模可接受）。
- GLM-4.7 工具调用稳定性一般；Web 版改用「直接 Prompt + JSON 解析」做语义过滤，更可控。
- 无认证机制，仅适合本地单用户使用。
