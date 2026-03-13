#!/usr/bin/env python3
"""
Agent CLI - connects to an LLM and answers questions with tool support.

Usage:
    uv run agent.py "Your question here"

Output (stdout):
    JSON with "answer", "source", and "tool_calls" fields.

All debug output goes to stderr.
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Constants
MAX_TOOL_CALLS = 10
PROJECT_ROOT = Path(__file__).parent


def load_env() -> None:
    """Load environment variables from .env.agent.secret."""
    env_file = PROJECT_ROOT / ".env.agent.secret"
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


# Tool definitions

def validate_path(path: str) -> tuple[bool, str]:
    """
    Validate that a path is safe (no directory traversal).
    
    Returns (is_valid, error_message).
    """
    if not path:
        return False, "Path cannot be empty"
    
    if path.startswith("/"):
        return False, "Absolute paths are not allowed"
    
    if ".." in path:
        return False, "Directory traversal (..) is not allowed"
    
    # Resolve and check it's within project root
    try:
        resolved = (PROJECT_ROOT / path).resolve()
        if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
            return False, f"Path escapes project directory: {path}"
    except (ValueError, OSError) as e:
        return False, f"Invalid path: {e}"
    
    return True, ""


def read_file(path: str) -> str:
    """
    Read a file from the project repository.
    
    Args:
        path: Relative path from project root.
    
    Returns:
        File contents or error message.
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"
    
    file_path = PROJECT_ROOT / path
    
    if not file_path.exists():
        return f"Error: File not found: {path}"
    
    if not file_path.is_file():
        return f"Error: Not a file: {path}"
    
    try:
        return file_path.read_text(encoding="utf-8")
    except (IOError, OSError) as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root.
    
    Returns:
        Newline-separated listing or error message.
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"
    
    dir_path = PROJECT_ROOT / path
    
    if not dir_path.exists():
        return f"Error: Directory not found: {path}"
    
    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"
    
    try:
        entries = sorted([e.name for e in dir_path.iterdir()])
        return "\n".join(entries)
    except (IOError, OSError) as e:
        return f"Error listing directory: {e}"


# Tool schema definitions for the LLM

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read documentation, code files, or any other file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a directory. Use this to discover what files exist in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

TOOLS_DICT = {
    "read_file": read_file,
    "list_files": list_files,
}


SYSTEM_PROMPT = """You are a helpful documentation assistant. You have access to tools that let you read files and list directories in a project repository.

When asked a question about the project:
1. Use `list_files` to discover what files exist if you're unsure where to look
2. Use `read_file` to read relevant files and find the answer
3. Provide a concise answer based on what you read
4. Always include the source reference (file path) in your answer

Think step by step. Only call tools when you need information you don't already have."""


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """
    Execute a tool and return the result.
    
    Args:
        tool_name: Name of the tool to execute.
        args: Arguments to pass to the tool.
    
    Returns:
        Tool result as a string.
    """
    if tool_name not in TOOLS_DICT:
        return f"Error: Unknown tool: {tool_name}"
    
    tool_func = TOOLS_DICT[tool_name]
    
    try:
        # Extract the 'path' argument
        path = args.get("path", "")
        return tool_func(path)
    except Exception as e:
        return f"Error executing {tool_name}: {e}"


def call_llm(messages: list[dict], config: dict, tools: list[dict]) -> dict:
    """
    Call the LLM API with tool support.
    
    Args:
        messages: List of message dicts for the conversation.
        config: LLM configuration dict.
        tools: List of tool schemas.
    
    Returns:
        Parsed LLM response dict.
    """
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if not choices:
                print("Error: No choices in LLM response", file=sys.stderr)
                return {"content": "Error: No response from LLM", "tool_calls": []}

            message = choices[0].get("message", {})
            return {
                "content": message.get("content"),
                "tool_calls": message.get("tool_calls", []),
            }

    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s)", file=sys.stderr)
        return {"content": "Error: Timeout", "tool_calls": []}
    except httpx.HTTPError as e:
        print(f"Error: HTTP error: {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response:
            print(f"Response: {e.response.text}", file=sys.stderr)
        return {"content": f"Error: HTTP error {e}", "tool_calls": []}


def extract_section_anchor(content: str, question: str) -> str:
    """
    Try to extract a section anchor from the content based on the question.
    
    Returns a section anchor like '#resolving-merge-conflicts' or empty string.
    """
    # Look for markdown headers that might match keywords in the question
    question_lower = question.lower()
    
    # Common keywords to look for
    keywords = {
        "merge conflict": "resolving-merge-conflicts",
        "conflict": "resolving-merge-conflicts",
        "commit": "commit-changes",
        "branch": "switch-to-the-task-branch",
        "pr": "create-a-pr-to-the-main-branch-in-your-fork",
        "pull request": "create-a-pr-to-the-main-branch-in-your-fork",
        "review": "get-a-pr-review",
        "push": "push-commits",
    }
    
    for keyword, anchor in keywords.items():
        if keyword in question_lower:
            return f"#{anchor}"
    
    # Try to find a header in the content
    header_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
    if header_match:
        header = header_match.group(1).lower()
        # Convert to anchor format
        anchor = header.replace(" ", "-").replace("`", "")
        return f"#{anchor}"
    
    return ""


def run_agentic_loop(question: str, config: dict) -> dict:
    """
    Run the agentic loop: call LLM, execute tools, repeat until final answer.
    
    Args:
        question: User's question.
        config: LLM configuration.
    
    Returns:
        Dict with answer, source, and tool_calls.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    all_tool_calls: list[dict] = []
    last_read_file_path: str = ""
    
    for iteration in range(MAX_TOOL_CALLS):
        print(f"\n--- Iteration {iteration + 1} ---", file=sys.stderr)
        
        # Call LLM
        response = call_llm(messages, config, TOOL_SCHEMAS)
        content = response.get("content")
        tool_calls = response.get("tool_calls", [])
        
        # If no tool calls, we have the final answer
        if not tool_calls:
            print(f"Final answer received", file=sys.stderr)
            
            # Determine source
            source = ""
            if last_read_file_path:
                anchor = extract_section_anchor("", question)
                source = f"{last_read_file_path}{anchor}"
            elif all_tool_calls:
                # Use the last read_file path if available
                for call in reversed(all_tool_calls):
                    if call["tool"] == "read_file":
                        source = call["args"].get("path", "")
                        break
            
            return {
                "answer": content or "No answer provided",
                "source": source,
                "tool_calls": all_tool_calls,
            }
        
        # Execute tool calls
        tool_messages = []
        for tc in tool_calls:
            tool_id = tc.get("id", str(uuid.uuid4()))
            function = tc.get("function", {})
            tool_name = function.get("name", "unknown")
            
            try:
                args = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            
            print(f"Executing tool: {tool_name} with args: {args}", file=sys.stderr)
            
            result = execute_tool(tool_name, args)
            
            # Track tool call for output
            tool_call_record = {
                "tool": tool_name,
                "args": args,
                "result": result,
            }
            all_tool_calls.append(tool_call_record)
            
            # Track last read_file path for source
            if tool_name == "read_file":
                last_read_file_path = args.get("path", "")
            
            # Prepare tool message for LLM
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result,
            })
        
        # Add assistant message with tool calls
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        })
        
        # Add tool response messages
        messages.extend(tool_messages)
    
    # Max iterations reached
    print("Max tool calls reached", file=sys.stderr)
    
    # Try to provide an answer based on collected information
    if all_tool_calls:
        # Use the last read file content as the answer source
        last_result = all_tool_calls[-1].get("result", "")
        source = last_read_file_path if last_read_file_path else ""
        return {
            "answer": f"Based on the files I examined: {last_result[:500]}..." if len(last_result) > 500 else f"Based on the files I examined: {last_result}",
            "source": source,
            "tool_calls": all_tool_calls,
        }
    
    return {
        "answer": "I was unable to find an answer after multiple tool calls.",
        "source": "",
        "tool_calls": all_tool_calls,
    }


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

    # Run agentic loop
    result = run_agentic_loop(question, config)

    # Output JSON to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
