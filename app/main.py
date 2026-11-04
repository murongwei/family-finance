"""家庭极简理财管家 · 入口（P0 骨架）"""
from fastapi import FastAPI
from .database import init_db
from .routers import ledger

# 启动即建表（幂等：已存在则跳过）
init_db()

app = FastAPI(title="家庭极简理财管家", version="0.1.0")


@app.get("/")
def root():
    return {"message": "理财管家已启动"}


app.include_router(ledger.router)
