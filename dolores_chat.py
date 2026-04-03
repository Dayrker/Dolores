#!/usr/bin/env python3
"""Dolores text-chat bootstrap with model fallback.

Phase-1 goal:
- Try Gemma 4 26B A4B first.
- Fallback to Gemma 4 E4B when needed.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


SYSTEM_PROMPT = (
    "You are Dolores, an emerging multimodal artificial consciousness prototype. "
    "For now, you only support text dialog but should provide clear and useful answers."
)


class OllamaClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint.rstrip("/")

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code} {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot reach Ollama endpoint {url}: {exc}") from exc

    def list_models(self) -> list[str]:
        url = f"{self.endpoint}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        models = payload.get("models", [])
        names = [m.get("name", "") for m in models if m.get("name")]
        return names

    def pull(self, model: str) -> None:
        self._request("/api/pull", {"name": model, "stream": False})

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        top_p: float,
        num_ctx: int,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
            },
        }
        result = self._request("/api/chat", payload)
        message = result.get("message", {})
        content = message.get("content", "")
        if not content:
            raise RuntimeError(f"Unexpected Ollama response: {result}")
        return content


def choose_model(
    available: list[str],
    primary: str,
    fallback: str,
) -> tuple[str | None, str | None]:
    if primary in available:
        return primary, None
    if fallback in available:
        return fallback, f"Primary model '{primary}' unavailable, fallback to '{fallback}'."
    return None, (
        f"Neither '{primary}' nor '{fallback}' is installed. "
        "Use --auto-pull or install model manually."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dolores phase-1 text chat")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434", help="Ollama API base URL")
    parser.add_argument("--primary", default="gemma4:26b-a4b", help="Primary model")
    parser.add_argument("--fallback", default="gemma4:e4b", help="Fallback model")
    parser.add_argument("--auto-pull", action="store_true", help="Auto pull fallback model when both missing")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--num-ctx", type=int, default=4096)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = OllamaClient(args.endpoint)

    available = client.list_models()
    active_model, warning = choose_model(available, args.primary, args.fallback)

    if active_model is None and args.auto_pull:
        print(f"[info] pulling fallback model '{args.fallback}'...")
        client.pull(args.fallback)
        active_model = args.fallback
        warning = f"Auto-pulled fallback model '{args.fallback}'."

    if active_model is None:
        print(
            "[error] No usable model found.\n"
            f"- primary: {args.primary}\n"
            f"- fallback: {args.fallback}\n"
            "Hint: start ollama and run `ollama pull <model>` first."
        )
        return 1

    if warning:
        print(f"[warn] {warning}")
    print(f"[ready] Dolores is online with model: {active_model}")
    print("Type /quit to exit, /model to show current model, /switch to fallback model.")

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[bye]")
            break

        if not user_text:
            continue
        if user_text == "/quit":
            print("[bye]")
            break
        if user_text == "/model":
            print(f"[model] {active_model}")
            continue
        if user_text == "/switch":
            active_model = args.fallback
            print(f"[model] switched to {active_model}")
            continue

        messages.append({"role": "user", "content": user_text})

        try:
            reply = client.chat(
                model=active_model,
                messages=messages,
                temperature=args.temperature,
                top_p=args.top_p,
                num_ctx=args.num_ctx,
            )
        except Exception as exc:
            err = str(exc)
            print(f"[error] {err}")
            if active_model != args.fallback:
                print(f"[info] trying fallback model '{args.fallback}'...")
                active_model = args.fallback
            continue

        print(f"dolores> {reply}")
        messages.append({"role": "assistant", "content": reply})

    return 0


if __name__ == "__main__":
    sys.exit(main())
