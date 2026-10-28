"""
Configuration flow tests.

Features: configuration_setup
See: docs/FEATURES.md#10-configuration-setup
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
import voluptuous as vol
from grocy.errors import GrocyError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.grocy.config_flow import (
    GrocyFlowHandler,
    _get_options_schema,
    _normalize_url_and_port,
    async_migrate_entry,
)
from custom_components.grocy.const import (
    CHORE_DONE_BY_API_KEY_OWNER,
    CHORE_DONE_BY_ASSIGNED_USER,
    CONF_API_KEY,
    CONF_CALENDAR_FIX_TIMEZONE,
    CONF_CALENDAR_SYNC_INTERVAL,
    CONF_CHORE_DONE_BY,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_CALENDAR_SYNC_INTERVAL,
    DOMAIN,
)

pytestmark = pytest.mark.feature("configuration_setup")


def _grocy_error(status: int, body: str = '{"error_message": "x"}') -> GrocyError:
    """Build the error grocy-py raises for an HTTP error response."""
    response = requests.Response()
    response.status_code = status
    response._content = body.encode()
    return GrocyError(response)


async def _user_step_error(
    hass, data: dict, side_effect: Exception | None
) -> tuple[dict | None, MagicMock]:
    """Run the user step with Grocy mocked; return the form errors and the mock."""
    flow = GrocyFlowHandler()
    flow.hass = hass

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        mock_grocy.return_value.system.info.side_effect = side_effect
        result = await flow.async_step_user(data)

    return result.get("errors"), mock_grocy


async def test_user_step_creates_entry(hass, config_entry_data) -> None:
    flow = GrocyFlowHandler()
    flow.hass = hass

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.return_value = {"version": "4.0"}
        mock_grocy.return_value = client

        result = await flow.async_step_user(config_entry_data)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == config_entry_data
    assert result["title"] == "Grocy"


async def test_user_step_handles_auth_failure(hass, config_entry_data) -> None:
    flow = GrocyFlowHandler()
    flow.hass = hass

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.side_effect = _grocy_error(401)
        mock_grocy.return_value = client

        result = await flow.async_step_user(config_entry_data)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_step_handles_connection_error(hass, config_entry_data) -> None:
    """Test handling of connection errors."""
    flow = GrocyFlowHandler()
    flow.hass = hass

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.side_effect = ConnectionError("Connection refused")
        mock_grocy.return_value = client

        result = await flow.async_step_user(config_entry_data)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_handles_timeout_error(hass, config_entry_data) -> None:
    """Test handling of timeout errors."""
    flow = GrocyFlowHandler()
    flow.hass = hass

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.side_effect = TimeoutError("Request timed out")
        mock_grocy.return_value = client

        result = await flow.async_step_user(config_entry_data)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "timeout"}


async def test_abort_when_configured(hass, mock_config_entry) -> None:
    mock_config_entry.add_to_hass(hass)

    flow = GrocyFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_credentials_use_full_payload(hass) -> None:
    flow = GrocyFlowHandler()
    flow.hass = hass

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    user_input = {
        CONF_URL: "https://demo.grocy.info/demo",
        CONF_API_KEY: "token",
        CONF_PORT: 1234,
        CONF_VERIFY_SSL: True,
    }

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.return_value = {"version": "4.0"}
        mock_grocy.return_value = client

        result = await flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    mock_grocy.assert_called_once_with(
        "https://demo.grocy.info",
        "token",
        port=1234,
        path="demo",
        verify_ssl=True,
    )
    assert result["data"] == user_input


async def test_reconfigure_step_shows_form(hass, mock_config_entry) -> None:
    """Test reconfigure step shows form with current values."""
    mock_config_entry.add_to_hass(hass)

    flow = GrocyFlowHandler()
    flow.hass = hass
    flow._get_reconfigure_entry = MagicMock(return_value=mock_config_entry)

    result = await flow.async_step_reconfigure()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_step_updates_entry(hass, mock_config_entry) -> None:
    """Test reconfigure step updates config entry on success."""
    mock_config_entry.add_to_hass(hass)

    flow = GrocyFlowHandler()
    flow.hass = hass
    flow._get_reconfigure_entry = MagicMock(return_value=mock_config_entry)
    flow.async_update_reload_and_abort = MagicMock(
        return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
    )

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    new_data = {
        CONF_URL: "https://new.grocy.info",
        CONF_API_KEY: "new_token",
        CONF_PORT: 9999,
        CONF_VERIFY_SSL: True,
    }

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.return_value = {"version": "4.0"}
        mock_grocy.return_value = client

        result = await flow.async_step_reconfigure(new_data)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    flow.async_update_reload_and_abort.assert_called_once_with(
        mock_config_entry,
        data_updates=new_data,
    )


async def test_reconfigure_step_handles_error(hass, mock_config_entry) -> None:
    """Test reconfigure step shows error on failure."""
    mock_config_entry.add_to_hass(hass)

    flow = GrocyFlowHandler()
    flow.hass = hass
    flow._get_reconfigure_entry = MagicMock(return_value=mock_config_entry)

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    new_data = {
        CONF_URL: "https://new.grocy.info",
        CONF_API_KEY: "bad_token",
        CONF_PORT: 9999,
        CONF_VERIFY_SSL: True,
    }

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.side_effect = _grocy_error(401)
        mock_grocy.return_value = client

        result = await flow.async_step_reconfigure(new_data)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_step_shows_confirm_form(hass, mock_config_entry) -> None:
    """Test reauth step shows confirmation form."""
    mock_config_entry.add_to_hass(hass)

    flow = GrocyFlowHandler()
    flow.hass = hass
    flow._get_reauth_entry = MagicMock(return_value=mock_config_entry)

    result = await flow.async_step_reauth(dict(mock_config_entry.data))

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_confirm_updates_entry(hass, mock_config_entry) -> None:
    """Test reauth confirm step updates config entry on success."""
    mock_config_entry.add_to_hass(hass)

    flow = GrocyFlowHandler()
    flow.hass = hass
    flow._get_reauth_entry = MagicMock(return_value=mock_config_entry)
    flow.async_update_reload_and_abort = MagicMock(
        return_value={"type": FlowResultType.ABORT, "reason": "reauth_successful"}
    )

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    user_input = {CONF_API_KEY: "new_api_key"}

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.return_value = {"version": "4.0"}
        mock_grocy.return_value = client

        result = await flow.async_step_reauth_confirm(user_input)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    flow.async_update_reload_and_abort.assert_called_once_with(
        mock_config_entry,
        data_updates={CONF_API_KEY: "new_api_key"},
    )


async def test_reauth_confirm_handles_error(hass, mock_config_entry) -> None:
    """Test reauth confirm step shows error on failure."""
    mock_config_entry.add_to_hass(hass)

    flow = GrocyFlowHandler()
    flow.hass = hass
    flow._get_reauth_entry = MagicMock(return_value=mock_config_entry)

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    user_input = {CONF_API_KEY: "bad_api_key"}

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.side_effect = _grocy_error(401)
        mock_grocy.return_value = client

        result = await flow.async_step_reauth_confirm(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_migrate_entry_v1_adds_calendar_defaults(hass, config_entry_data) -> None:
    """
    A v1 entry gains the calendar options and becomes 2.3.

    Entries created before ConfigFlow.VERSION was raised to 2 are still out in
    the wild. If this path breaks, an upgrade bricks those installs.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Grocy",
        data=config_entry_data,
        entry_id="v1-entry",
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 2
    assert entry.minor_version == 3
    assert entry.options == {
        CONF_CALENDAR_SYNC_INTERVAL: DEFAULT_CALENDAR_SYNC_INTERVAL,
        CONF_CALENDAR_FIX_TIMEZONE: True,
    }
    # The original credentials must survive the migration untouched.
    assert entry.data == config_entry_data


async def test_migrate_entry_v2_3_is_left_alone(hass, config_entry_data) -> None:
    """Migration is idempotent: an already-migrated entry is not rewritten."""
    options = {CONF_CALENDAR_SYNC_INTERVAL: 42, CONF_CALENDAR_FIX_TIMEZONE: False}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Grocy",
        data=config_entry_data,
        options=options,
        entry_id="v2-3-entry",
        version=2,
        minor_version=3,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.minor_version == 3
    assert entry.data == config_entry_data
    assert entry.options == options


async def test_migrate_entry_v2_1_moves_port_from_url(hass, config_entry_data) -> None:
    """
    A 2.1 entry whose URL carries a port is repaired and becomes 2.3.

    v1.16.0 appended the port field to such a URL and never connected (#68).
    """
    data = {
        **config_entry_data,
        CONF_URL: "http://192.168.1.10:9283",
        CONF_PORT: 9192,
        CONF_CALENDAR_SYNC_INTERVAL: 42,
        CONF_CALENDAR_FIX_TIMEZONE: False,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Grocy",
        data=data,
        entry_id="v2-1-entry",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 2
    assert entry.minor_version == 3
    assert entry.data[CONF_URL] == "http://192.168.1.10"
    assert entry.data[CONF_PORT] == 9283
    assert entry.data[CONF_API_KEY] == config_entry_data[CONF_API_KEY]
    assert entry.options[CONF_CALENDAR_SYNC_INTERVAL] == 42


async def test_migrate_entry_v2_2_moves_options(hass, config_entry_data) -> None:
    """
    The options move from data to options. The old copy in options is dropped.

    The old options flow saved its whole form, with the API key, to options.
    """
    data = {
        **config_entry_data,
        CONF_CALENDAR_SYNC_INTERVAL: 42,
        CONF_CALENDAR_FIX_TIMEZONE: False,
        CONF_CHORE_DONE_BY: CHORE_DONE_BY_ASSIGNED_USER,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Grocy",
        data=data,
        options={**data, CONF_CALENDAR_SYNC_INTERVAL: 7},
        entry_id="v2-2-entry",
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.minor_version == 3
    assert entry.data == config_entry_data
    assert entry.options == {
        CONF_CALENDAR_SYNC_INTERVAL: 42,
        CONF_CALENDAR_FIX_TIMEZONE: False,
        CONF_CHORE_DONE_BY: CHORE_DONE_BY_ASSIGNED_USER,
    }


def test_chore_done_by_defaults_to_the_api_key_owner() -> None:
    """A new entry logs chores for the API key owner, as Grocy does (#81)."""
    options = _get_options_schema({})({})

    assert options[CONF_CHORE_DONE_BY] == CHORE_DONE_BY_API_KEY_OWNER


@pytest.mark.parametrize(("interval", "valid"), [(0, False), (-1, False), (1, True)])
def test_calendar_sync_interval_must_be_at_least_one_minute(interval, valid) -> None:
    """0 would schedule the calendar sync in a tight loop (#76)."""
    schema = _get_options_schema({})
    data = {CONF_CALENDAR_SYNC_INTERVAL: interval}

    if valid:
        assert schema(data)[CONF_CALENDAR_SYNC_INTERVAL] == interval
    else:
        with pytest.raises(vol.Invalid):
            schema(data)


def test_url_with_password_is_logged_only_at_debug(caplog) -> None:
    """The URL can carry user:password@, so it goes to the log only at DEBUG (#82)."""
    user_input = {CONF_URL: "http://user:s3cret@192.168.1.10:9283", CONF_PORT: 9192}

    caplog.set_level(logging.INFO, logger="custom_components.grocy")
    _normalize_url_and_port(user_input)
    assert "s3cret" not in caplog.text

    caplog.set_level(logging.DEBUG, logger="custom_components.grocy")
    _normalize_url_and_port(user_input)
    assert "s3cret" in caplog.text


async def test_user_step_moves_port_from_url(hass, config_entry_data) -> None:
    """A port typed into the URL is used as the port and stripped from the URL."""
    flow = GrocyFlowHandler()
    flow.hass = hass

    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)

    user_input = {
        **config_entry_data,
        CONF_URL: "http://192.168.1.10:9283/grocy",
        CONF_PORT: 9192,
    }

    with patch("custom_components.grocy.config_flow.Grocy") as mock_grocy:
        client = MagicMock()
        client.system.info.return_value = {"version": "4.0"}
        mock_grocy.return_value = client

        result = await flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == "http://192.168.1.10/grocy"
    assert result["data"][CONF_PORT] == 9283

    # The connection test must already use the corrected values.
    mock_grocy.assert_called_once_with(
        "http://192.168.1.10",
        config_entry_data[CONF_API_KEY],
        port=9283,
        path="grocy",
        verify_ssl=config_entry_data[CONF_VERIFY_SSL],
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_grocy_error(401), "invalid_auth"),
        (_grocy_error(403), "invalid_auth"),
        (_grocy_error(500), "cannot_connect"),
        (requests.exceptions.SSLError("certificate verify failed"), "ssl_error"),
        (requests.exceptions.ConnectTimeout("timed out"), "timeout"),
        (TimeoutError("timed out"), "timeout"),
        (requests.exceptions.ConnectionError("refused"), "cannot_connect"),
        (ConnectionError("refused"), "cannot_connect"),
        (requests.exceptions.InvalidURL("bad host"), "cannot_connect"),
        (
            requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0),
            "cannot_connect",
        ),
        (RuntimeError("boom"), "unknown"),
    ],
    ids=lambda value: value if isinstance(value, str) else type(value).__name__,
)
async def test_user_step_maps_each_failure_to_its_message(
    hass, config_entry_data, error, expected
) -> None:
    """
    Only a 401 or 403 from Grocy means a wrong API key (#57).

    requests' exceptions do not subclass the builtin ConnectionError, so
    every network or SSL failure used to be reported as invalid_auth.
    """
    errors, _ = await _user_step_error(hass, config_entry_data, error)

    assert errors == {"base": expected}


def test_html_error_page_maps_to_cannot_connect() -> None:
    """A non-Grocy server answers with HTML; grocy-py keeps it as a GrocyError."""
    from custom_components.grocy.config_flow import _error_key

    error = _grocy_error(404, "<!DOCTYPE html><html></html>")

    assert error.status_code == HTTPStatus.NOT_FOUND
    assert _error_key(error) == "cannot_connect"


@pytest.mark.parametrize(
    "url",
    [
        "https://homeassistant.local:8123/a0d7b954_grocy",
        "http://homeassistant.local:8123/a0d7b954_grocy/",
        "http://192.168.1.2:8123/api/hassio_ingress/abcDEF123",
    ],
)
async def test_user_step_rejects_ingress_url(hass, config_entry_data, url) -> None:
    """An add-on ingress URL can never work with an API key (#57)."""
    errors, mock_grocy = await _user_step_error(
        hass, {**config_entry_data, CONF_URL: url}, None
    )

    assert errors == {"base": "ingress_url"}
    mock_grocy.assert_not_called()


@pytest.mark.parametrize(
    "url",
    ["http://grocy.local/grocy", "http://grocy.local/abcdef12", "http://grocy.local"],
)
async def test_user_step_accepts_normal_subpath(hass, config_entry_data, url) -> None:
    """A Grocy subdirectory is not mistaken for an ingress URL."""
    errors, mock_grocy = await _user_step_error(
        hass, {**config_entry_data, CONF_URL: url}, None
    )

    assert errors is None
    mock_grocy.assert_called_once()


async def test_user_flow_recovers_from_an_error(
    hass, enable_custom_integrations, config_entry_data
) -> None:
    """Through the flow manager: form, an error, then the entry is created."""
    hass.config.components.add("http")
    hass.http = MagicMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(
            "custom_components.grocy.config_flow._async_test_credentials",
            new_callable=AsyncMock,
            side_effect=["cannot_connect", None],
        ),
        patch("custom_components.grocy.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config_entry_data
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config_entry_data
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == config_entry_data[CONF_URL]
    assert result["data"][CONF_API_KEY] == config_entry_data[CONF_API_KEY]


async def test_options_flow_starts_from_the_entry(
    hass, enable_custom_integrations, config_entry_data
) -> None:
    """The options form has only the options, with the stored values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        options={CONF_CALENDAR_SYNC_INTERVAL: 15},
        version=2,
        minor_version=3,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    defaults = {key: key.default() for key in result["data_schema"].schema}
    assert defaults == {
        CONF_CALENDAR_SYNC_INTERVAL: 15,
        CONF_CALENDAR_FIX_TIMEZONE: True,
        CONF_CHORE_DONE_BY: CHORE_DONE_BY_API_KEY_OWNER,
    }


async def test_options_flow_saves_options_and_reloads(
    hass, enable_custom_integrations, config_entry_data
) -> None:
    """The options go to ConfigEntry.options, data stays, and HA reloads."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=config_entry_data, version=2, minor_version=3
    )
    entry.add_to_hass(hass)
    new_options = {
        CONF_CALENDAR_SYNC_INTERVAL: 15,
        CONF_CALENDAR_FIX_TIMEZONE: False,
        CONF_CHORE_DONE_BY: CHORE_DONE_BY_ASSIGNED_USER,
    }

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], new_options
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == new_options
    assert entry.data == config_entry_data
    reload.assert_called_once_with(entry.entry_id)
