# FILE: app/models/pi_colony.py
# VERSION: 1.0.0

from dataclasses import dataclass, field


@dataclass
class PiColony:
    """
    Represents a single PI colony on a planet.
    """
    planet_id: int
    planet_type: str
    solar_system_id: int
    num_pins: int
    upgrade_level: int
    last_update: str
    owner_id: int = 0

    # Resolved names (filled in by worker)
    planet_name: str = ""
    system_name: str = ""

    @property
    def display_name(self) -> str:
        if self.planet_name:
            return self.planet_name
        return f"Planet {self.planet_id}"

    @property
    def display_location(self) -> str:
        if self.system_name:
            return self.system_name
        return f"System {self.solar_system_id}"