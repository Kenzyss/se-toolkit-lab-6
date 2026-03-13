# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM API and answers questions. It forms the foundation for the agentic system that will be extended with tools in subsequent tasks.

## LLM Provider

**Provider:** OpenRouter  
**Model:** `meta-llama/llama-3.3-70b-instruct:free`  
**API Base:** `https://openrouter.ai/api/v1`

### Why OpenRouter?

- Free tier available (50 requests/day)
- No VM setup required
- OpenAI-compatible API format
- Good model quality for the lab tasks

> **Note:** For production use with higher rate limits, consider Qwen Code API (1000 requests/day).

## Architecture

### Components

1. **CLI Entry Point** (`agent.py`)
   - Parses command-line arguments using `sys.argv`
   - Loads environment variables from `.env.agent.secret`
   - Orchestrates the request flow

2. **Environment Loader**
   - Uses `python-dotenv` to load `.env.agent.secret`
   - Validates that all required variables are present

3. **LLM Client**
   - Uses `httpx` for HTTP requests
   - Sends POST requests to `/chat/completions` endpoint
   - Follows OpenAI-compatible API format

4. **Response Parser**
   - Extracts the answer from the LLM response
   - Formats output as JSON with `answer` and `tool_calls` fields

### Data Flow

```
Command line argument → agent.py
                      ↓
                Load .env.agent.secret
                      ↓
                Build API request
                      ↓
                httpx POST → OpenRouter API
                      ↓
                Parse JSON response
                      ↓
                Output JSON to stdout
                      ↓
                (debug logs to stderr)
```

## Input/Output

### Input

```bash
uv run agent.py "What does REST stand for?"
```

### Output (stdout)

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

### Error Output (stderr)

All debug and error messages are written to stderr to keep stdout clean for JSON parsing.

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

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py -v
```

The test verifies that:
- `agent.py` outputs valid JSON
- The `answer` field is present and non-empty
- The `tool_calls` field is present and is an array

## Future Extensions (Tasks 2-3)

- **Tools:** Add `read_file`, `list_files`, `query_api` tools
- **Agentic loop:** Implement tool execution and multi-turn reasoning
- **System prompt:** Expand with domain knowledge and tool instructions
- **Wiki integration:** Enable the agent to read project documentation
