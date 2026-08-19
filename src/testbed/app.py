"""testbed FastAPI 应用."""

from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/echo")
async def echo_get(request: Request):
    query = dict(request.query_params)
    headers = {key.lower(): value for key, value in request.headers.items()}
    path = request.url.path
    query_str = str(request.url.query)
    url = f"{path}?{query_str}" if query_str else path
    return {
        "method": request.method,
        "url": url,
        "query": query,
        "headers": headers,
    }


@app.post("/echo")
async def echo_post(request: Request):
    query = dict(request.query_params)
    headers = {key.lower(): value for key, value in request.headers.items()}
    path = request.url.path
    query_str = str(request.url.query)
    url = f"{path}?{query_str}" if query_str else path
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = await request.json()
    else:
        body = {"text": (await request.body()).decode(), "content_type": content_type}
    return {
        "method": request.method,
        "url": url,
        "query": query,
        "headers": headers,
        "body": body,
    }
