"""CLI entrypoint (placeholder until M8)."""
import typer

app = typer.Typer(add_completion=False, help="Travel Assistant Agent CLI")


@app.command()
def plan(
    fake: bool = typer.Option(False, "--fake", help="Use the deterministic fake model"),
) -> None:
    """Plan a trip (not implemented until M8)."""
    typer.echo("Travel Assistant scaffold OK. Planning is implemented in M8.")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
