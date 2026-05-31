第一个终端：

source .venv/bin/activate

uvicorn main:app --host 0.0.0.0 --port 8000

第二个终端：

source .venv/bin/activate

python wechat_adapter.py



main.py 是一个 FastAPI 模块，但文件末尾没有 uvicorn.run()
  的启动代码。你运行 python main.py 时，Python只是加载了模块定义然后就退出了，所以服务器根本没启动。
     
  README 中写的 python main.py 不准确。从代码中的提示来看，正确启动方式是：

  uvicorn main:app --host 0.0.0.0 --port 8000
  
  ValueError: Unknown LLM provider: 'Moonshot'. Available: ['dashscope', 'openai', 'moonshot', 'ollama', 'gemini', 'claude', 'stepfun', 'minimax']