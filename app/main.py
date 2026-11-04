"""家庭极简理财管家 · 入口（P0 骨架）"""
from fastapi import FastAPI
from .database import init_db
from .routers import ledger
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# 启动即建表（幂等：已存在则跳过）
init_db()

app = FastAPI(title="家庭极简理财管家", version="0.1.0")

app.include_router(ledger.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"  # 前端目录
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")  # 挂载前端目录
