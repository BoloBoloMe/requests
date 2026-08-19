#!/usr/bin/env python3
"""
apic — AI CLI shell prototype for an in-house Postman alternative.

This is a throw-away design verification script. It intentionally uses
in-process stubs and fake data to answer four design questions:

1. Command surface: how should execution/management commands be named and
   grouped (send/run/collection/item/env/history/service/schema/guide)?
2. Structured output: should the default be JSON, NDJSON streaming, or pretty
   text? What does each look like for human debugging vs. agent consumption?
3. Exit code / error model: can an agent reliably distinguish usage errors,
   not-found, operational failures, and domain assertion failures?
4. Discoverability: can an agent learn the CLI from --help, schema, and guide?

Assumptions / known deviations:
- This branch is the command-line shell prototype, not an interactive TUI,
  not a UI variant, and not the real service.
- The execution core is a stub. No real HTTP, no subprocess model, no auth,
  no security model, and no persistence is being validated here.
- Only the Python standard library is used.
"""

import argparse
import difflib
import json
import re
import sys
import time
from typing import Any, Dict, Generator, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Exit code contract
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_ASSERTION_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_SERVICE_ERROR = 3
EXIT_NOT_FOUND = 4

EXIT_LABELS = {
    EXIT_OK: "OK",
    EXIT_ASSERTION_FAILED: "ASSERTION_FAILED",
    EXIT_USAGE_ERROR: "USAGE_ERROR",
    EXIT_SERVICE_ERROR: "SERVICE_ERROR",
    EXIT_NOT_FOUND: "NOT_FOUND",
}


# ---------------------------------------------------------------------------
# Stub fixtures
# ---------------------------------------------------------------------------
COLLECTIONS: Dict[str, Any] = {
    "demo": {
        "ref": "demo",
        "name": "Demo Collection",
        "description": "A demo collection used to exercise the CLI shape.",
        "items": {
            "get-json": {
                "method": "GET",
                "url": "http://{{host}}/json",
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {"hello": "world", "list": [1, 2, 3]},
                "assertions": [
                    {"type": "status", "expected": 200},
                    {"type": "body_field", "path": "hello", "expected": "world"},
                ],
            },
            "sse-stream": {
                "method": "GET",
                "url": "http://{{host}}/stream",
                "status": 200,
                "headers": {"Content-Type": "text/event-stream"},
                "stream": True,
                "chunks": ["alpha", "beta", "gamma"],
                "sleep": 0.05,
                "assertions": [
                    {"type": "status", "expected": 200},
                ],
            },
            "failing-check": {
                "method": "GET",
                "url": "http://{{host}}/fail",
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {"ok": False},
                "assertions": [
                    {"type": "status", "expected": 200},
                    {"type": "body_field", "path": "ok", "expected": True},
                ],
            },
        },
    }
}

ENVIRONMENTS: Dict[str, Dict[str, Any]] = {
    "dev": {"name": "dev", "host": "localhost:3000"},
    "prod": {"name": "prod", "host": "api.example.com"},
}

HISTORY: List[Dict[str, Any]] = [
    {
        "id": "h-001",
        "item_ref": "demo/get-json",
        "env": "dev",
        "status": 200,
        "started_at": "2024-01-15T09:12:00Z",
        "duration_ms": 12,
        "assertions_passed": 2,
        "assertions_failed": 0,
    },
    {
        "id": "h-002",
        "item_ref": "demo/failing-check",
        "env": "dev",
        "status": 200,
        "started_at": "2024-01-15T09:13:00Z",
        "duration_ms": 8,
        "assertions_passed": 1,
        "assertions_failed": 1,
    },
]

SERVICE = {
    "status": "running",
    "pid": 4242,
    "port": 8080,
    "uptime_seconds": 3607,
    "version": "0.0.0-stub",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class NotFoundError(Exception):
    """Base not-found error; carries a machine error code and candidate refs."""

    def __init__(
        self,
        message: str,
        code: str = "NOT_FOUND",
        candidates: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.candidates = candidates or []


class ServiceError(Exception):
    pass


class UnresolvedVariablesError(Exception):
    def __init__(self, missing: List[str]) -> None:
        self.missing = missing
        super().__init__(f"unresolved variables: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _resolve_vars(template: str, variables: Dict[str, Any]) -> str:
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def _placeholder_vars(text: str) -> List[str]:
    return re.findall(r"\{\{([^{}]+)\}\}", text)


def _find_candidates(query: str, refs: List[str]) -> List[str]:
    """Substring matching (case-insensitive) unioned with difflib close matches."""
    query = query.lower()
    hits = [ref for ref in refs if query in ref.lower()]
    close = difflib.get_close_matches(query, refs, n=len(refs), cutoff=0.6)
    return sorted(set(hits) | set(close))


def _extract_unresolved(item: Dict[str, Any], variables: Dict[str, Any]) -> List[str]:
    """Return sorted list of {{...}} variable names still present after substitution."""
    missing: List[str] = []

    resolved_url = _resolve_vars(item["url"], variables)
    missing.extend(_placeholder_vars(resolved_url))

    for key, value in item.get("headers", {}).items():
        missing.extend(_placeholder_vars(str(key)))
        missing.extend(_placeholder_vars(str(value)))

    body = item.get("body")
    if body is not None:
        if isinstance(body, str):
            missing.extend(_placeholder_vars(body))
        else:
            missing.extend(_placeholder_vars(json.dumps(body, ensure_ascii=False)))

    return sorted(set(missing) - {"$now", "$uuid"})


def _parse_item_ref(ref: str) -> Tuple[str, str]:
    parts = ref.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise NotFoundError(
            f"item-ref must be <collection>/<item-slug>, got: {ref!r}",
            code="ITEM_NOT_FOUND",
            candidates=[],
        )
    return parts[0], parts[1]


def _get_collection(ref: str) -> Dict[str, Any]:
    if ref not in COLLECTIONS:
        raise NotFoundError(
            f"collection not found: {ref}",
            code="COLLECTION_NOT_FOUND",
            candidates=_find_candidates(ref, list(COLLECTIONS.keys())),
        )
    return COLLECTIONS[ref]


def _get_item(ref: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    collection_ref, slug = _parse_item_ref(ref)
    collection = _get_collection(collection_ref)
    if slug not in collection["items"]:
        raise NotFoundError(
            f"item not found: {ref}",
            code="ITEM_NOT_FOUND",
            candidates=_find_candidates(slug, list(collection["items"].keys())),
        )
    return collection, collection["items"][slug]


def _get_env(name: Optional[str]) -> Dict[str, Any]:
    if name is None:
        return {}
    if name not in ENVIRONMENTS:
        raise NotFoundError(
            f"environment not found: {name}",
            code="ENV_NOT_FOUND",
            candidates=_find_candidates(name, list(ENVIRONMENTS.keys())),
        )
    return ENVIRONMENTS[name]


def _build_variables(env_name: Optional[str], extra_vars: Optional[List[str]]) -> Dict[str, Any]:
    variables: Dict[str, Any] = {}
    if env_name:
        variables.update(_get_env(env_name))
    if extra_vars:
        for pair in extra_vars:
            if "=" not in pair:
                raise ServiceError(f"variable must be KEY=VALUE, got: {pair!r}")
            k, v = pair.split("=", 1)
            variables[k] = v
    return variables


def _evaluate_assertions(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    status = item.get("status", 200)
    body = item.get("body", {})
    for assertion in item.get("assertions", []):
        atype = assertion["type"]
        if atype == "status":
            passed = status == assertion["expected"]
            results.append(
                {
                    "name": "status",
                    "expected": assertion["expected"],
                    "actual": status,
                    "passed": passed,
                }
            )
        elif atype == "body_field":
            actual = body.get(assertion["path"])
            passed = actual == assertion["expected"]
            results.append(
                {
                    "name": f"body.{assertion['path']}",
                    "expected": assertion["expected"],
                    "actual": actual,
                    "passed": passed,
                }
            )
        else:
            results.append({"name": atype, "expected": None, "actual": None, "passed": False})
    return results


# ---------------------------------------------------------------------------
# Output primitives
# ---------------------------------------------------------------------------
def _emit_error(code: str, message: str, details: Optional[Any] = None) -> None:
    payload: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    sys.stderr.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _emit_ndjson(event: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _emit_json(data: Any) -> None:
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _emit_pretty_event(event: Dict[str, Any]) -> None:
    etype = event.get("type", "event")
    print(f"{etype} {json.dumps(event, ensure_ascii=False)}")


def _stream(events: Generator[Dict[str, Any], None, Any], mode: str) -> Any:
    """Render a generator of events according to the selected output mode.

    Returns the generator's final return value (or None).
    """
    if mode == "ndjson":
        try:
            while True:
                _emit_ndjson(next(events))
        except StopIteration as exc:
            return exc.value
    elif mode == "json":
        collected = list(events)
        _emit_json(collected)
        # The generator return value is lost when consumed with list() in Py3;
        # for this prototype we recompute the pass flag from the collected data.
        return None
    elif mode == "pretty":
        try:
            while True:
                _emit_pretty_event(next(events))
        except StopIteration as exc:
            return exc.value
    return None


def _all_assertions_passed(events: List[Dict[str, Any]]) -> bool:
    for event in events:
        if event.get("type") == "done":
            for assertion in event.get("assertions", []):
                if not assertion.get("passed"):
                    return False
        elif event.get("type") == "summary":
            if event.get("failed", 0) > 0:
                return False
    return True


# ---------------------------------------------------------------------------
# Event builders
# ---------------------------------------------------------------------------
def _event_meta(ref: str, method: str, resolved_url: str, env_name: Optional[str]) -> Dict[str, Any]:
    return {
        "type": "meta",
        "timestamp": _now(),
        "item_ref": ref,
        "item": ref,
        "method": method,
        "resolved_url": resolved_url,
        "env": env_name,
    }


def _event_chunk(ref: str, index: int, data: Any) -> Dict[str, Any]:
    return {"type": "chunk", "timestamp": _now(), "item": ref, "index": index, "data": data}


def _event_done(ref: str, status: int, duration_ms: int, assertions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "type": "done",
        "timestamp": _now(),
        "item": ref,
        "status": status,
        "duration_ms": duration_ms,
        "assertions": assertions,
    }


def _event_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "summary", "timestamp": _now(), **summary}


# ---------------------------------------------------------------------------
# Execution engine (stub)
# ---------------------------------------------------------------------------
def _execute_send(ref: str, env_name: Optional[str], extra_vars: Optional[List[str]]) -> Generator[Dict[str, Any], None, bool]:
    collection, item = _get_item(ref)
    variables = _build_variables(env_name, extra_vars)
    resolved_url = _resolve_vars(item["url"], variables)

    missing = _extract_unresolved(item, variables)
    if missing:
        raise UnresolvedVariablesError(missing)

    start = time.monotonic()
    yield _event_meta(ref, item["method"], resolved_url, env_name)

    if item.get("stream"):
        for idx, chunk in enumerate(item["chunks"]):
            time.sleep(item.get("sleep", 0.05))
            yield _event_chunk(ref, idx, chunk)
    else:
        # tiny delay so duration is observable
        time.sleep(0.01)
        yield _event_chunk(ref, 0, item.get("body", ""))

    duration_ms = int((time.monotonic() - start) * 1000)
    assertions = _evaluate_assertions(item)
    yield _event_done(ref, item.get("status", 200), duration_ms, assertions)
    return all(a["passed"] for a in assertions)


def _execute_run(collection_ref: str, env_name: Optional[str], extra_vars: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, bool]:
    collection = _get_collection(collection_ref)
    variables = _build_variables(env_name, extra_vars)

    # Fail fast if any item has unresolved placeholders; no normal event stream is emitted.
    all_missing: List[str] = []
    for slug in collection["items"]:
        item = collection["items"][slug]
        all_missing.extend(_extract_unresolved(item, variables))
    if all_missing:
        raise UnresolvedVariablesError(sorted(set(all_missing)))

    overall_pass = True
    summary = {"total": 0, "passed": 0, "failed": 0, "items": []}

    for slug in collection["items"]:
        item = collection["items"][slug]
        ref = f"{collection_ref}/{slug}"
        resolved_url = _resolve_vars(item["url"], variables)
        start = time.monotonic()
        yield _event_meta(ref, item["method"], resolved_url, env_name)

        if item.get("stream"):
            for idx, chunk in enumerate(item["chunks"]):
                time.sleep(item.get("sleep", 0.05))
                yield _event_chunk(ref, idx, chunk)
        else:
            time.sleep(0.01)
            yield _event_chunk(ref, 0, item.get("body", ""))

        duration_ms = int((time.monotonic() - start) * 1000)
        assertions = _evaluate_assertions(item)
        passed = all(a["passed"] for a in assertions)
        yield _event_done(ref, item.get("status", 200), duration_ms, assertions)
        overall_pass = overall_pass and passed
        summary["total"] += 1
        if passed:
            summary["passed"] += 1
        else:
            summary["failed"] += 1
        summary["items"].append({"item_ref": ref, "passed": passed})

    yield _event_summary(summary)
    return overall_pass


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
def _cmd_send(args: argparse.Namespace) -> int:
    mode = args.output if args.output else "ndjson"
    events = _execute_send(args.item_ref, args.env, args.var)
    # For ndjson/pretty we consume the generator lazily; for json we collect.
    if mode == "json":
        collected = list(events)
        _emit_json(collected)
        return EXIT_OK if _all_assertions_passed(collected) else EXIT_ASSERTION_FAILED
    try:
        while True:
            event = next(events)
            if mode == "ndjson":
                _emit_ndjson(event)
            else:
                _emit_pretty_event(event)
    except StopIteration as exc:
        all_pass = exc.value
    return EXIT_OK if all_pass else EXIT_ASSERTION_FAILED


def _cmd_run(args: argparse.Namespace) -> int:
    mode = args.output if args.output else "ndjson"
    events = _execute_run(args.collection_ref, args.env, getattr(args, "var", None))
    if mode == "json":
        collected = list(events)
        _emit_json(collected)
        return EXIT_OK if _all_assertions_passed(collected) else EXIT_ASSERTION_FAILED
    try:
        while True:
            event = next(events)
            if mode == "ndjson":
                _emit_ndjson(event)
            else:
                _emit_pretty_event(event)
    except StopIteration as exc:
        all_pass = exc.value
    return EXIT_OK if all_pass else EXIT_ASSERTION_FAILED


def _cmd_collection_list(args: argparse.Namespace) -> int:
    data = [
        {"ref": c["ref"], "name": c["name"], "item_count": len(c["items"])}
        for c in COLLECTIONS.values()
    ]
    _emit_json(data)
    return EXIT_OK


def _cmd_collection_show(args: argparse.Namespace) -> int:
    collection = _get_collection(args.ref)
    _emit_json(collection)
    return EXIT_OK


def _cmd_item_list(args: argparse.Namespace) -> int:
    collection = _get_collection(args.collection_ref)
    data = [
        {"ref": f"{collection['ref']}/{slug}", "method": item["method"], "url": item["url"]}
        for slug, item in collection["items"].items()
    ]
    _emit_json(data)
    return EXIT_OK


def _cmd_item_show(args: argparse.Namespace) -> int:
    _, item = _get_item(args.item_ref)
    _emit_json(item)
    return EXIT_OK


def _cmd_env_list(args: argparse.Namespace) -> int:
    data = [{"name": e["name"], "host": e["host"]} for e in ENVIRONMENTS.values()]
    _emit_json(data)
    return EXIT_OK


def _cmd_env_show(args: argparse.Namespace) -> int:
    env = _get_env(args.name)
    _emit_json(env)
    return EXIT_OK


def _cmd_history_list(args: argparse.Namespace) -> int:
    _emit_json(HISTORY)
    return EXIT_OK


def _cmd_history_show(args: argparse.Namespace) -> int:
    for record in HISTORY:
        if record["id"] == args.id:
            _emit_json(record)
            return EXIT_OK
    raise NotFoundError(f"history entry not found: {args.id}")


def _cmd_service_status(args: argparse.Namespace) -> int:
    _emit_json(SERVICE)
    return EXIT_OK


def _cmd_service_stop(args: argparse.Namespace) -> int:
    SERVICE["status"] = "stopped"
    _emit_json({"status": "stopped", "pid": SERVICE["pid"]})
    return EXIT_OK


def _cmd_service_token(args: argparse.Namespace) -> int:
    _emit_json({"token": "stub-token-do-not-use-in-production"})
    return EXIT_OK


def _cmd_schema(args: argparse.Namespace) -> int:
    schema = {
        "program": "apic",
        "description": "AI-friendly CLI shell for the in-house API client.",
        "global_flags": [
            {
                "name": "--output",
                "type": "choice",
                "choices": ["json", "ndjson", "pretty"],
                "default": "per-command default; see commands",
                "description": "Structured output format.",
            }
        ],
        "output_modes": {
            "json": "Streaming commands (send/run): JSON array of events. Non-streaming commands: single JSON object.",
            "ndjson": "Streaming commands (send/run): newline-delimited JSON stream, one event per line. Non-streaming commands: same as json, emitted as a single line.",
            "pretty": "Streaming commands (send/run): human-readable event dump. Non-streaming commands: human-readable table/abbreviated rendering.",
        },
        "commands": [
            {
                "path": ["send", "<item-ref>"],
                "options": ["--env NAME", "--var KEY=VALUE (repeatable)"],
                "default_output": "ndjson",
                "event_stream": [
                    {"event": "meta", "fields": ["type", "timestamp", "item_ref", "item", "method", "resolved_url", "env"]},
                    {"event": "chunk", "fields": ["type", "timestamp", "item", "index", "data"], "note": "one or more per item"},
                    {"event": "done", "fields": ["type", "timestamp", "item", "status", "duration_ms", "assertions"]},
                ],
                "description": "Execute a single request item and stream the result.",
            },
            {
                "path": ["run", "<collection-ref>"],
                "options": ["--env NAME", "--var KEY=VALUE (repeatable)"],
                "default_output": "ndjson",
                "event_stream": [
                    {"event": "meta", "fields": ["type", "timestamp", "item_ref", "item", "method", "resolved_url", "env"]},
                    {"event": "chunk", "fields": ["type", "timestamp", "item", "index", "data"], "note": "one per item (more for streaming items)"},
                    {"event": "done", "fields": ["type", "timestamp", "item", "status", "duration_ms", "assertions"]},
                    {"event": "summary", "fields": ["type", "timestamp", "total", "passed", "failed", "items"]},
                ],
                "description": "Run every item in a collection sequentially.",
            },
            {
                "path": ["collection", "list"],
                "default_output": "json",
                "description": "List collections.",
            },
            {
                "path": ["collection", "show", "<ref>"],
                "default_output": "json",
                "description": "Show a collection definition.",
            },
            {
                "path": ["item", "list", "<collection-ref>"],
                "default_output": "json",
                "description": "List items inside a collection.",
            },
            {
                "path": ["item", "show", "<item-ref>"],
                "default_output": "json",
                "description": "Show a request item definition.",
            },
            {
                "path": ["env", "list"],
                "default_output": "json",
                "description": "List environments.",
            },
            {
                "path": ["env", "show", "<name>"],
                "default_output": "json",
                "description": "Show environment variables.",
            },
            {
                "path": ["history", "list"],
                "default_output": "json",
                "description": "List recent execution history entries.",
            },
            {
                "path": ["history", "show", "<id>"],
                "default_output": "json",
                "description": "Show one history entry.",
            },
            {
                "path": ["service", "status"],
                "default_output": "json",
                "description": "Show service runtime status.",
            },
            {
                "path": ["service", "stop"],
                "default_output": "json",
                "description": "Signal the service to stop (stub).",
            },
            {
                "path": ["service", "token"],
                "default_output": "json",
                "description": "Return an access token for the service (stub).",
            },
            {
                "path": ["schema"],
                "default_output": "json",
                "description": "Return this self-describing schema as JSON.",
            },
            {
                "path": ["guide"],
                "default_output": "text",
                "description": "Return a concise plain-text guide for agents.",
            },
        ],
        "events": {
            "meta": {
                "type": "meta",
                "timestamp": "ISO-8601 UTC string",
                "item_ref": "<collection>/<item-slug>",
                "item": "<collection>/<item-slug>",
                "method": "HTTP method",
                "resolved_url": "URL with environment variables substituted",
                "env": "environment name or null",
            },
            "chunk": {
                "type": "chunk",
                "timestamp": "ISO-8601 UTC string",
                "item": "<collection>/<item-slug>",
                "index": "zero-based chunk index",
                "data": "arbitrary payload (string, object, etc.)",
            },
            "done": {
                "type": "done",
                "timestamp": "ISO-8601 UTC string",
                "item": "<collection>/<item-slug>",
                "status": "HTTP status code",
                "duration_ms": "integer",
                "assertions": "list of {name, expected, actual, passed}",
            },
            "summary": {
                "type": "summary",
                "timestamp": "ISO-8601 UTC string",
                "total": "integer",
                "passed": "integer",
                "failed": "integer",
                "items": "list of {item_ref, passed}",
            },
        },
        "exit_codes": [
            {"code": EXIT_OK, "label": "OK", "meaning": "Success; all assertions passed."},
            {"code": EXIT_ASSERTION_FAILED, "label": "ASSERTION_FAILED", "meaning": "Domain failure; data was produced normally but at least one assertion failed."},
            {"code": EXIT_USAGE_ERROR, "label": "USAGE_ERROR", "meaning": "Invalid CLI invocation, unresolved variables, or bad arguments."},
            {"code": EXIT_SERVICE_ERROR, "label": "SERVICE_ERROR", "meaning": "Service/operation failure."},
            {"code": EXIT_NOT_FOUND, "label": "NOT_FOUND", "meaning": "Collection, item, or environment does not exist."},
        ],
        "error_codes": [
            {"code": "USAGE_ERROR", "exit": EXIT_USAGE_ERROR, "meaning": "Invalid CLI invocation or bad arguments."},
            {"code": "UNRESOLVED_VARIABLES", "exit": EXIT_USAGE_ERROR, "meaning": "URL/headers/body still contain {{NAME}} placeholders after variable substitution. Dynamic variables {{$now}} and {{$uuid}} are excluded.", "details": {"missing": "list of unresolved variable names"}},
            {"code": "COLLECTION_NOT_FOUND", "exit": EXIT_NOT_FOUND, "meaning": "Collection reference does not exist.", "details": {"candidates": "list of similar collection refs"}},
            {"code": "ITEM_NOT_FOUND", "exit": EXIT_NOT_FOUND, "meaning": "Item reference does not exist.", "details": {"candidates": "list of similar item slugs"}},
            {"code": "ENV_NOT_FOUND", "exit": EXIT_NOT_FOUND, "meaning": "Environment name does not exist.", "details": {"candidates": "list of similar environment names"}},
            {"code": "SERVICE_ERROR", "exit": EXIT_SERVICE_ERROR, "meaning": "Service/operation failure."},
        ],
        "error_format": {
            "error": {"code": "<MACHINE_CODE>", "message": "human-readable text", "details": "optional object"}
        },
    }
    _emit_json(schema)
    return EXIT_OK


def _cmd_guide(args: argparse.Namespace) -> int:
    guide = """# apic agent guide

apic is a machine-friendly CLI for executing API requests.
Use it to run items, batch collections, inspect fixtures, and manage the service.

## Quick examples

  apic schema
  apic send demo/get-json
  apic send demo/get-json --env dev --var host=localhost:8000
  apic run demo

## Command surface

Execution:
  send <item-ref> [--env NAME] [--var KEY=VALUE]...
  run <collection-ref> [--env NAME] [--var KEY=VALUE]...

Inventory:
  collection list | collection show <ref>
  item list <collection-ref> | item show <item-ref>
  env list | env show <name>
  history list | history show <id>

Service:
  service status | service stop | service token

Meta:
  schema     # JSON self-description of every command, event, and exit code
  guide      # this plain-text document

## Output modes

--output json     Streaming commands (send/run): JSON array of events. Others: one JSON object.
--output ndjson   Streaming commands (send/run): newline-delimited JSON stream, one event per line. Others: same as json, single line.
--output pretty   Streaming commands (send/run): human-readable event dump. Others: table/abbreviated human-readable rendering.

send and run default to ndjson; everything else defaults to json.
On error, stderr receives {"error": {"code": "...", "message": "...", "details": {...}}}.

## Exit codes

0  OK
1  ASSERTION_FAILED  (domain failure; data still produced)
2  USAGE_ERROR       (bad CLI invocation or unresolved variables)
3  SERVICE_ERROR     (service/operation failure)
4  NOT_FOUND         (resource does not exist)

## Error codes

USAGE_ERROR, UNRESOLVED_VARIABLES, COLLECTION_NOT_FOUND, ITEM_NOT_FOUND, ENV_NOT_FOUND, SERVICE_ERROR

NOT_FOUND (4) is reported as one of COLLECTION_NOT_FOUND, ITEM_NOT_FOUND, or ENV_NOT_FOUND,
with a `candidates` list of similar refs when possible.

## Item references

<item-ref> is always <collection>/<item-slug>, e.g. demo/get-json.

## Important caveats

This is a stub prototype. No real HTTP is performed, no auth/security model is
implemented, and no state is persisted.

If URL/headers/body still contain unresolved {{...}} placeholders after variable
substitution, the command exits 2 with UNRESOLVED_VARIABLES and produces no normal
event stream. Dynamic variables {{$now}} and {{$uuid}} are evaluated by the engine
and are never treated as unresolved.

## Variables

`--var KEY=VALUE` overrides environment variables. This works for both `send` and `run`.

run now emits a chunk event for each item (one synthetic chunk for non-streaming
items, multiple chunks for streaming items), matching the send event contract.
"""
    sys.stdout.write(guide)
    return EXIT_OK


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
class _JSONErrorParser(argparse.ArgumentParser):
    """Emit machine-readable JSON on usage errors instead of plain argparse text."""

    def error(self, message: str) -> None:
        _emit_error("USAGE_ERROR", message)
        self.exit(EXIT_USAGE_ERROR)


def _create_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--output",
        dest="output",
        choices=["json", "ndjson", "pretty"],
        default=None,
        help="Output format: json, ndjson (default for send/run), or pretty.",
    )

    parser = _JSONErrorParser(
        prog="apic",
        description="AI-friendly CLI shell for an in-house API client (prototype).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exit codes:
  0 OK / 1 assertion failed / 2 usage / 3 service / 4 not found

Error codes:
  USAGE_ERROR, UNRESOLVED_VARIABLES, COLLECTION_NOT_FOUND, ITEM_NOT_FOUND, ENV_NOT_FOUND, SERVICE_ERROR

Event stream:
  meta(type,timestamp,item_ref,item,method,resolved_url,env) / chunk(type,timestamp,item,index,data) / done(type,timestamp,item,status,duration_ms,assertions) / summary(type,timestamp,total,passed,failed,items)

Agent examples: apic schema | apic send demo/get-json | apic run demo""",
    )

    subparsers = parser.add_subparsers(dest="command", parser_class=_JSONErrorParser)

    # send
    send_parser = subparsers.add_parser(
        "send",
        parents=[parent],
        help="Execute a single request item.",
        epilog="Example: apic send demo/get-json --env dev --output pretty\n\n"
        "--var KEY=VALUE overrides environment variables. "
        "Dynamic variables {{$now}} and {{$uuid}} are evaluated by the engine and are never reported as unresolved.",
    )
    send_parser.add_argument("item_ref", metavar="<item-ref>")
    send_parser.add_argument("--env", default=None, help="Environment name.")
    send_parser.add_argument(
        "--var",
        action="append",
        metavar="KEY=VALUE",
        help="Extra variable (repeatable).",
    )
    send_parser.set_defaults(func=_cmd_send)

    # run
    run_parser = subparsers.add_parser(
        "run",
        parents=[parent],
        help="Run every item in a collection.",
        epilog="Example: apic run demo --env dev\n\n"
        "--var KEY=VALUE overrides environment variables. "
        "Dynamic variables {{$now}} and {{$uuid}} are evaluated by the engine and are never reported as unresolved.",
    )
    run_parser.add_argument("collection_ref", metavar="<collection-ref>")
    run_parser.add_argument("--env", default=None, help="Environment name.")
    run_parser.add_argument(
        "--var",
        action="append",
        metavar="KEY=VALUE",
        help="Extra variable (repeatable); overrides environment variables.",
    )
    run_parser.set_defaults(func=_cmd_run)

    # collection
    collection_parser = subparsers.add_parser(
        "collection",
        help="Collection management.",
        epilog="Examples: apic collection list | apic collection show demo",
    )
    collection_sub = collection_parser.add_subparsers(dest="collection_cmd", parser_class=_JSONErrorParser)

    collection_list = collection_sub.add_parser(
        "list",
        parents=[parent],
        help="List collections.",
    )
    collection_list.set_defaults(func=_cmd_collection_list)

    collection_show = collection_sub.add_parser(
        "show",
        parents=[parent],
        help="Show a collection.",
    )
    collection_show.add_argument("ref", metavar="<ref>")
    collection_show.set_defaults(func=_cmd_collection_show)

    # item
    item_parser = subparsers.add_parser(
        "item",
        help="Item management.",
        epilog="Examples: apic item list demo | apic item show demo/get-json",
    )
    item_sub = item_parser.add_subparsers(dest="item_cmd", parser_class=_JSONErrorParser)

    item_list = item_sub.add_parser(
        "list",
        parents=[parent],
        help="List items in a collection.",
    )
    item_list.add_argument("collection_ref", metavar="<collection-ref>")
    item_list.set_defaults(func=_cmd_item_list)

    item_show = item_sub.add_parser(
        "show",
        parents=[parent],
        help="Show a request item.",
    )
    item_show.add_argument("item_ref", metavar="<item-ref>")
    item_show.set_defaults(func=_cmd_item_show)

    # env
    env_parser = subparsers.add_parser(
        "env",
        help="Environment management.",
        epilog="Examples: apic env list | apic env show dev",
    )
    env_sub = env_parser.add_subparsers(dest="env_cmd", parser_class=_JSONErrorParser)

    env_list = env_sub.add_parser(
        "list",
        parents=[parent],
        help="List environments.",
    )
    env_list.set_defaults(func=_cmd_env_list)

    env_show = env_sub.add_parser(
        "show",
        parents=[parent],
        help="Show environment variables.",
    )
    env_show.add_argument("name", metavar="<name>")
    env_show.set_defaults(func=_cmd_env_show)

    # history
    history_parser = subparsers.add_parser(
        "history",
        help="Execution history.",
        epilog="Examples: apic history list | apic history show h-001",
    )
    history_sub = history_parser.add_subparsers(dest="history_cmd", parser_class=_JSONErrorParser)

    history_list = history_sub.add_parser(
        "list",
        parents=[parent],
        help="List history entries.",
    )
    history_list.set_defaults(func=_cmd_history_list)

    history_show = history_sub.add_parser(
        "show",
        parents=[parent],
        help="Show a history entry.",
    )
    history_show.add_argument("id", metavar="<id>")
    history_show.set_defaults(func=_cmd_history_show)

    # service
    service_parser = subparsers.add_parser(
        "service",
        help="Service lifecycle.",
        epilog="Examples: apic service status | apic service token",
    )
    service_sub = service_parser.add_subparsers(dest="service_cmd", parser_class=_JSONErrorParser)

    service_status = service_sub.add_parser(
        "status",
        parents=[parent],
        help="Show service status.",
    )
    service_status.set_defaults(func=_cmd_service_status)

    service_stop = service_sub.add_parser(
        "stop",
        parents=[parent],
        help="Stop the service (stub).",
    )
    service_stop.set_defaults(func=_cmd_service_stop)

    service_token = service_sub.add_parser(
        "token",
        parents=[parent],
        help="Return service token (stub).",
    )
    service_token.set_defaults(func=_cmd_service_token)

    # schema / guide
    schema_parser = subparsers.add_parser(
        "schema",
        parents=[parent],
        help="Emit the self-describing JSON schema.",
        epilog="Use this to teach an agent the CLI surface.",
    )
    schema_parser.set_defaults(func=_cmd_schema)

    guide_parser = subparsers.add_parser(
        "guide",
        parents=[parent],
        help="Emit the plain-text agent guide.",
        epilog="Use this as an llms.txt-style quick reference.",
    )
    guide_parser.set_defaults(func=_cmd_guide)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    parser = _create_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.error("no command provided")
        return EXIT_USAGE_ERROR

    try:
        return args.func(args)
    except UnresolvedVariablesError as exc:
        _emit_error("UNRESOLVED_VARIABLES", str(exc), {"missing": exc.missing})
        return EXIT_USAGE_ERROR
    except NotFoundError as exc:
        _emit_error(exc.code, str(exc), {"candidates": exc.candidates})
        return EXIT_NOT_FOUND
    except ServiceError as exc:
        _emit_error("SERVICE_ERROR", str(exc))
        return EXIT_SERVICE_ERROR
    except BrokenPipeError:
        # Consumer closed stdout (e.g. piped to `head`).  Exit cleanly.
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
