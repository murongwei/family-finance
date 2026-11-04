"""记账 API —— 家庭极简理财管家 P1"""
import json
import time as _time
from fastapi import APIRouter
from pydantic import BaseModel
from ..database import get_conn

router = APIRouter(prefix="/api")


class Entry(BaseModel):
    """一条账目的数据模型（pydantic 自动校验）"""
    date: str            # 日期，必填
    category: str        # 分类，必填（支出：饮食/交通…；收入：工资/奖金…）
    amount: float        # 金额，必填
    note: str = ""       # 备注，可选，默认空
    type: str = "expense"   # 类型：expense支出 / income收入，默认支出


@router.post("/entries")
def create_entry(entry: Entry):
    """新增一条账目（支出或收入）"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO ledger (date, category, amount, note, type) VALUES (?, ?, ?, ?, ?)",
            (entry.date, entry.category, entry.amount, entry.note, entry.type),
        )
        last_id = cur.lastrowid
    return {
        "id": last_id,
        "date": entry.date,
        "category": entry.category,
        "amount": entry.amount,
        "note": entry.note,
        "type": entry.type,
    }


@router.get("/entries")
def list_entries():
    """查询全部账目（按日期倒序）"""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM ledger ORDER BY date DESC").fetchall()
    return [dict(r) for r in rows]


@router.get("/summary")
def summary():
    """本月支出按分类统计：每类金额 + 总计（喂给饼图，只统计支出）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM ledger "
            "WHERE type='expense' GROUP BY category ORDER BY total DESC"
        ).fetchall()
    data = [{"category": r["category"], "amount": r["total"]} for r in rows]
    total = sum(r["total"] for r in rows)
    return {"categories": data, "total": total}


@router.get("/overview")
def overview():
    """资金概览：可用资金/收入/4模块（预算规则模拟，后面填真实数据）"""
    initial = 0     # 期初资金（用户选0，后填真实存款）
    with get_conn() as conn:
        inc = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type='income'"
        ).fetchone()[0]
        exp = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type='expense'"
        ).fetchone()[0]
    income = inc
    available = initial + income - exp    # 可用资金 = 期初 + 收入 − 支出（真实联动）
    modules = [
        {"name": "应急救命", "pct": 30, "current": 2000},
        {"name": "稳健理财", "pct": 30, "current": 1900},
        {"name": "个人投资", "pct": 30, "current": 1800},
        {"name": "日常娱乐", "pct": 10, "current": 700},
    ]
    for m in modules:
        m["plan"] = round(available * m["pct"] / 100)   # 应分配 = 可用 × 比例
    return {"available": available, "income": income, "modules": modules}


@router.get("/assets")
def assets():
    """总资产页：自己拥有的全部 = 4资金模块余额之和（模拟，后填真实）"""
    modules = [
        {"name": "应急救命", "pct": 30, "current": 2000},
        {"name": "稳健理财", "pct": 30, "current": 1900},
        {"name": "个人投资", "pct": 30, "current": 1800},
        {"name": "日常娱乐", "pct": 10, "current": 700},
    ]
    total = sum(m["current"] for m in modules)
    for m in modules:
        m["ratio"] = round(m["current"] / total * 100) if total else 0   # 每模块占比
    return {"total": total, "modules": modules}


@router.get("/trend")
def trend():
    """近7天支出趋势：按日期聚合每日支出（喂折线图，从早到晚）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date, SUM(amount) AS total FROM ledger "
            "WHERE type='expense' GROUP BY date ORDER BY date DESC LIMIT 7"
        ).fetchall()
    rows = rows[::-1]   # 升序：早 → 晚
    return {"dates": [r["date"] for r in rows], "amounts": [r["total"] for r in rows]}


QUOTES_TTL = 300          # 行情缓存 5 分钟
QUOTES_TARGETS = [("wenwen", "sh000012", "稳健理财"), ("touzi", "sh000300", "个人投资")]


def _fetch_quote(sym):
    """akshare 拉指数近30交易日；返回 {latest, change, day_change, dates, values}，失败返回 None"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol=sym).tail(30)
        values = [round(float(x), 2) for x in df["close"].tolist()]
        dates = [str(d)[:10] for d in df["date"].tolist()]
        if len(values) < 2:
            return None
        change = round((values[-1] - values[0]) / values[0] * 100, 2)         # 区间(30日)涨跌
        day_change = round((values[-1] - values[-2]) / values[-2] * 100, 2)   # 单日涨跌
        return {"latest": values[-1], "change": change, "day_change": day_change,
                "dates": dates, "values": values}
    except Exception:
        return None


def _get_setting(conn, key, default="0"):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


@router.get("/quotes")
def quotes():
    """投资行情：先读本地缓存(5分钟内)，过期才拉 akshare 刷新；断网时返回最近缓存。
    按投入本金算市值/总盈亏/单日盈亏（本金=0 则前端纯展示行情+推荐）"""
    now = _time.time()
    result = {}
    with get_conn() as conn:
        for key, sym, name in QUOTES_TARGETS:
            row = conn.execute("SELECT data, updated_at FROM quotes_cache WHERE key=?", (key,)).fetchone()
            data = json.loads(row["data"]) if row else None
            stale = row is None or now - row["updated_at"] > QUOTES_TTL
            if stale:
                fresh = _fetch_quote(sym)
                if fresh:
                    data = fresh
                    conn.execute(
                        "INSERT OR REPLACE INTO quotes_cache(key, data, updated_at) VALUES(?,?,?)",
                        (key, json.dumps(fresh), now))

            principal = float(_get_setting(conn, key + "_principal", "0"))   # 该模块投入本金
            if data is None:
                result[key] = {"name": name, "principal": principal, "error": "暂无行情（请检查网络）"}
            else:
                market_value = round(principal * (1 + data["change"] / 100), 2)      # 当前市值
                total_pnl = round(market_value - principal, 2)                        # 总盈亏
                day_pnl = round(principal * data["day_change"] / 100, 2)              # 单日盈亏
                result[key] = {**data, "name": name, "principal": principal,
                               "market_value": market_value, "total_pnl": total_pnl,
                               "day_pnl": day_pnl, "cached_at": _time.strftime("%m-%d %H:%M")}
    return result
