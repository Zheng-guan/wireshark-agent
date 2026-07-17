# HANDOFF.md

> 会话交接文档。记录项目当前状态、已完成工作、待办事项与关键决策，供下次会话或接手者快速上手。

## 项目状态：✅ 可用（Web 版 v2.1）

项目为前后端分离的「Web 版智能 Wireshark」。v2.1 在 v2.0 基础上新增：
分页缓存、Hex 视图、统计图表、网卡实时流量图、异步抓包进度、多 LLM 提供商、
HTML 报告导出、AI 总结独立面板、可拖拽布局、单进程部署、单元测试。
双击 `run.bat` 一键启动；或 `npm run build` 后只启动后端（单进程）。

**最后更新**: 2026-07-17

## v2.1 新增功能（本次升级）

### 后端
- [x] **分页缓存**：`packet_service._RowsCache` 按 (文件, 过滤器, mtime) 缓存全量行，翻页不再重复扫描（实测第2页 0.28s→0.01s）
- [x] **Hex 视图**：`get_packet_hex()` 调 `tshark -x`，解析为 {offset, hex, ascii} 行
- [x] **协议分布**：`GET /api/packets/distribution` 返回 JSON 供图表
- [x] **网卡实时流量**：`core/nic_monitor.py` 基于 psutil 采样速率，匹配 tshark 网卡
- [x] **异步抓包**：`core/capture_service.py` 后台线程抓包 + task_id 轮询进度
- [x] **多 LLM 提供商**：`agent.py` 拆分 `_build_zhipu/openai/ollama_llm`，按 `LLM_PROVIDER` 切换
- [x] **HTML 报告导出**：`core/report_service.py` 渲染自包含 HTML（Markdown + 数据包表格）
- [x] **单进程部署**：`main.py` 检测 `frontend/dist` 存在则托管 SPA + 静态资源

### 前端
- [x] **可拖拽布局**：`Splitter.jsx` 调整右栏宽度 + 表格/详情高度比例
- [x] **AI 总结独立面板**：`SummaryPanel.jsx` Markdown 渲染（react-markdown）+ 导出 HTML，不再混入聊天
- [x] **Hex 面板**：`PacketDetail.jsx` 新增 Hex Tab
- [x] **统计图表**：`StatsModal.jsx` 纯 CSS 水平条形图
- [x] **抓包面板**：`Toolbar.jsx` 网卡实时流量迷你图（SVG sparkline）+ 异步抓包进度条

### 测试与部署
- [x] **单元测试**：`backend/tests/test_services.py` 8 个测试全部通过（report/packet_service/capture/llm）
- [x] **生产构建**：`npm run build` 成功（280KB JS / 12KB CSS）
- [x] **单进程验证**：后端 8000 同时服务 SPA + API + 静态资源

## v2.0 完成工作（架构升级）

### 后端（backend/，FastAPI）
- [x] 迁移 `config/settings.py`、`core/pyshark_analyzer.py`、`core/agent.py`、`core/tools.py`
- [x] 新增 `core/packet_service.py`：分页数据包列表 + 协议树构建（`_all_fields` 递归）
- [x] 新增 `core/llm_service.py`：自然语言→Wireshark 过滤表达式（JSON 结构化输出）、选中包 AI 总结、通用对话
- [x] 新增 `api/packets.py`：`/api/packets/list|count|detail|stats`
- [x] 新增 `api/chat.py`：`/api/chat/message|summarize`
- [x] 新增 `api/capture.py`：`/api/capture/interfaces|start` + `/api/files/list|upload`
- [x] 新增 `main.py`：FastAPI 入口 + CORS + `/api/health`
- [x] `requirements.txt` 去掉 streamlit，加入 fastapi/uvicorn/python-multipart

### 前端（frontend/，React + Vite）
- [x] 初始化 Vite + React 18 项目，`vite.config.js` 配置 `/api` 代理到 8000
- [x] `api.js`：API 客户端封装
- [x] `App.jsx`：整体三屏布局 + 全局状态（文件/过滤器/分页/选中/多选）
- [x] `Toolbar.jsx`：文件列表/上传/抓包表单/过滤器输入
- [x] `PacketTable.jsx`：Wireshark 风格表格（No./Time/Src/Dst/Proto/Len/Info）+ 协议着色 + 分页 + 多选
- [x] `PacketDetail.jsx`：可折叠协议树 TreeView + 原始详情 Tab
- [x] `ChatPanel.jsx`：AI 控制台（语义过滤自动应用 / AI 总结选中包 / 对话）
- [x] `app.css`：Tokyo Night 深色现代主题

### 启动与文档
- [x] `run.bat` 重写：启动后端（新窗口）+ 前端（新窗口）+ 自动开浏览器（保持纯 ASCII）
- [x] `README.md` 重写为 Web 版
- [x] `AGENTS.md` 更新架构决策与目录

## 端到端验证结果（全部通过）

- ✅ 后端导入正常，8 条路由注册
- ✅ `/api/health`：tshark 4.6.4 识别、API Key 已配置
- ✅ `/api/capture/interfaces`：返回 10 个网卡
- ✅ `/api/packets/list`：分页返回 Wireshark 风格行（源/目的/协议/Info）
- ✅ `/api/packets/count`：精确计数（测试文件 39 包）
- ✅ `/api/packets/detail`：协议树递归正常（ETH/IP/TCP/TLS 分层）
- ✅ 显示过滤器：`dns` 过滤计数正常
- ✅ `/api/chat/message`：「过滤 DNS 查询」→ 自动生成 `dns.qry.type == 1 or dns.flags.response == 0`
- ✅ `/api/chat/summarize`：选中 3 包生成中文诊断报告（含异常检测）
- ✅ 前端 Vite 编译无报错，4 个组件均 HTTP 200，`/api` 代理打通

## 关键决策记录

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 架构 | FastAPI + React 前后端分离 | Streamlit 无法支撑三屏互动 |
| 前端 | React 18 + Vite 5 + Vanilla CSS | 计划指定；无 UI 库依赖，轻量可控 |
| UI 主题 | Tokyo Night 深色 | 现代感、协议着色仿 Wireshark |
| 语义过滤 | 直接 Prompt + JSON 结构化输出 | 比 Agent 工具调用更可控、更快 |
| 协议树 | 递归解析 layer._all_fields | 复用 pyshark 字段元数据 |
| 分页 | 顺序扫描跳过 offset | 实现简单，中小规模够用 |
| 旧代码 | 保留 `wireshark_llm_agent/` 作参考 | 不删除，便于回退 |

## 待办 / 可改进项

### 高优先级
- [ ] **API Key 安全**：当前 key 已在对话中暴露，建议提醒用户重置
- [ ] 抓包需管理员权限，`run.bat` 未做自动提权，需用户右键管理员运行

### 中优先级
- [ ] 抓包实时进度目前按时间估算，可改为解析 dumpcap 实际包数
- [ ] 网卡流量匹配是「名称模糊匹配」，个别虚拟网卡可能匹配不上
- [ ] 统计可视化可扩展：IO 曲线、对话矩阵等
- [ ] AI 总结面板可加「重新生成」「复制 Markdown」按钮

### 低优先级
- [ ] 对话历史持久化（刷新后保留）
- [ ] WebSocket 推送抓包进度（替代轮询）
- [ ] 导出 PDF（当前为 HTML）
- [ ] 前端 E2E 测试（Playwright）

## 接手须知

1. **先读 `AGENTS.md`**，了解架构决策（特别是 GLM 两个坑、pyshark 事件循环、前后端分离）。
2. 启动验证：双击 `run.bat`（抓包需管理员），浏览器访问 `localhost:5173`。
3. 真实配置在 `backend/.env`（不在根目录，也不在旧的 `wireshark_llm_agent/`）。
4. `pyshark-master/` 不可删（editable 安装依赖）。
5. 改 `run.bat` 后必须保持纯 ASCII，否则中文乱码。
6. 前端改端口需同步 `vite.config.js` proxy 与 `backend/main.py` CORS。
7. 旧 Streamlit 版在 `wireshark_llm_agent/`，仅供参考，不再维护。
