"""Configuration flow tests.

Features: configuration_setup
See: docs/FEATURES.md#10-configuration--setup
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_REAUTH
from homeassistant.data_entry_flow import FlowResultType

from custom_components.grocy.config_flow import GrocyFlowHandler
from custom_components.grocy.const import (
    CONF_API_KEY,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
)

pytestmark = pytest.mark.feature("configuration_setup")


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
        client.system.info.side_effect = RuntimeError("boom")
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
        client.system.info.side_effect = RuntimeError("Invalid API key")
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
        client.system.info.side_effect = RuntimeError("Invalid API key")
        mock_grocy.return_value = client

        result = await flow.async_step_reauth_confirm(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
