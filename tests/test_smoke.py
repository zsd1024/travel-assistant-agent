from typer.testing import CliRunner

from travel_assistant import __version__
from travel_assistant.cli import app


def test_version_present() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_runs() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Travel Assistant" in result.output


def test_langchain_imports() -> None:
    # M0 import smoke (spec §13): confirm core APIs import.
    from langchain.agents import create_agent  # noqa: F401
    from langgraph.checkpoint.memory import InMemorySaver  # noqa: F401
