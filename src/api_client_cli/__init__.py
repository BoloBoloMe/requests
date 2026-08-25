"""api-client CLI 外壳 (MILESTONE-10): 纯 API client, 供 AI subprocess 调用.

唯一允许 import 核心库的模块是 api_client.launch (M3 D002 唯一例外);
全部业务 (变量解析/断言求值/执行) 在服务端, CLI 只做参数解析/输出渲染/错误映射.
"""
