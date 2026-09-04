# FILE: app/services/ignore_groups.py
# VERSION: 1.1.0
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
    "t1 guns": [
        # Small/Medium/Large Hybrid
        567, 568, 569, 570, 571, 572, 574, 575, 576, 577, 578, 579, 581, 582, 583, 584, 585, 586,
        # Projectile
        559, 560, 561, 562, 563, 564, 566, 567, 568, 569, 570, 571, 573, 574, 575, 576, 577, 578,
        # Laser
        543, 544, 545, 546, 547, 548, 550, 551, 552, 553, 554, 555, 557, 558, 559, 560, 561, 562,
    ],
    "t1 launchers": [
        2410, 2411, 2412, 2413, 2414, 2415, 2416, 2417, 2418, 2419, 2420, 2421, 2422, 2423, 2424,
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
