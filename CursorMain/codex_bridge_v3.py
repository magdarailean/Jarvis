"""Bounded, cancellable stdio client for the locally authenticated Codex CLI."""
from collections import deque
import copy
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

import diagnostics_v2 as diagnostics


BASE_DIR = Path(__file__).resolve().parent


class CodexCancelled(Exception):
    pass


class CodexProtocolError(RuntimeError):
    pass


def strict_schema(schema):
    schema = copy.deepcopy(schema)

    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(schema)
    return schema


def find_codex(explicit=None):
    binary = explicit or os.environ.get("JARVIS_CODEX_BIN") or shutil.which("codex")
    if not binary:
        raise FileNotFoundError("Codex CLI not found. Add codex.exe to PATH or pass --codex-bin.")
    path = Path(binary).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in (".exe", ""):
        raise FileNotFoundError("Use the Codex executable, rather than a shell/batch wrapper.")
    return str(path)


class CodexSession:
    """One ephemeral analysis request. Never read or copy authentication files."""
    def __init__(self, cancelled=None, timeout=120, binary=None, process_factory=subprocess.Popen):
        self.cancelled = cancelled or threading.Event()
        self.timeout, self.binary, self.process_factory = timeout, binary, process_factory
        self.process = None
        self.messages = queue.Queue()
        self.pending = deque()
        self.next_id = 0
        self.stage = "startup"
        self.thread_id = self.turn_id = None
        self.deadline = None

    def _pump(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except (ValueError, TypeError):
                    self.messages.put(CodexProtocolError("Codex stdout contains a non-JSON message."))
                    return
                self.messages.put(message)
        except (OSError, ValueError):
            pass  # Closing a cancelled process can close a pipe during readline.
        finally:
            self.messages.put(CodexProtocolError("Codex app-server closed its output stream."))

    def _drain_stderr(self):
        # Runtime logs can contain private context. Consume them without echoing.
        try:
            for _ in self.process.stderr:
                pass
        except (OSError, ValueError):
            pass

    def _check(self):
        if self.cancelled.is_set():
            raise CodexCancelled("Analysis cancelled.")
        if time.monotonic() >= self.deadline:
            raise TimeoutError(f"Codex exceeded {self.timeout:g}s at stage {self.stage}.")

    def _receive(self):
        while True:
            self._check()
            try:
                message = self.messages.get(timeout=min(.1, max(.001, self.deadline - time.monotonic())))
            except queue.Empty:
                continue
            if isinstance(message, Exception):
                raise message
            if not isinstance(message, dict):
                raise CodexProtocolError("Expected a JSON object from Codex.")
            if "method" in message and "id" in message:
                # No interactive permissions or external tool execution in a pointer app.
                self._send({"id": message["id"], "error": {
                    "code": -32601, "message": "This client does not permit tools or approval requests."
                }})
                continue
            return message

    def _send(self, message):
        self._check()
        self.process.stdin.write(json.dumps(message, ensure_ascii=True) + "\n")
        self.process.stdin.flush()

    def _rpc(self, method, params):
        self.next_id += 1
        identifier = self.next_id
        self._send({"id": identifier, "method": method, "params": params})
        while True:
            message = self._receive()
            if message.get("id") == identifier:
                if "error" in message:
                    error = message["error"]
                    raise CodexProtocolError(f"{method}: {error.get('code')}: {error.get('message')}")
                return message.get("result", {})
            if "method" in message:
                self.pending.append(message)

    def _start(self):
        self.deadline = time.monotonic() + self.timeout
        self._check()
        binary = find_codex(self.binary)
        self.process = self.process_factory(
            [binary, "app-server", "--listen", "stdio://", "-c", "mcp_servers={}",
             "-c", 'web_search="disabled"'],
            cwd=str(BASE_DIR), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        threading.Thread(target=self._pump, daemon=True, name="codex-json").start()
        threading.Thread(target=self._drain_stderr, daemon=True, name="codex-errors").start()
        self.stage = "initialize"
        self._rpc("initialize", {
            "clientInfo": {"name": "jarvis_pointer_v3", "title": "Jarvis pointer", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True},
        })
        self._send({"method": "initialized", "params": {}})
        self.stage = "authentication"
        account = self._rpc("account/read", {"refreshToken": False}).get("account")
        if not account or account.get("type") != "chatgpt":
            raise CodexProtocolError("ChatGPT login required. Run codex login, then restart the companion.")
        diagnostics.event("codex.auth.ready", authentication="chatgpt")

    @staticmethod
    def final_message(items):
        final = [item.get("text", "") for item in items
                 if item.get("type") == "agentMessage" and item.get("phase") in (None, "final_answer")]
        return final[-1] if final else ""

    def analyze(self, prompt, image_url, schema, model=None):
        try:
            self._start()
            self.stage = "thread_start"
            params = {
                "cwd": str(BASE_DIR), "modelProvider": "openai", "ephemeral": True,
                "approvalPolicy": "never", "sandbox": "read-only", "environments": [],
                "baseInstructions": "You analyze screenshots and return the requested JSON. Never use tools, inspect files, execute commands, or change the computer.",
                "developerInstructions": "Use only the supplied image and task context. Return one JSON decision, without commentary.",
                "config": {"web_search": "disabled", "mcp_servers": {},
                           "features": {"shell_tool": False, "code_mode": False}},
            }
            if model:
                params["model"] = model
            thread = self._rpc("thread/start", params)
            self.thread_id = thread["thread"]["id"]
            diagnostics.event("codex.thread.ready", ephemeral=thread["thread"].get("ephemeral"),
                              model=thread.get("model", model or "configured-default"))
            self.stage = "turn_start"
            turn = self._rpc("turn/start", {
                "threadId": self.thread_id, "input": [
                    {"type": "text", "text": prompt}, {"type": "image", "url": image_url},
                ], "outputSchema": strict_schema(schema), "effort": "low", "environments": [],
                "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly"},
            })
            self.turn_id = turn["turn"]["id"]
            self.stage = "inference"
            completed_items = []
            while True:
                self._check()
                message = self.pending.popleft() if self.pending else self._receive()
                params = message.get("params", {})
                if params.get("threadId") not in (None, self.thread_id):
                    continue
                method = message.get("method")
                if method == "item/completed" and params.get("turnId") == self.turn_id:
                    completed_items.append(params.get("item", {}))
                elif method == "turn/completed" and params.get("turn", {}).get("id") == self.turn_id:
                    result = params["turn"]
                    if result.get("status") != "completed":
                        error = result.get("error") or {}
                        raise CodexProtocolError(f"Codex turn {result.get('status')}: {error.get('message', 'no details')}")
                    text = self.final_message(result.get("items", [])) or self.final_message(completed_items)
                    if not text:
                        raise CodexProtocolError("Completed turn has no final assistant JSON.")
                    return text
                elif method == "error" and params.get("willRetry") is False:
                    error = params.get("error") or {}
                    raise CodexProtocolError(error.get("message", "Codex inference failed."))
        finally:
            self.close()

    def close(self):
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            # Closing this dedicated sidecar cancels its in-flight request.
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe:
                pipe.close()
        self.process = None
