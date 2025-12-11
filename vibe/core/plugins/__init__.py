"""Plugin system for Mistral Vibe.

Provides functionality to install, manage, and run plugins from GitHub repositories,
similar to Claude Code's plugin system.
"""
from __future__ import annotations

from vibe.core.plugins.manager import PluginManager
from vibe.core.plugins.models import InstalledPlugin, Marketplace, PluginManifest

__all__ = [
    "InstalledPlugin",
    "Marketplace",
    "PluginManager",
    "PluginManifest",
]
