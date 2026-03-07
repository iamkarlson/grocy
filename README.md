[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

# Grocy Custom Component for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for [Grocy](https://grocy.info/) — the self-hosted groceries & household management solution. Track stock, chores, tasks, batteries, meal plans, and shopping lists directly from your Home Assistant dashboard.

This integration communicates with an existing Grocy installation via its API, powered by the [grocy-py](https://github.com/iamkarlson/grocy-py) library.

> **Requirements**
>
> - **Grocy** version 3.2 or above
> - **Home Assistant** version 2021.12 or above (for integration v4.3.3+)
>
> You must have Grocy already installed and running. You can set it up using the [Grocy add-on](https://github.com/hassio-addons/addon-grocy) or another method from the [Grocy website](https://grocy.info/).

---

## Setup Guide

### Installation

#### HACS (Recommended)

The easiest way to install this integration is with [HACS][hacs].

1. Install [HACS][hacs-download] if you don't have it yet
2. In Home Assistant, go to `HACS` → 3 dot menu → "Custom repositories"
3. Add this repository URL: `https://github.com/iamkarlson/grocy`
4. Select "Integration" as the type
5. Find "Grocy custom component" in the list and click on it
6. Click "Download" → "Download" → Restart Home Assistant
7. Install the [Grocy integration](https://my.home-assistant.io/redirect/config_flow_start/?domain=grocy)

Future updates will appear automatically within Home Assistant via HACS.

[hacs]: https://hacs.xyz
[hacs-download]: https://hacs.xyz/docs/setup/download

#### Manual Installation

1. Update Home Assistant to version 2026.02 or newer
2. Download this repository
3. Copy the `custom_components/grocy` folder into your Home Assistant's `custom_components` folder
4. Restart Home Assistant

### Configuration

#### Adding the Integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Grocy" and select it
3. Fill in the configuration parameters described below

#### For Grocy Add-on Users

If you use the [official Grocy add-on](https://github.com/hassio-addons/addon-grocy):

1. Install Grocy from the add-on store if you haven't already
2. In the add-on **Configuration** tab, set the Network port to `9192` (see screenshot below)
3. Save changes and restart the add-on
4. Configure the integration with your local Home Assistant address:
   - **URL**: `http://192.168.1.135` (use your HA machine's local IP)
   - **Port**: `9192`

   For example, if your Home Assistant is at `192.168.1.135`, Grocy will be accessible at `http://192.168.1.135:9192`.

![Grocy Add-on Configuration — set the Network port to 9192](grocy-addon-config.png)

#### Configuration Parameters

- **URL**: Your Grocy instance URL (e.g., `http://192.168.1.100` or `https://grocy.example.com`)
  - Start with `http://` or `https://`
  - Do **not** include the port in the URL field
  - If connecting to the Grocy add-on, do **not** include any path after the URL
  - Subdomains are supported (fill out the full URL)
  - Works with Duck DNS addresses as well
- **API Key**: Generate in Grocy via the wrench icon → "Manage API keys" → add a new key and copy it
- **Port**:
  - `9192` for the Grocy add-on (without HTTPS)
  - `80` for HTTP or `443` for HTTPS (or your custom port)
  - Make sure the port is open in your router, or use your internal Home Assistant address
- **Verify SSL**: Check if using HTTPS with a valid certificate
- **Calendar Sync Interval**: How often to sync calendar events from Grocy (in minutes)
  - Default: `5` minutes
  - Lower values provide more frequent updates but increase API usage
- **Fix timezone for calendar**: Workaround for a Grocy timezone issue
  - Default: enabled
  - Grocy may send local times marked as UTC in the iCal feed
  - When enabled, UTC times from Grocy are treated as local time (no conversion)
  - Disable this if your Grocy instance correctly sends UTC times

![Integration Configuration — URL, API Key, Port, and SSL settings](grocy-integration-config.png)

#### Editing Settings After Initial Setup

To change connection settings (URL, API Key, Port, etc.) after initial setup:

1. Go to **Settings → Devices & Services**
2. Find the **Grocy** integration
3. Click the **three dots menu** (⋮) next to the integration
4. Select **"Reconfigure"**
5. Update any settings and click **"Submit"** — the integration will automatically reload

**Note:** The "Edit" button only changes the integration name and area. Use "Configure" to edit connection settings.

---

## Usage Guide

### Entities

**All entities are disabled by default.** You must manually enable the entities you want to use in Home Assistant.

Available entities:

- **Sensors**: one each for chores, meal plan, shopping list, stock, tasks, and batteries
- **Binary sensors**: overdue/expired/expiring/missing products, overdue tasks, overdue chores, and overdue batteries
- **Calendar**: `calendar.grocy_calendar` — displays all Grocy events (chores, tasks, meal plans, products, and more)

If you enable a todo entity (like *todo.grocy_stock*), you should also enable the corresponding sensor. Otherwise you may see "entity is unknown" errors in Home Assistant.

### Calendar Entity

The calendar entity (`calendar.grocy_calendar`) syncs with your Grocy instance's iCal feed and includes:

- Upcoming chore executions
- Task due dates
- Planned meals
- Product expiration dates and other product-related events
- All other Grocy calendar events

The calendar syncs automatically at the interval configured during setup (default: 5 minutes). You can view it through Home Assistant's calendar interface, use it in automations, and integrate it with other calendar integrations.

**Timezone note:** Grocy may send local times marked as UTC in the iCal feed. The "Fix timezone for calendar" option (enabled by default) addresses this by treating UTC times as local time. If your Grocy instance correctly sends UTC times, disable this in the integration configuration.

### Services

The following services are available. For all options, check [Developer Tools: Services](https://my.home-assistant.io/redirect/developer_services/) in Home Assistant.

| Service | Description |
|---|---|
| `grocy.add_generic` | Add a single object of a given entity type |
| `grocy.add_product_to_stock` | Add a given amount of a product to stock |
| `grocy.open_product` | Open a given amount of a product in stock |
| `grocy.track_battery` | Track a battery |
| `grocy.complete_task` | Complete a task |
| `grocy.consume_product_from_stock` | Consume a given amount of a product from stock |
| `grocy.execute_chore` | Execute a chore (with optional timestamp and executor) |
| `grocy.consume_recipe` | Consume a recipe |
| `grocy.add_missing_products_to_shopping_list` | Add currently missing products to a shopping list |
| `grocy.remove_product_in_shopping_list` | Remove a product from a shopping list |

### Feature Reference

For detailed documentation of all feature groups, entities, services, and their parameters, see [docs/FEATURES.md](docs/FEATURES.md).

---

## Troubleshooting

1. **Enable debug logging** by adding this to your `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       grocy.grocy_api_client: debug
       custom_components.grocy: debug
   ```

2. **Ensure compatibility**: Use the latest version of the integration, Grocy, and Home Assistant

3. **Check your setup**: Verify your Grocy URL, API key, and port configuration

4. **Get help**:
   - [Community Forum Discussion](https://community.home-assistant.io/t/grocy-custom-component-and-card-s/218978)
   - [Report Issues on GitHub](https://github.com/iamkarlson/grocy/issues/new?assignees=&labels=&template=bug_report.md&title=)

---

## Contributing

Want to contribute? Check out the [CONTRIBUTING.md](CONTRIBUTING.md) guide for development environment setup, debugging, code structure, testing, and submission guidelines.

### Translations

Translation files are located in `custom_components/grocy/translations/`. Feel free to open a PR if you find an error in a translation.

---

## Acknowledgments

- [Grocy](https://grocy.info/) — the self-hosted groceries & household management solution by [Bernd Bestel](https://berrnd.de/)
- [grocy-py](https://github.com/iamkarlson/grocy-py) — Python wrapper for the Grocy API
- [HACS](https://hacs.xyz) — Home Assistant Community Store
- Originally forked from [custom-components/grocy](https://github.com/custom-components/grocy)
