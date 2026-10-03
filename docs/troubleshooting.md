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

- **Validation errors** from the Grocy API (e.g., unexpected `null` values). Update the integration and [grocy-py](https://github.com/iamkarlson/grocy-py) to the latest version.
- **Connection issues** — see below.

With the latest version of the integration, a failure in one entity type (e.g., stock) will not bring down other entity types (e.g., chores, tasks). If you see only some entities unavailable, check the logs for the specific entity type that failed.

### Connection errors

- Verify the Grocy URL is reachable from your Home Assistant instance.
- Check that the port number is correct.
- Verify your API key is valid (Grocy → Settings → Manage API keys).
- If using HTTPS, ensure your certificate is valid or disable SSL verification in the integration config.

### The URL is the Home Assistant ingress path

A URL like `https://homeassistant.local:8123/a0d7b954_grocy` is the Home Assistant ingress path of the Grocy add-on. Ingress only works inside a logged-in Home Assistant browser session, so a Grocy API key can never authenticate through it. Since 1.17.3 the setup form detects this URL and tells you so.

The integration needs Grocy's own port. In the add-on settings, open **Network** and expose a port (for example 9192). Then use `http://homeassistant.local` as the URL and that port in the **Port** field.

If the add-on does not start after you expose the port, check two things:

- **SSL.** The add-on has `ssl: true` by default. With an exposed port it then needs the certificate files `certfile` and `keyfile` in `/ssl`. Without them it does not start. Turn `ssl` off in the add-on configuration, or add the certificates. With `ssl` on and a certificate that does not match the host name, use `https://` and turn off **Verify SSL Certificate** in the integration.
- **The port.** Another service on the host can already use it. Pick another port.

### Setup says "Invalid API key" for a wrong address

Before 1.17.3, the setup form reported every connection or SSL problem as an invalid API key. Since 1.17.3 it shows the real cause: cannot connect, timeout, SSL certificate check failed, or the ingress address. "Invalid API key" now means that Grocy answered and rejected the key.

### The port is in the URL

Since 1.17.0, a port written into the URL (`http://192.168.1.10:9283`) is used as the port and the **Port** field is ignored. Older versions appended the port field to the URL and tried to reach `http://192.168.1.10:9283:9192`. Existing entries are corrected on upgrade.

### Entities not appearing

- Go to **Settings → Devices & services → Grocy** and check the entity list.
- Some entities are disabled by default. Click on the entity and enable it.
- Make sure the corresponding feature is enabled in Grocy (e.g., meal planning, chores, tasks).

## Filing a bug report

If your issue persists, [open a bug report](https://github.com/iamkarlson/grocy/issues/new?template=bug_report.yml) with:

1. Your HA, Grocy, and integration versions
2. Debug log output (see above)
3. Steps to reproduce the issue
