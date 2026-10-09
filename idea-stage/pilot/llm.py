"""Minimal headless-LLM helper for API-only (no-GPU) pilots.

Calls the `claude` CLI in print mode. Used both as a rubric judge and as a
response generator. Results are cached on disk keyed by (model, prompt) so
pilots can be resumed without re-billing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CACHE = Path(os.environ.get("PILOT_CACHE", Path(__file__).parent / ".cache"))
CACHE.mkdir(parents=True, exist_ok=True)
# Lean mode: no MCP servers, no tools, no settings/plugins -> ~45% less CPU per call on a 4-core box.
# Pilots started before this flag existed (pilot 0/0b/0c, bank variants, pilot 1 stage B) ran in default mode.
LEAN = os.environ.get("PILOT_LEAN", "1") == "1"
LEAN_FLAGS = ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence",
              "--tools", "", "--setting-sources", ""]


def call(prompt: str, model: str = "claude-haiku-5-5", timeout: int = 240, retries: int = 2) -> str:
    tag = f"{model}+lean" if LEAN else model
    key = hashlib.sha256(f"{tag}\n{prompt}".encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["out"]
    last = ""
    for _ in range(retries + 1):
        try:
            proc = subprocess.run(
                ["claude", "-p", "--model", model, "--output-format", "text"] + (LEAN_FLAGS if LEAN else []),
                input=prompt, capture_output=True, text=True, timeout=timeout, cwd="/tmp",
            )
            last = proc.stdout.strip()
            if proc.returncode == 0 and last:
                path.write_text(json.dumps({"model": model, "out": last}))
                return last
        except subprocess.TimeoutExpired:
            last = ""
    return last


def call_many(prompts: list[str], model: str = "claude-haiku-5-5", workers: int = 8) -> list[str]:
    workers = min(workers, int(os.environ.get("PILOT_MAX_WORKERS", "10")))
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda p: call(p, model), prompts))


def extract_json(text: str):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = m.group(1) if m else text
    start = min([i for i in (body.find("{"), body.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no json")
    end = max(body.rfind("}"), body.rfind("]"))
    return json.loads(body[start : end + 1])
