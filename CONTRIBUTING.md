# Contributing to Grocy Custom Component

This guide keeps development fast while preserving the context you need.

## Quick Start

1. Fork the repository and clone your fork.
2. Ensure Docker, Docker Compose, and [Task](https://taskfile.dev) are installed locally.
3. Install tooling with `task install`.

## Development Workflow

- Start Grocy backend: `task grocy:up` (exposes http://localhost:9192).
- Launch Home Assistant: `task ha:run` for foreground logs or `task ha:up` to run it in the background.
- Inspect logs: `task grocy:logs` and `task ha:logs`.
- Launch VSCode debugger "Attach to Home Assistant"
- Set breakpoints and debug info should be available
- To apply code changes, restart HA: `task ha:restart` or restart it from the HA UI.
- Shut everything down: `task grocy:down` and `task ha:down`.
- Need a fresh config snapshot? Run `task clean` (removes local `config`).


## Architecture Overview

- **Coordinator pattern**: [coordinator.py](custom_components/grocy/coordinator.py) houses a single `DataUpdateCoordinator` fetching all Grocy data on a 30 s interval.
- **Base entity**: [entity.py](custom_components/grocy/entity.py) defines `GrocyEntity` that wires coordinator data with Home Assistant entities.
- **Service layer**: [grocy_data.py](custom_components/grocy/grocy_data.py) wraps `grocy-py` to keep API calls isolated.
- **Config flow**: [config_flow.py](custom_components/grocy/config_flow.py) validates URL, API key, and port before creating config entries.

## Extending the Integration

### Adding Entities

1. Inherit from `GrocyEntity` (see [sensor.py](custom_components/grocy/sensor.py) or [binary_sensor.py](custom_components/grocy/binary_sensor.py)).
2. Expose entity-specific state/attributes sourced from the coordinator payload.
3. Register the entity in the appropriate `async_setup_entry` platform.

### Adding Services

1. Declare service metadata in [services.yaml](custom_components/grocy/services.yaml).
2. Implement the handler in [services.py](custom_components/grocy/services.py) using `GrocyData` helpers.
3. Register the service inside [__init__.py](custom_components/grocy/__init__.py) during integration setup.

## Testing

- **Manual**: Configure the integration against the dev containers, enable desired entities, and exercise automations/services.
- **Automated**: Run `pytest tests/` when adding or updating test coverage (add tests if functionality warrants it).
- **Static checks**: `uv run pre-commit run --all-files` keeps linting in sync with CI.

## Pull Requests

- Branch from `main`, rebase before submitting, and avoid unrelated churn.
- Describe behavior changes, testing performed, and any user-facing impacts.
- Update docs, translations, or manifests when behavior or dependencies change.
- Target compatibility with Grocy 3.2+ and recent Home Assistant releases (see README requirements).

## Common Pitfalls

- **Port conflicts**: `lsof -i :8123` or `:9192` helps locate existing services.
- **Stale caches**: Run `task ha:restart` after touching manifests or service registration.
- **Import resolution**: Ensure Home Assistant config path includes `custom_components/grocy` (Docker mounts in docker-compose.yml handle this).
- **Verbose logging**: Add to `config/configuration.yaml` when investigating:
	```yaml
	logger:
		logs:
			custom_components.grocy: debug
			grocy.grocy_api_client: debug
	```
