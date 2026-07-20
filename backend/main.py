"""FastAPI 应用入口。

启动方式：
    cd backend
    uvicorn main:app --host 127.0.0.1 --port 8000 --reload

提供：
- /api/packets/*   数据包列表/详情/统计
- /api/chat/*      AI 语义过滤与总结
- /api/capture/*   网卡与抓包
- /api/files/*     pcap 文件管理
- /api/health      健康检查 / 配置摘要
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 确保 backend/ 在 sys.path（支持 `python main.py` 直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import packets, chat, capture, live          # noqa: E402
from config.settings import get_settings_summary  # noqa: E402
from core.pyshark_analyzer import get_tshark_version  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wireshark 智能分析 API", version="2.0.0")

# 允许 Vite 开发服务器（默认 5173）跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(packets.router)
app.include_router(chat.router)
app.include_router(capture.router)
app.include_router(live.router)


@app.get("/api/health")
def health():
    """健康检查 + 配置摘要。"""
    summary = get_settings_summary()
    summary["tshark_version"] = get_tshark_version()
    return {"status": "ok", "config": summary}


# ---------------------------------------------------------------------
# 前端静态文件托管（单进程部署模式）
# 若 frontend/dist 存在（npm run build 产物），则由后端直接托管，
# 用户只需启动后端即可访问完整应用。
# ---------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    # 静态资源（js/css/assets）
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        """SPA 兜底路由：非 /api 路径一律返回 index.html。"""
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        index = _FRONTEND_DIST / "index.html"
        return FileResponse(index)

    logger.info("检测到前端构建产物，已由后端托管: %s", _FRONTEND_DIST)


if __name__ == "__main__":
    import uvicorn
    logger.info("启动 FastAPI 后端: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
