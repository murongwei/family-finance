"""SQLite 连接与建表 —— 家庭极简理财管家 P0"""
import sqlite3
import hashlib
import secrets
from pathlib import Path

# 数据库文件放在项目根目录：family-finance/family_finance.db
DB_PATH = Path(__file__).resolve().parent.parent / "family_finance.db"


def get_conn():
    """拿到一个 SQLite 连接，行按字典方式返回"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_pwd(password, salt):
    """PBKDF2 密码哈希（内置，不依赖第三方库）"""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def init_db():
    """建 ledger 记账表（不存在才建）"""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                date     TEXT    NOT NULL,     -- 日期，如 2026-11-04
                category TEXT    NOT NULL,     -- 分类，如 饮食/交通/工资
                amount   REAL    NOT NULL,     -- 金额（元）
                note     TEXT,                 -- 备注，可空
                type     TEXT    NOT NULL DEFAULT 'expense'   -- expense支出 / income收入
            )
            """
        )
        # 兼容旧表：若缺 type 列则补（已有数据默认记支出）
        cols = [r[1] for r in conn.execute("PRAGMA table_info(ledger)")]
        if "type" not in cols:
            conn.execute("ALTER TABLE ledger ADD COLUMN type TEXT NOT NULL DEFAULT 'expense'")

        # 行情缓存表：akshare 数据定时落库，前端读缓存不依赖外网
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quotes_cache (
                key        TEXT PRIMARY KEY,
                data       TEXT,        -- 行情 JSON（dates/values/latest/change/day_change）
                updated_at REAL         -- 最后刷新时间戳
            )
            """
        )
        # 设置表：存期初资金、各模块投入本金等
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        # 投资流水表：投入/赎回记录，累计本金真实化
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invest_records (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                date   TEXT    NOT NULL,
                module TEXT    NOT NULL,   -- wenwen稳健 / touzi投资
                action TEXT    NOT NULL,   -- add投入 / remove赎回
                amount REAL    NOT NULL
            )
            """
        )
        # 分类表：内置 + 自定义；builtin=1 内置不可删
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL,
                type    TEXT    NOT NULL,   -- expense支出 / income收入
                builtin INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        BUILTIN = [
            ("饮食", "expense"), ("交通", "expense"), ("住房", "expense"),
            ("购物", "expense"), ("医疗", "expense"), ("其他", "expense"),
            ("工资", "income"), ("奖金", "income"), ("理财", "income"),
            ("红包", "income"), ("其他", "income"),
        ]
        for name, typ in BUILTIN:
            if not conn.execute("SELECT 1 FROM categories WHERE name=? AND type=? AND builtin=1",
                                (name, typ)).fetchone():
                conn.execute("INSERT INTO categories(name, type, builtin) VALUES(?,?,1)", (name, typ))

        # ===== 多用户：users 表 + 各数据表加 user_id（家人各记各的） =====
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT UNIQUE NOT NULL,
                salt    TEXT NOT NULL,
                pwdhash TEXT NOT NULL,
                token   TEXT,
                created TEXT DEFAULT ''
            )
            """
        )
        # settings 重建为按用户：(user_id, key) 联合主键
        scols = [r[1] for r in conn.execute("PRAGMA table_info(settings)")]
        if "user_id" not in scols:
            conn.execute("ALTER TABLE settings RENAME TO settings_old")
            conn.execute("CREATE TABLE settings (user_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT, PRIMARY KEY(user_id, key))")
            conn.execute("INSERT INTO settings(user_id, key, value) SELECT 1, key, value FROM settings_old")
            conn.execute("DROP TABLE settings_old")
        # 其余数据表加 user_id（存量账目归 user_id=1）
        for tbl in ["ledger", "invest_records", "categories"]:
            tcols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")]
            if "user_id" not in tcols:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER DEFAULT 1")
        # 种子管理员：初始账号 admin / 123456（登录后家人各自注册新账号）
        if not conn.execute("SELECT 1 FROM users").fetchone():
            salt = secrets.token_hex(8)
            conn.execute("INSERT INTO users(name, salt, pwdhash) VALUES('admin',?,?)",
                         (salt, _hash_pwd("123456", salt)))
