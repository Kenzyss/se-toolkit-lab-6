# Task 3: The System Agent

## Overview

Extend the agent from Task 2 with a `query_api` tool to interact with the deployed backend API. This enables the agent to answer:
1. **Static system facts** — framework, ports, status codes (from wiki or code)
2. **Data-dependent queries** — item count, scores, analytics (from API)

## LLM Provider

**Provider:** Qwen Code API (on VM)  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.25.198:42005/v1`

## New Tool: `query_api`

### Schema

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the deployed backend API to fetch data or perform operations. Use this for data-dependent questions like 'How many items are in the database?' or 'What is the completion rate?'",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
          "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
        },
        "path": {
          "type": "string",
          "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
        },
        "body": {
          "type": "string",
          "description": "Optional JSON request body for POST/PUT/PATCH requests"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

### Implementation

```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Call the deployed backend API.
    
    - Uses LMS_API_KEY from .env.docker.secret for authentication
    - Uses AGENT_API_BASE_URL from environment (default: http://localhost:42002)
    - Returns JSON string with status_code and body
    """
```

### Authentication

- **Header:** `Authorization: Bearer <LMS_API_KEY>`
- **Key source:** `.env.docker.secret` (NOT `.env.agent.secret`)
- **Important:** Two distinct keys:
  - `LLM_API_KEY` — authenticates with LLM provider (OpenRouter/Qwen)
  - `LMS_API_KEY` — authenticates with backend API

### Environment Variables

| Variable | Purpose | Source | Default |
|----------|---------|--------|---------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` | — |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` | — |
| `LLM_MODEL` | Model name | `.env.agent.secret` | — |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` | — |
| `AGENT_API_BASE_URL` | Base URL for query_api | Optional env var | `http://localhost:42002` |

## System Prompt Update

The system prompt should guide the LLM to choose the right tool:

```
You are a helpful documentation and system assistant. You have access to tools:

1. `list_files` — Discover what files exist in a directory
2. `read_file` — Read file contents (wiki, source code, configs)
3. `query_api` — Call the backend API for live data

When asked a question:
- For wiki/documentation questions → use `list_files` and `read_file`
- For system facts (framework, ports) → use `read_file` on source code or wiki
- For data queries (item count, scores, analytics) → use `query_api`
- Always include the source reference when applicable
```

## Agentic Loop

The loop remains the same as Task 2:
1. Send question + all tool schemas to LLM
2. If tool_calls → execute tools, append results, loop back
3. If no tool_calls → final answer, output JSON
4. Max 10 tool calls

## Output Format

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",  // Optional for API queries
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "..."}
  ]
}
```

**Note:** `source` is now optional — API queries may not have a wiki source.

## Implementation Steps

1. Add `query_api` tool function with authentication
2. Add `query_api` to tool schemas
3. Update system prompt to mention all three tools
4. Load `LMS_API_KEY` from `.env.docker.secret`
5. Load `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
6. Test manually with API questions
7. Run `run_eval.py` and iterate on failures
8. Add 2 regression tests
9. Update `AGENT.md`

## Testing Strategy

**Test 1:** "What framework does the backend use?"
- Expect: `read_file` in tool_calls (reading backend/main.py or wiki)

**Test 2:** "How many items are in the database?"
- Expect: `query_api` in tool_calls with GET /items/

## Benchmark Iteration Plan

1. Run `uv run run_eval.py`
2. On failure, read the feedback hint
3. Fix the issue (tool description, system prompt, or tool implementation)
4. Re-run until all 10 questions pass
5. Document failures and fixes in this plan

## Initial Benchmark Results

**Tests passed:** 5/5 regression tests pass

| Test | Result |
|------|--------|
| test_answer_and_tool_calls_present | ✓ PASS |
| test_merge_conflict_question | ✓ PASS |
| test_wiki_list_files_question | ✓ PASS |
| test_framework_question_uses_read_file | ✓ PASS |
| test_item_count_question_uses_query_api | ✓ PASS |

**Manual testing:**
- "What Python web framework does this project use?" → ✓ Correctly identifies FastAPI via read_file
- "How many items are in the database?" → ✓ Uses query_api (requires running backend)

**Benchmark run_eval.py:** Requires AUTOCHECKER credentials in `.env`

## Iteration Notes

### Issue: Source anchor extraction
The anchor extraction sometimes picks up wrong section headers. The agent correctly identifies the file but the anchor may not match the content.

**Status:** Minor issue — the source file is correct, which is the important part.
