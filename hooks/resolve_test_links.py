"""
MkDocs hook: resolve test file/function references to GitHub URLs with line numbers.

Scans Markdown table rows for patterns like:
    | tests/test_foo.py | `test_bar` | description |

and replaces them with GitHub blob links including the line number of the test function.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("mkdocs.hooks.resolve_test_links")

# Matches a table row with: | tests/some_file.py | `test_function_name` | ...  |
_ROW_RE = re.compile(
    r"^\|"
    r"\s*(tests/\S+\.py)\s*"  # group 1: file path
    r"\|"
    r"\s*`([^`]+)`\s*"  # group 2: function name (backtick-wrapped)
    r"\|"
    r"(.*)\|$",  # group 3: rest of the row
)


@lru_cache(maxsize=128)
def _read_lines(path: Path) -> tuple[str, ...]:
    """Read and cache file lines (tuple for hashability)."""
    try:
        return tuple(path.read_text().splitlines())
    except OSError:
        log.warning("Could not read %s", path)
        return ()


def _find_line_number(file_path: Path, func_name: str) -> int | None:
    """Return the 1-based line number where ``def <func_name>`` appears."""
    pattern = f"def {func_name}("
    for i, line in enumerate(_read_lines(file_path), start=1):
        if pattern in line:
            return i
    return None


def _get_repo_url(config: dict) -> str | None:
    """Extract repo_url from MkDocs config, stripping trailing slash."""
    url = config.get("repo_url", "")
    return url.rstrip("/") if url else None


def _get_branch(config: dict) -> str:
    """Extract branch from edit_uri or default to 'main'."""
    edit_uri = config.get("edit_uri", "")
    # edit_uri is typically "edit/main/docs/" or "blob/main/docs/"
    parts = edit_uri.strip("/").split("/")
    if len(parts) >= 2:  # noqa: PLR2004
        return parts[1]
    return "main"


def on_page_markdown(
    markdown: str,
    page: object,
    config: dict,
    files: object,
) -> str:
    """Replace test references in table rows with GitHub links."""
    repo_url = _get_repo_url(config)
    if not repo_url:
        log.warning("No repo_url in mkdocs.yml — skipping test link resolution")
        return markdown

    branch = _get_branch(config)
    project_root = Path(config["docs_dir"]).parent
    lines = markdown.split("\n")
    result = []

    for line in lines:
        m = _ROW_RE.match(line)
        if m:
            file_rel = m.group(1)
            func_name = m.group(2)
            rest = m.group(3)

            file_path = project_root / file_rel
            line_num = _find_line_number(file_path, func_name)

            if line_num is not None:
                file_url = f"{repo_url}/blob/{branch}/{file_rel}#L{line_num}"
                func_url = f"{repo_url}/blob/{branch}/{file_rel}#L{line_num}"
                result.append(
                    f"| [{file_rel}]({file_url})"
                    f" | [`{func_name}`]({func_url})"
                    f" |{rest}|"
                )
            else:
                log.warning(
                    "Could not find def %s in %s",
                    func_name,
                    file_rel,
                )
                result.append(line)
        else:
            result.append(line)

    return "\n".join(result)
