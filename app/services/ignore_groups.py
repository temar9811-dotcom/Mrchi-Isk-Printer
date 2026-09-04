# FILE: app/services/ignore_groups.py
# VERSION: 1.0.0
from typing import Dict, List, Set

IGNORE_GROUPS: Dict[str, List[int]] = {
    "ammo": [
        # Hybrid charges
        159, 160, 161, 162, 163, 164, 165, 166,
        # Projectile ammo
        177, 178, 179, 180, 181, 182, 183, 184,
        # Frequency crystals
        587, 588, 589, 590, 591, 592, 593, 594, 595, 596,
        # Light missiles
        1447, 1448, 1449, 1450, 1451, 1452, 1453, 1454,
        # Heavy missiles
        2597, 2598, 2599, 2600, 2601, 2602, 2603, 2604,
    ],
    "tech 1 modules": [
        # Small Shield Extender
        438, 440, 442,
        # Medium Shield Extender
        444, 446, 448,
        # Large Shield Extender
        450, 452, 454,
        # Small Armor Plates
        399, 401, 403,
        # Medium Armor Plates
        405, 407, 409,
        # Large Armor Plates
        411, 413, 415,
        # Afterburner
        434, 436,
        # Microwarpdrive
        1195, 1197, 1199, 1201,
    ],
}


def get_ignore_group_names() -> List[str]:
    return list(IGNORE_GROUPS.keys())


def get_type_ids_for_groups(enabled_groups: Set[str]) -> Set[int]:
    type_ids: Set[int] = set()
    for group_name in enabled_groups:
        if group_name in IGNORE_GROUPS:
            type_ids.update(IGNORE_GROUPS[group_name])
    return type_ids
