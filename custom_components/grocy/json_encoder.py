"""JSON encoder for Grocy."""

import datetime as dt
from typing import Any

from homeassistant.helpers.json import ExtendedJSONEncoder


class CustomJSONEncoder(ExtendedJSONEncoder):
    """JSONEncoder for compatibility, falls back to the Home Assistant Core ExtendedJSONEncoder."""

    def default(self, o: Any) -> Any:
        """Convert certain objects."""
        if isinstance(o, (dt.date, dt.time)):
            return o.isoformat()

        return super().default(o)
