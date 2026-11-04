# 最小 demo：一个后端，访问它返回一句话
# 运行方法（先 cd 到这个文件所在目录）：
#   python -m uvicorn demo1_hello:app --reload
# 然后浏览器打开 http://127.0.0.1:8000

from fastapi import FastAPI      # 1. 从 fastapi 这个库，拿来 FastAPI 这个类

app = FastAPI()                  # 2. 创建"应用"——这就是你的后端本体

@app.get("/")                    # 3. 路由：当有人 GET 访问 "/" 时，执行下面这个函数
def home():                      # 4. 这个函数 = 处理这次请求的"处理器"
    return {"message": "你好，我在学 Web"}   # 5. 返回字典 → FastAPI 自动转成 JSON 响应
