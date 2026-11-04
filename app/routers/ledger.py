"""记账 API —— 家庭极简理财管家 P1"""
import json
import time as _time
import io
import csv
from fastapi import APIRouter, Response
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


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int):
    """删除一条账目"""
    with get_conn() as conn:
        conn.execute("DELETE FROM ledger WHERE id=?", (entry_id,))
    return {"ok": True}


@router.put("/entries/{entry_id}")
def update_entry(entry_id: int, entry: Entry):
    """修改一条账目（金额记错/分类改）"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE ledger SET date=?, category=?, amount=?, note=?, type=? WHERE id=?",
            (entry.date, entry.category, entry.amount, entry.note, entry.type, entry_id),
        )
    return {"ok": True, "id": entry_id}


@router.get("/export")
def export_csv():
    """导出全部账目为 CSV（UTF-8 + BOM，Excel 打开中文不乱码）"""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM ledger ORDER BY date DESC, id DESC").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "date", "category", "amount", "note", "type"])
    for r in rows:
        w.writerow([r["id"], r["date"], r["category"], r["amount"], r["note"], r["type"]])
    content = "\ufeff" + buf.getvalue()   # BOM：让 Excel/记事本正确识别 UTF-8
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ledger_export.csv"'},
    )


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
    """资金概览：可用资金 = 收入−支出−净投资投入(投入转去理财/赎回转回)；模块余额真实化"""
    with get_conn() as conn:
        inc = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type='income'"
        ).fetchone()[0]
        exp = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type='expense'"
        ).fetchone()[0]
        net_invest = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN action='add' THEN amount ELSE -amount END), 0) "
            "FROM invest_records"
        ).fetchone()[0]
        w = round(_get_principal(conn, "wenwen"), 2)
        t = round(_get_principal(conn, "touzi"), 2)
        e_pct = int(_get_setting(conn, "budget_emergency", "30"))
        w_pct = int(_get_setting(conn, "budget_wenwen", "30"))
        t_pct = int(_get_setting(conn, "budget_touzi", "30"))
        d_pct = int(_get_setting(conn, "budget_daily", "10"))
    available = round(inc - exp - net_invest, 2)   # 手上可用 = 收入 − 支出 − 投进理财的钱 + 赎回
    modules = [
        {"name": "应急救命", "pct": e_pct, "current": 0},   # 应急/日常的钱在手边(可用资金里)
        {"name": "稳健理财", "pct": w_pct, "current": w},
        {"name": "个人投资", "pct": t_pct, "current": t},
        {"name": "日常娱乐", "pct": d_pct, "current": 0},
    ]
    for m in modules:
        m["plan"] = round(available * m["pct"] / 100)   # 应分配 = 可用 × 比例
    return {"available": available, "income": inc, "modules": modules}


@router.get("/assets")
def assets():
    """总资产页 = 手上可用 + 稳健理财本金 + 个人投资本金（投资盈亏见投资页市值）"""
    with get_conn() as conn:
        inc = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type='income'"
        ).fetchone()[0]
        exp = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type='expense'"
        ).fetchone()[0]
        net_invest = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN action='add' THEN amount ELSE -amount END), 0) "
            "FROM invest_records"
        ).fetchone()[0]
        avail = round(inc - exp - net_invest, 2)
        w = round(_get_principal(conn, "wenwen"), 2)
        t = round(_get_principal(conn, "touzi"), 2)
    modules = [
        {"name": "手上可用", "current": avail},
        {"name": "稳健理财", "current": w},
        {"name": "个人投资", "current": t},
    ]
    total = round(sum(m["current"] for m in modules), 2)
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


def _get_principal(conn, key):
    """该模块累计本金 = 投入(SUM add) − 赎回(SUM remove)"""
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN action='add' THEN amount ELSE -amount END), 0) "
        "FROM invest_records WHERE module=?", (key,)).fetchone()
    return row[0]


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

            principal = _get_principal(conn, key)   # 该模块投入本金（流水累计）
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


class InvestRec(BaseModel):
    """一笔投资操作：投入/赎回"""
    module: str        # wenwen稳健 / touzi投资
    action: str        # add投入 / remove赎回
    amount: float


@router.post("/invest")
def add_invest(rec: InvestRec):
    """记录一笔投入/赎回（累计本金由流水自动计算）"""
    today = _time.strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.execute("INSERT INTO invest_records(date, module, action, amount) VALUES(?,?,?,?)",
                     (today, rec.module, rec.action, rec.amount))
    return {"ok": True}


@router.get("/invest")
def invest():
    """投资总览：各模块累计本金 + 全部流水"""
    with get_conn() as conn:
        records = conn.execute("SELECT * FROM invest_records ORDER BY date DESC, id DESC").fetchall()
        modules = {}
        for key, _sym, name in QUOTES_TARGETS:
            modules[key] = {"name": name, "principal": round(_get_principal(conn, key), 2)}
    return {"modules": modules, "records": [dict(r) for r in records]}


class CatRec(BaseModel):
    """新增一个自定义分类"""
    name: str
    type: str   # expense支出 / income收入


@router.get("/categories")
def categories():
    """全部分类：内置(builtin=1) + 自定义；按 支出/收入 分组"""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY builtin DESC, id ASC").fetchall()
    result = {"expense": [], "income": []}
    for r in rows:
        result[r["type"]].append({"id": r["id"], "name": r["name"], "builtin": r["builtin"]})
    return result


@router.post("/categories")
def add_category(rec: CatRec):
    """加一个自定义分类（同名同类型去重）"""
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM categories WHERE name=? AND type=?",
                        (rec.name, rec.type)).fetchone():
            return {"ok": False, "msg": "分类已存在"}
        cur = conn.execute("INSERT INTO categories(name, type, builtin) VALUES(?,?,0)",
                           (rec.name, rec.type))
    return {"ok": True, "id": cur.lastrowid}


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int):
    """删一个自定义分类（内置不可删）"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not row:
            return {"ok": False, "msg": "分类不存在"}
        if row["builtin"]:
            return {"ok": False, "msg": "内置分类不可删"}
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    return {"ok": True}


class BudgetRec(BaseModel):
    """4资金模块的分配比例（加起来100）"""
    emergency: int   # 应急救命
    wenwen: int      # 稳健理财
    touzi: int       # 个人投资
    daily: int       # 日常娱乐


@router.get("/budget")
def budget():
    """读取预算分配比例"""
    with get_conn() as conn:
        return {
            "emergency": int(_get_setting(conn, "budget_emergency", "30")),
            "wenwen": int(_get_setting(conn, "budget_wenwen", "30")),
            "touzi": int(_get_setting(conn, "budget_touzi", "30")),
            "daily": int(_get_setting(conn, "budget_daily", "10")),
        }


@router.put("/budget")
def update_budget(rec: BudgetRec):
    """保存预算分配比例（存 settings 表）"""
    with get_conn() as conn:
        for key, val in [("budget_emergency", rec.emergency), ("budget_wenwen", rec.wenwen),
                         ("budget_touzi", rec.touzi), ("budget_daily", rec.daily)]:
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(val)))
    return {"ok": True}
