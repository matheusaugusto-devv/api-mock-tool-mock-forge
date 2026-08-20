from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from src.cli import cli, _open_browser_when_ready, main

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "start" in result.output


def test_cli_start_help():
    result = runner.invoke(cli, ["start", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.output
    assert "--host" in result.output
    assert "--db-path" in result.output
    assert "--open-browser" in result.output or "--no-browser" in result.output


@patch("uvicorn.Server.run")
@patch("webbrowser.open")
def test_cli_start_default(mock_browser, mock_server_run):
    result = runner.invoke(cli, ["start", "--no-browser"])
    assert result.exit_code == 0
    assert "Starting Mock Forge on http://127.0.0.1:8000/" in result.output
    assert mock_server_run.called


@patch("uvicorn.Server.run")
@patch("webbrowser.open")
def test_cli_invoke_without_command(mock_browser, mock_server_run):
    result = runner.invoke(cli, ["--no-browser"])
    assert result.exit_code == 0
    assert "Starting Mock Forge on http://127.0.0.1:8000/" in result.output
    assert mock_server_run.called


@patch("uvicorn.Server.run")
@patch("threading.Thread")
def test_cli_start_custom_args(mock_thread, mock_server_run):
    result = runner.invoke(cli, [
        "start",
        "--port", "9000",
        "--host", "0.0.0.0",
        "--db-path", "custom.db",
        "--open-browser"
    ])
    assert result.exit_code == 0
    assert "Starting Mock Forge on http://0.0.0.0:9000/" in result.output
    assert mock_server_run.called
    assert mock_thread.called


@patch("webbrowser.open")
@patch("time.sleep")
def test_open_browser_when_ready(mock_sleep, mock_browser):
    _open_browser_when_ready("http://127.0.0.1:8000/", delay=0.01)
    mock_sleep.assert_called_once_with(0.01)
    mock_browser.assert_called_once_with("http://127.0.0.1:8000/")


@patch("src.cli.cli")
def test_main_entrypoint(mock_cli):
    main()
    assert mock_cli.called
