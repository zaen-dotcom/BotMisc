"""
╔══════════════════════════════════════════════════════════════════════╗
║  💾 BotMisc — Master Database & Spots Storage Manager               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
from typing import Dict, List, Optional, Any
from config import MISCRITS_FILE, SPOTS_FILE


class Database:
    def __init__(self):
        self.miscrits: Dict[int, Dict[str, Any]] = {}
        self.spots: List[Dict[str, Any]] = []
        self._load_miscrits()
        self._load_spots()

    def _load_miscrits(self):
        if os.path.exists(MISCRITS_FILE):
            try:
                with open(MISCRITS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for m in data:
                        mid = m.get("id")
                        name = m.get("names", ["?"])[0]
                        rar = m.get("rarity", "Common")
                        elem = m.get("element", "Misc")
                        locs = m.get("locations", {})
                        
                        self.miscrits[mid] = {
                            "id": mid,
                            "name": name,
                            "rarity": rar,
                            "element": elem,
                            "locations": locs
                        }
            except Exception as e:
                print(f"[!] Gagal membaca database miscrits: {e}")

    def _load_spots(self):
        if os.path.exists(SPOTS_FILE):
            try:
                with open(SPOTS_FILE, "r", encoding="utf-8") as f:
                    self.spots = json.load(f)
            except Exception as e:
                print(f"[!] Gagal membaca spots.json: {e}")
                self.spots = []
        else:
            self.spots = []

    def save_spots(self):
        try:
            with open(SPOTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.spots, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[!] Gagal menyimpan spots.json: {e}")
            return False

    def get_miscrit(self, mid: int) -> Optional[Dict[str, Any]]:
        return self.miscrits.get(mid)

    def find_miscrit_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        name_lower = name.lower().strip()
        for mid, info in self.miscrits.items():
            if info["name"].lower() == name_lower:
                return info
        for mid, info in self.miscrits.items():
            if name_lower in info["name"].lower():
                return info
        return None

    def get_enabled_spots(self, region: Optional[str] = None) -> List[Dict[str, Any]]:
        spots = [s for s in self.spots if s.get("enabled", True)]
        if region:
            spots = [s for s in spots if s.get("region", "").lower() == region.lower()]
        return spots

    def get_all_spots(self) -> List[Dict[str, Any]]:
        return self.spots

    def add_spot(self, region: str, zone: str, object_id: int, target_name: str, target_id: int, target_rarity: str) -> Dict[str, Any]:
        spot_id = f"{region.lower()}_{zone.lower().replace(' ', '_')}_{target_name.lower().replace(' ', '_')}"
        new_spot = {
            "id": spot_id,
            "region": region,
            "zone": zone,
            "object_id": object_id,
            "target_name": target_name,
            "target_id": target_id,
            "target_rarity": target_rarity,
            "enabled": True
        }
        # Check if already exists, update if so
        for i, s in enumerate(self.spots):
            if s.get("region") == region and s.get("zone") == zone and s.get("object_id") == object_id:
                self.spots[i] = new_spot
                self.save_spots()
                return new_spot

        self.spots.append(new_spot)
        self.save_spots()
        return new_spot

    def toggle_spot(self, spot_index: int) -> bool:
        if 0 <= spot_index < len(self.spots):
            self.spots[spot_index]["enabled"] = not self.spots[spot_index].get("enabled", True)
            self.save_spots()
            return True
        return False
