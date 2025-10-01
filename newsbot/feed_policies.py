"""Feed selection utilities supporting allow/deny lists and extended registries."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .rss_feeds import RSS_FEEDS, RSS_FEEDS_EXTENDED

LOGGER = logging.getLogger(__name__)
DEFAULT_POLICY_DIR = Path(__file__).resolve().parent / "config"
DEFAULT_ALLOWLIST_PATH = DEFAULT_POLICY_DIR / "feed_allowlist.json"
DEFAULT_DENYLIST_PATH = DEFAULT_POLICY_DIR / "feed_denylist.json"


def _load_json_list(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return {k: list(v) for k, v in data.items() if isinstance(v, (list, tuple))}
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Failed to load feed policy %s: %s", path, exc)
    return {}


def load_policy(
    allowlist_path: Optional[Path] = None,
    denylist_path: Optional[Path] = None,
) -> Tuple[Dict[str, List[str]], List[str]]:
    """Return (allowlist_by_category, denylist_global)."""

    allow_map = _load_json_list(allowlist_path or DEFAULT_ALLOWLIST_PATH)
    deny_map = _load_json_list(denylist_path or DEFAULT_DENYLIST_PATH)
    deny_global: List[str] = [item for items in deny_map.values() for item in items]
    return allow_map, deny_global


def _resolve_base_registry(use_extended: bool) -> Dict[str, List[str]]:
    registry = RSS_FEEDS_EXTENDED if use_extended else RSS_FEEDS
    return {cat: list(urls) for cat, urls in registry.items()}


def build_feed_registry(
    *,
    categories: Optional[Iterable[str]] = None,
    use_extended: bool = False,
    allowlist_only: bool = False,
    allowlist_path: Optional[str] = None,
    denylist_path: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Build registry filtered by allow/deny lists.

    Args:
        categories: optional iterable of categories to include.
        use_extended: if True use RSS_FEEDS_EXTENDED otherwise RSS_FEEDS.
        allowlist_only: if True only return feeds present in the allowlist.
        allowlist_path / denylist_path: override policy paths.
    """

    allow_map, deny_global = load_policy(
        allowlist_path=Path(allowlist_path) if allowlist_path else None,
        denylist_path=Path(denylist_path) if denylist_path else None,
    )

    selected_categories = None if categories is None else {c.strip() for c in categories if c}

    registry = _resolve_base_registry(use_extended)

    if selected_categories is not None:
        registry = {cat: registry.get(cat, []) for cat in selected_categories}

    resolved: Dict[str, List[str]] = {}
    for category, feeds in registry.items():
        if not feeds:
            continue
        allow_set = set(allow_map.get(category, []))
        # Filter denies first
        filtered = [url for url in feeds if url not in deny_global]
        if allowlist_only:
            filtered = [url for url in filtered if not allow_set or url in allow_set]
        elif allow_set:
            # Prioritise allowlisted feeds while keeping remainder for coverage
            prioritized = [url for url in filtered if url in allow_set]
            remainder = [url for url in filtered if url not in allow_set]
            filtered = prioritized + remainder
        if filtered:
            resolved[category] = filtered
    return resolved


def environment_options() -> Dict[str, str]:
    return {
        "use_extended": os.environ.get("RSS_USE_EXTENDED", "0"),
        "allowlist_only": os.environ.get("RSS_ALLOWLIST_ONLY", "0"),
        "allowlist_path": os.environ.get("RSS_ALLOWLIST_PATH", ""),
        "denylist_path": os.environ.get("RSS_DENYLIST_PATH", ""),
    }
