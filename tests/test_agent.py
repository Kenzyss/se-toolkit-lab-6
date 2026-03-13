"""Regression tests for agent.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def agent_path() -> Path:
    """Return the path to agent.py."""
    return Path(__file__).parent.parent / "agent.py"


def run_agent(question: str, agent_path: Path) -> dict:
    """
    Run agent.py with a question and return the parsed JSON output.
    
    Args:
        question: The question to ask the agent.
        agent_path: Path to agent.py.
    
    Returns:
        Parsed JSON output dict.
    
    Raises:
        pytest.fail: If the agent fails or outputs invalid JSON.
    """
    result = subprocess.run(
        ["uv", "run", str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,  # Give more time for tool calls
    )

    # Check exit code
    if result.returncode != 0:
        pytest.fail(f"Agent failed: {result.stderr}")

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Invalid JSON output: {e}\nStdout: {result.stdout}\nStderr: {result.stderr}")

    return output


class TestAgentOutputFormat:
    """Test that agent.py outputs valid JSON with required fields."""

    def test_answer_and_tool_calls_present(self, agent_path: Path) -> None:
        """Test that the agent outputs 'answer', 'source', and 'tool_calls' fields.
        
        This test runs agent.py with a simple question and verifies:
        1. The process exits with code 0
        2. The stdout contains valid JSON
        3. The 'answer' field is present and non-empty
        4. The 'source' field is present
        5. The 'tool_calls' field is present and is an array
        """
        output = run_agent("What is 2+2?", agent_path)

        # Verify 'answer' field exists and is non-empty
        assert "answer" in output, "Missing 'answer' field in output"
        assert output["answer"], "'answer' field is empty"
        assert isinstance(output["answer"], str), "'answer' must be a string"

        # Verify 'source' field exists
        assert "source" in output, "Missing 'source' field in output"
        assert isinstance(output["source"], str), "'source' must be a string"

        # Verify 'tool_calls' field exists and is an array
        assert "tool_calls" in output, "Missing 'tool_calls' field in output"
        assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"


class TestDocumentationAgent:
    """Test the documentation agent with tool-calling questions."""

    def test_merge_conflict_question(self, agent_path: Path) -> None:
        """Test that asking about merge conflicts uses read_file and references wiki.
        
        This test verifies:
        1. The agent uses read_file tool to find the answer
        2. The source references wiki/git-workflow.md
        """
        output = run_agent("How do you resolve a merge conflict?", agent_path)

        # Verify tool_calls contains read_file
        tool_names = [call.get("tool") for call in output["tool_calls"]]
        assert "read_file" in tool_names, (
            f"Expected 'read_file' in tool_calls, got: {tool_names}"
        )

        # Verify source references git-workflow.md
        source = output.get("source", "").lower()
        assert "git-workflow" in source or "git_workflow" in source, (
            f"Expected 'git-workflow' in source, got: {output.get('source')}"
        )

        # Verify answer is non-empty
        assert output["answer"], "Answer should not be empty"

    def test_wiki_list_files_question(self, agent_path: Path) -> None:
        """Test that asking about wiki files uses list_files tool.
        
        This test verifies:
        1. The agent uses list_files tool
        2. tool_calls array is non-empty
        """
        output = run_agent("What files are in the wiki?", agent_path)

        # Verify tool_calls is non-empty
        assert len(output["tool_calls"]) > 0, (
            "Expected non-empty tool_calls for wiki listing question"
        )

        # Verify tool_calls contains list_files
        tool_names = [call.get("tool") for call in output["tool_calls"]]
        assert "list_files" in tool_names, (
            f"Expected 'list_files' in tool_calls, got: {tool_names}"
        )

        # Verify answer is non-empty
        assert output["answer"], "Answer should not be empty"
