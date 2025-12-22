[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

# Grocy Custom Component for Home Assistant

A Home Assistant custom integration for [Grocy](https://grocy.info/) - the self-hosted groceries & household management solution.

---
**IMPORTANT INFORMATION**

**The integration supports Grocy version 3.2 and above.**

**At least Home Assistant version 2021.12 is required for the integration from v4.3.3 and above.**

You must have Grocy software already installed and running. This integration only communicates with an existing installation of Grocy. You can install Grocy using the [Grocy add-on](https://github.com/hassio-addons/addon-grocy) or another installation method found at the [Grocy website](https://grocy.info/).

---

## Installation

### HACS (Recommended)

The easiest way to install this integration is with [HACS][hacs].

1. Install [HACS][hacs-download] if you don't have it yet
2. In Home Assistant, go to `HACS` → 3 dot menu → "Custom repositories"
3. Add this repository URL: `https://github.com/iamkarlson/grocy`
4. Select "Integration" as the type
5. Find "Grocy custom component" in the list and click on it
6. Click "Download" → "Download" → Restart Home Assistant
7. Install the [Grocy integration](https://my.home-assistant.io/redirect/config_flow_start/?domain=grocy)

Future integration updates will appear automatically within Home Assistant via HACS.

[hacs]: https://hacs.xyz
[hacs-download]: https://hacs.xyz/docs/setup/download

### Manual Installation

1. Update Home Assistant to version 2025.02 or newer
2. Download this repository
3. Copy the `custom_components/grocy` folder into your Home Assistant's `custom_components` folder
4. Restart Home Assistant

## Configuration

### Adding the Integration

1. Go to Settings → Devices & Services → Add Integration
2. Search for "Grocy" and select it
3. Configure according to your setup:

#### For Grocy Add-on Users

If you use the [official Grocy add-on](https://github.com/hassio-addons/addon-grocy):

1. Install Grocy from the add-on store if you haven't already
2. In the add-on 'Configuration', set the Network port to `9192` ([see screenshot](#screenshot-addon-config))
3. Save changes and restart the add-on
4. Use port `9192` when configuring the integration

#### Configuration Parameters

- **URL**: Your Grocy instance URL (e.g., `http://192.168.1.100` or `https://grocy.example.com`)
  - Start with `http://` or `https://`
  - Do **not** include the port in the URL field
  - Subdomains are supported
- **API Key**: Generate in Grocy via the wrench icon → "Manage API keys"
- **Port**:
  - `9192` for Grocy add-on (without https)
  - `80` for http or `443` for https (or your custom port)
- **Verify SSL**: Check if using HTTPS with valid certificate
- **Calendar Sync Interval**: How often to sync calendar events from Grocy (in minutes)
  - Default: `5` minutes
  - The calendar includes all events: chores, tasks, meal plans, products, etc.
  - Lower values provide more frequent updates but may increase API usage
- **Fix timezone for calendar**: Workaround for Grocy timezone issue
  - Default: `True` (enabled)
  - Grocy may send local times marked as UTC in the iCal feed
  - When enabled, UTC times from Grocy are treated as local time (no conversion)
  - Disable this if your Grocy instance correctly sends UTC times

![Integration Configuration](grocy-integration-config.png)

**All entities are disabled by default.** Enable the entities you want to use in Home Assistant.

### Editing Integration Settings

To edit connection settings (URL, API Key, Port, etc.) after initial setup:

1. Go to **Settings → Devices & Services**
2. Find the **Grocy** integration
3. Click the **three dots menu** (⋮) next to the integration
4. Select **"Configure"**
5. Update any settings (URL, API Key, Port, Verify SSL, Calendar Sync Interval)
6. Click **"Submit"** - the integration will automatically reload with new settings

**Note:** The "Edit" button only allows changing the integration name and area. Use "Configure" to edit connection settings.


# Entities

**All entities are disabled from the start. You have to manually enable the entities you want to use in Home Assistant.**
You get a sensor each for chores, meal plan, shopping list, stock, tasks and batteries.
You get a binary sensor each for overdue, expired, expiring and missing products and for overdue tasks, overdue chores and overdue batteries.
You get a calendar entity (`calendar.grocy_calendar`) that displays all Grocy events including chores, tasks, meal plans, products, and more.

If you enable a certain entity (like *todo*), you should also enable a sensor. Otherwise, you may have errors in Home Assistant stating that the "entity is unknown".

## Calendar Entity

The calendar entity (`calendar.grocy_calendar`) provides a Home Assistant calendar that syncs with your Grocy instance's iCal feed. It includes:

- **Chores**: Upcoming chore executions
- **Tasks**: Task due dates
- **Meal Plans**: Planned meals
- **Products**: Product expiration dates and other product-related events
- **All other Grocy calendar events**

The calendar automatically syncs at the interval configured during setup (default: 5 minutes). You can view and interact with the calendar through Home Assistant's calendar interface, use it in automations, and integrate it with other calendar integrations.

**Note on Timezone Handling:** Grocy may send local times marked as UTC in the iCal feed. The "Fix timezone for calendar" option (enabled by default) addresses this by treating UTC times as local time. If your Grocy instance correctly sends UTC times, you can disable this option in the integration configuration.


# Services

The following services come with the integration. For all available options check the [Developer Tools: Services](https://my.home-assistant.io/redirect/developer_services/) within Home Assistant.

- **Grocy: Add Generic** (_grocy.add_generic_)

Adds a single object of the given entity type.

- **Grocy: Add Product To Stock** (_grocy.add_product_to_stock_)

Adds a given amount of a product to the stock.

- **Grocy: Open Product** (_grocy.open_product_)

Opens a given amount of a product in stock.

- **Grocy: Track Battery** (_grocy.track_battery_)

Tracks the given battery.

- **Grocy: Complete Task** (_grocy.complete_task_)

Completes the given task.

- **Grocy: Consume Product From Stock** (_grocy.consume_product_from_stock_)

Consumes a given amount of a product from the stock.

- **Grocy: Execute Chore** (_grocy.execute_chore_)

Executes the given chore with an optional timestamp and executor.

- **Grocy: Consume Recipe** (_grocy.consume_recipe_)

Consumes the given recipe.

- **Grocy: Add Missing Products to Shopping List** (_grocy.add_missing_products_to_shopping_list_)

Adds currently missing products to a given shopping list.

- **Grocy: Remove Product in Shopping List** (_grocy.remove_product_in_shopping_list_)

Removes a product in the given shopping list.

# Translations

Before this was forked, translation was done using paid service lokalise.com. However, it's now just bunch of `json` files in `custom_components/grocy/translations/` directory. Feel free to open a PR if there's an error in translation.


# Troubleshooting

If you experience issues with the integration:

1. **Enable debug logging** by adding this to your `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       pygrocy.grocy_api_client: debug
       custom_components.grocy: debug
   ```

2. **Ensure compatibility**: Use the latest version of the integration, Grocy, and Home Assistant

3. **Check your setup**: Verify your Grocy URL, API key, and port configuration

4. **Get help**:
   - [Community Forum Discussion](https://community.home-assistant.io/t/grocy-custom-component-and-card-s/218978)
   - [Report Issues on GitHub](https://github.com/iamkarlson/grocy/issues/new?assignees=&labels=&template=bug_report.md&title=)

## Contributing

Want to contribute to this project? Check out our [CONTRIBUTING.md](CONTRIBUTING.md) guide for:

- Setting up the development environment
- Debugging with VSCode
- Running development tasks
- Code structure overview
- Testing procedures
- Submission guidelines

We welcome contributions of all kinds! 🎉

## Screenshots

### <a name="screenshot-addon-config"></a>Add-on Port Configuration

![Grocy Add-on Configuration](grocy-addon-config.png)
# <a name="integration-configuration"></a>Integration configuration

## URL
The Grocy url should be in the form below (start with `http://` or `https://`) and point to your Grocy instance. If you use a SSL certificate you should have `https` and also check the "Verify SSL Certificate" box. Do **not** enter a port in the url field. Subdomains are also supported, fill out the full url in the field.

## API key
Go to your Grocy instance. Navigate via the wrench icon in the top right corner to "Manage API keys" and add a new API key. Copy and paste the generated key.

## Port
It should work with for example a Duck DNS address as well, but you still have to access it via a port, and the above instructions for the url still apply.
- If you have configured the [Grocy add-on](#addon) as described, use port 9192 (without https). Either be sure the port is open in your router or use your internal Home Assistant address.
- If you have configured an [external Grocy](#both) instance and not sure, use port 80 for http or port 443 for https. Unless you have set a custom port for Grocy.

![alt text](grocy-integration-config.png)


# <a name="screenshot-addon-config"></a>Add-on port configuration

![alt text](grocy-addon-config.png)
