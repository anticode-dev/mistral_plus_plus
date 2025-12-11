from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class Command:
    aliases: frozenset[str]
    description: str
    handler: str
    exits: bool = False
    subcommands: dict[str, str] | None = None  # Maps subcommand to description


@dataclass
class PluginCommand:
    """A command provided by an installed plugin."""

    name: str
    plugin_name: str
    description: str
    prompt_file: str


class CommandRegistry:
    def __init__(self, excluded_commands: list[str] | None = None) -> None:
        if excluded_commands is None:
            excluded_commands = []
        self.commands = {
            "help": Command(
                aliases=frozenset(["/help", "/h"]),
                description="Show help message",
                handler="_show_help",
            ),
            "status": Command(
                aliases=frozenset(["/status", "/stats"]),
                description="Display agent statistics",
                handler="_show_status",
            ),
            "config": Command(
                aliases=frozenset(["/config", "/cfg", "/theme", "/model"]),
                description="Edit config settings",
                handler="_show_config",
            ),
            "reload": Command(
                aliases=frozenset(["/reload", "/r"]),
                description="Reload configuration from disk",
                handler="_reload_config",
            ),
            "clear": Command(
                aliases=frozenset(["/clear", "/reset"]),
                description="Clear conversation history",
                handler="_clear_history",
            ),
            "log": Command(
                aliases=frozenset(["/log", "/logpath"]),
                description="Show path to current interaction log file",
                handler="_show_log_path",
            ),
            "compact": Command(
                aliases=frozenset(["/compact", "/summarize"]),
                description="Compact conversation history by summarizing",
                handler="_compact_history",
            ),
            "plugin": Command(
                aliases=frozenset(["/plugin", "/plugins"]),
                description="Manage plugins (install, list, remove)",
                handler="_handle_plugin_command",
                subcommands={
                    "install": "Install a plugin from GitHub or marketplace",
                    "remove": "Remove an installed plugin",
                    "list": "List installed plugins",
                    "enable": "Enable a disabled plugin",
                    "disable": "Disable a plugin",
                    "marketplace": "Manage plugin marketplaces",
                },
            ),
            "subagent": Command(
                aliases=frozenset(["/subagent", "/subagents"]),
                description="Run a plugin subagent prompt",
                handler="_run_subagent",
            ),
            "exit": Command(
                aliases=frozenset(["/exit", "/quit", "/q"]),
                description="Exit the application",
                handler="_exit_app",
                exits=True,
            ),
        }
        self._plugin_commands: dict[str, PluginCommand] = {}

        for command in excluded_commands:
            self.commands.pop(command, None)

        self._alias_map: dict[str, str] = {}
        for cmd_name, cmd in self.commands.items():
            for alias in cmd.aliases:
                self._alias_map[alias] = cmd_name

    def register_plugin_command(self, cmd: PluginCommand) -> None:
        """Register a command from a plugin."""
        # Full form: /plugin-name:command
        full_alias = f"/{cmd.plugin_name}:{cmd.name}"
        self._plugin_commands[full_alias] = cmd

        # Short form if not conflicting: /command
        short_alias = f"/{cmd.name}"
        if short_alias not in self._alias_map and short_alias not in self._plugin_commands:
            self._plugin_commands[short_alias] = cmd

    def set_plugin_commands(self, commands: Iterable[PluginCommand]) -> None:
        """Replace the current plugin command registry."""
        self._plugin_commands.clear()
        for command in commands:
            self.register_plugin_command(command)

    def find_command(self, user_input: str) -> Command | None:
        """Find a built-in command by alias."""
        # Handle commands with arguments (e.g., "/plugin install foo")
        parts = user_input.lower().strip().split(maxsplit=1)
        base_cmd = parts[0] if parts else ""
        cmd_name = self._alias_map.get(base_cmd)
        return self.commands.get(cmd_name) if cmd_name else None

    def find_plugin_command(self, user_input: str) -> PluginCommand | None:
        """Find a plugin command by alias."""
        parts = user_input.strip().split(maxsplit=1)
        base_cmd = parts[0].lower() if parts else ""
        return self._plugin_commands.get(base_cmd)

    def parse_command_args(self, user_input: str) -> tuple[str, list[str]]:
        """Parse a command into base command and arguments."""
        parts = user_input.strip().split()
        base = parts[0] if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        return base, args

    def completion_entries(self) -> list[tuple[str, str]]:
        """Return all command aliases with descriptions for autocompletion."""
        entries: list[tuple[str, str]] = []
        for command in self.commands.values():
            for alias in sorted(command.aliases):
                entries.append((alias, command.description))

        seen: set[str] = {alias for alias, _ in entries}
        for alias, plugin_cmd in self._plugin_commands.items():
            if alias in seen:
                continue
            entries.append((alias, plugin_cmd.description))
            seen.add(alias)

        return entries

    def get_help_text(self) -> str:
        lines: list[str] = [
            "### Keyboard Shortcuts",
            "",
            "- `Enter` Submit message",
            "- `Ctrl+J` / `Shift+Enter` Insert newline",
            "- `Escape` Interrupt agent or close dialogs",
            "- `Ctrl+C` Quit (or clear input if text present)",
            "- `Ctrl+O` Toggle tool output view",
            "- `Ctrl+T` Toggle todo view",
            "- `Shift+Tab` Toggle auto-approve mode",
            "",
            "### Special Features",
            "",
            "- `!<command>` Execute bash command directly",
            "- `@path/to/file/` Autocompletes file paths",
            "",
            "### Commands",
            "",
        ]

        for cmd in self.commands.values():
            aliases = ", ".join(f"`{alias}`" for alias in sorted(cmd.aliases))
            lines.append(f"- {aliases}: {cmd.description}")
            if cmd.subcommands:
                for subcmd, desc in cmd.subcommands.items():
                    lines.append(f"  - `{subcmd}`: {desc}")

        # Add plugin commands
        if self._plugin_commands:
            lines.extend(["", "### Plugin Commands", ""])
            seen: set[str] = set()
            for _alias, cmd in self._plugin_commands.items():
                if cmd.name not in seen:
                    lines.append(f"- `/{cmd.plugin_name}:{cmd.name}`: {cmd.description}")
                    seen.add(cmd.name)

        return "\n".join(lines)
