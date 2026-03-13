# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM API and answers questions using an **agentic loop** with tool support. The agent can read files and list directories to find answers in the project documentation.

## LLM Provider

**Provider:** OpenRouter  
**Model:** `meta-llama/llama-3.3-70b-instruct:free`  
**API Base:** `https://openrouter.ai/api/v1`

### Why OpenRouter?

- Free tier available (50 requests/day)
- No VM setup required
- OpenAI-compatible API format with tool calling support
- Good model quality for the lab tasks

> **Note:** For production use with higher rate limits, consider Qwen Code API (1000 requests/day).

## Architecture

### Components

1. **CLI Entry Point** (`agent.py`)
   - Parses command-line arguments using `sys.argv`
   - Loads environment variables from `.env.agent.secret`
   - Orchestrates the agentic loop

2. **Environment Loader**
   - Uses `python-dotenv` to load `.env.agent.secret`
   - Validates that all required variables are present

3. **LLM Client**
   - Uses `httpx` for HTTP requests
   - Sends POST requests to `/chat/completions` endpoint
   - Supports OpenAI-compatible tool calling API

4. **Tools**
   - `read_file`: Read file contents from the project
   - `list_files`: List directory contents

5. **Agentic Loop**
   - Iteratively calls LLM and executes tools
   - Maximum 10 tool calls per question
   - Feeds tool results back to LLM for reasoning

### Data Flow

```
Question → agent.py
           ↓
     [Agentic Loop]
           ↓
    1. Send question + tool schemas to LLM
           ↓
    2. LLM returns tool_calls or final answer
           ↓
    3. If tool_calls: execute tools → back to step 1
           ↓
    4. If answer: extract source → output JSON
           ↓
     JSON output to stdout
     (debug logs to stderr)
```

## Tools

### `read_file`

**Purpose:** Read the contents of a file from the project repository.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative path from project root (e.g., `wiki/git-workflow.md`) |

**Returns:** File contents as a string, or an error message if the file doesn't exist.

**Security:**
- Rejects paths containing `..` (directory traversal)
- Rejects absolute paths
- Verifies resolved path is within project root

### `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative directory path from project root (e.g., `wiki`) |

**Returns:** Newline-separated listing of entries, or an error message.

**Security:**
- Rejects paths containing `..` (directory traversal)
- Rejects absolute paths
- Verifies resolved path is within project root

### Tool Schemas

Tools are registered with the LLM using OpenAI-compatible function schemas:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file...",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "..."}
      },
      "required": ["path"]
    }
  }
}
```

## Agentic Loop

The agentic loop enables multi-turn reasoning with tool execution:

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question}
]

for iteration in range(MAX_TOOL_CALLS):  # max 10
    # 1. Call LLM with messages and tool schemas
    response = call_llm(messages, config, TOOL_SCHEMAS)
    
    # 2. If no tool calls → final answer
    if not response.tool_calls:
        return format_answer(response.content)
    
    # 3. Execute each tool call
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call.name, tool_call.args)
        all_tool_calls.append({...})
    
    # 4. Append tool messages and continue
    messages.append({"role": "assistant", "tool_calls": ...})
    messages.append({"role": "tool", "content": result, ...})
```

### Message Format

The conversation uses the OpenAI tool-calling message format:

```python
# User message
{"role": "user", "content": "How do I resolve a merge conflict?"}

# Assistant response with tool calls
{"role": "assistant", "content": None, "tool_calls": [
    {"id": "call_123", "function": {"name": "read_file", "arguments": '{"path": "wiki/git-workflow.md"}'}}
]}

# Tool result
{"role": "tool", "tool_call_id": "call_123", "content": "...file contents..."}
```

## System Prompt Strategy

The system prompt guides the LLM to use tools effectively:

```
You are a helpful documentation assistant. You have access to tools 
that let you read files and list directories in a project repository.

When asked a question about the project:
1. Use `list_files` to discover what files exist if you're unsure where to look
2. Use `read_file` to read relevant files and find the answer
3. Provide a concise answer based on what you read
4. Always include the source reference (file path) in your answer
```

## Input/Output

### Input

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output (stdout)

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Wiki file reference with optional section anchor |
| `tool_calls` | array | All tool calls made during the agentic loop |

### Error Output (stderr)

All debug and error messages are written to stderr.

## Configuration

### Environment Variables

Create `.env.agent.secret` by copying `.env.agent.example`:

```bash
cp .env.agent.example .env.agent.secret
```

Then edit `.env.agent.secret`:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | Your API key | `sk-or-...` |
| `LLM_API_BASE` | API base URL | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Model name | `meta-llama/llama-3.3-70b-instruct:free` |

## How to Run

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.agent.example .env.agent.secret
   # Edit .env.agent.secret with your credentials
   ```

3. **Run the agent:**
   ```bash
   uv run agent.py "Your question here"
   ```

## Error Handling

- **Missing API key:** Exits with error message to stderr
- **API timeout (60s):** Exits with timeout error to stderr
- **Invalid response:** Exits with error message to stderr
- **Missing arguments:** Shows usage instructions to stderr
- **Path traversal attempts:** Blocked by security validation
- **Max tool calls (10):** Returns partial answer with collected information

## Security

### Path Security

Both tools implement path security to prevent directory traversal:

1. **Reject `..` patterns:** Any path containing `..` is rejected
2. **Reject absolute paths:** Paths starting with `/` are rejected
3. **Resolve and verify:** The path is resolved and checked to be within the project root using `Path.is_relative_to()`

```python
def validate_path(path: str) -> tuple[bool, str]:
    if ".." in path:
        return False, "Directory traversal not allowed"
    if path.startswith("/"):
        return False, "Absolute paths not allowed"
    
    resolved = (PROJECT_ROOT / path).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        return False, "Path escapes project directory"
    
    return True, ""
```

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- Valid JSON output with `answer`, `source`, and `tool_calls` fields
- Correct tool usage for documentation questions
- Tool calls are populated when tools are used

## Future Extensions (Task 3)

- **Additional tools:** `query_api` to query the backend LMS
- **Enhanced system prompt:** More detailed instructions for complex queries
- **Better source extraction:** Improved section anchor detection
- **Caching:** Cache file reads to reduce redundant tool calls
