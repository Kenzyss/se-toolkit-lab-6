# Task 1: Call an LLM from Code

## LLM Provider

**Provider:** Qwen Code API (on VM)  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.25.198:42005/v1`

**Why Qwen Code API:**
- 1000 free requests per day
- Available in Russia
- No credit card required
- Already deployed on the VM

## Architecture

### Components

1. **CLI Entry Point** (`agent.py`)
   - Parse command-line argument (the question)
   - Load environment variables from `.env.agent.secret`
   - Call the LLM API
   - Format and output JSON response

2. **LLM Client**
   - Use `httpx` (already in dependencies) for HTTP requests
   - Send POST request to `/chat/completions` endpoint
   - OpenAI-compatible format

3. **Response Parser**
   - Extract the answer from LLM response
   - Format as JSON with `answer` and `tool_calls` fields

### Data Flow

```
Command line → agent.py → httpx → Qwen Code API → LLM → JSON response → stdout
                              ↓
                          stderr (debug logs)
```

### Input/Output

**Input:**
```bash
uv run agent.py "What does REST stand for?"
```

**Output (stdout):**
```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

### Error Handling

- Missing API key → exit with error message to stderr
- API timeout (60s) → exit with error message to stderr
- Invalid JSON → exit with error message to stderr

### Testing Strategy

One regression test (`tests/test_agent.py`):
- Run `agent.py` as subprocess with a test question
- Parse stdout JSON
- Verify `answer` field exists and is non-empty
- Verify `tool_calls` field exists and is an array

## Implementation Steps

1. Create `.env.agent.secret` with Qwen Code API credentials
2. Create `agent.py` with:
   - Argument parsing (`sys.argv`)
   - Environment loading (`python-dotenv`)
   - HTTP request to LLM API
   - JSON output formatting
3. Create `AGENT.md` documentation
4. Create `tests/test_agent.py` regression test
5. Test manually and with pytest
