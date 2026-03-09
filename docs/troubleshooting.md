# Troubleshooting

## Enable debug logging

Add the following to your `configuration.yaml` and restart Home Assistant:

```yaml
logger:
  default: warning
  logs:
    custom_components.grocy: debug
```

To view logs, go to **Settings → System → Logs** and filter by `grocy`.

## Common issues

### All entities unavailable

This usually means the coordinator update cycle failed entirely. Check the debug logs for specific error messages.

**Possible causes:**

- **Validation errors** from the Grocy API (e.g., unexpected `null` values). Update the integration and [grocy-py](https://github.com/iamkarlson/pygrocy2) to the latest version.
- **Connection issues** — see below.

With the latest version of the integration, a failure in one entity type (e.g., stock) will not bring down other entity types (e.g., chores, tasks). If you see only some entities unavailable, check the logs for the specific entity type that failed.

### Connection errors

- Verify the Grocy URL is reachable from your Home Assistant instance.
- Check that the port number is correct.
- Verify your API key is valid (Grocy → Settings → Manage API keys).
- If using HTTPS, ensure your certificate is valid or disable SSL verification in the integration config.

### Entities not appearing

- Go to **Settings → Devices & services → Grocy** and check the entity list.
- Some entities are disabled by default. Click on the entity and enable it.
- Make sure the corresponding feature is enabled in Grocy (e.g., meal planning, chores, tasks).

## Filing a bug report

If your issue persists, [open a bug report](https://github.com/iamkarlson/grocy/issues/new?template=bug_report.yml) with:

1. Your HA, Grocy, and integration versions
2. Debug log output (see above)
3. Steps to reproduce the issue
