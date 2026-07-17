# Web 版智能 Wireshark 实现方案

根据您的反馈，您希望不仅有一个聊天机器人，而是希望在网页上**复刻 Wireshark 的核心功能（如数据包列表、协议树详细信息）**，并在此基础上融合 LLM 的语义指令，实现对数据包的智能过滤和总结分析。

由于 Streamlit 主要适用于简单的数据展示和对话，无法很好地支撑复杂的三屏互动（列表、协议树、Hex视窗），我们需要对架构进行升级，采用前后端分离的模式来实现一个真正的“Web 版智能 Wireshark”。

## 架构选型升级

### 1. 后端：FastAPI + PyShark
- **FastAPI**：作为高性能的异步 Python Web 框架，提供 API 接口给前端。
- **职责**：
  - 加载和解析 `.pcap` 文件。
  - 分页返回数据包列表（Packet List）。
  - 返回单个数据包的协议树结构（Packet Details）。
  - 提供 LLM 对话接口，接收前端的语义指令。
- **PyShark**：继续作为底层解析引擎，调用系统上的 `tshark`。

### 2. 前端：React + Vite (Web SPA)
- **技术栈**：使用 React 构建单页应用（SPA），使用 Vite 作为构建工具，辅以 Vanilla CSS 构建极具现代感、深色模式的 UI（符合高端、生动的设计美学）。
- **界面布局**：
  - **左/上侧（抓包视图）**：经典的 Wireshark 布局。
    - 顶部：数据包列表表格（类似 Wireshark 的主窗口）。
    - 底部：选中数据包的详细协议树（Tree View）。
  - **右侧（AI 控制台）**：LLM 聊天窗口。
    - 可以在这里输入：“过滤出所有 HTTP 500 的包” -> AI 解析意图后，告诉前端应用 Wireshark 过滤语法 `http.response.code == 500`，前端刷新列表。
    - 也可以输入：“总结一下这几个包在干什么” -> 前端将选中的包数据发给后端，后端请求 LLM 并返回人类可读的总结。

### 3. 大模型代理层：LangChain
- 继续保留 `wireshark_llm_agent/core` 中的 LangChain 逻辑，将其接入 FastAPI。
- Agent 将具备控制前端视图的能力（例如输出特殊的 JSON 指令让前端执行过滤）。

## 目录结构设计 (更新)

```text
wireshark-agent/
│
├── backend/                    # Python FastAPI 后端
│   ├── main.py                 # FastAPI 入口
│   ├── api/                    # 路由定义 (packets, chat)
│   ├── core/                   # 之前的 agent 逻辑与 pyshark 解析
│   ├── data/                   # 存放 pcap 文件
│   └── requirements.txt        # 增加 fastapi, uvicorn 等依赖
│
├── frontend/                   # React 前端
│   ├── package.json
│   ├── index.html
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx           # 整体布局
│   │   ├── components/       # 数据包列表、协议树、AI 聊天框等组件
│   │   └── styles/           # 高级现代 CSS 样式
│   └── vite.config.js
│
└── README.md
```

## 交互流程示例

1. **常规查看**：前端向后端请求第一页数据包，后端用 `pyshark` 读取后转为 JSON 数组，前端用 Table 渲染。用户点击某一行，前端请求该包详细数据，渲染出协议树。
2. **语义过滤**：用户在聊天框输入“帮我找出三次握手失败的包”。
3. **LLM 处理**：后端 LangChain 识别到这是一个“过滤”意图，LLM 生成 Wireshark 过滤规则 `tcp.flags.syn==1 and tcp.flags.ack==0`，并通过结构化输出返回给前端。
4. **前端响应**：前端接收到过滤规则，自动将其填入过滤框，并向后端请求带有该过滤条件的新数据包列表。
5. **智能总结**：用户选中几个包，点击“AI总结”。前端将这些包的简要信息发给 LLM，LLM 分析对话过程并返回诊断报告。

## User Review Required

> [!IMPORTANT]
> **确认技术栈升级**
> 1. **前后端分离方案：** 这需要我们用 React 编写前端，用 FastAPI 编写后端。相比之前纯 Python 的 Streamlit，这能做到真正的“Web版Wireshark”体验，但也稍微复杂一些。您是否同意采用这套方案？
> 2. **原有代码迁移：** 我会将您原有的 `wireshark_llm_agent` 下的核心逻辑迁移到 `backend` 目录下，而废弃 `ui/app.py`。
> 3. **前端 Node.js 环境：** 开发这套前端需要您的系统安装了 Node.js（用于运行 npm/npx 命令）。如果您没有安装，我可以帮您打包好，或者我们可以退而求其次，用普通的 HTML+JS 直接写在后端的模板里，但界面美观度不如 Vite+React。请确认您是否有 Node 环境？

## Verification Plan

1. **搭建基础框架：** 初始化 FastAPI 后端和 React 前端。
2. **打通数据链路：** 在前端实现类似 Wireshark 的表格，成功通过后端 PyShark 展示 pcap 文件的内容。
3. **实现协议树：** 点击表格行，展示详细的协议层级解析。
4. **接入 LLM：** 在侧边栏实现聊天框，并通过 LLM 实现自然语言转化为 Wireshark 过滤表达式并应用到表格。
