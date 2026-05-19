"""CLI entrypoint: interactive / one-shot trip planning (M8)."""
import uuid

import typer

from travel_assistant.config import Settings
from travel_assistant.llm import ModelConfigError
from travel_assistant.models import TripPlan
from travel_assistant.runner import RunResult, build_runner
from travel_assistant.streaming import format_stream_event
from travel_assistant.tracing import configure_tracing

app = typer.Typer(add_completion=False, help="Travel Assistant Agent CLI")


@app.callback()
def main() -> None:
    """Travel Assistant Agent CLI."""


def _print_plan(plan: TripPlan | None) -> None:
    if plan is None:
        typer.echo("No structured plan produced.")
        return
    typer.echo("")
    typer.echo("==================== Trip Plan ====================")
    typer.echo(f"Summary: {plan.summary}")

    if plan.days:
        typer.echo("")
        typer.echo("Itinerary:")
        for day in plan.days:
            date = f" ({day.date})" if day.date else ""
            weather = f" — weather: {day.weather}" if day.weather else ""
            typer.echo(f"  Day {day.day_index}{date}{weather}")
            for act in day.activities:
                note = f" — {act.notes}" if act.notes else ""
                typer.echo(f"    - [{act.category}] {act.name}{note}")

    if plan.flight_options:
        typer.echo("")
        typer.echo("Flight options:")
        for f in plan.flight_options:
            typer.echo(
                f"  - {f.carrier}: {f.depart} -> {f.arrive} "
                f"({f.price:.2f} {f.currency})"
            )

    if plan.hotel_options:
        typer.echo("")
        typer.echo("Hotel options:")
        for h in plan.hotel_options:
            typer.echo(
                f"  - {h.name} ({h.area}) — {h.price_per_night:.2f} "
                f"{h.currency}/night, rating {h.rating}"
            )

    if plan.transport_notes:
        typer.echo("")
        typer.echo(f"Transport: {plan.transport_notes}")

    b = plan.budget
    typer.echo("")
    typer.echo(f"Budget breakdown ({b.currency}):")
    typer.echo(f"  Flights:         {b.flights:.2f}")
    typer.echo(f"  Lodging:         {b.lodging:.2f}")
    typer.echo(f"  Food:            {b.food:.2f}")
    typer.echo(f"  Activities:      {b.activities:.2f}")
    typer.echo(f"  Local transport: {b.local_transport:.2f}")
    typer.echo(f"  Total:           {b.total:.2f}")

    if plan.assumptions:
        typer.echo("")
        typer.echo("Assumptions:")
        for a in plan.assumptions:
            typer.echo(f"  - {a}")
    typer.echo("===================================================")


def _render_event(event: object) -> None:
    for line in format_stream_event(event):
        typer.echo(line)


@app.command()
def plan(
    message: str = typer.Option(
        "", "--message", "-m", help="Trip request; omit for an interactive session"
    ),
    user_id: str = typer.Option(
        "default", "--user-id", help="Traveler id for long-term preferences"
    ),
    thread_id: str = typer.Option(
        "", "--thread-id", help="Conversation thread id (default: generated)"
    ),
    new: bool = typer.Option(
        False, "--new", help="Force a fresh conversation thread"
    ),
    fake: bool = typer.Option(
        False, "--fake", help="Use the deterministic fake model"
    ),
    once: bool = typer.Option(
        False, "--once", help="Run a single turn and exit (no interactive loop)"
    ),
) -> None:
    """Plan a trip (streaming output, multi-turn unless --once)."""
    settings = Settings()
    if fake:
        settings = settings.model_copy(update={"travel_agent_fake_model": True})

    if settings.travel_agent_fake_model:
        typer.echo("*** FAKE MODEL ***")
    else:
        typer.echo(f"Model: {settings.travel_agent_model_id}")

    if new or not thread_id:
        thread_id = uuid.uuid4().hex
    typer.echo(f"(thread: {thread_id})")

    if configure_tracing(settings):
        typer.echo("(LangSmith tracing enabled)")

    try:
        runner = build_runner(settings)
    except ModelConfigError as exc:
        typer.echo(f"Cannot start: {exc}")
        raise typer.Exit(code=2) from exc

    def turn(text: str) -> RunResult:
        result = runner.stream(user_id, thread_id, text, _render_event)
        _print_plan(result.plan)
        return result

    if message:
        turn(message)
        if once:
            raise typer.Exit(code=0)

    if once:
        typer.echo("Nothing to do: --once requires --message.")
        raise typer.Exit(code=0)

    typer.echo("")
    typer.echo("Interactive session. Type 'quit' or 'exit' (or Ctrl-D) to stop.")
    while True:
        try:
            text = typer.prompt("you")
        except (EOFError, KeyboardInterrupt, typer.Abort):
            typer.echo("")
            break
        text = text.strip()
        if not text:
            continue
        if text.lower() in {"quit", "exit"}:
            break
        turn(text)

    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
