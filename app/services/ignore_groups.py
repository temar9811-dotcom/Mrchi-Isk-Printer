# FILE: app/services/ignore_groups.py
# VERSION: 1.3.0
import json
import logging
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger("app.services.ignore_groups")

IGNORE_GROUPS_FILE = Path(__file__).resolve().parent.parent.parent / "ignore_groups.json"

DEFAULT_GROUPS: Dict[str, List[int]] = {
    "ammo": [
        159, 160, 161, 162, 163, 164, 165, 166,
        177, 178, 179, 180, 181, 182, 183, 184,
        587, 588, 589, 590, 591, 592, 593, 594, 595, 596,
        1447, 1448, 1449, 1450, 1451, 1452, 1453, 1454,
        2597, 2598, 2599, 2600, 2601, 2602, 2603, 2604,
    ],
    "tech 1 modules": [
        438, 440, 442, 444, 446, 448, 450, 452, 454,
        399, 401, 403, 405, 407, 409, 411, 413, 415,
        434, 436, 1195, 1197, 1199, 1201,
    ],
    "t1 guns": [
        567, 568, 569, 570, 571, 572, 574, 575, 576, 577, 578, 579,
        581, 582, 583, 584, 585, 586, 559, 560, 561, 562, 563, 564,
        566, 573, 543, 544, 545, 546, 547, 548, 550, 551, 552, 553,
        554, 555, 557, 558,
    ],
    "t1 launchers": [
        2410, 2411, 2412, 2413, 2414, 2415, 2416, 2417, 2418, 2419,
        2420, 2421, 2422, 2423, 2424,
    ],
    "ores": [
        16275, 16274, 16272, 17471, 17473, 17475,
        1230, 1228, 1232, 1224, 1226, 1222, 1220, 1218, 1216, 1214, 
        1212, 1210, 1208, 1206, 1204, 1239,
    ],
    "materials": [
        34, 35, 36, 37, 38, 39, 40, 11399,
    ],
}


def _load_groups() -> Dict[str, List[int]]:
    if IGNORE_GROUPS_FILE.exists():
        try:
            return json.loads(IGNORE_GROUPS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load ignore groups JSON: %s", exc)
    _save_groups(DEFAULT_GROUPS)
    return DEFAULT_GROUPS


def _save_groups(groups: Dict[str, List[int]]) -> None:
    try:
        IGNORE_GROUPS_FILE.write_text(json.dumps(groups, indent=4), encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to save ignore groups JSON: %s", exc)


def get_ignore_group_names() -> List[str]:
    return list(_load_groups().keys())


def get_type_ids_for_groups(enabled_groups: Set[str]) -> Set[int]:
    groups = _load_groups()
    type_ids: Set[int] = set()
    for group_name in enabled_groups:
        if group_name in groups:
            type_ids.update(groups[group_name])
    return type_ids


def add_type_to_group(type_id: int, group_name: str) -> None:
    groups = _load_groups()
    if group_name not in groups:
        groups[group_name] = []
    if type_id not in groups[group_name]:
        groups[group_name].append(type_id)
        _save_groups(groups)
        logger.info("Added type %s to ignore group '%s'", type_id, group_name)