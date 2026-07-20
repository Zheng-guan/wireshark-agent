# 🦈 Wireshark 智能分析助手（Web 版）

> 一个「Web 版智能 Wireshark」：在浏览器中复刻 Wireshark 的核心体验
> （数据包列表 + 协议树详情 + 追踪流），并融合 **智谱 GLM** 的语义能力——
> 用自然语言过滤流量、AI 总结数据包、AI 解释协议字段、AI 诊断整个会话。

例如，在右侧 AI 控制台输入：

> 「过滤出所有 HTTP 错误的包」

AI 会生成 Wireshark 过滤表达式 `http.response.code >= 400` 并**自动应用到左侧列表**。

---

## ✨ 功能特性

### Wireshark 核心体验
- **三屏界面**：数据包列表 + 可折叠协议树 + AI 控制台，各窗口**可拖拽调整大小**。
- **追踪 TCP/UDP 流**：右键数据包 →「追踪流」，弹窗按**客户端(蓝)/服务端(红)分色**展示完整双向会话。
- **右键上下文菜单**：数据包/协议树字段右键 →「作为过滤器应用」（`and` 叠加，仿原生 Wireshark）。
- **键盘导航**：`↑`/`↓` 切换数据包并联动协议树/Hex，`/` 聚焦过滤器。
- **列宽拖拽**：表头拖拽调整列宽，双击重置，**localStorage 持久化**。
- **时间戳格式切换**：相对时间 / 绝对时间 / 间隔时间（Δ），工具栏下拉即时切换。
- **Hex 视图**：仿 Wireshark 的 Hex 面板（offset / hex / ascii）。
- **PCAP 下载**：原样下载，或**按当前过滤器导出**匹配子集。
- **导出对象**：提取 pcap 中 HTTP 传输的文件（`tshark --export-objects`），一键下载。

### 抓包
- **定时抓包**：设时长，抓完自动打开；网卡选择带**实时流量图**，异步执行 + 进度条。
- **🔴 实时瀑布流**：WebSocket 推送，数据包**直接在主表格实时刷出**（不弹窗），
  可随时停止、一键加载到主界面深入分析。采用单进程 `tshark -l` 行缓冲方案，
  带首次连接自动重试 + rAF 批量刷入防闪烁。

### AI 能力（智谱 GLM）
- **语义过滤**：自然语言 → Wireshark 显示过滤表达式，一键应用。
- **AI 总结**：勾选数据包，独立面板生成 Markdown 诊断报告，可**导出 HTML**。
- **AI 字段解释**：协议树每行 `(?)` 按钮/右键 → AI 解释该字段含义与当前值，
  Popover 气泡原位展示，**结果缓存**避免重复调用。
- **AI 会话诊断**：追踪流弹窗内一键分析整个 TCP/UDP 会话（是否成功/安全观察/结论建议）。

### 过滤器增强
- **自动补全**：输入时下拉提示常用字段（~60 个，含描述示例），`Tab` 补全。
- **实时语法校验**：tshark 后端校验，合法绿 `✓` / 非法红 `✕` + 错误提示，非法禁用应用按钮。
- **历史记录**：localStorage 存最近 20 条，聚焦空输入框自动弹出。

### 工程化
- **工作区持久化**：刷新后恢复打开的文件/过滤器/页码/布局/时间格式。
- **分页缓存**：文件+过滤器+时间格式结果缓存，翻页不重复扫描。
- **多 LLM 提供商**：智谱 GLM / OpenAI / Ollama 可切换。
- **单进程部署**：前端构建后由后端托管，只需启动后端。
- **深色现代 UI**：Tokyo Night 配色，协议着色仿 Wireshark。

---

## 🏗️ 架构概览（前后端分离）

```
┌────────────────────────────────────────────────────┐
│  前端 React + Vite (localhost:5173)                 │
│  ├─ PacketTable    数据包列表（右键/键盘/列宽/实时）  │
│  ├─ PacketDetail   协议树（右键过滤/AI 字段解释）     │
│  ├─ StreamModal    追踪流（分色 + AI 会话诊断）       │
│  └─ ChatPanel      AI 控制台（语义过滤/总结）         │
└──────────────────┬─────────────────────────────────┘
                   │ HTTP /api/*  +  WebSocket /api/live/*
                   ▼
┌────────────────────────────────────────────────────┐
│  后端 FastAPI (127.0.0.1:8000)                      │
│  ├─ api/packets.py   列表/详情/统计/追踪流/校验       │
│  ├─ api/chat.py      语义过滤/AI 总结/字段解释/流诊断 │
│  ├─ api/capture.py   网卡/抓包/文件/下载/导出对象     │
│  └─ api/live.py      WebSocket 实时抓包推送          │
│                                                     │
│  core/                                               │
│  ├─ packet_service.py       分页 + 协议树 + 时间格式  │
│  ├─ stream_service.py       追踪流 + 过滤导出 + 对象  │
│  ├─ live_capture_service.py 实时抓包（单进程 tshark） │
│  ├─ llm_service.py          NL→过滤/总结/解释/诊断    │
│  └─ pyshark_analyzer.py     PyShark/Tshark 底层封装   │
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
│   │   ├── packets.py          # 列表/详情/统计/追踪流(stream)/过滤器校验
│   │   ├── chat.py             # 语义过滤/AI 总结/字段解释/流诊断
│   │   ├── capture.py          # 网卡/抓包/文件/下载/导出对象
│   │   └── live.py             # WebSocket 实时抓包推送
│   ├── core/
│   │   ├── packet_service.py       # 分页 + 协议树 + 时间格式
│   │   ├── stream_service.py       # 追踪流 + 过滤导出 + 导出对象
│   │   ├── live_capture_service.py # 实时抓包（单进程 tshark -l）
│   │   ├── llm_service.py          # NL→过滤/总结/字段解释/流诊断
│   │   ├── pyshark_analyzer.py     # PyShark 封装
│   │   ├── agent.py / tools.py     # LangGraph Agent（保留）
│   ├── config/settings.py      # 配置中心
│   ├── data/captures/          # pcap 存储
│   ├── requirements.txt
│   └── .env                    # 真实配置（API Key）
│
├── frontend/                   # React + Vite 前端
│   ├── src/
│   │   ├── App.jsx             # 整体布局/状态/实时抓包控制
│   │   ├── api.js              # API 客户端
│   │   ├── filterFields.js     # 过滤器字段表（自动补全）
│   │   ├── components/
│   │   │   ├── Toolbar.jsx         # 工具栏（文件/抓包/过滤器补全校验）
│   │   │   ├── PacketTable.jsx     # 数据包表格（右键/键盘/列宽/实时）
│   │   │   ├── PacketDetail.jsx    # 协议树（右键过滤/AI 字段解释）
│   │   │   ├── ContextMenu.jsx     # 通用右键菜单（useContextMenu）
│   │   │   ├── StreamModal.jsx     # 追踪流弹窗（分色 + AI 诊断）
│   │   │   ├── ExportObjectsModal.jsx # 导出对象面板
│   │   │   ├── ChatPanel.jsx       # AI 控制台
│   │   │   ├── SummaryPanel.jsx    # AI 总结面板（Markdown + 导出）
│   │   │   ├── StatsModal.jsx      # 协议分布图表
│   │   │   └── Splitter.jsx        # 可拖拽分隔条
│   │   └── styles/app.css      # Tokyo Night 深色主题
│   └── vite.config.js          # /api 代理（含 WebSocket ws:true）
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

> ⚠️ 抓包（含实时抓包）需要**管理员权限**：请右键 `run.bat` →「以管理员身份运行」。

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

> 💡 实时抓包（WebSocket）在 `npm run dev` 模式下需确保 `vite.config.js`
> 的 proxy 配置了 `ws: true`（已默认配置）。

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

1. **打开数据**：工具栏「抓包」（定时 / 实时瀑布流两种模式）、「上传 pcap」或「文件」打开历史。
2. **浏览数据包**：`↑`/`↓` 键盘切换，或点击行查看协议树；右键行可过滤/追踪流。
3. **过滤流量**：
   - 顶部过滤框直接输 Wireshark 语法（带**自动补全 + 实时校验**），回车应用；
   - 右键数据包/协议树字段 →「作为过滤器应用」；
   - 右侧 AI 控制台输入自然语言，AI 自动生成并应用。
4. **追踪流**：右键数据包 →「追踪 TCP/UDP 流」→ 分色查看完整会话，可一键 AI 诊断。
5. **AI 字段解释**：协议树悬停点 `(?)` 或右键 → AI 解释该字段（结果缓存）。
6. **AI 总结**：勾选若干包 →「✨ AI 总结」→ Markdown 报告，可导出 HTML。
7. **下载/导出**：工具栏「⬇ 下载」导出 pcap（可带过滤器）；「📦 导出对象」提取 HTTP 文件。

---

## 🔌 API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 + 配置摘要 |
| GET | `/api/packets/list` | 分页数据包列表（带缓存，支持时间格式） |
| GET | `/api/packets/count` | 精确计数 |
| GET | `/api/packets/detail` | 单包协议树 + Hex |
| GET | `/api/packets/stats` | tshark -z 统计 |
| GET | `/api/packets/distribution` | 协议分布（图表） |
| GET | `/api/packets/stream/info` | 定位数据包所属 TCP/UDP 流 |
| GET | `/api/packets/stream` | 追踪流内容（分段 + 方向） |
| GET | `/api/packets/validate-filter` | 过滤器语法校验 |
| POST | `/api/chat/message` | 语义过滤 / 对话 |
| POST | `/api/chat/summarize` | 选中包 AI 总结 |
| POST | `/api/chat/explain-field` | AI 字段解释 |
| POST | `/api/chat/analyze-stream` | AI 会话诊断 |
| POST | `/api/chat/report` | 导出 HTML 报告 |
| GET | `/api/capture/interfaces` | 网卡列表（含实时流量） |
| GET | `/api/capture/traffic` | 各网卡实时速率 |
| POST | `/api/capture/start` | 启动定时抓包（返回 task_id） |
| GET | `/api/capture/status/{id}` | 查询抓包进度 |
| GET | `/api/files/list` | 历史文件列表 |
| POST | `/api/files/upload` | 上传 pcap |
| GET | `/api/files/download` | 下载 pcap（可带过滤器导出子集） |
| GET | `/api/files/export-objects` | 列出可提取的协议对象 |
| WS | `/api/live/capture` | 实时抓包推送（WebSocket） |

交互式 API 文档：启动后端后访问 `http://127.0.0.1:8000/docs`。

---

## ⚠️ 注意事项

- **抓包（含实时）需管理员权限**，否则无法访问网卡。实时抓包请选**有流量的网卡**。
- GLM-4.7 默认已关闭「深度思考」以加速响应（`LLM_THINKING=enabled` 可开启）。
- 超大 pcap 建议先用显示过滤器聚焦再分页浏览。
- API Key 请勿提交到版本库；如已泄露请到智谱平台重置。
- 仅限本地单用户使用，无认证机制。
- Windows 下抓包完成后 stderr 可能打印 `I/O operation on closed pipe`，
  为 CPython asyncio 已知清理噪音，不影响抓包数据（详见 HANDOFF.md）。

---

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + Vite 5 + Vanilla CSS（Tokyo Night 深色主题） |
| 后端 | FastAPI + Uvicorn（HTTP + WebSocket） |
| 抓包/解析 | PyShark（本地源码）+ Tshark 4.6.4 |
| LLM | 智谱 GLM-4.7（langchain-community ChatZhipuAI） |
| Agent | LangChain 1.x + LangGraph（保留用于扩展） |
