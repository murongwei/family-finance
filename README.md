# 家庭极简理财管家（P0 骨架）

给自己和家人的记账工具，Python 全栈第一版骨架。

## 运行步骤

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 启动服务
uvicorn app.main:app --reload
```

浏览器打开：
- 主页：http://127.0.0.1:8000
- 接口文档（FastAPI 自带）：http://127.0.0.1:8000/docs

## 测试记账 API

**新增一条账目**（POST）：

```bash
curl -X POST http://127.0.0.1:8000/api/entries \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-11-04","category":"饮食","amount":30,"note":"午餐"}'
```

**查询全部账目**（GET）：

```bash
curl http://127.0.0.1:8000/api/entries
```

## 目录结构

```
family-finance/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── database.py      # SQLite 连接 + 建表
│   └── routers/
│       └── ledger.py    # 记账 API（POST/GET）
├── requirements.txt
└── README.md
```

## 进度

- [x] P0：FastAPI 起 GET / + SQLite 建表 + 记账增查 API
- [ ] P1：4 资金模块 + 饼图 + 响应式页面（下一步）
