# Grocy Custom Component for Home Assistant

A Home Assistant custom integration for [Grocy](https://grocy.info/) — the self-hosted groceries & household management solution.

## Quick Links

- [Features Reference](FEATURES.md) — entities, services, and test coverage for every feature group
- [GitHub Repository](https://github.com/iamkarlson/grocy)
- [Issue Tracker](https://github.com/iamkarlson/grocy/issues)
- [HACS](https://hacs.xyz) — recommended installation method

## What's Included

| Feature | Sensors | Binary Sensors | Todo Lists | Services |
|---------|---------|----------------|------------|----------|
| Stock Management | 1 | 4 | 1 | 3 |
| Shopping List | 1 | — | 1 | 2 |
| Chore Management | 1 | 1 | 1 | 1 |
| Task Management | 1 | 1 | 1 | 1 |
| Battery Tracking | 1 | 1 | 1 | 1 |
| Meal Planning | 1 | — | 1 | 1 |
| Calendar | — | — | — | 1 |
| Generic CRUD | — | — | — | 3 |

All entities are **disabled by default**. Enable the ones you need in Settings > Devices & Services > Grocy.

## Installation

### HACS (Recommended)

1. Install [HACS](https://hacs.xyz/docs/setup/download) if you don't have it yet
2. In Home Assistant, go to HACS > 3-dot menu > "Custom repositories"
3. Add repository URL: `https://github.com/iamkarlson/grocy`
4. Select "Integration" as the type
5. Find "Grocy custom component" and click Download
6. Restart Home Assistant
7. Add the integration in Settings > Devices & Services

### Manual

1. Download this repository
2. Copy `custom_components/grocy` into your Home Assistant `custom_components` folder
3. Restart Home Assistant
