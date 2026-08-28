"""
╔══════════════════════════════════════════════════════════════════════╗
║  🏹 BotMisc — Multi-Spot Exotic & Legendary Rotation Hunter Engine   ║
║  Continuous 24/7 Loop with Smart Auto-Attack & Auto-Capture          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import time
import sys
import os
from typing import Dict, List, Any, Optional

from config import (
    STEP_DELAY, RATING_MAP, MIN_TARGET_RATING,
    WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)
from database import Database
from auth import TokenManager
from client import NakamaClient
from combat import CombatEngine
from notifier import Notifier, Colors, RARITY_COLORS


class AutoHunter:
    def __init__(self, db: Database, token_mgr: TokenManager, client: NakamaClient):
        self.db = db
        self.token_mgr = token_mgr
        self.client = client
        self.combat = CombatEngine(client, db)
        self.is_running = False
        
        # Statistics
        self.total_encounters = 0
        self.high_tier_encounters = 0
        self.bingo_caught_count = 0
        self.flee_count = 0
        self.start_time = 0
        self.spot_stats: Dict[str, int] = {}
        self.captured_history: List[dict] = []

    def start(self, region: str = "Forest"):
        enabled_spots = self.db.get_enabled_spots(region=region)
        if not enabled_spots:
            Notifier.error(f"Tidak ada spot hunting yang aktif untuk region '{region}' di spots.json!")
            Notifier.log("Gunakan menu Spot Manager untuk menambahkan atau mengaktifkan spot.", "INFO")
            return

        self.is_running = True
        self.start_time = time.time()
        self.total_encounters = 0
        self.high_tier_encounters = 0
        self.bingo_caught_count = 0
        self.flee_count = 0
        self.spot_stats = {s.get("target_name", f"Spot_{i}"): 0 for i, s in enumerate(enabled_spots)}
        self.captured_history = []

        Notifier.print_banner(len(enabled_spots))
        print(f"{Colors.GREEN}{Colors.BOLD}🚀 Memulai Multi-Spot Rotation Hunting di [{region.upper()}] (24/7 Continuous Loop)...{Colors.RESET}")
        print(f"  • Target Hewan: {Colors.YELLOW}{Colors.BOLD}HANYA Exotic & Legendary{Colors.RESET} (Common/Rare/Epic langsung Flee)")
        print(f"  • Target Tier : {Colors.GREEN}{Colors.BOLD}A+ (10), S (11), S+ (12){Colors.RESET} (Tier di bawah A+ langsung Flee)")
        print(f"  • Mode Tangkap: {Colors.CYAN}{Colors.BOLD}Auto-Weaken (5-15% HP) ➔ Auto-Capture ➔ Auto-Keep{Colors.RESET}")
        print(f"{Colors.YELLOW}Tekan Ctrl+C kapan saja untuk berhenti.{Colors.RESET}\n")

        # Initial connection
        if not self.client.connect():
            Notifier.error("Koneksi awal gagal. Mencoba menghubungkan kembali...")

        spot_index = 0
        
        try:
            while self.is_running:
                # Reload enabled spots in case config changed
                enabled_spots = self.db.get_enabled_spots(region=region)
                if not enabled_spots:
                    Notifier.warn("Semua spot dinonaktifkan. Bot berhenti.")
                    break

                current_spot = enabled_spots[spot_index % len(enabled_spots)]
                spot_index += 1

                obj_id = current_spot.get("object_id")
                target_name = current_spot.get("target_name", "Unknown")
                target_id = current_spot.get("target_id", 0)
                target_rar = current_spot.get("target_rarity", "Exotic")
                reg = current_spot.get("region", "Forest")
                zone = current_spot.get("zone", "Zone 4")
                spot_label = f"{reg} {zone} (Obj #{obj_id})"

                # ── Probing Object on Server ──
                status, enemy_mid, enemy_name, match_id, initial_battle_data, cd = self.client.probe_object(obj_id)

                if status == "COOLDOWN":
                    # Object still cooling down, move to next spot immediately
                    time.sleep(0.3)
                    continue

                elif status == "EMPTY":
                    # Invalid/Empty object or no battle spawned
                    time.sleep(0.2)
                    continue

                elif status == "ERROR":
                    # Network hiccup, wait a bit and reconnect
                    time.sleep(2.0)
                    self.client.connect()
                    continue

                elif status == "SUCCESS" and enemy_mid and initial_battle_data:
                    self.total_encounters += 1
                    self.spot_stats[target_name] = self.spot_stats.get(target_name, 0) + 1

                    # Extract Enemy Details & Rating
                    player2 = initial_battle_data.get("player2", {})
                    enemy_miscrit = player2.get("miscrits", [{}])[0]
                    enemy_info = self.db.get_miscrit(enemy_mid)
                    enemy_rar = enemy_info.get("rarity", "Common") if enemy_info else "Common"
                    actual_name = enemy_info.get("name", enemy_name) if enemy_info else enemy_name
                    rating_score = enemy_miscrit.get("rating", 0)
                    rating_name = RATING_MAP.get(rating_score, f"R{rating_score}")

                    rc = RARITY_COLORS.get(enemy_rar, Colors.WHITE)
                    ts = time.strftime("%H:%M:%S")

                    # ── CHECK 1: MUST BE EXOTIC OR LEGENDARY TARGET ──
                    is_target_species = (
                        enemy_rar in ("Exotic", "Legendary")
                        or enemy_mid == target_id
                        or target_name.lower() in actual_name.lower()
                    )

                    # Print encounter line
                    tier_color = Colors.GREEN if (rating_score >= MIN_TARGET_RATING and is_target_species) else Colors.DIM
                    print(
                        f"{Colors.DIM}[{ts}]{Colors.RESET} "
                        f"{Colors.CYAN}#{self.total_encounters:<4d}{Colors.RESET} "
                        f"[{spot_label:<20s}] → "
                        f"{rc}{actual_name} (#{enemy_mid}) [{enemy_rar}]{Colors.RESET} | "
                        f"Tier: {tier_color}{rating_name} ({rating_score}/12){Colors.RESET}"
                    )

                    # ── CHECK 2: EXECUTE ONLY IF EXOTIC/LEGENDARY AND RATING >= 10 ──
                    if is_target_species and rating_score >= MIN_TARGET_RATING:
                        self.high_tier_encounters += 1
                        
                        # Execute Combat & Capture Phase!
                        result, captured_info = self.combat.handle_encounter(match_id, initial_battle_data, current_spot)
                        
                        if result == "CAUGHT" and captured_info:
                            self.bingo_caught_count += 1
                            self.captured_history.append(captured_info)
                            
                            # External Alert
                            Notifier.send_external_alert(
                                target_name=f"{actual_name} [Tier {rating_name}]",
                                target_mid=enemy_mid,
                                rarity=enemy_rar,
                                spot_name=spot_label,
                                webhook_url=WEBHOOK_URL,
                                tg_token=TELEGRAM_BOT_TOKEN,
                                tg_chat=TELEGRAM_CHAT_ID
                            )
                            
                            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Tangkapan berhasil disimpan! Melanjutkan rotasi hunting...{Colors.RESET}\n")

                    elif is_target_species and rating_score < MIN_TARGET_RATING:
                        # Exotic/Legendary but rating is low (e.g. F- to A)
                        print(f"{Colors.DIM}  [-] {actual_name} [{enemy_rar}] Rating {rating_name} ({rating_score}/12) < A+ → Auto Flee.{Colors.RESET}")
                        self.flee_count += 1
                        self.client.flee_and_leave(match_id)

                    else:
                        # Common / Rare / Epic: Fast Flee (0.1s)
                        self.flee_count += 1
                        self.client.flee_and_leave(match_id)

                    time.sleep(STEP_DELAY)

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}[*] Bot dihentikan oleh pengguna (Ctrl+C).{Colors.RESET}")
        finally:
            self.stop()
            self._print_stats()

    def stop(self):
        self.is_running = False
        if self.client:
            self.client.disconnect()

    def _print_stats(self):
        elapsed = max(1, int(time.time() - self.start_time)) if self.start_time > 0 else 0
        mins, secs = divmod(elapsed, 60)
        rate = round((self.total_encounters / elapsed) * 60, 1) if elapsed > 0 else 0

        print(f"\n{Colors.CYAN}{Colors.BOLD}==================================================")
        print(f"               STATISTIK HUNTING                  ")
        print(f"=================================================={Colors.RESET}")
        print(f"  Durasi Berjalan         : {mins}m {secs}s")
        print(f"  Total Encounter         : {self.total_encounters} kali")
        print(f"  Target A+ s/d S+ Muncul : {self.high_tier_encounters} ekor")
        print(f"  Berhasil Ditangkap/Keep : {Colors.GREEN}{Colors.BOLD}{self.bingo_caught_count} ekor{Colors.RESET}")
        print(f"  Total Flee / Skip       : {self.flee_count} kali")
        print(f"  Kecepatan Farm          : {rate} encounter / menit")
        
        if self.captured_history:
            print(f"\n{Colors.GREEN}{Colors.BOLD}── Daftar Hewan yang Berhasil Ditangkap: ──{Colors.RESET}")
            for c in self.captured_history:
                print(f"  • {c['name']} (#{c['mid']}) [Tier {c['rating_name']}] | Stars: {json.dumps(c.get('stars', {}))}")

        print(f"{Colors.CYAN}{Colors.BOLD}=================================================={Colors.RESET}\n")
