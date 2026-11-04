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
