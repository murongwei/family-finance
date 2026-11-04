"""记账 API —— 家庭极简理财管家 P0"""
from fastapi import APIRouter
from pydantic import BaseModel
from ..database import get_conn

router = APIRouter(prefix="/api")


class Entry(BaseModel):
    """一条账目的数据模型（pydantic 自动校验）"""
    date: str          # 日期，必填
    category: str      # 分类，必填
    amount: float      # 金额，必填
    note: str = ""     # 备注，可选，默认空


@router.post("/entries")
def create_entry(entry: Entry):
    """新增一条账目"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO ledger (date, category, amount, note) VALUES (?, ?, ?, ?)",
            (entry.date, entry.category, entry.amount, entry.note),
        )
        last_id = cur.lastrowid
    return {
        "id": last_id,
        "date": entry.date,
        "category": entry.category,
        "amount": entry.amount,
        "note": entry.note,
    }


@router.get("/entries")
def list_entries():
    """查询全部账目（按日期倒序）"""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM ledger ORDER BY date DESC").fetchall()
    return [dict(r) for r in rows]


@router.get("/summary")
def summary():
    """本月支出按分类统计：每类金额 + 总计（喂给饼图）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM ledger GROUP BY category ORDER BY total DESC"
        ).fetchall()
    data = [{"category": r["category"], "amount": r["total"]} for r in rows]
    total = sum(r["total"] for r in rows)
    return {"categories": data, "total": total}


@router.get("/overview")
def overview():
    """资金概览：可用资金/收入/4模块（预算规则模拟，后面填真实数据）"""
    available = 6400     # 可用资金（模拟，后填真实）
    income = 3000        # 本月收入（模拟）
    modules = [
        {"name": "应急救命", "pct": 30, "current": 2000},
        {"name": "稳健理财", "pct": 30, "current": 1900},
        {"name": "个人投资", "pct": 30, "current": 1800},
        {"name": "日常娱乐", "pct": 10, "current": 700},
    ]
    for m in modules:
        m["plan"] = round(available * m["pct"] / 100)   # 应分配 = 可用 × 比例
    return {"available": available, "income": income, "modules": modules}
