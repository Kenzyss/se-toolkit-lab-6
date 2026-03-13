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


class TestAgentOutput:
    """Test that agent.py outputs valid JSON with required fields."""

    def test_answer_and_tool_calls_present(self, agent_path: Path) -> None:
        """Test that the agent outputs both 'answer' and 'tool_calls' fields.
        
        This test runs agent.py with a simple question and verifies:
        1. The process exits with code 0
        2. The stdout contains valid JSON
        3. The 'answer' field is present and non-empty
        4. The 'tool_calls' field is present and is an array
        """
        # Run agent.py with a simple test question
        result = subprocess.run(
            [sys.executable, "-m", "uv", "run", str(agent_path), "What is 2+2?"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Check exit code
        assert result.returncode == 0, f"Agent failed: {result.stderr}"

        # Parse stdout as JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}\nStdout: {result.stdout}\nStderr: {result.stderr}")

        # Verify 'answer' field exists and is non-empty
        assert "answer" in output, "Missing 'answer' field in output"
        assert output["answer"], "'answer' field is empty"
        assert isinstance(output["answer"], str), "'answer' must be a string"

        # Verify 'tool_calls' field exists and is an array
        assert "tool_calls" in output, "Missing 'tool_calls' field in output"
        assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"
