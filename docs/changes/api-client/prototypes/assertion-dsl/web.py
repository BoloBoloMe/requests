"""断言 DSL 原型 — Web 外壳 (一次性, 用后即焚).

问题陈述见 dsl.py 顶部. DSL + Python 逃生舱双形态.

运行: uv run python docs/changes/api-client/prototypes/assertion-dsl/web.py
然后开浏览器: http://127.0.0.1:8765
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from dsl import MISSING, evaluate, to_yaml
from fixtures import FIXTURES

app = FastAPI()


class EvalRequest(BaseModel):
    sample: int
    assertions: list[dict]


@app.get("/api/fixtures")
def get_fixtures():
    return [
        {
            "name": name,
            "response": {
                "status": r.status,
                "headers": r.headers,
                "body": r.body_text,
                "elapsed_ms": r.elapsed_ms,
            },
            "assertions": assertions,
        }
        for name, r, assertions in FIXTURES
    ]


@app.post("/api/eval")
def post_eval(req: EvalRequest):
    _, resp, _ = FIXTURES[req.sample]
    results = evaluate(resp, req.assertions)
    return {
        "results": [
            {
                "ok": r.ok,
                "actual": None if r.actual is MISSING or r.actual is None or r.ok else repr(r.actual),
                "message": r.message,
            }
            for r in results
        ],
        "yaml": "assert:\n" + to_yaml(req.assertions),
    }


PAGE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>断言 DSL 原型</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; display: flex; height: 100vh; background: #fafafa; }
  .col { padding: 16px; overflow-y: auto; }
  #left { width: 340px; border-right: 1px solid #ddd; background: #fff; }
  #mid { flex: 1; border-right: 1px solid #ddd; background: #fff; }
  #right { width: 360px; background: #fff; }
  h2 { font-size: 14px; margin: 0 0 8px; }
  select, input, textarea, button { font: inherit; }
  .resp { font: 12px monospace; background: #f0f0f0; padding: 8px; border-radius: 4px; white-space: pre-wrap; word-break: break-all; }
  .a-item { border: 1px solid #ddd; border-radius: 6px; padding: 8px; margin-bottom: 8px; }
  .a-item.fail { border-color: #e53935; background: #fff5f5; }
  .a-item.pass { border-color: #43a047; }
  .row { display: flex; gap: 4px; margin-top: 4px; }
  .row input { flex: 1; min-width: 0; }
  textarea { width: 100%; box-sizing: border-box; font: 12px monospace; margin-top: 4px; }
  .verdict { font-size: 12px; margin-top: 4px; }
  .pass .verdict { color: #43a047; }
  .fail .verdict { color: #e53935; }
  pre.yaml { font: 12px monospace; background: #f0f0f0; padding: 8px; border-radius: 4px; white-space: pre-wrap; }
  .del { color: #999; cursor: pointer; float: right; border: none; background: none; }
  button { cursor: pointer; }
</style>
</head>
<body>
<div class="col" id="left">
  <h2>响应样例</h2>
  <select id="sample" style="width:100%"></select>
  <div class="resp" id="resp" style="margin-top:8px"></div>
</div>
<div class="col" id="mid">
  <h2>断言</h2>
  <div id="alist"></div>
  <button onclick="addDsl()">+ DSL 断言</button>
  <button onclick="addPy()">+ Python 断言</button>
</div>
<div class="col" id="right">
  <h2>集合文件形态 (YAML)</h2>
  <pre class="yaml" id="yaml"></pre>
</div>
<script>
const OPS = ["eq","ne","lt","lte","gt","gte","contains","not_contains","matches","exists"];
let fixtures = [], cur = 0, assertions = [];

async function load() {
  fixtures = await (await fetch("/api/fixtures")).json();
  const sel = document.getElementById("sample");
  fixtures.forEach((f, i) => sel.add(new Option(f.name, i)));
  sel.onchange = () => switchSample(+sel.value);
  switchSample(0);
}

function switchSample(i) {
  cur = i;
  document.getElementById("sample").value = i;
  const f = fixtures[i];
  document.getElementById("resp").textContent =
    `status=${f.response.status}  elapsed=${f.response.elapsed_ms}ms\\n` +
    `headers=${JSON.stringify(f.response.headers)}\\nbody=${f.response.body}`;
  assertions = JSON.parse(JSON.stringify(f.assertions));
  render();
}

function addDsl() { assertions.push({target: "status", op: "eq", expect: 200}); render(); }
function addPy() { assertions.push({python: "assert response.status == 200"}); render(); }
function del(i) { assertions.splice(i, 1); render(); }

function onField(i, key, raw) {
  const a = assertions[i];
  if (key === "expect") { try { a.expect = JSON.parse(raw); } catch { a.expect = raw; } }
  else a[key] = raw;
  scheduleEval();
}

let timer = null;
function scheduleEval() { clearTimeout(timer); timer = setTimeout(evalNow, 300); }

async function evalNow() {
  const res = await (await fetch("/api/eval", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({sample: cur, assertions}),
  })).json();
  document.getElementById("yaml").textContent = res.yaml;
  document.querySelectorAll(".a-item").forEach((el, i) => {
    const r = res.results[i];
    el.className = "a-item " + (r.ok ? "pass" : "fail");
    el.querySelector(".verdict").textContent = r.ok ? "✓ 通过" : `✗ ${r.actual ?? ""} ${r.message}`;
  });
}

function render() {
  const list = document.getElementById("alist");
  list.innerHTML = "";
  assertions.forEach((a, i) => {
    const div = document.createElement("div");
    div.className = "a-item";
    let inner = `<button class="del" onclick="del(${i})">✕</button>`;
    if ("python" in a) {
      inner += `<div style="font-size:12px;color:#666">Python 断言</div>` +
        `<textarea rows="4" oninput="onField(${i},'python',this.value)">${a.python.replace(/</g,"&lt;")}</textarea>`;
    } else {
      inner += `<div class="row"><input value="${a.target ?? ""}" placeholder="target" oninput="onField(${i},'target',this.value)">` +
        `<select onchange="onField(${i},'op',this.value)">` +
        OPS.map(o => `<option ${o === a.op ? "selected" : ""}>${o}</option>`).join("") + `</select></div>`;
      if (a.op !== "exists") {
        inner += `<div class="row"><input value='${JSON.stringify(a.expect ?? "")}' placeholder="expect (JSON 或字符串)" oninput="onField(${i},'expect',this.value)"></div>`;
      }
    }
    inner += `<div class="verdict"></div>`;
    div.innerHTML = inner;
    list.appendChild(div);
  });
  evalNow();
}

load();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
