# Plugin SDK Architecture

## Overview

The Plugin SDK lets external code extend OpportunityOS at 5 extension points. Each extension point follows the same pattern already used by `SearchProvider`/`SearchRegistry` and `AIProvider`/`AIRegistry`: a base ABC, a registry, and automatic discovery at startup.

---

## 1. Package Layout

```
opportunityos-plugin-example/
├── pyproject.toml              # entry-points: opportunityos.plugins
├── src/
│   └── opportunityos_plugin_example/
│       ├── __init__.py          # Plugin class exported here
│       ├── plugin.py            # class ExamplePlugin(BasePlugin)
│       ├── search.py            # class ExampleSearch(SearchProvider)
│       ├── ranking.py           # class ExampleRanking(RankingProvider)
│       ├── datasource.py        # class ExampleSource(DataSourceProvider)
│       ├── notification.py      # class ExampleNotify(NotificationChannel)
│       └── pages.py             # class ExamplePage(PagePlugin)
```

---

## 2. Core Plugin Class

### `plugins/base.py` — `BasePlugin`

```python
class BasePlugin(ABC):
    """Base class for all plugins."""

    # ── Metadata (set as class attributes or overridden) ────────────
    plugin_name: str = ""
    plugin_version: str = "0.1.0"
    plugin_description: str = ""
    plugin_author: str = ""

    # ── Lifecycle (called by the framework) ────────────────────────
    @abstractmethod
    def initialize(self) -> None:
        """Register hooks, set up state. Called after discovery."""

    def on_enable(self) -> None:
        """Called when the plugin is enabled (after init or at runtime)."""

    def on_disable(self) -> None:
        """Called when the plugin is disabled at runtime."""

    # ── Extension points — override to provide capabilities ────────
    def get_search_providers(self) -> list[type[SearchProvider]]:
        return []

    def get_ranking_providers(self) -> list[type[RankingProvider]]:
        return []

    def get_data_sources(self) -> list[type[DataSourceProvider]]:
        return []

    def get_notification_channels(self) -> list[type[NotificationChannel]]:
        return []

    def get_gui_pages(self) -> list[type[PagePlugin]]:
        return []
```

Each plugin class declares what it provides by overriding the `get_*` methods. The framework calls these during initialization and registers the returned types with the corresponding registries.

---

## 3. Extension Point Interfaces

### 3a. Search Provider — *exists*

### `services/search/provider.py`

```python
class SearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def search(
        self, query: str, count: int = 10, offset: int = 0
    ) -> list[SearchResult]: ...
```

### `services/search/registry.py` — `SearchRegistry`

- `register(provider: SearchProvider)`
- `get(name: str) -> SearchProvider`
- `list() -> list[str]`

A plugin returns `SearchProvider` subclasses from `get_search_providers()`. The framework instantiates them and registers each one.

---

### 3b. Ranking Provider — *new*

### `plugins/sdk/types.py` (re-exported as `opportunityos_plugin_sdk`)

```python
class RankingProvider(ABC):
    """Ranks a list of opportunities by relevance to a profile."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, used as registry key."""

    @abstractmethod
    async def rank(
        self,
        opportunities: list[dict],
        profile: dict,
    ) -> list[dict]:
        """Return opportunities sorted by score (descending), with a
        'ranking_score' float added to each dict."""
```

### Registry

```python
class RankingRegistry:
    """Stores available RankingProvider instances."""
    def register(self, provider: RankingProvider) -> None: ...
    def get(self, name: str) -> RankingProvider: ...
    def list(self) -> list[str]: ...
    def default() -> RankingRegistry: ...
```

**Integration**: `AIRankingStep` in the pipeline currently calls the AI scorer. A `RankingRegistry` would add a dispatch: if the pipeline config specifies a ranking provider, use it; otherwise fall back to the AI scorer. The step reads `ctx["ranking_provider"]` from the pipeline config.

```python
# In AIRankingStep.execute():
registry = RankingRegistry.default()
provider_name = ctx.get("ranking_provider", "ai_scorer")
provider = registry.get(provider_name)
ranked = await provider.rank(opportunities, profile)
```

---

### 3c. Data Source — *new*

### `plugins/sdk/types.py`

```python
class DataSourceProvider(ABC):
    """Fetches or imports opportunities from an external system."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, used as registry key."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Type identifier stored in the Source model (e.g. 'rss', 'api')."""

    @abstractmethod
    async def fetch(self, config: dict) -> list[dict]:
        """Return a list of raw opportunity dicts.

        Each dict should contain at minimum:
          - title: str
          - url: str (optional)
          - description: str (optional)
          - source: str (will be overwritten with self.name)
        """

    @abstractmethod
    def get_config_schema(self) -> dict:
        """Return a JSON Schema dict describing the required config fields."""
```

### Registry

```python
class DataSourceRegistry:
    def register(self, source: DataSourceProvider) -> None: ...
    def get(self, name: str) -> DataSourceProvider: ...
    def list(self) -> list[str]: ...
```

**Integration**: A new `/api/v1/sources/import` endpoint accepts a source name and config, calls `DataSourceRegistry.get(name).fetch(config)`, and creates `Opportunity` records from the returned dicts.

---

### 3d. Notification Channel — *extend existing*

### `services/notifications/providers.py`

Add `channel_name` property to the existing `BaseNotificationProvider`:

```python
class BaseNotificationProvider(ABC):
    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Used as registry key (e.g. 'desktop', 'email', 'slack')."""

    @abstractmethod
    def send(
        self, user_id: str, title: str, message: str, **kwargs: Any
    ) -> bool: ...
```

### New Registry

```python
class NotificationChannelRegistry:
    def register(self, provider: BaseNotificationProvider) -> None: ...
    def get(self, name: str) -> BaseNotificationProvider: ...
    def list(self) -> list[str]: ...
```

### Integration

`NotificationService._init_providers()` changes from hardcoded config checks to iterating the registry:

```python
for name in self._config.notifications.enabled_channels:
    try:
        provider = NotificationChannelRegistry.default().get(name)
        self._providers.append(provider)
    except KeyError:
        logger.warning("Notification channel '%s' not found", name)
```

---

### 3e. GUI Page — *new*

### `plugins/sdk/types.py`

```python
class PagePlugin(ABC):
    """A page that appears in the sidebar and QStackedWidget."""

    @property
    @abstractmethod
    def title(self) -> str:
        """Page title (shown in sidebar and header)."""

    @property
    @abstractmethod
    def icon(self) -> str:
        """Unicode glyph or icon identifier for the sidebar button."""

    @property
    def order(self) -> int:
        """Position in the sidebar (default: 99 = after built-in pages)."""
        return 99

    @abstractmethod
    def create_widget(self) -> QWidget:
        """Return a QWidget instance for this page."""
```

### No registry needed — pages are collected via plugin.get_gui_pages()

### Integration in `MainWindow`

`MainWindow._setup_ui()` adds a step after its built-in pages:

```python
# In MainWindow, after building _pages from built-in classes:
plugin_pages = PluginRegistry.get_instance().collect_pages()
for page_cls in plugin_pages:
    page = page_cls().create_widget()
    self._pages.append(page)
    self._stack.addWidget(page)
    # Add a sidebar button for each plugin page
    sidebar.add_plugin_button(page_cls.icon, page_cls.title)
```

---

## 4. Plugin Discovery & Loading

### `plugins/discovery.py`

Two mechanisms:

#### 4a. Package Entry Points (recommended for pip-installed plugins)

```python
import importlib.metadata

def discover_entry_point_plugins() -> list[type[BasePlugin]]:
    plugins = []
    for ep in importlib.metadata.entry_points(group="opportunityos.plugins"):
        cls = ep.load()
        plugins.append(cls)
    return plugins
```

The plugin's `pyproject.toml`:

```toml
[project.entry-points."opportunityos.plugins"]
example = "opportunityos_plugin_example:ExamplePlugin"
```

#### 4b. Filesystem Discovery (for local/development plugins)

```python
import importlib.util

def discover_filesystem_plugins(plugin_dir: str) -> list[type[BasePlugin]]:
    """Scan plugin_dir for Python packages, import each, find BasePlugin subclasses."""
    plugins = []
    for entry in os.scandir(plugin_dir):
        if entry.is_dir() and (entry.path / "__init__.py").exists():
            spec = importlib.util.spec_from_file_location(entry.name, entry.path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for obj in vars(mod).values():
                if isinstance(obj, type) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                    plugins.append(obj)
    return plugins
```

### `plugins/registry.py`

```python
class PluginRegistry:
    """Singleton — holds all discovered plugins and their state."""

    _instance: PluginRegistry | None = None

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}

    @classmethod
    def get_instance(cls) -> PluginRegistry: ...

    def discover(self, config: PluginSettings) -> None:
        """Run both discovery mechanisms."""
        pass  # calls discover_entry_point_plugins + discover_filesystem_plugins

    def enable(self, name: str) -> None: ...
    def disable(self, name: str) -> None: ...
    def get(self, name: str) -> BasePlugin: ...
    def list(self) -> list[dict]: ...  # name, version, enabled, capabilities

    def collect_search_providers(self) -> list[SearchProvider]: ...
    def collect_ranking_providers(self) -> list[RankingProvider]: ...
    def collect_data_sources(self) -> list[DataSourceProvider]: ...
    def collect_notification_channels(self) -> list[BaseNotificationProvider]: ...
    def collect_pages(self) -> list[PagePlugin]: ...
```

`collect_*` methods iterate all enabled plugins, call the corresponding `get_*` method, instantiate each returned class, and return the list.

---

## 5. Wiring into the Application

### Backend — `backend/main.py`

```python
from plugins.registry import PluginRegistry
from plugins.discovery import discover_entry_point_plugins

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:
    init_db()

    # ── Plugin bootstrap ────────────────────────────────────────────
    registry = PluginRegistry.get_instance()
    registry.discover(cfg.plugins)
    for provider_class in registry.collect_search_providers():
        SearchRegistry.default().register(provider_class())
    for provider_class in registry.collect_ranking_providers():
        RankingRegistry.default().register(provider_class())
    for provider_class in registry.collect_data_sources():
        DataSourceRegistry.default().register(provider_class())
    for provider_class in registry.collect_notification_channels():
        NotificationChannelRegistry.default().register(provider_class())

    _scheduler = create_and_start_scheduler(cfg)
    yield
    if _scheduler:
        _scheduler.stop()
```

### Frontend — `frontend/main.py`

```python
def main() -> None:
    app = QApplication(sys.argv)
    # ...
    registry = PluginRegistry.get_instance()
    registry.discover(get_config().plugins)
    window = MainWindow(plugin_registry=registry)
    # ...
```

### Frontend — `frontend/windows/main_window.py`

`MainWindow.__init__` accepts an optional `plugin_registry` parameter and calls `_add_plugin_pages()` after `_setup_ui()`.

---

## 6. Plugin Management API

Endpoints under `/api/v1/plugins`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/plugins` | List all discovered plugins (name, version, enabled, capabilities) |
| `POST` | `/plugins/{name}/enable` | Enable a plugin at runtime |
| `POST` | `/plugins/{name}/disable` | Disable a plugin at runtime |

Response schema:

```json
{
  "name": "example",
  "version": "0.1.0",
  "description": "Example plugin for demonstration",
  "author": "Jane Doe",
  "enabled": true,
  "capabilities": ["search", "ranking"]
}
```

---

## 7. SDK Exports

### `plugins/sdk/__init__.py` — Public API for plugin authors

```python
from plugins.base import BasePlugin
from plugins.sdk.types import (
    SearchProvider,        # re-export from services.search
    RankingProvider,       # new
    DataSourceProvider,    # new
    NotificationChannel,   # re-export from services.notifications
    PagePlugin,            # new
)
```

Plugin authors only need `from opportunityos_plugin_sdk import BasePlugin, SearchProvider, RankingProvider`.

---

## 8. Complete Plugin Example

```python
# opportunityos_plugin_example/plugin.py
from opportunityos_plugin_sdk import BasePlugin, SearchProvider, RankingProvider

class ExamplePlugin(BasePlugin):
    plugin_name = "example"
    plugin_version = "0.1.0"
    plugin_description = "Example search + ranking plugin"
    plugin_author = "Jane Doe"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type[SearchProvider]]:
        return [ExampleSearch]

    def get_ranking_providers(self) -> list[type[RankingProvider]]:
        return [ExampleRanking]


class ExampleSearch(SearchProvider):
    @property
    def name(self) -> str:
        return "ExampleSearch"

    async def search(self, query: str, count: int = 10, offset: int = 0) -> list[SearchResult]:
        ...


class ExampleRanking(RankingProvider):
    @property
    def name(self) -> str:
        return "ExampleRanking"

    async def rank(self, opportunities: list[dict], profile: dict) -> list[dict]:
        ...
```

---

## 9. Migration Path

| Step | What changes |
|------|-------------|
| 1 | Create `plugins/registry.py`, `plugins/discovery.py`, `plugins/sdk/` package |
| 2 | Add `channel_name` property to `BaseNotificationProvider`; create `NotificationChannelRegistry` |
| 3 | Create `RankingProvider` ABC + `RankingRegistry` |
| 4 | Create `DataSourceProvider` ABC + `DataSourceRegistry` |
| 5 | Create `PagePlugin` ABC |
| 6 | Wire `PluginRegistry` into `backend/main.py` lifespan and `frontend/main.py` startup |
| 7 | Add `/api/v1/plugins/*` endpoints |
| 8 | Modify `NotificationService`, `SearchPipeline`, and `MainWindow` to read from registries |
| 9 | Write integration tests with a test plugin fixture |
