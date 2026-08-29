"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚔️  BotMisc — Smart Combat & Auto-Capture Engine v3.0               ║
║  Features:                                                           ║
║  - Legendary: Catch ALL Tiers (Lowest is C+, Never Flee)             ║
║  - Exotic: Catch A+ to S+ (Score >= 10, or Capture Chance <= 1%)     ║
║  - Turn 1 Safe Probe: ALWAYS start with lowest AP skill (Anti-KO)    ║
║  - Dynamic Damage Calibration: Accurately predicts subsequent hits    ║
║  - Strict Overkill Shield: Stops attacking when enemy HP is fragile   ║
║  - Infinite Capture Loop & Auto-Keep                                 ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import time
import base64
import json
from typing import Dict, List, Optional, Tuple, Any

from config import (
    MIN_TARGET_SCORE, get_tier_info, TARGET_CAPTURE_HP_PCT,
    MIN_SAFE_HP_PCT, AUTO_KEEP_CAUGHT, TURN_DELAY, FLEE_DELAY
)
from notifier import Notifier, Colors, RARITY_COLORS


class CombatEngine:
    def __init__(self, client, database):
        self.client = client
        self.db = database

    def handle_encounter(self, match_id: str, initial_battle_data: dict, spot_info: dict) -> Tuple[str, Optional[dict]]:
        """
        Manages the complete battle and capture lifecycle:
        1. Validates targeting rules:
           - Legendary: Catch ALL tiers!
           - Exotic: Catch A+ to S+ (Score >= 10, or Initial Chance <= 1%)
        2. Safe Weakening (Turn 1 uses WEAKEST skill to safely calibrate damage without 1-shotting)
        3. Strict Anti-KO Protection: Ceases attack if next hit could KO
        4. Capture Crate loop until caught -> Keep to inventory
        """
        player1 = initial_battle_data.get("player1", {})
        player2 = initial_battle_data.get("player2", {})
        
        enemy_miscrit = player2.get("miscrits", [{}])[0]
        enemy_mid = enemy_miscrit.get("mId", 0)
        enemy_name = enemy_miscrit.get("name", "Unknown")
        enemy_hp = enemy_miscrit.get("hp", 100)
        enemy_chp = enemy_miscrit.get("chp", enemy_hp)
        enemy_info = self.db.get_miscrit(enemy_mid)
        enemy_rar = enemy_info.get("rarity", "Exotic") if enemy_info else spot_info.get("target_rarity", "Exotic")
        
        server_rating = enemy_miscrit.get("rating", 0)
        tier_name, tier_score = get_tier_info(server_rating)
        capture_chance = initial_battle_data.get("capture_chance", 1)

        my_miscrit = player1.get("miscrits", [{}])[0]
        my_name = my_miscrit.get("name", "Player Miscrit")
        my_mid = my_miscrit.get("mId", 0)
        my_level = my_miscrit.get("level", 35)

        # ── 1. TARGET QUALIFICATION CHECK ──
        # Legendary: Always Catch (C+ to S+)
        is_legendary = (enemy_rar == "Legendary")
        
        # Exotic: Catch A+ to S+ (Score >= 10, OR initial chance <= 1% for unmasked accounts)
        is_exotic_target = False
        if enemy_rar == "Exotic":
            if server_rating > 0:
                is_exotic_target = (tier_score >= MIN_TARGET_SCORE)
            else:
                # For accounts < level 150 where server sends rating: 0
                # From capture chance table at 100% HP: A, A+, S, S+ = 1%
                is_exotic_target = (capture_chance <= 1)

        should_catch = is_legendary or is_exotic_target

        if not should_catch:
            print(
                f"{Colors.DIM}  [-] {enemy_name} [{enemy_rar}] Tier {tier_name} "
                f"(Score {tier_score}/12 | Chance {capture_chance}%) < Target → Auto Flee.{Colors.RESET}"
            )
            self.client.flee_and_leave(match_id)
            return "FLEE_RATING", None

        # ── 2. HIGH TIER / LEGENDARY TARGET CONFIRMED ──
        target_type_label = "LEGENDARY (SEMUA TIER DITANGKAP)" if is_legendary else "EXOTIC A+ s/d S+"
        print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} 🌟 TARGET UTAMA DITEMUKAN! [{target_type_label}] 🌟 {Colors.RESET}")
        print(f"  Target  : {Colors.GREEN}{Colors.BOLD}{enemy_name} (#{enemy_mid}) [{enemy_rar}]{Colors.RESET}")
        print(f"  Tier    : {Colors.YELLOW}{Colors.BOLD}{tier_name} (Score: {tier_score}/12 | Stars: {server_rating}){Colors.RESET}")
        print(f"  HP Awal : {enemy_chp}/{enemy_hp} | Peluang Tangkap Awal: {capture_chance}%")
        print(f"{Colors.CYAN}──────────────────────────────────────────────────{Colors.RESET}")

        # Get player's attacking skills sorted from LOWEST AP to HIGHEST AP (safest first!)
        skills_asc = self._get_player_skills_asc(my_mid)
        
        # Turn loop variables
        turn = 1
        damage_per_ap: Optional[float] = None  # calibrated from Turn 1 hit
        captured_data = None

        while True:
            # Calculate current HP percentage
            hp_pct = (enemy_chp / enemy_hp) * 100 if enemy_hp > 0 else 100

            # ── 3. DECISION: ATTACK vs THROW CAPTURE CRATE ──
            # Determine if enemy is already weakened or in lethal danger
            lowest_skill = skills_asc[0] if skills_asc else {"id": 264, "name": "Light Tap", "ap": 7}
            lowest_ap = lowest_skill.get("ap", 7)
            
            # Estimated damage of our weakest attack (with 30% safety buffer for variance/crits)
            est_lowest_dmg = int(lowest_ap * (damage_per_ap if damage_per_ap else 3.5) * 1.3)

            # STOP ATTACKING IF:
            # - HP is already in sweet spot (<= 20%)
            # - OR capture chance is high (>= 85%)
            # - OR our WEAKEST skill has ANY chance of KO'ing the enemy!
            is_in_capture_zone = (hp_pct <= TARGET_CAPTURE_HP_PCT or capture_chance >= 85)
            is_fragile_or_lethal = (enemy_chp <= est_lowest_dmg or enemy_chp <= int(enemy_hp * (MIN_SAFE_HP_PCT / 100.0)))

            if is_in_capture_zone or is_fragile_or_lethal:
                reason = "ZONA TANGKAP TERCAPAI (5-20%)" if is_in_capture_zone else "ANTI-KO ACTIVATED (Musuh terlalu tipis, stop attack!)"
                print(f"  {Colors.MAGENTA}[T{turn}] HP Musuh: {enemy_chp}/{enemy_hp} ({hp_pct:.1f}%) | Chance: {capture_chance}% | {reason}")
                print(f"       → 📦 MELEMPAR CRATE CAPTURE!{Colors.RESET}")
                
                # Send OpCode 10 (Throw Crate)
                self.client.send_capture(match_id)
                time.sleep(TURN_DELAY)
                
                # Send OpCode 8 (Animation Sync)
                self.client.send_sync_animation(match_id)

                # Receive result
                resp = self.client.recv_battle_message()
                if not resp:
                    time.sleep(0.8)
                    continue

                if resp.get("captured") is True:
                    # 🌟 CAPTURED SUCCESSFULLY! 🌟
                    stars = resp.get("stars", {})
                    print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} 🎉 BERHASIL DITANGKAP! [{enemy_name} - Tier: {tier_name}] 🎉 {Colors.RESET}")
                    print(f"  Stars (IVs): {json.dumps(stars)}")
                    
                    if AUTO_KEEP_CAUGHT:
                        print(f"  {Colors.GREEN}💾 Mengirim sinyal KEEP MISCRIT ke inventory...{Colors.RESET}")
                        self.client.send_keep_or_release(match_id, keep=True)
                        time.sleep(0.3)
                        self.client.send_sync_animation(match_id)
                        time.sleep(0.5)

                    # Sound alarm / notification
                    Notifier.sound_alarm(times=10)
                    
                    # Clean leave
                    self.client.send_match_leave(match_id)
                    
                    captured_data = {
                        "name": enemy_name,
                        "mid": enemy_mid,
                        "rating_score": tier_score,
                        "rating_name": tier_name,
                        "stars": stars
                    }
                    return "CAUGHT", captured_data
                else:
                    print(f"  {Colors.YELLOW}⚠️ Crate lepas / belum berhasil. Melanjutkan melempar crate...{Colors.RESET}")

            else:
                # ── SELECT SAFE WEAKENING SKILL ──
                # On Turn 1: ALWAYS start with the WEAKEST skill (lowest AP) to safely calibrate damage
                # Never use ultimate/heavy skills on Turn 1!
                if turn == 1 or damage_per_ap is None:
                    chosen_skill = skills_asc[0]  # Lowest AP skill (e.g. AP 7 Breeze/Swipe)
                else:
                    chosen_skill = self._select_safe_skill(skills_asc, enemy_chp, enemy_hp, damage_per_ap)

                s_id = chosen_skill.get("id", 264)
                s_name = chosen_skill.get("name", "Light Attack")
                s_ap = chosen_skill.get("ap", 7)
                est_dmg = int(s_ap * (damage_per_ap if damage_per_ap else 3.0))

                print(f"  {Colors.CYAN}[T{turn}] HP Musuh: {enemy_chp}/{enemy_hp} ({hp_pct:.1f}%) → ⚡ Safe Skill: {s_name} (AP: {s_ap}, Est Dmg: ~{est_dmg}){Colors.RESET}")
                
                # Send OpCode 2 (Cast Ability)
                self.client.cast_ability(match_id, s_id)
                time.sleep(TURN_DELAY)

                # Send OpCode 8 (Animation Sync)
                self.client.send_sync_animation(match_id)

            # Wait for Server Turn Response
            server_turn = self.client.recv_battle_message()
            if not server_turn:
                time.sleep(0.8)
                continue

            # Update enemy HP & calibrate damage ratio dynamically
            if "actions" in server_turn:
                for act in server_turn.get("actions", []):
                    atype = act.get("type", "")
                    if atype == "Attack" and act.get("target") == "Wild":
                        actual_dmg = act.get("damage", 0)
                        enemy_chp = max(0, enemy_chp - actual_dmg)
                        
                        # Calibrate real damage per AP ratio dynamically
                        if s_ap > 0 and actual_dmg > 0:
                            damage_per_ap = actual_dmg / s_ap
                        
                        print(f"    💥 Damage Masuk: -{actual_dmg} HP (Sisa HP Musuh: {enemy_chp}/{enemy_hp})")
                    
                    elif atype == "Faint" and act.get("target") == "Wild":
                        print(f"\n{Colors.RED}{Colors.BOLD}💀 Musuh KO / Fainted! Tidak dapat ditangkap.{Colors.RESET}")
                        self.client.send_match_leave(match_id)
                        return "FAINTED", None

            if "capture_chance" in server_turn:
                capture_chance = server_turn.get("capture_chance", capture_chance)

            # If it's wild's turn, receive enemy attack and sync animation
            if server_turn.get("next_turn") == "Wild":
                self.client.recv_battle_message()
                self.client.send_sync_animation(match_id)

            turn += 1
            if turn > 35:
                print(f"{Colors.YELLOW}Battle melebihi 35 giliran. Kabur.{Colors.RESET}")
                self.client.flee_and_leave(match_id)
                return "ESCAPED", None

    def _get_player_skills_asc(self, my_mid: int) -> List[dict]:
        """
        Loads all attacking skills from database and sorts from LOWEST AP to HIGHEST AP.
        Prioritizes light/safe attacks to strictly prevent accidental KOs.
        """
        m_info = self.db.get_miscrit(my_mid)
        abilities = m_info.get("abilities", []) if m_info else []

        valid_attacks = []
        for a in abilities:
            if a.get("type") == "Attack" and a.get("ap", 0) > 0:
                valid_attacks.append({
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "ap": a.get("ap", 7)
                })

        if not valid_attacks:
            # Safe fallbacks from lowest to highest
            valid_attacks = [
                {"id": 264, "name": "Breeze / Swipe", "ap": 7},
                {"id": 680, "name": "Medium Strike", "ap": 13},
                {"id": 272, "name": "Dive", "ap": 15}
            ]

        # Sort ascending by AP (Lowest damage to highest damage)
        valid_attacks.sort(key=lambda x: x.get("ap", 0))
        return valid_attacks

    def _select_safe_skill(self, skills_asc: List[dict], enemy_chp: int, enemy_hp: int, dmg_per_ap: float) -> dict:
        """
        Chooses the most effective skill that strictly guarantees the enemy
        survives with at least 10% HP, factoring in a 25% safety buffer.
        """
        safe_floor_hp = int(enemy_hp * (MIN_SAFE_HP_PCT / 100.0))  # at least 10% HP surviving
        target_hp = int(enemy_hp * (TARGET_CAPTURE_HP_PCT / 100.0)) # target ~15% HP

        candidate_skills = []
        for s in skills_asc:
            ap = s.get("ap", 7)
            # High roll buffer (25% higher than average damage)
            max_possible_dmg = int(ap * dmg_per_ap * 1.25)
            remaining_hp = enemy_chp - max_possible_dmg
            
            if remaining_hp >= safe_floor_hp:
                candidate_skills.append((remaining_hp, s))

        if candidate_skills:
            # Pick the skill that brings remaining HP closest to target_hp (15%)
            candidate_skills.sort(key=lambda x: abs(x[0] - target_hp))
            return candidate_skills[0][1]

        # If even the weakest skill might drop HP below floor, return the lowest AP skill
        return skills_asc[0]
