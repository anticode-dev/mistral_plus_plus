# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mistral Vibe is Mistral AI's open-source CLI coding assistant. It provides a conversational interface powered by Mistral's models with tools for file manipulation, code searching, and shell command execution.

## Development Commands

```bash
# Install dependencies (uses uv package manager)
uv sync --all-extras

# Run the CLI in development
uv run vibe

# Run tests (uses pytest with parallel execution)
uv run pytest

# Run a specific test file
uv run pytest tests/test_agent_tool_call.py

# Linting and formatting (uses ruff)
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .

# Type checking (uses pyright)
uv run pyright

# Run all pre-commit hooks
uv run pre-commit run --all-files
```

## Architecture

### Core Components

- **Agent** (`vibe/core/agent.py`): Central orchestrator managing conversation flow, tool execution, and LLM interactions. Handles streaming responses, middleware pipeline (auto-compact, turn limits, price limits), and tool approval workflows.

- **ToolManager** (`vibe/core/tools/manager.py`): Discovers and manages tools from multiple sources:
  - Built-in tools in `vibe/core/tools/builtins/`
  - Custom tools in `.vibe/tools/` (project) or `~/.vibe/tools/` (global)
  - MCP (Model Context Protocol) servers via HTTP or stdio transports

- **LLM Backends** (`vibe/core/llm/backend/`): Abstraction layer for model providers. Two implementations:
  - `MistralBackend`: Native Mistral API support
  - `GenericBackend`: OpenAI-compatible APIs

- **VibeConfig** (`vibe/core/config.py`): Pydantic-based configuration loaded from `~/.vibe/config.toml` or `.vibe/config.toml`. Handles model definitions, provider settings, tool permissions, and MCP server configs.

### CLI Layer

- **Entrypoint** (`vibe/cli/entrypoint.py`): Parses CLI args, handles programmatic vs interactive modes, session continuation/resume
- **Textual UI** (`vibe/cli/textual_ui/`): Interactive TUI built with Textual framework. Main app in `app.py`, widgets for messages, tool calls, autocompletion

### ACP (Agent Client Protocol)

- **ACP Module** (`vibe/acp/`): Alternative entrypoint (`vibe-acp`) implementing the Agent Client Protocol for programmatic agent control

### Tool System

Each tool inherits from `BaseTool` (`vibe/core/tools/base.py`) with:
- Pydantic models for args/results
- Permission levels (always/ask/never)
- Allowlist/denylist patterns
- Prompt templates in `vibe/core/tools/builtins/prompts/`

Built-in tools: `bash`, `grep`, `read_file`, `write_file`, `search_replace`, `todo`

## Code Style Guidelines

- **Python 3.12+**: Use modern syntax (match-case, walrus operator, `list`/`dict` generics, `|` for unions)
- **Type hints required**: All functions and methods must have type annotations
- **Pydantic-first**: Use `model_validate`, field validators for data parsing
- **Flat code**: Prefer early returns and guard clauses over deep nesting
- **pathlib**: Use `Path` methods instead of `os.path`
- **No inline ignores**: Avoid `# type: ignore` and `# noqa` - fix types at source
- **Always use uv**: Never run bare `python` or `pip` commands

## Configuration

- Main config: `~/.vibe/config.toml` or `.vibe/config.toml`
- API keys: `~/.vibe/.env` or environment variables
- Custom prompts: `~/.vibe/prompts/`
- Custom agents: `~/.vibe/agents/`
- Project documentation: `AGENTS.md`, `VIBE.md`, or `.vibe.md` in project root
