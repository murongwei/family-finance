"""记账 API 自测脚本：POST 两条 + GET 全部（避开命令行 JSON 编码坑）"""
import json
import urllib.request

base = "http://127.0.0.1:8000"


def post(date, category, amount, note):
    payload = json.dumps(
        {"date": date, "category": category, "amount": amount, "note": note}
    ).encode("utf-8")
    req = urllib.request.Request(
        base + "/api/entries", data=payload, headers={"Content-Type": "application/json"}
    )
    return urllib.request.urlopen(req).read().decode()


print("POST 饮食 ->", post("2026-11-04", "饮食", 30, "午餐"))
print("POST 交通 ->", post("2026-11-03", "交通", 12, "地铁"))
print("GET 全部 ->", urllib.request.urlopen(base + "/api/entries").read().decode())
