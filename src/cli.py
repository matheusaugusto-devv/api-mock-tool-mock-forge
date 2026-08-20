import threading
import time
import webbrowser
import typer
import uvicorn

from .app import create_app

cli = typer.Typer(name="mock-forge", help="Mock Forge - Dynamic REST API Mocking Tool", no_args_is_help=False)


def _open_browser_when_ready(url: str, delay: float = 0.5) -> None:
    time.sleep(delay)
    webbrowser.open(url)


@cli.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind to"),
    db_path: str = typer.Option("mock-forge.db", "--db-path", help="Path to SQLite database file"),
    open_browser: bool = typer.Option(True, "--open-browser/--no-browser", help="Open browser automatically"),
) -> None:
    if ctx.invoked_subcommand is None:
        run_server(port=port, host=host, db_path=db_path, open_browser=open_browser)


def run_server(port: int, host: str, db_path: str, open_browser: bool) -> None:
    app = create_app(db_path=db_path)
    url = f"http://{host}:{port}/"
    typer.echo(f"Starting Mock Forge on {url}")

    if open_browser:
        threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server.run()


@cli.command("start")
def start(
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind to"),
    db_path: str = typer.Option("mock-forge.db", "--db-path", help="Path to SQLite database file"),
    open_browser: bool = typer.Option(True, "--open-browser/--no-browser", help="Open browser automatically"),
) -> None:
    run_server(port=port, host=host, db_path=db_path, open_browser=open_browser)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
