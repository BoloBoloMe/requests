# testbed

testbed 是仓库自研的最小 HTTP 测试后端, 定位 = 开发夹具 / dogfooding 对象 / demo, 不是产品功能.

## 启动

```bash
# console script
uv run testbed

# 指定 host/port; --port 0 表示由内核分配端口, 启动后会打印实际端口
uv run testbed --host 127.0.0.1 --port 8000

# 模块入口
uv run python -m testbed --port 0
```

启动成功后会输出一行: `listening on http://host:port`.

## 端点清单

| 方法 | 路径 | 参数 | 说明 |
| --- | --- | --- | --- |
| GET / POST | `/echo` | query / headers / body | 回显 method / url / query / headers / body |
| POST | `/things` | body: `{"content": "..."}` | 创建 thing, 返回 `{"id": N, "content": "..."}` |
| GET / PUT / DELETE | `/things/{id}` | `id`: 整数 | 读取 / 更新 / 删除 thing; 不存在返回 404 |
| GET | `/auth/basic` | `Authorization: Basic <base64>` | Basic 认证, demo 凭证见下表 |
| GET | `/auth/bearer` | `Authorization: Bearer <token>` | Bearer token 认证 |
| GET | `/auth/apikey` | `X-API-Key: <key>` 或 `?api_key=<key>` | API Key 认证, 支持 header / query 两种携带 |
| GET | `/auth/digest` | `Authorization: Digest ...` | Digest 认证 (MD5, qop=auth), demo 凭证见下表 |
| GET | `/sse` | `?count=5&interval=0.01&event=message` | 返回 `text/event-stream`, count 个递增序号事件 |
| GET | `/dynamic/now` | `?ts=<ISO8601>` | 校验时间戳在服务器当前时间 ±60s 内 |
| GET | `/dynamic/uuid` | `?uuid=<UUID>` | 校验 UUIDv4 格式 |
| GET | `/status/{code}` | `code`: 200-599 | 返回指定 HTTP 状态码 |
| GET | `/delay/{seconds}` | `seconds`: 0-5 | asyncio.sleep 后返回实际延迟, 用于超时测试 |
| GET | `/large` | `?bytes=N` | 返回 N 字节 `\x00` 响应体, 上限 10MB |

## Demo 凭证

| 类型 | 用户名 / Key / Token | 密码 |
| --- | --- | --- |
| Basic | `demo` | `demo-pass` |
| Bearer | `demo-token` | - |
| API Key | `demo-key` | - |
| Digest | `demo` | `digest-pass` |

## Dogfooding 用法示例

### 用 curl 快速验证

```bash
# echo
uv run testbed --port 8000 &
curl -i "http://127.0.0.1:8000/echo?hello=world"

# Basic 认证
curl -u demo:demo-pass "http://127.0.0.1:8000/auth/basic"

# Bearer 认证
curl -H "Authorization: Bearer demo-token" "http://127.0.0.1:8000/auth/bearer"

# API Key (header)
curl -H "X-API-Key: demo-key" "http://127.0.0.1:8000/auth/apikey"

# Digest 认证
curl --digest -u demo:digest-pass "http://127.0.0.1:8000/auth/digest"

# SSE 流
curl -N "http://127.0.0.1:8000/sse?count=3&interval=0.1"

# 状态码 / 延迟 / 大响应
curl -i "http://127.0.0.1:8000/status/503"
curl -i "http://127.0.0.1:8000/delay/0.5"
curl -s "http://127.0.0.1:8000/large?bytes=1048576" | wc -c
```

### 产品 CLI 原型对接示意

```bash
# 假设产品 CLI 支持基本请求参数
# 仓库根目录 (以下相对路径均以此为基准)
cd /path/to/this-repo
uv run testbed --port 9000 &

api-client send GET http://127.0.0.1:9000/echo \
  --query hello=world

api-client send GET http://127.0.0.1:9000/auth/basic \
  --auth basic --user demo --password demo-pass

api-client send GET http://127.0.0.1:9000/auth/bearer \
  --auth bearer --token demo-token

api-client send GET http://127.0.0.1:9000/sse \
  --query count=3 --query interval=0.1
```

> 产品 CLI 目前为原型示意, 实际命令以最终实现为准. testbed 本身即可作为 runner / SPA / 断言引擎开发的公共靶子.
