"""Plugin manager for installing and managing plugins."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, ClassVar

import httpx

from vibe.core.plugins.models import (
    InstalledPlugin,
    Marketplace,
    MarketplacePlugin,
    PluginAgent,
    PluginCommand,
    PluginManifest,
)
from vibe.core.utils import logger


def get_plugins_dir() -> Path:
    """Get the plugins installation directory."""
    from vibe.core.config import get_vibe_home

    plugins_dir = get_vibe_home() / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    return plugins_dir


def get_plugins_config_file() -> Path:
    """Get the plugins configuration file path."""
    from vibe.core.config import get_vibe_home

    return get_vibe_home() / "plugins.json"


class PluginManager:
    """Manages plugin installation, removal, and discovery."""

    MANIFEST_PATHS: ClassVar[list[str]] = [
        ".vibe-plugin/manifest.json",
        ".claude-plugin/marketplace.json",  # Claude Code compatibility
        ".claude-plugin/plugin.json",  # Claude Code plugin format
        "plugin.json",
        "manifest.json",
    ]

    def __init__(self) -> None:
        self.plugins_dir = get_plugins_dir()
        self.config_file = get_plugins_config_file()
        self._installed: dict[str, InstalledPlugin] = {}
        self._marketplaces: dict[str, Marketplace] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load installed plugins from config file."""
        if not self.config_file.exists():
            return

        try:
            data = json.loads(self.config_file.read_text())
            for plugin_data in data.get("installed", []):
                plugin = InstalledPlugin.model_validate(plugin_data)
                self._installed[plugin.name] = plugin
            for mp_data in data.get("marketplaces", []):
                mp = Marketplace.model_validate(mp_data)
                self._marketplaces[mp.url] = mp
        except Exception as e:
            logger.warning(f"Failed to load plugins config: {e}")

    def _save_config(self) -> None:
        """Save installed plugins to config file."""
        data = {
            "installed": [p.model_dump(mode="json") for p in self._installed.values()],
            "marketplaces": [m.model_dump(mode="json") for m in self._marketplaces.values()],
        }
        self.config_file.write_text(json.dumps(data, indent=2, default=str))

    def list_installed(self) -> list[InstalledPlugin]:
        """List all installed plugins."""
        return list(self._installed.values())

    def list_marketplaces(self) -> list[Marketplace]:
        """List all added marketplaces."""
        return list(self._marketplaces.values())

    def get_plugin(self, name: str) -> InstalledPlugin | None:
        """Get an installed plugin by name."""
        return self._installed.get(name)

    async def add_marketplace(self, url: str) -> Marketplace:
        """Add a marketplace by URL.

        Args:
            url: GitHub repository URL or shorthand (e.g., 'EveryInc/every-marketplace')

        Returns:
            The added marketplace
        """
        repo = self._normalize_repo(url)
        github_url = f"https://github.com/{repo}"

        # Fetch marketplace info from GitHub
        marketplace = await self._fetch_marketplace_info(repo)
        marketplace.url = github_url
        self._marketplaces[github_url] = marketplace
        self._save_config()
        return marketplace

    def remove_marketplace(self, url: str) -> bool:
        """Remove a marketplace."""
        repo = self._normalize_repo(url)
        github_url = f"https://github.com/{repo}"

        if github_url in self._marketplaces:
            del self._marketplaces[github_url]
            self._save_config()
            return True
        return False

    async def install(self, source: str, from_marketplace: str | None = None) -> InstalledPlugin:
        """Install a plugin from GitHub or a marketplace.

        Args:
            source: Plugin name (if from marketplace) or GitHub repo (e.g., 'EveryInc/compound-engineering-plugin')
            from_marketplace: Optional marketplace URL to search for the plugin

        Returns:
            The installed plugin

        Raises:
            ValueError: If the source is not a valid repository format and can't be resolved
        """
        # Check if it's a marketplace plugin name
        if from_marketplace or "/" not in source:
            plugin_info = self._find_in_marketplaces(source)
            if plugin_info:
                source = plugin_info.repository

        repo = self._normalize_repo(source)

        # Validate repo format - must have owner/repo structure
        if "/" not in repo:
            # Try to find it as a GitHub organization and search for plugin repos
            resolved_repo = await self._resolve_org_plugin(repo)
            if resolved_repo:
                repo = resolved_repo
            else:
                raise ValueError(
                    f"Invalid plugin source '{source}'. Expected format: 'owner/repo' "
                    f"(e.g., 'EveryInc/compound-engineering-plugin'). "
                    f"Could not find a plugin repository in the '{repo}' GitHub organization."
                )
        plugin_name = repo.split("/")[-1]

        # Clone or update the repository
        install_path = self.plugins_dir / plugin_name
        if install_path.exists():
            # Update existing installation
            logger.info(f"Updating plugin {plugin_name}...")
            self._git_pull(install_path)
        else:
            # Clone new plugin
            logger.info(f"Installing plugin {plugin_name}...")
            self._git_clone(repo, install_path)

        # Parse manifest
        manifest = self._parse_manifest(install_path)

        # Create plugin entry
        plugin = InstalledPlugin(
            name=manifest.name if manifest else plugin_name,
            version=manifest.version if manifest else "1.0.0",
            description=manifest.description if manifest else "",
            repository=repo,
            install_path=install_path,
            enabled=True,
            manifest=manifest,
        )

        self._installed[plugin.name] = plugin
        self._save_config()

        # Install any commands as slash commands
        if manifest and manifest.commands:
            self._install_commands(plugin, manifest)

        return plugin

    def uninstall(self, name: str) -> bool:
        """Uninstall a plugin.

        Args:
            name: Plugin name

        Returns:
            True if uninstalled successfully
        """
        plugin = self._installed.get(name)
        if not plugin:
            return False

        # Remove the plugin directory
        if plugin.install_path.exists():
            shutil.rmtree(plugin.install_path)

        # Remove from installed list
        del self._installed[name]
        self._save_config()

        return True

    def enable(self, name: str) -> bool:
        """Enable a plugin."""
        if plugin := self._installed.get(name):
            plugin.enabled = True
            self._save_config()
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a plugin."""
        if plugin := self._installed.get(name):
            plugin.enabled = False
            self._save_config()
            return True
        return False

    def get_plugin_commands(self) -> dict[str, tuple[InstalledPlugin, PluginCommand]]:
        """Get all commands from enabled plugins.

        Returns:
            Dict mapping command aliases to (plugin, command) tuples
        """
        commands: dict[str, tuple[InstalledPlugin, PluginCommand]] = {}
        for plugin in self._installed.values():
            if not plugin.enabled or not plugin.manifest:
                continue
            for cmd in plugin.manifest.commands:
                # Register with plugin prefix (e.g., /compound-engineering:plan)
                alias = f"/{plugin.name}:{cmd.name}"
                commands[alias] = (plugin, cmd)
                # Also register short form if unique
                short_alias = f"/{cmd.name}"
                if short_alias not in commands:
                    commands[short_alias] = (plugin, cmd)
        return commands

    def get_command_prompt(self, plugin: InstalledPlugin, command: PluginCommand) -> str | None:
        """Get the prompt content for a plugin command.

        Args:
            plugin: The plugin
            command: The command

        Returns:
            The prompt content or None
        """
        if not command.prompt_file:
            return None

        prompt_path = plugin.install_path / command.prompt_file
        if not prompt_path.exists() and plugin.manifest:
            # Try in prompts directory
            prompt_path = plugin.install_path / plugin.manifest.prompts_dir / command.prompt_file

        if prompt_path.exists():
            return prompt_path.read_text()
        return None

    def get_agent_prompt(self, plugin: InstalledPlugin, agent: PluginAgent) -> str | None:
        """Get the prompt content for a plugin subagent."""
        prompt_path = plugin.install_path / agent.prompt_file
        if not prompt_path.exists() and plugin.manifest:
            prompt_path = plugin.install_path / plugin.manifest.prompts_dir / agent.prompt_file

        if prompt_path.exists():
            return prompt_path.read_text()
        return None

    def _normalize_repo(self, source: str) -> str:
        """Normalize a repository source to owner/repo format."""
        source = source.strip()
        # Remove github.com prefix if present
        if source.startswith("https://github.com/"):
            source = source[19:]
        elif source.startswith("github.com/"):
            source = source[11:]
        # Remove .git suffix
        if source.endswith(".git"):
            source = source[:-4]
        # Remove trailing slash
        source = source.rstrip("/")
        return source

    async def _resolve_org_plugin(self, org_name: str) -> str | None:
        """Try to find a plugin repository in a GitHub organization.

        Searches for repositories that look like plugins (contain 'plugin', 'vibe',
        'claude', or have plugin manifests).

        Args:
            org_name: GitHub organization or user name

        Returns:
            The resolved repo in 'owner/repo' format, or None if not found
        """
        async with httpx.AsyncClient() as client:
            # First, try common plugin naming patterns
            if repo := await self._try_common_plugin_patterns(client, org_name):
                return repo

            # Fall back to searching org/user repos
            return await self._search_org_repos_for_plugin(client, org_name)

    async def _try_common_plugin_patterns(
        self, client: httpx.AsyncClient, org_name: str
    ) -> str | None:
        """Try common plugin naming patterns for an org."""
        plugin_patterns = [
            f"{org_name}-plugin",
            f"{org_name}-vibe-plugin",
            f"{org_name}-claude-plugin",
            "plugin",
            "vibe-plugin",
            "claude-plugin",
        ]

        for pattern in plugin_patterns:
            repo = f"{org_name}/{pattern}"
            if await self._check_repo_exists(client, repo):
                logger.info(f"Found plugin repository: {repo}")
                return repo
        return None

    async def _check_repo_exists(self, client: httpx.AsyncClient, repo: str) -> bool:
        """Check if a GitHub repository exists."""
        try:
            response = await client.get(
                f"https://api.github.com/repos/{repo}",
                timeout=10,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            return response.is_success
        except Exception:
            return False

    async def _search_org_repos_for_plugin(
        self, client: httpx.AsyncClient, org_name: str
    ) -> str | None:
        """Search organization/user repos for plugin-like repositories."""
        try:
            repos = await self._fetch_org_repos(client, org_name)
            return await self._find_plugin_in_repos(client, repos)
        except Exception as e:
            logger.debug(f"Failed to search org repos: {e}")
            return None

    async def _fetch_org_repos(
        self, client: httpx.AsyncClient, org_name: str
    ) -> list[dict]:
        """Fetch repositories for an org or user."""
        # Try as organization first
        response = await client.get(
            f"https://api.github.com/orgs/{org_name}/repos",
            timeout=10,
            params={"per_page": 100, "sort": "updated"},
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if not response.is_success:
            # Try as user
            response = await client.get(
                f"https://api.github.com/users/{org_name}/repos",
                timeout=10,
                params={"per_page": 100, "sort": "updated"},
                headers={"Accept": "application/vnd.github.v3+json"},
            )

        if response.is_success:
            return response.json()
        return []

    async def _find_plugin_in_repos(
        self, client: httpx.AsyncClient, repos: list[dict]
    ) -> str | None:
        """Find a plugin repository from a list of repos."""
        plugin_keywords = {"plugin", "vibe", "claude", "extension", "addon"}

        for repo_data in repos:
            repo_name = repo_data.get("name", "").lower()
            description = (repo_data.get("description") or "").lower()

            # Check if name or description contains plugin keywords
            if not any(kw in repo_name or kw in description for kw in plugin_keywords):
                continue

            full_name = repo_data.get("full_name")
            if not full_name:
                continue

            # Verify it has a plugin manifest
            if await self._check_repo_has_manifest(client, full_name):
                logger.info(f"Found plugin repository: {full_name}")
                return full_name

        return None

    async def _check_repo_has_manifest(self, client: httpx.AsyncClient, repo: str) -> bool:
        """Check if a repository has a plugin manifest file."""
        manifest_paths = [
            ".vibe-plugin/manifest.json",
            ".claude-plugin/marketplace.json",
            "plugin.json",
            "manifest.json",
            "commands",  # Directory with commands
            "prompts",  # Directory with prompts
        ]

        for path in manifest_paths:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/contents/{path}",
                    timeout=5,
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if response.is_success:
                    return True
            except Exception:
                continue

        return False

    def _find_in_marketplaces(self, name: str) -> MarketplacePlugin | None:
        """Find a plugin by name in registered marketplaces."""
        for marketplace in self._marketplaces.values():
            for plugin in marketplace.plugins:
                if plugin.name == name:
                    return plugin
        return None

    async def _fetch_marketplace_info(self, repo: str) -> Marketplace:
        """Fetch marketplace information from GitHub."""
        # Try to fetch registry.json or marketplace.json
        raw_urls = [
            f"https://raw.githubusercontent.com/{repo}/main/registry.json",
            f"https://raw.githubusercontent.com/{repo}/main/marketplace.json",
            f"https://raw.githubusercontent.com/{repo}/main/.claude-plugin/marketplace.json",
            f"https://raw.githubusercontent.com/{repo}/main/.vibe-plugin/marketplace.json",
        ]

        async with httpx.AsyncClient() as client:
            for url in raw_urls:
                try:
                    response = await client.get(url, timeout=10)
                    if response.is_success:
                        data = response.json()
                        return self._parse_marketplace_data(repo, data)
                except Exception:
                    continue

        # Return a basic marketplace entry if no registry found
        return Marketplace(
            name=repo.split("/")[-1],
            url=f"https://github.com/{repo}",
            plugins=[],
        )

    def _parse_marketplace_data(self, repo: str, data: dict[str, Any]) -> Marketplace:
        """Parse marketplace data from various formats."""
        plugins: list[MarketplacePlugin] = []

        # Handle different marketplace formats
        if "plugins" in data:
            # Standard format
            for p in data["plugins"]:
                plugins.append(
                    MarketplacePlugin(
                        name=p.get("name", ""),
                        version=p.get("version", "1.0.0"),
                        description=p.get("description", ""),
                        author=p.get("author", ""),
                        repository=p.get("repository", ""),
                    )
                )
        elif "extensions" in data:
            # Claude Code format
            for p in data["extensions"]:
                plugins.append(
                    MarketplacePlugin(
                        name=p.get("name", ""),
                        version=p.get("version", "1.0.0"),
                        description=p.get("description", ""),
                        author=p.get("developer", {}).get("name", ""),
                        repository=p.get("repository", ""),
                    )
                )

        return Marketplace(
            name=data.get("name", repo.split("/")[-1]),
            version=data.get("version", "1.0.0"),
            url=f"https://github.com/{repo}",
            plugins=plugins,
        )

    def _git_clone(self, repo: str, path: Path) -> None:
        """Clone a GitHub repository."""
        url = f"https://github.com/{repo}.git"
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(path)],
            check=True,
            capture_output=True,
        )

    def _git_pull(self, path: Path) -> None:
        """Pull latest changes in a repository."""
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=path,
            check=True,
            capture_output=True,
        )

    def _parse_manifest(self, path: Path) -> PluginManifest | None:
        """Parse plugin manifest from various locations."""
        for manifest_path in self.MANIFEST_PATHS:
            full_path = path / manifest_path
            if full_path.exists():
                try:
                    data = json.loads(full_path.read_text())
                    return self._convert_manifest(data, path)
                except Exception as e:
                    logger.warning(f"Failed to parse manifest at {full_path}: {e}")

        # Try to infer from directory structure
        return self._infer_manifest(path)

    def _read_frontmatter(self, path: Path) -> dict[str, str]:
        """Read simple YAML-style frontmatter from a markdown file."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return {}

        if not text.startswith("---"):
            return {}

        lines = text.splitlines()[1:]
        frontmatter_lines: list[str] = []
        for line in lines:
            if line.strip() == "---":
                break
            frontmatter_lines.append(line)

        data: dict[str, str] = {}
        for line in frontmatter_lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()

        return data

    def _convert_manifest(self, data: dict[str, Any], path: Path) -> PluginManifest:
        """Convert various manifest formats to PluginManifest."""
        commands: list[PluginCommand] = []
        agents: list[PluginAgent] = []

        # Handle Claude Code format
        if "extensions" in data:
            ext = data["extensions"][0] if data["extensions"] else {}
            name = ext.get("name", path.name)
            version = ext.get("version", "1.0.0")
            description = ext.get("description", "")
            author = ext.get("developer", {}).get("name", "")
        else:
            name = data.get("name", path.name)
            version = data.get("version", "1.0.0")
            description = data.get("description", "")
            author_data = data.get("author", "")
            # Handle author as object or string
            if isinstance(author_data, dict):
                author = author_data.get("name", "")
            else:
                author = author_data

        # Look for commands in various places
        if "commands" in data:
            for cmd in data["commands"]:
                commands.append(
                    PluginCommand(
                        name=cmd.get("name", ""),
                        description=cmd.get("description", ""),
                        prompt_file=cmd.get("prompt_file", cmd.get("prompt", "")),
                    )
                )

        if "agents" in data:
            for agent in data["agents"]:
                try:
                    parsed_agent = PluginAgent(
                        name=agent.get("name", ""),
                        description=agent.get("description", ""),
                        prompt_file=agent.get("prompt_file", agent.get("prompt", "")),
                    )
                    if parsed_agent.name:
                        agents.append(parsed_agent)
                except Exception:
                    continue

        agents.extend(self._discover_agents(path))

        # Discover commands from directory structure
        commands_dir = path / "commands"
        skip_files = {"readme.md", "claude.md", "agents.md", "vibe.md"}
        if commands_dir.exists():
            for cmd_file in commands_dir.rglob("*.md"):
                if cmd_file.name.lower() in skip_files:
                    continue
                metadata = self._read_frontmatter(cmd_file)
                commands.append(
                    PluginCommand(
                        name=metadata.get("name", cmd_file.stem),
                        description=metadata.get("description", ""),
                        prompt_file=str(cmd_file.relative_to(path)),
                    )
                )

        unique_commands: list[PluginCommand] = []
        seen_commands: set[tuple[str, str]] = set()
        for cmd in commands:
            key = (cmd.name, cmd.prompt_file)
            if not cmd.name or key in seen_commands:
                continue
            seen_commands.add(key)
            unique_commands.append(cmd)

        unique_agents: list[PluginAgent] = []
        seen_agents: set[tuple[str, str]] = set()
        for agent in agents:
            key = (agent.name, agent.prompt_file)
            if not agent.name or key in seen_agents:
                continue
            seen_agents.add(key)
            unique_agents.append(agent)

        return PluginManifest(
            name=name,
            version=version,
            description=description,
            author=author,
            repository=data.get("repository", ""),
            commands=unique_commands,
            agents=unique_agents,
        )

    def _infer_manifest(self, path: Path) -> PluginManifest | None:
        """Infer manifest from directory structure."""
        commands: list[PluginCommand] = []

        skip_files = {"readme.md", "claude.md", "agents.md", "vibe.md"}

        for base_dir in (path / "commands", path / "prompts"):
            if base_dir.exists():
                for md_file in base_dir.rglob("*.md"):
                    if md_file.name.lower() in skip_files:
                        continue
                    metadata = self._read_frontmatter(md_file)
                    commands.append(
                        PluginCommand(
                            name=metadata.get("name", md_file.stem),
                            description=metadata.get("description", ""),
                            prompt_file=str(md_file.relative_to(path)),
                        )
                    )

        for md_file in path.glob("*.md"):
            if md_file.name.lower() in skip_files:
                continue
            metadata = self._read_frontmatter(md_file)
            commands.append(
                PluginCommand(
                    name=metadata.get("name", md_file.stem),
                    description=metadata.get("description", ""),
                    prompt_file=str(md_file.relative_to(path)),
                )
            )

        agents = self._discover_agents(path)

        if not commands:
            return None

        unique_commands: list[PluginCommand] = []
        seen_commands: set[tuple[str, str]] = set()
        for cmd in commands:
            key = (cmd.name, cmd.prompt_file)
            if not cmd.name or key in seen_commands:
                continue
            seen_commands.add(key)
            unique_commands.append(cmd)

        unique_agents: list[PluginAgent] = []
        seen_agents: set[tuple[str, str]] = set()
        for agent in agents:
            key = (agent.name, agent.prompt_file)
            if not agent.name or key in seen_agents:
                continue
            seen_agents.add(key)
            unique_agents.append(agent)

        return PluginManifest(
            name=path.name,
            commands=unique_commands,
            agents=unique_agents,
        )

    def _discover_agents(self, path: Path) -> list[PluginAgent]:
        agents: list[PluginAgent] = []
        agents_dir = path / "agents"
        if not agents_dir.exists():
            return agents
        skip_files = {"readme.md", "claude.md", "agents.md", "vibe.md"}

        for agent_file in agents_dir.rglob("*.md"):
            if agent_file.name.lower() in skip_files:
                continue
            try:
                agent_name = agent_file.relative_to(agents_dir).with_suffix("").as_posix()
            except ValueError:
                agent_name = agent_file.stem

            metadata = self._read_frontmatter(agent_file)
            agent_name = metadata.get("name", agent_name)
            description = metadata.get("description", "")

            agents.append(
                PluginAgent(
                    name=agent_name,
                    description=description,
                    prompt_file=str(agent_file.relative_to(path)),
                )
            )

        return agents

    def _install_commands(self, plugin: InstalledPlugin, manifest: PluginManifest) -> None:
        """Install plugin commands as slash commands."""
        from vibe.core.config import get_vibe_home

        commands_dir = get_vibe_home() / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)

        for cmd in manifest.commands:
            # Create a command file that references the plugin
            cmd_file = commands_dir / f"{plugin.name}_{cmd.name}.md"
            prompt_content = self.get_command_prompt(plugin, cmd)
            if prompt_content:
                cmd_file.write_text(prompt_content)
