#!/usr/bin/env python3
"""
Agent CLI - connects to an LLM and answers questions.

Usage:
    uv run agent.py "Your question here"

Output (stdout):
    JSON with "answer" and "tool_calls" fields.

All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


def load_env() -> None:
    """Load environment variables from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        print("Copy .env.agent.example to .env.agent.secret and fill in your credentials", file=sys.stderr)
        sys.exit(1)
    load_dotenv(env_file)


def get_llm_config() -> dict:
    """Get LLM configuration from environment variables."""
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        print("Error: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not api_base:
        print("Error: LLM_API_BASE not set", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set", file=sys.stderr)
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_base": api_base.rstrip("/"),
        "model": model,
    }


def call_lllm(question: str, config: dict) -> str:
    """Call the LLM API and return the answer."""
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract answer from response
            choices = data.get("choices", [])
            if not choices:
                print("Error: No choices in LLM response", file=sys.stderr)
                sys.exit(1)

            answer = choices[0].get("message", {}).get("content", "")
            if not answer:
                print("Error: Empty answer from LLM", file=sys.stderr)
                sys.exit(1)

            return answer

    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"Error: HTTP error: {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    # Parse command-line argument
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    load_env()
    config = get_llm_config()

    print(f"Question: {question}", file=sys.stderr)

    # Call LLM
    answer = call_lllm(question, config)

    # Output JSON to stdout
    result = {
        "answer": answer,
        "tool_calls": [],
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
