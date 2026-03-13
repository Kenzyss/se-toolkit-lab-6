# Task 2: The Documentation Agent

## Overview

Extend the agent from Task 1 with two tools (`read_file`, `list_files`) and implement an agentic loop that allows the LLM to call tools iteratively before producing a final answer.

## LLM Provider

**Provider:** Qwen Code API (on VM)  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.25.198:42005/v1`

## Tool Definitions

### `read_file`

**Purpose:** Read a file from the project repository.

**Schema:**
```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file from the project repository",
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
}
```

**Implementation:**
- Use `Path` to resolve the path relative to project root
- Security: reject paths containing `..` or absolute paths
- Return file contents or error message

### `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "type": "function",
  "function": {
    "name": "list_files",
    "description": "List files and directories in a directory",
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
```

**Implementation:**
- Use `Path.iterdir()` to list entries
- Security: reject paths containing `..` or absolute paths
- Return newline-separated list of entries

## Path Security

Both tools must prevent directory traversal attacks:

1. Reject any path containing `..`
2. Reject absolute paths (starting with `/`)
3. Resolve the path and verify it's within project root using `Path.resolve()` and `is_relative_to()`

## Agentic Loop

```
1. Send user question + tool schemas to LLM
2. Parse response:
   - If tool_calls present:
     a. Execute each tool
     b. Append results as tool messages
     c. Loop back to step 1 (max 10 iterations)
   - If no tool_calls:
     a. Extract final answer
     b. Determine source from tool calls made
     c. Output JSON and exit
```

**Message format:**
```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question}
]
# After each tool call:
messages.append({"role": "assistant", "content": None, "tool_calls": [...]})
messages.append({"role": "tool", "content": result, "tool_call_id": "..."})
```

## System Prompt Strategy

The system prompt should instruct the LLM to:
1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read relevant wiki files
3. Extract the answer and include the source reference (file path with section anchor)
4. Only call tools when needed; don't over-use them

## Output Format

```json
{
  "answer": "...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Implementation Steps

1. Define tool schemas as Python dictionaries
2. Implement `read_file()` and `list_files()` functions with security checks
3. Implement `execute_tool()` dispatcher
4. Rewrite `call_llm()` to support tool calling with function-calling API
5. Implement agentic loop with max 10 iterations
6. Track all tool calls for output
7. Extract source from tool calls (last read_file path + section if found)
8. Update output JSON to include `source` and `tool_calls`
9. Create 2 regression tests
10. Update AGENT.md documentation

## Testing Strategy

**Test 1:** "How do you resolve a merge conflict?"
- Expect: `read_file` in tool_calls
- Expect: `wiki/git-workflow.md` in source

**Test 2:** "What files are in the wiki?"
- Expect: `list_files` in tool_calls
- Expect: tool_calls array is non-empty
