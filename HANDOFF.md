# HANDOFF.md

> 会话交接文档。记录项目当前状态、已完成工作、待办事项与关键决策，供下次会话或接手者快速上手。

## 项目状态：✅ 可用（Web 版 v2.2）

项目为前后端分离的「Web 版智能 Wireshark」。v2.2 在 v2.1 基础上，按外部评审建议补齐了
Wireshark 的「杀手锏」功能与桌面级交互：**追踪 TCP/UDP 流、右键上下文菜单、键盘导航、
列宽拖拽、PCAP 下载、时间格式切换、AI 字段解释、AI 会话级诊断**。

双击 `run.bat` 一键启动；或 `npm run build` 后只启动后端（单进程）。

**最后更新**: 2026-07-18

## v2.2 新增功能（本次升级）

### Wireshark 核心功能补齐
- [x] **追踪 TCP/UDP 流**：新增 `core/stream_service.py`，先 pyshark 定位流索引（`tcp.stream`），
  再调 `tshark -q -z follow,<proto>,ascii,<index>` 提取完整双向内容，解析为带方向的分段列表。
  前端 `StreamModal.jsx` 弹窗按客户端(蓝)/服务端(红)分色展示。实测提取 232 段流正常。
- [x] **PCAP 下载**：`GET /api/files/download`，无过滤器直接返回原文件；有过滤器时
  `tshark -Y ... -w` 导出匹配子集。Toolbar 新增「⬇ 下载」按钮。
- [x] **时间戳格式切换**：`packet_service` 支持 relative（相对首包）/ absolute（绝对时刻）/
  delta（距上一包间隔），缓存 key 含格式；Toolbar 下拉切换即时生效。

### UI/UX 桌面级交互
- [x] **右键上下文菜单**：通用 `ContextMenu.jsx`（`useContextMenu` hook）。
  - 表格行右键：作为过滤器应用（ip.addr / 会话 / 协议）、追踪 TCP/UDP 流、复制 Info。
  - 协议树节点右键：作为过滤器应用（启发式映射 IP/端口/流索引字段）、复制文本、AI 解释。
  - 过滤器以 `and` 叠加，贴近原生 Wireshark 行为。
- [x] **键盘导航**：`↑`/`↓` 切换选中包并联动协议树/Hex（自动滚动到可视区）；
  `/` 聚焦过滤器输入框；输入框聚焦时不劫持按键。
- [x] **列宽拖拽**：表头拖拽手柄实时调整，双击重置，列宽持久化到 `localStorage`。

### AI 能力深挖
- [x] **字段级 AI 解释**：协议树每行悬停显示 `(?)` 按钮（或右键菜单），
  `POST /api/chat/explain-field`，GLM 解释字段含义与当前值意义，Popover 气泡原位展示。
- [x] **AI 会话级诊断**：追踪流弹窗内「🤖 AI 诊断会话」按钮，把完整流文本（标注方向、
  截断保护 8KB）发给 `POST /api/chat/analyze-stream`，输出会话概要/是否正常/安全观察/结论建议。

### 新增/修改文件
```
后端：
  core/stream_service.py      [新增] 追踪流 + 过滤导出 pcap
  core/packet_service.py      [修改] 时间格式（relative/absolute/delta）+ _epoch 内部字段
  core/llm_service.py         [修改] explain_field() + analyze_stream()
  api/packets.py              [修改] /stream/info + /stream 路由 + time_format 参数
  api/chat.py                 [修改] /explain-field + /analyze-stream 路由
  api/capture.py              [修改] /files/download 路由（FileResponse / 过滤导出）

前端：
  components/ContextMenu.jsx  [新增] 通用右键菜单（useContextMenu hook）
  components/StreamModal.jsx  [新增] 追踪流弹窗（双向分色 + AI 诊断）
  components/PacketTable.jsx  [重写] 右键菜单 + ↑↓ 导航 + 列宽拖拽
  components/PacketDetail.jsx [重写] 协议树右键菜单 + AI 字段解释 Popover
  components/Toolbar.jsx      [修改] 下载按钮 + 时间格式下拉 + / 聚焦过滤器
  App.jsx                     [修改] 串联所有新功能（handleAppendFilter/handleFollowStream 等）
  api.js                      [修改] streamInfo/followStream/analyzeStream/explainField/downloadPcap
  styles/app.css              [修改] 右键菜单/流弹窗/解释气泡/列宽手柄样式
```

## v2.1 功能（沿用）

分页缓存、Hex 视图、协议分布图表、网卡实时流量图、异步抓包进度、多 LLM 提供商、
HTML 报告导出、AI 总结独立面板、可拖拽布局、单进程部署、单元测试。详见 git 历史。

## 端到端验证结果（全部通过）

- ✅ 后端 8 个单元测试全部通过（`python tests/test_services.py`）
- ✅ 追踪流：`/api/packets/stream/info` 定位流 → `/api/packets/stream` 提取 232 段
- ✅ PCAP 下载：原样下载 671KB + 过滤导出均 200
- ✅ 时间格式：relative/absolute/delta 三种格式正确，非法值回退 relative
- ✅ AI 接口：`/explain-field`、`/analyze-stream` 结构校验通过
- ✅ 前端 `vite build` 成功（292KB JS / 16KB CSS）
- ✅ 实机运行：抓包 1378KB → 追踪流 → AI 诊断 → 语义过滤（bilibili 复合过滤器 11 行匹配）全链路 200

## 关键决策记录

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 架构 | FastAPI + React 前后端分离 | Streamlit 无法支撑三屏互动 |
| 前端 | React 18 + Vite 5 + Vanilla CSS | 无 UI 库依赖，轻量可控 |
| UI 主题 | Tokyo Night 深色 | 现代感、协议着色仿 Wireshark |
| 语义过滤 | 直接 Prompt + JSON 结构化输出 | 比 Agent 工具调用更可控、更快 |
| 追踪流 | tshark `-z follow,ascii` + 自解析 | 官方实现，输出稳定；pyshark 无此能力 |
| 流内容截断 | 单段 512KB / AI 输入 8KB | 防止超大流撑爆内存/LLM 上下文 |
| 过滤器叠加 | `and` 连接现有过滤器 | 贴近 Wireshark「Apply as Filter」行为 |
| 列宽持久化 | localStorage | 无后端状态，刷新保留 |
| 协议树过滤表达式 | 启发式映射（IP/端口/流索引） | pyshark 树节点无字段缩写，只能猜常见字段 |
| 分页 | 顺序扫描跳过 offset + 全量行缓存 | 实现简单，中小规模够用 |
| 旧代码 | 保留 `wireshark_llm_agent/` 作参考 | 不删除，便于回退 |

## 已知噪音（不影响功能，勿误报为 bug）

1. **Windows `I/O operation on closed pipe`**：抓包完成后 Python GC 回收 asyncio
   `BaseSubprocessTransport` 时，`__del__` 打印警告触发 `__repr__` 访问已关闭 socket。
   这是 CPython 在 Windows ProactorEventLoop 下的已知问题（bpo-43693），
   异常以 `Exception ignored in:` 前缀打印到 stderr，抓包数据完整。`_safe_close()` 拦不住
   （异常发生在 GC 阶段而非 close() 调用时）。**建议保持现状**。

2. **过滤器并发构建两次**：前端 `Promise.all([list, count])` 同时发请求，
   缓存 `get()`/`set()` 之间无原子性，两个请求都未命中则各自扫描一遍 pcap。
   结果正确（后者覆盖前者），只是浪费一次扫描。**优化方案**：前端删掉 `/count` 请求
   （`/list` 已返回 `total_matched`），或后端加 single-flight 锁。

## 待办 / 可改进项

### 高优先级
- [ ] **API Key 安全**：当前 key 已在对话中暴露，建议提醒用户到智谱平台重置
- [ ] 抓包需管理员权限，`run.bat` 未做自动提权，需用户右键管理员运行

### 中优先级
- [ ] 前端 `/count` 请求去重（`/list` 已返回 `total_matched`，1 行改动）
- [ ] 协议树过滤表达式覆盖率：当前仅映射 IP/端口/流索引，可扩展 HTTP/DNS/TLS 常见字段
- [ ] 追踪流支持 HEX/EBCDIC/Raw 模式切换（当前仅 ASCII）
- [ ] 抓包实时进度按 dumpcap 实际包数（当前按时间估算）
- [ ] 统计可视化扩展：IO 曲线、对话矩阵

### 低优先级（长期架构演进）
- [ ] **WebSocket 实时抓包推送**：FastAPI WebSocket + asyncio.subprocess 读 tshark stdout，
  前端虚拟滚动，实现「数据包瀑布流」（替代当前的抓完再看）
- [ ] **超大 PCAP 索引**：初始化时用 `tshark -T fields` 生成 SQLite/JSON 行号映射，
  分页改 `frame.number in (x..y)` 精准提取，消除顺序扫描开销
- [ ] 对话历史持久化（刷新后保留）
- [ ] 导出 PDF（当前为 HTML）
- [ ] 前端 E2E 测试（Playwright）
- [ ] 智能过滤器补全（历史成功语义转化记录下拉提示）

## 接手须知

1. **先读 `AGENTS.md`**，了解架构决策（特别是 GLM 两个坑、pyshark 事件循环、前后端分离）。
2. 启动验证：双击 `run.bat`（抓包需管理员），浏览器访问 `localhost:5173`。
3. 真实配置在 `backend/.env`（不在根目录，也不在旧的 `wireshark_llm_agent/`）。
4. `pyshark-master/` 不可删（editable 安装依赖）。
5. 改 `run.bat` 后必须保持纯 ASCII，否则中文乱码。
6. 前端改端口需同步 `vite.config.js` proxy 与 `backend/main.py` CORS。
7. 旧 Streamlit 版在 `wireshark_llm_agent/`，仅供参考，不再维护。
8. 追踪流解析依赖 tshark `follow,ascii` 输出格式，升级 tshark 大版本后需回归测试
   `stream_service._parse_follow_output()`。
