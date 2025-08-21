"""Validate and reorder translation files."""  # noqa: INP001

import json
import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Translation directory path
TRANSLATIONS_DIR = Path("custom_components/grocy/translations")


def get_keys(obj, prefix=""):
    """Get all nested keys as dot notation."""
    keys = set()
    for key, value in obj.items():
        full_key = f"{prefix}.{key}" if prefix else key
        keys.add(full_key)
        if isinstance(value, dict):
            keys.update(get_keys(value, full_key))
    return keys


def main():
    """Validate translation files and reorder their contents."""
    en_file = TRANSLATIONS_DIR / "en.json"

    if not en_file.exists():
        logger.error("No en.json found at %s", en_file)
        sys.exit(1)

    with en_file.open() as f:
        base_keys = get_keys(json.load(f))

    all_valid = True
    for file in TRANSLATIONS_DIR.glob("*.json"):
        if file.name == "en.json":
            continue

        with file.open() as f:
            data = json.load(f)

        file_keys = get_keys(data)
        missing = base_keys - file_keys
        extra = file_keys - base_keys

        for key in sorted(missing):
            logger.error("Missing translation %s for %s", key, file.name)
            all_valid = False

        for key in sorted(extra):
            logger.error("Unknown translation %s for %s", key, file.name)
            all_valid = False

        # Reorder and save
        output = json.dumps(data, indent=4, ensure_ascii=False, sort_keys=True)
        output = output.replace("/", "\\/")
        with file.open("w") as f:
            f.write(output + "\n")

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
