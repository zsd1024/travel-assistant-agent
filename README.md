# Travel Assistant Agent

Engineering-grade CLI travel-planning agent (LangChain 1.x `create_agent` + LangGraph).

## Status
Scaffold (M0). See `docs/superpowers/plans/2026-05-18-travel-assistant-agent.md`.

## Quickstart
```bash
make install
cp .env.example .env   # set DEEPSEEK_API_KEY, or run with --fake
python -m travel_assistant --help
```

## Architecture
See `docs/superpowers/specs/2026-05-18-travel-assistant-agent-design.md`.

## Roadmap
M0 scaffold · M1 models · M2 tools · M3 memory · M4 LLM layer ·
M5 agent core · M6 ToolRuntime/Command · M7 short-term memory ·
M8 streaming/CLI · M9 tracing + polish.
