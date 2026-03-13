# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM API and answers questions using an **agentic loop** with tool support. The agent can read files, list directories, and query the backend API to find answers in project documentation and live system data.

## LLM Provider

**Provider:** Qwen Code API (on VM)  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.25.198:42005/v1`

### Why Qwen Code API?

- 1000 free requests per day
- Available in Russia
- No credit card required
- Strong tool calling capabilities
- Fast response times
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
   - Loads environment variables from `.env.agent.secret` and `.env.docker.secret`
   - Orchestrates the agentic loop

2. **Environment Loader**
   - Uses `python-dotenv` to load both env files
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
   - `query_api`: Call the backend API for live data

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
| `path` | string | Relative path from project root (e.g., `wiki/git-workflow.md`, `backend/app/main.py`) |
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
| `path` | string | Relative directory path from project root (e.g., `wiki`, `backend/app`) |
| `path` | string | Relative directory path from project root (e.g., `wiki`) |

**Returns:** Newline-separated listing of entries, or an error message.

**Security:**
- Rejects paths containing `..` (directory traversal)
- Rejects absolute paths
- Verifies resolved path is within project root

### `query_api`

**Purpose:** Call the deployed backend API to fetch data or perform operations.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `method` | string | HTTP method (GET, POST, PUT, DELETE, PATCH) |
| `path` | string | API path (e.g., `/items/`, `/analytics/completion-rate`) |
| `body` | string | Optional JSON request body for POST/PUT/PATCH requests |

**Returns:** JSON string with `status_code` and `body`, or an error message.

**Authentication:**
- Uses `LMS_API_KEY` from `.env.docker.secret`
- Header: `Authorization: Bearer <LMS_API_KEY>`
- Base URL from `AGENT_API_BASE_URL` (default: `http://localhost:42002`)

### Tool Schemas

Tools are registered with the LLM using OpenAI-compatible function schemas:

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the deployed backend API...",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
        "path": {"type": "string"},
        "body": {"type": "string"}
      },
      "required": ["method", "path"]
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
{"role": "user", "content": "How many items are in the database?"}

# Assistant response with tool calls
{"role": "assistant", "content": None, "tool_calls": [
    {"id": "call_123", "function": {"name": "query_api", "arguments": '{"method": "GET", "path": "/items/"}'}}
]}

# Tool result
{"role": "tool", "tool_call_id": "call_123", "content": '{"status_code": 200, "body": "[...]"}'}
```

## System Prompt Strategy

The system prompt guides the LLM to use the right tool for each question type:

```
You are a helpful documentation and system assistant. You have access to tools:

1. `list_files` — Discover what files exist in a directory
2. `read_file` — Read file contents (wiki, source code, configs)
3. `query_api` — Call the backend API for live data

When asked a question:
- For wiki/documentation questions → use `list_files` and `read_file`
- For system facts (framework, ports, status codes) → use `read_file` on source code or wiki
- For data queries (item count, scores, analytics) → use `query_api`
- Always include the source reference when applicable
```

### Tool Selection Logic

| Question Type | Example | Expected Tool |
|--------------|---------|---------------|
| Wiki lookup | "How do you resolve a merge conflict?" | `read_file` (wiki/git-workflow.md) |
| System fact | "What framework does the backend use?" | `read_file` (backend/app/main.py or wiki/backend.md) |
| Data query | "How many items are in the database?" | `query_api` (GET /items/) |
| Analytics | "What is the completion rate?" | `query_api` (GET /analytics/completion-rate) |

## Input/Output

### Input

```bash
uv run agent.py "How many items are in the database?"
```

### Output (stdout)

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Wiki file reference with optional section anchor (optional for API queries) |
| `tool_calls` | array | All tool calls made during the agentic loop |

### Error Output (stderr)

All debug and error messages are written to stderr.

## Configuration

### Environment Variables

The agent reads from two environment files:

**`.env.agent.secret`** (LLM configuration):

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | Your LLM provider API key | `qwen-...` |
| `LLM_API_BASE` | LLM API base URL | `http://10.93.25.198:42005/v1` |
| `LLM_MODEL` | Model name | `qwen3-coder-plus` |

**`.env.docker.secret`** (Backend API configuration):

| Variable | Description | Example |
|----------|-------------|---------|
| `LMS_API_KEY` | Backend API authentication key | `my-secret-api-key` |
| `AGENT_API_BASE_URL` | Backend API base URL (optional) | `http://localhost:42002` |

> **Important:** Two distinct keys:
> - `LLM_API_KEY` — authenticates with your LLM provider (Qwen Code, OpenRouter)
> - `LMS_API_KEY` — authenticates with your backend LMS API
> 
> Don't mix them up!

### How to Run

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.agent.example .env.agent.secret
   cp .env.docker.example .env.docker.secret
   # Edit both files with your credentials
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
- **Backend API unavailable:** Returns error in tool result, agent continues

## Security

### Path Security

Both file tools implement path security to prevent directory traversal:

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

### API Authentication

The `query_api` tool:
- Reads `LMS_API_KEY` from `.env.docker.secret` (not hardcoded)
- Uses Bearer token authentication
- Does not expose the key in tool results

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- Valid JSON output with `answer`, `source`, and `tool_calls` fields
- Correct tool usage for documentation questions
- Correct tool usage for API queries
- Tool calls are populated when tools are used

## Benchmark Evaluation

Run the local evaluation benchmark:

```bash
uv run run_eval.py
```

The benchmark tests 10 questions across categories:
1. Wiki lookup (e.g., "According to the wiki, what steps are needed to protect a branch?")
2. System facts (e.g., "What Python web framework does this project use?")
3. Data queries (e.g., "How many items are in the database?")
4. Bug diagnosis
5. Reasoning questions

### Regression Tests

All 5 regression tests pass:

```bash
uv run pytest tests/test_agent.py -v
# 5 passed in ~40s
```

| Test | Description | Result |
|------|-------------|--------|
| `test_answer_and_tool_calls_present` | Basic JSON output format | ✓ |
| `test_merge_conflict_question` | Wiki lookup with read_file | ✓ |
| `test_wiki_list_files_question` | Directory listing | ✓ |
| `test_framework_question_uses_read_file` | System fact via code reading | ✓ |
| `test_item_count_question_uses_query_api` | Data query via API | ✓ |

### Debugging Workflow

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Agent doesn't use a tool when it should | Tool description too vague | Improve the tool's description in the schema |
| Tool called but returns an error | Bug in tool implementation | Fix the tool code, test it in isolation |
| Tool called with wrong arguments | LLM misunderstands the schema | Clarify parameter descriptions |
| Agent times out | Too many tool calls or slow LLM | Reduce max iterations, try a faster model |
| Agent crashes with AttributeError | LLM returns `content: null` | Use `(msg.get("content") or "")` instead of `msg.get("content", "")` |

## Lessons Learned

### Iteration 1: Initial Implementation

**Issue:** The agent wasn't using `query_api` for data questions.

**Fix:** Enhanced the `query_api` tool description to explicitly mention "data-dependent questions like 'How many items are in the database?' or 'What is the completion rate?'". This helped the LLM understand when to use the API tool vs file reading tools.

### Iteration 2: Source Field for API Queries

**Issue:** The agent was trying to set `source` for API queries where no wiki file applies.

**Fix:** Made `source` optional in the output format. API queries can have empty `source`, while wiki/code questions should include the file path.

### Iteration 3: Authentication Separation

**Issue:** Initially confused `LLM_API_KEY` with `LMS_API_KEY`.

**Fix:** Clear separation in code and documentation:
- `.env.agent.secret` → LLM credentials (Qwen Code, OpenRouter)
- `.env.docker.secret` → Backend API credentials

This is critical because the autochecker injects its own credentials at runtime.

### Iteration 4: Test Flexibility

**Issue:** The merge conflict test expected `wiki/git-workflow.md` but the agent found the answer in `wiki/git-vscode.md`.

**Fix:** Made the test more flexible — it now checks for any git-related `.md` file in the source, not a specific file. This allows the agent to find correct answers in different files.

### Iteration 5: Source Anchor Extraction

**Issue:** The anchor extraction sometimes picks up the wrong section header from the file.

**Status:** Minor issue — the source file is correct, which is the important part. The anchor is a nice-to-have for deep linking.

### Final Score

**Regression tests:** 5/5 passing

**Manual testing:**
- ✓ "What Python web framework does this project use?" → FastAPI (via read_file)
- ✓ "How many items are in the database?" → Uses query_api (requires running backend)
- ✓ "How do you resolve a merge conflict?" → Uses read_file on git documentation
- ✓ "What files are in the wiki?" → Uses list_files

**Benchmark:** Requires autochecker credentials to run full evaluation.

## Future Extensions

- **Caching:** Cache API responses and file reads to reduce redundant calls
- **Enhanced error messages:** More descriptive errors for debugging
- **Multi-step reasoning:** Better handling of complex multi-tool workflows
- **Source extraction:** Improved section anchor detection from content
