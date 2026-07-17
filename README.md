# 🦈 Wireshark 智能分析助手（Web 版）

> 一个「Web 版智能 Wireshark」：在浏览器中复刻 Wireshark 的核心体验
> （数据包列表 + 协议树详情），并融合 **智谱 GLM** 的语义能力——
> 用自然语言过滤流量、让 AI 总结选中的数据包。

例如，在右侧 AI 控制台输入：

> 「过滤出所有 HTTP 错误的包」

AI 会生成 Wireshark 过滤表达式 `http.response.code >= 400` 并**自动应用到左侧列表**。

---

## ✨ 功能特性

- **Wireshark 风格三屏界面**：数据包列表表格 + 可折叠协议树 + AI 控制台，**各窗口可拖拽调整大小**。
- **语义过滤**：自然语言 → Wireshark 显示过滤表达式，一键应用。
- **AI 总结**：勾选若干数据包，LLM 在**独立美观面板**中生成 Markdown 诊断报告，可**导出为 HTML**。
- **Hex 视图**：仿 Wireshark 的 Hex 面板（offset / hex / ascii）。
- **统计图表**：协议分布水平条形图。
- **实时抓包**：网卡选择带**实时流量图**，抓包**异步执行 + 进度条**。
- **分页缓存**：文件+过滤器结果缓存，翻页不重复扫描。
- **文件管理**：上传 pcap / 打开历史抓包文件。
- **多 LLM 提供商**：智谱 GLM / OpenAI / Ollama 可切换。
- **单进程部署**：前端构建后由后端托管，只需启动后端。
- **深色现代 UI**：Tokyo Night 配色，协议着色仿 Wireshark。

---

## 🏗️ 架构概览（前后端分离）

```
┌────────────────────────────────────────────────────┐
│  前端 React + Vite (localhost:5173)                 │
│  ├─ PacketTable    数据包列表（分页/过滤/多选）      │
│  ├─ PacketDetail   协议树 TreeView + 原始详情        │
│  └─ ChatPanel      AI 控制台（语义过滤/总结）        │
└──────────────────┬─────────────────────────────────┘
                   │ HTTP /api/*
                   ▼
┌────────────────────────────────────────────────────┐
│  后端 FastAPI (127.0.0.1:8000)                      │
│  ├─ api/packets.py   列表/详情/计数/统计             │
│  ├─ api/chat.py      语义过滤 + AI 总结              │
│  └─ api/capture.py   网卡/抓包/文件管理              │
│                                                     │
│  core/                                               │
│  ├─ packet_service.py   分页列表 + 协议树构建        │
│  ├─ llm_service.py      NL→过滤表达式 + 包总结       │
│  ├─ pyshark_analyzer.py PyShark/Tshark 底层封装      │
│  └─ agent.py            LangGraph Agent（保留）      │
└──────────────────┬─────────────────────────────────┘
                   │ 调用 tshark.exe
                   ▼
┌────────────────────────────────────────────────────┐
│  PyShark + Tshark (Wireshark 4.6.4)                 │
└────────────────────────────────────────────────────┘
```

**架构解耦说明**：本项目不修改 Wireshark C++ 源码，而是作为独立应用，
通过调用系统已安装的 `tshark.exe` 来工作。

---

## 📁 目录结构

```
wireshark-agent/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 应用入口（uvicorn main:app）
│   ├── api/
│   │   ├── packets.py          # 数据包列表/详情/统计
│   │   ├── chat.py             # AI 语义过滤/总结
│   │   └── capture.py          # 网卡/抓包/文件
│   ├── core/
│   │   ├── packet_service.py   # 分页 + 协议树构建
│   │   ├── llm_service.py      # NL→过滤器 + 总结
│   │   ├── pyshark_analyzer.py # PyShark 封装
│   │   ├── agent.py / tools.py # LangGraph Agent（保留）
│   ├── config/settings.py      # 配置中心
│   ├── data/captures/          # pcap 存储
│   ├── requirements.txt
│   └── .env                    # 真实配置（API Key）
│
├── frontend/                   # React + Vite 前端
│   ├── src/
│   │   ├── App.jsx             # 整体布局与状态
│   │   ├── api.js              # API 客户端
│   │   ├── components/
│   │   │   ├── Toolbar.jsx     # 工具栏（文件/抓包/过滤器）
│   │   │   ├── PacketTable.jsx # 数据包表格
│   │   │   ├── PacketDetail.jsx# 协议树
│   │   │   └── ChatPanel.jsx   # AI 控制台
│   │   └── styles/app.css      # 深色主题
│   └── vite.config.js          # 含 /api 代理到 8000
│
├── wireshark_llm_agent/        # 旧版 Streamlit 应用（保留参考）
├── pyshark-master/             # pyshark 源码（editable 安装，不可删）
└── run.bat                     # 一键启动（后端+前端+浏览器）
```

---

## 🚀 快速开始

### 前置要求

- **Python 3.10+**
- **Node.js 18+**（前端需要）
- **Wireshark / Tshark** 已安装（默认探测 `E:\Wireshark\tshark.exe`）
- 智谱 GLM API Key

### 一键启动（推荐）

双击 `run.bat`：自动安装依赖 → 启动后端（8000）→ 启动前端（5173）→ 打开浏览器。

> ⚠️ 抓包需要**管理员权限**：请右键 `run.bat` →「以管理员身份运行」。

### 手动启动

```bash
# 终端 1：后端
cd backend
pip install -r requirements.txt
pip install -e ../pyshark-master/src   # 首次
python main.py                         # http://127.0.0.1:8000

# 终端 2：前端
cd frontend
npm install                            # 首次
npm run dev                            # http://localhost:5173
```

### 配置

`backend/.env`：

```env
TSHARK_PATH=E:\Wireshark\tshark.exe

# LLM 提供商：zhipu（默认）| openai | ollama
LLM_PROVIDER=zhipu

# 智谱
ZHIPUAI_API_KEY=你的智谱APIKey
LLM_MODEL=glm-4.7

# OpenAI（provider=openai 时）
# OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=            # 可选，自定义网关
# LLM_MODEL=gpt-4o-mini

# Ollama（provider=ollama 时）
# OLLAMA_BASE_URL=http://localhost:11434
# LLM_MODEL=qwen2.5
```

### 单进程部署（可选）

前端构建后由后端托管，无需单独启动前端：

```bash
cd frontend && npm run build   # 生成 frontend/dist
cd ../backend && python main.py
# 浏览器访问 http://127.0.0.1:8000 （前端 + API 同端口）
```

---

## 🎯 使用方式

1. **打开数据**：顶部工具栏 →「抓包」实时抓取，或「上传 pcap」/「文件」打开历史文件。
2. **浏览数据包**：表格支持分页；点击行查看下方协议树；勾选复选框可多选。
3. **语义过滤**：在右侧 AI 控制台输入「过滤出 TCP 重传的包」，AI 自动生成过滤表达式并应用。
4. **AI 总结**：勾选若干包 → 点「✨ AI 总结选中包」→ 获得中文诊断报告。
5. **手动过滤**：顶部过滤框直接输入 Wireshark 显示过滤语法，回车应用。

---

## 🔌 API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 + 配置摘要 |
| GET | `/api/packets/list` | 分页数据包列表（带缓存） |
| GET | `/api/packets/count` | 精确计数 |
| GET | `/api/packets/detail` | 单包协议树 + Hex |
| GET | `/api/packets/stats` | tshark -z 统计 |
| GET | `/api/packets/distribution` | 协议分布（图表） |
| POST | `/api/chat/message` | 语义过滤 / 对话 |
| POST | `/api/chat/summarize` | 选中包 AI 总结 |
| POST | `/api/chat/report` | 导出 HTML 报告 |
| GET | `/api/capture/interfaces` | 网卡列表（含实时流量） |
| GET | `/api/capture/traffic` | 各网卡实时速率 |
| POST | `/api/capture/start` | 启动异步抓包（返回 task_id） |
| GET | `/api/capture/status/{id}` | 查询抓包进度 |
| GET | `/api/files/list` | 历史文件列表 |
| POST | `/api/files/upload` | 上传 pcap |

交互式 API 文档：启动后端后访问 `http://127.0.0.1:8000/docs`。

---

## ⚠️ 注意事项

- **抓包需管理员权限**，否则无法访问网卡。
- GLM-4.7 默认已关闭「深度思考」以加速响应（`LLM_THINKING=enabled` 可开启）。
- 超大 pcap 建议先用显示过滤器聚焦再分页浏览。
- API Key 请勿提交到版本库；如已泄露请到智谱平台重置。
- 仅限本地单用户使用，无认证机制。

---

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + Vite 5 + Vanilla CSS（Tokyo Night 深色主题） |
| 后端 | FastAPI + Uvicorn |
| 抓包/解析 | PyShark（本地源码）+ Tshark 4.6.4 |
| LLM | 智谱 GLM-4.7（langchain-community ChatZhipuAI） |
| Agent | LangChain 1.x + LangGraph（保留用于扩展） |
