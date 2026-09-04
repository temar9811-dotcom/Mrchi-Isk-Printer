# FILE: app/esi/scopes.py
# VERSION: 1.1.0

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


DEFAULT_SCOPES_PATH = (
    Path(__file__).resolve().parents[2] / "esi_scopes.json"
)

logger = logging.getLogger("app.esi.scopes")


def load_scopes_file(
    path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """
    Load the raw ESI scope JSON file.
    """
    if path is None:
        path = DEFAULT_SCOPES_PATH

    path = Path(path)

    logger.debug("Loading ESI scope file: %s", path.resolve())

    if not path.exists():
        logger.error("ESI scope file missing: %s", path.resolve())
        raise FileNotFoundError(f"ESI scope file missing: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed reading ESI scope file")
        raise

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.exception("ESI scope file is not valid JSON")
        raise

    if not isinstance(data, dict):
        logger.error("ESI scope file must contain a JSON object")
        raise ValueError("ESI scope file must contain a JSON object")

    logger.debug("ESI scope file loaded successfully")
    return data


def load_scopes(
    path: Optional[Union[Path, str]] = None,
) -> List[str]:
    """
    Load and clean the active ESI scope list.

    'future_scopes' entries are ignored here on purpose.
    """
    data = load_scopes_file(path)

    file_version = data.get("version", "UNKNOWN")
    logger.debug("esi_scopes.json version: %s", file_version)

    scopes = data.get("scopes", [])
    future_scopes = data.get("future_scopes", [])

    if not isinstance(scopes, list):
        logger.error("esi_scopes.json 'scopes' must be a list")
        raise ValueError("esi_scopes.json 'scopes' must be a list")

    if isinstance(future_scopes, list):
        logger.debug(
            "Scope file contains %s future scopes (not requested at login)",
            len(future_scopes),
        )

    cleaned_scopes: List[str] = []

    for raw_scope in scopes:
        if not isinstance(raw_scope, str):
            logger.warning("Ignoring non-string scope value: %r", raw_scope)
            continue

        scope = raw_scope.strip()

        if not scope:
            continue

        if scope in cleaned_scopes:
            logger.warning("Duplicate scope ignored: %s", scope)
            continue

        cleaned_scopes.append(scope)

    logger.info("Loaded %s active ESI scopes", len(cleaned_scopes))
    return cleaned_scopes


def get_scope_list_string(
    scopes: Optional[List[str]] = None,
) -> str:
    """
    Return scopes as a space-separated string for OAuth URLs.
    """
    if scopes is None:
        scopes = load_scopes()

    scope_string = " ".join(scopes)

    logger.debug("Built scope string with %s characters", len(scope_string))

    return scope_string


def validate_scopes(
    scopes: Optional[List[str]] = None,
) -> List[str]:
    """
    Basic sanity validation for scope names.
    """
    if scopes is None:
        scopes = load_scopes()

    warnings: List[str] = []

    for scope in scopes:
        if scope == "publicData":
            continue

        if not scope.startswith("esi-"):
            warnings.append(f"Scope does not start with 'esi-': {scope}")

        if not scope.endswith(".v1"):
            warnings.append(f"Scope does not end with '.v1': {scope}")

    if warnings:
        for warning in warnings:
            logger.warning(warning)
    else:
        logger.debug("Scope validation produced no warnings")

    return warnings