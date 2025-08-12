# Contributing to Grocy Custom Component

## Quick Start

Fork the repo, open in VS Code dev container, run `scripts/setup` then `scripts/develop`. Access Home Assistant at [localhost:8123](http://localhost:8123).

## Development Environment

### Dev Container Setup

Dev containers provide isolated, reproducible development environments using Docker. Install the "Dev Containers" extension in VS Code, then:

```bash
git clone git@github.com:iamkarlson/grocy.git
cd grocy-custom-component
code .
# VS Code will detect .devcontainer config and prompt "Reopen in Container" - click it
# Otherwise, run "Remote-Containers: Reopen in Container" from the command palette
# Container builds automatically with Python 3.13, HA dependencies, and tools pre-installed
```

The container mounts your local code as a volume, so file changes persist. Terminal runs inside the container with all dependencies available.

### Debugging

The project includes debugpy configuration. Start Home Assistant (`scripts/develop`), then attach VSCode debugger (`F5` → "Python: Attach to Home Assistant"). Set breakpoints in `custom_components/grocy/` files.

## Architecture

- **Coordinator pattern**: Single `DataUpdateCoordinator` fetches all data from Grocy API
- **Entity inheritance**: Common `GrocyEntity` base class handles coordinator integration
- **Service layer**: `grocy_data.py` abstracts pygrocy API calls
- **Config flow**: Standard HA config entry setup with validation

## Key Components

### Data Flow
1. `coordinator.py` polls Grocy API every 30 seconds
2. Entities subscribe to coordinator updates
3. Services interact directly with API for commands

### Adding New Entities
1. Inherit from `GrocyEntity` in `entity.py`
2. Implement required properties (`name`, `state`, etc.)
3. Register in platform files (`sensor.py`, `binary_sensor.py`)

### Adding New Services
1. Add service definition to `services.yaml`
2. Implement handler in `services.py`
3. Register in `__init__.py`

## Testing

Manual testing: Configure integration in dev environment, enable entities, test functionality.

For unit tests (if available): `pytest tests/`

## Pull Requests

- Create feature branch: `git checkout -b feature/description`
- Test changes in dev environment
- Ensure compatibility with Grocy 3.2+
- Update docs if needed
- Submit PR with clear description

## Common Issues

- **Port conflicts**: `lsof -i :8123` to find conflicting processes
- **Import errors**: Check `PYTHONPATH` includes `custom_components/`
- **Config changes**: Restart HA after modifying `manifest.json` or `__init__.py`
- **Debug logging**: Add to `config/configuration.yaml`:
  ```yaml
  logger:
    logs:
      custom_components.grocy: debug
  ```
