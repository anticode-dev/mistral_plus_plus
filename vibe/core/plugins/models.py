"""Plugin data models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PluginCommand(BaseModel):
    """A command provided by a plugin."""

    name: str = Field(description="Command name (e.g., 'plan', 'review')")
    description: str = Field(default="", description="Command description")
    prompt_file: str = Field(default="", description="Path to prompt file relative to plugin root")


class PluginAgent(BaseModel):
    """An agent provided by a plugin."""

    name: str = Field(description="Agent name")
    description: str = Field(default="", description="Agent description")
    prompt_file: str = Field(default="", description="Path to prompt file")


class PluginManifest(BaseModel):
    """Plugin manifest from .vibe-plugin/manifest.json or similar."""

    name: str = Field(description="Plugin name")
    version: str = Field(default="1.0.0", description="Plugin version")
    description: str = Field(default="", description="Plugin description")
    author: str | dict[str, Any] = Field(default="", description="Plugin author (string or object)")
    repository: str = Field(default="", description="Source repository URL")
    commands: list[PluginCommand] = Field(default_factory=list, description="Plugin commands")
    agents: list[PluginAgent] = Field(default_factory=list, description="Plugin agents")
    mcp_server: dict[str, Any] | None = Field(
        default=None, description="MCP server configuration if plugin provides one"
    )
    prompts_dir: str = Field(default="prompts", description="Directory containing prompt files")


class InstalledPlugin(BaseModel):
    """An installed plugin."""

    model_config = {"arbitrary_types_allowed": True}

    name: str = Field(description="Plugin name")
    version: str = Field(default="1.0.0", description="Plugin version")
    description: str = Field(default="", description="Plugin description")
    repository: str = Field(description="Source repository (e.g., 'EveryInc/compound-engineering-plugin')")
    install_path: Path = Field(description="Local installation path")
    enabled: bool = Field(default=True, description="Whether the plugin is enabled")
    manifest: PluginManifest | None = Field(default=None, description="Parsed plugin manifest")


class MarketplacePlugin(BaseModel):
    """A plugin available in a marketplace."""

    name: str = Field(description="Plugin name")
    version: str = Field(default="1.0.0", description="Plugin version")
    description: str = Field(default="", description="Plugin description")
    author: str = Field(default="", description="Plugin author")
    repository: str = Field(description="Source repository")


class Marketplace(BaseModel):
    """A plugin marketplace registry."""

    name: str = Field(description="Marketplace name")
    version: str = Field(default="1.0.0", description="Marketplace version")
    url: str = Field(description="Marketplace URL (GitHub repo)")
    plugins: list[MarketplacePlugin] = Field(default_factory=list, description="Available plugins")


class PluginConfig(BaseModel):
    """Plugin configuration stored in config.toml."""

    marketplaces: list[str] = Field(
        default_factory=list,
        description="List of marketplace URLs (GitHub repos)",
    )
    installed: list[InstalledPlugin] = Field(
        default_factory=list,
        description="List of installed plugins",
    )
