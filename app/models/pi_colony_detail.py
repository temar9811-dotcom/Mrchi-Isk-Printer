# FILE: app/models/pi_colony_detail.py
# VERSION: 1.0.0

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PiPinContent:
    """
    One item stored inside a pin.
    """
    type_id: int
    amount: int
    type_name: str = ""


@dataclass
class PiPin:
    """
    One pin (structure) on a planet.
    """
    pin_id: int
    type_id: int
    type_name: str = ""
    upgrade_level: int = 0
    schematic_id: Optional[int] = None
    schematic_name: str = ""
    install_time: str = ""
    last_cycle_start: str = ""
    expiry_time: str = ""

    # Extractor details
    head_count: int = 0
    cycle_time_seconds: int = 0
    qty_per_cycle: int = 0
    product_type_id: Optional[int] = None
    product_type_name: str = ""

    contents: List[PiPinContent] = field(default_factory=list)
    category: str = "Other"

    @property
    def cycle_time_display(self) -> str:
        if self.cycle_time_seconds <= 0:
            return ""
        hours = self.cycle_time_seconds / 3600
        days = hours / 24
        return f"{hours:.0f}h ({days:.1f}d)"


@dataclass
class PiRoute:
    """
    One route moving material between pins.
    """
    source_pin_id: int
    destination_pin_id: int
    quantity: int
    content_type_id: int = 0
    content_type_name: str = ""
    source_name: str = ""
    destination_name: str = ""


@dataclass
class PiColonyDetail:
    """
    Full layout of one planet colony.
    """
    planet_id: int
    planet_name: str = ""
    pins: List[PiPin] = field(default_factory=list)
    routes: List[PiRoute] = field(default_factory=list)
    links_count: int = 0