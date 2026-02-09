from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.data_entry_flow import FlowResultType

from custom_components.grocy.config_flow import GrocyFlowHandler
from custom_components.grocy.const import (
    CONF_API_KEY,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
)


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
    assert result["errors"] == {"base": "auth"}


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
