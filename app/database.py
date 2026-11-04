"""SQLite 连接与建表 —— 家庭极简理财管家 P0"""
import sqlite3
from pathlib import Path

# 数据库文件放在项目根目录：family-finance/family_finance.db
DB_PATH = Path(__file__).resolve().parent.parent / "family_finance.db"


def get_conn():
    """拿到一个 SQLite 连接，行按字典方式返回"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """建 ledger 记账表（不存在才建）"""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                date     TEXT    NOT NULL,     -- 日期，如 2026-11-04
                category TEXT    NOT NULL,     -- 分类，如 饮食/交通/住房
                amount   REAL    NOT NULL,     -- 金额（元），正数记支出
                note     TEXT                 -- 备注，可空
            )
            """
        )
