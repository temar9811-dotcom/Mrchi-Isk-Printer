# FILE: app/esi/universe_resolver.py
# VERSION: 1.8.0

import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from app.db.database import Database
from app.db.universe_cache_repository import UniverseCacheRepository
from app.db.esi_cache_repository import EsiCacheRepository

logger = logging.getLogger("app.esi.universe_resolver")
ESI_BASE_URL = "https://esi.evetech.net/latest"

GROUP_MAP_WORKERS = 8
GROUP_MAP_KEY = "market_groups:reverse"


class UniverseResolver:
    def __init__(self, db: Database):
        self.cache = UniverseCacheRepository(db)
        self.esi_cache = EsiCacheRepository(db)
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _fetch_from_esi(self, endpoint: str) -> Optional[dict]:
        url = f"{ESI_BASE_URL}{endpoint}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("ESI universe request failed: %s", endpoint)
            return None

    def _fetch_structure(self, structure_id, access_token) -> Optional[dict]:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        try:
            resp = self.session.get(
                f"{ESI_BASE_URL}/universe/structures/{structure_id}/",
                headers=headers, timeout=10,
            )
            if resp.status_code in (400, 401, 403, 404):
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Structure fetch failed for %s", structure_id)
            return None

    # --- bulk resolution (Jita-safe) ---

    def resolve_names_bulk(self, ids: List[int], category: str = "type") -> Dict[int, str]:
        """
        Resolve many IDs to names.

        Cache pass is batched (chunked IN queries); only true misses
        go to ESI via POST /universe/names/ (1000 ids per request).
        """
        out: Dict[int, str] = {}
        unique_ids = list(set(ids))
        if not unique_ids:
            return out

        out = self.cache.get_names_by_category(unique_ids, category)
        missing = [i for i in unique_ids if i not in out]

        for start in range(0, len(missing), 1000):
            chunk = missing[start:start + 1000]
            try:
                resp = self.session.post(
                    f"{ESI_BASE_URL}/universe/names/", json=chunk, timeout=30
                )
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
            except Exception:
                logger.exception("Bulk names request failed")
                continue

            for row in resp.json():
                esi_cat = row.get("category", "")
                store_cat = "type" if esi_cat == "inventory_type" else (
                    "market_group" if esi_cat == "market_group" else category
                )
                self.cache.set_name(row["id"], row["name"], store_cat)
                out[row["id"]] = row["name"]

        logger.info(
            "Bulk resolved %s names (%s from cache, %s from ESI)",
            len(out), len(out) - len(missing), len(missing),
        )
        return out

    def get_market_group_map(self, force: bool = False) -> Dict[int, Tuple[int, str]]:
        """
        type_id -> (market_group_id, market_group_name).
        Built once from /markets/groups/ and cached forever in esi_cache.
        """
        if not force:
            payload, _ = self.esi_cache.get(GROUP_MAP_KEY)
            if payload:
                return {int(k): (int(v[0]), v[1]) for k, v in payload.items()}

        resp = self.session.get(f"{ESI_BASE_URL}/markets/groups/", timeout=30)
        resp.raise_for_status()
        group_ids = resp.json()

        reverse: Dict[int, list] = {}

        def fetch_group(group_id: int):
            try:
                r = self.session.get(
                    f"{ESI_BASE_URL}/markets/groups/{group_id}/", timeout=20
                )
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except Exception:
                logger.warning("Group %s fetch failed", group_id)
                return None

        with ThreadPoolExecutor(max_workers=GROUP_MAP_WORKERS) as ex:
            for data in ex.map(fetch_group, group_ids):
                if not data:
                    continue
                gid = data.get("market_group_id", 0)
                gname = data.get("name", f"Group {gid}")
                self.cache.set_name(gid, gname, "market_group")
                for tid in data.get("types", []):
                    reverse[tid] = [gid, gname]

        self.esi_cache.set(GROUP_MAP_KEY, reverse)
        logger.info("Built market group reverse map: %s types", len(reverse))
        return {int(k): (int(v[0]), v[1]) for k, v in reverse.items()}

    # --- single resolution ---

    def get_region_id_for_location(self, location_id, access_token=None) -> Optional[int]:
        cached = self.cache.get_name_by_category(location_id, "loc_region")
        if cached is not None:
            try:
                return int(cached)
            except ValueError:
                pass

        system_id = None
        station = self._fetch_from_esi(f"/universe/stations/{location_id}/")
        if station:
            system_id = station.get("solar_system_id") or station.get("system_id")

        if not system_id:
            structure = self._fetch_structure(location_id, access_token)
            if structure:
                system_id = structure.get("solar_system_id") or structure.get("system_id")

        if not system_id:
            return None

        system = self._fetch_from_esi(f"/universe/systems/{system_id}/")
        if not system or "constellation_id" not in system:
            return None

        constellation = self._fetch_from_esi(
            f"/universe/constellations/{system['constellation_id']}/"
        )
        if not constellation or "region_id" not in constellation:
            return None

        region_id = int(constellation["region_id"])
        self.cache.set_name(location_id, str(region_id), "loc_region")
        return region_id

    def resolve_market_group(self, group_id: int) -> str:
        if not group_id:
            return "Other"
        cached = self.cache.get_name_by_category(group_id, "market_group")
        if cached:
            return cached
        data = self._fetch_from_esi(f"/markets/groups/{group_id}/")
        if data and data.get("name"):
            self.cache.set_name(group_id, data["name"], "market_group")
            return data["name"]
        return f"Group {group_id}"

    def resolve_system(self, system_id: int) -> str:
        cached = self.cache.get_name(system_id)
        if cached:
            return cached
        data = self._fetch_from_esi(f"/universe/systems/{system_id}/")
        if data and "name" in data:
            self.cache.set_name(system_id, data["name"], "system")
            return data["name"]
        return f"System {system_id}"

    def resolve_station(self, station_id: int) -> str:
        cached = self.cache.get_name(station_id)
        if cached:
            return cached
        data = self._fetch_from_esi(f"/universe/stations/{station_id}/")
        if data and "name" in data:
            self.cache.set_name(station_id, data["name"], "station")
            return data["name"]
        return f"Station {station_id}"

    def resolve_structure(self, structure_id, access_token=None) -> str:
        cached = self.cache.get_name(structure_id)
        if cached:
            return cached
        data = self._fetch_structure(structure_id, access_token)
        if data and "name" in data:
            self.cache.set_name(structure_id, data["name"], "structure")
            return data["name"]
        return f"Structure {structure_id}"

    def resolve_type(self, type_id: int) -> str:
        cached = self.cache.get_name_by_category(type_id, "type")
        if cached:
            return cached
        data = self._fetch_from_esi(f"/universe/types/{type_id}/")
        if data and "name" in data:
            self.cache.set_name(type_id, data["name"], "type")
            return data["name"]
        return f"Type {type_id}"

    def resolve_planet(self, planet_id: int) -> str:
        cached = self.cache.get_name(planet_id)
        if cached:
            return cached
        data = self._fetch_from_esi(f"/universe/planets/{planet_id}/")
        if data and "name" in data:
            self.cache.set_name(planet_id, data["name"], "planet")
            return data["name"]
        return f"Planet {planet_id}"

    def resolve_schematic(self, schematic_id: int) -> str:
        cached = self.cache.get_name_by_category(schematic_id, "schematic")
        if cached:
            return cached
        data = self._fetch_from_esi(f"/universe/schematics/{schematic_id}/")
        if data and "name" in data:
            self.cache.set_name(schematic_id, data["name"], "schematic")
            return data["name"]
        return f"Schematic {schematic_id}"

    def resolve_constellation(self, constellation_id: int) -> str:
        cached = self.cache.get_name(constellation_id)
        if cached:
            return cached
        data = self._fetch_from_esi(f"/universe/constellations/{constellation_id}/")
        if data and "name" in data:
            self.cache.set_name(constellation_id, data["name"], "constellation")
            return data["name"]
        return f"Constellation {constellation_id}"

    def resolve_region(self, region_id: int) -> str:
        cached = self.cache.get_name(region_id)
        if cached:
            return cached
        data = self._fetch_from_esi(f"/universe/regions/{region_id}/")
        if data and "name" in data:
            self.cache.set_name(region_id, data["name"], "region")
            return data["name"]
        return f"Region {region_id}"