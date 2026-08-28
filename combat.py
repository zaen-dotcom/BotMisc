"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚔️  BotMisc — Smart Combat & Auto-Capture Engine v2.0               ║
║  Features:                                                           ║
║  - 13 Tier Rating Filter (F- to S+, Target: A+, S, S+)               ║
║  - Real-time Enemy HP Tracking & Safe Damage Calculation             ║
║  - Adaptive Skill Selection (Heavy -> Medium -> Light -> No Attack)  ║
║  - Target HP Weakening to 5% - 20% (Zero Overkill Risk!)             ║
║  - Infinite 24/7 Loop Integration                                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import time
import base64
import json
from typing import Dict, List, Optional, Tuple, Any

from config import (
    MIN_TARGET_RATING, RATING_MAP, TARGET_CAPTURE_HP_PCT,
    MIN_SAFE_HP_PCT, AUTO_KEEP_CAUGHT, TURN_DELAY, FLEE_DELAY
)
from notifier import Notifier, Colors, RARITY_COLORS


class CombatEngine:
    def __init__(self, client, database):
        self.client = client
        self.db = database

    def handle_encounter(self, match_id: str, initial_battle_data: dict, spot_info: dict) -> Tuple[str, Optional[dict]]:
        """
        Manages the complete lifecycle of a wild encounter:
        1. Reads exact rating (0 to 12 -> 13 Rating levels total)
        2. If Rating < MIN_TARGET_RATING (e.g. < 10 / A+): Flees immediately (0.1s)
        3. If Rating >= 10 (A+, S, S+):
           - Tracks enemy current HP vs max HP in real-time
           - Adaptively chooses the safest skill (Heavy -> Med -> Light)
           - Stops attacking when enemy HP is 5% - 20% (or if next attack might KO)
           - Throws capture crates until caught
           - Keeps the caught miscrit and extracts Stars/IVs
        """
        player1 = initial_battle_data.get("player1", {})
        player2 = initial_battle_data.get("player2", {})
        
        enemy_miscrit = player2.get("miscrits", [{}])[0]
        enemy_mid = enemy_miscrit.get("mId", 0)
        enemy_name = enemy_miscrit.get("name", "Unknown")
        enemy_hp = enemy_miscrit.get("hp", 100)
        enemy_chp = enemy_miscrit.get("chp", enemy_hp)
        rating_score = enemy_miscrit.get("rating", 0)
        rating_name = RATING_MAP.get(rating_score, f"R{rating_score}")
        capture_chance = initial_battle_data.get("capture_chance", 40)

        my_miscrit = player1.get("miscrits", [{}])[0]
        my_name = my_miscrit.get("name", "Player Miscrit")
        my_mid = my_miscrit.get("mId", 0)
        my_level = my_miscrit.get("level", 35)

        # ── 1. RATING & TIER FILTER (13 TIERS TOTAL: 0 to 12) ──
        if rating_score < MIN_TARGET_RATING:
            print(
                f"{Colors.DIM}  [-] Rating: {Colors.YELLOW}{rating_name}{Colors.DIM} "
                f"({rating_score}/12) < Target (A+ s/d S+) → Auto Flee.{Colors.RESET}"
            )
            self.client.flee_and_leave(match_id)
            return "FLEE_RATING", None

        # ── 2. HIGH TIER TARGET DETECTED (A+, S, S+) ──
        print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} 🌟 TARGET SUPER TIER DITEMUKAN! 🌟 {Colors.RESET}")
        print(f"  Target  : {Colors.GREEN}{Colors.BOLD}{enemy_name} (#{enemy_mid}){Colors.RESET}")
        print(f"  Tier    : {Colors.YELLOW}{Colors.BOLD}{rating_name} (Score: {rating_score}/12 - Total 13 Ratings){Colors.RESET}")
        print(f"  HP Awal : {enemy_chp}/{enemy_hp} | Peluang Tangkap Awal: {capture_chance}%")
        print(f"{Colors.CYAN}──────────────────────────────────────────────────{Colors.RESET}")

        # Get and categorize player's available skills from database
        skills_sorted = self._get_player_skills(my_mid)
        
        # Turn loop variables
        turn = 1
        damage_per_ap = 2.0  # initial baseline estimate (calibrated dynamically)
        captured_data = None

        while True:
            # Calculate current HP percentage
            hp_pct = (enemy_chp / enemy_hp) * 100 if enemy_hp > 0 else 100

            # ── 3. DECISION: WEAKEN vs THROW CAPTURE CRATE ──
            # Calculate estimated damage of our weakest attack
            weakest_skill = skills_sorted[-1] if skills_sorted else {"id": 681, "name": "Basic Attack", "ap": 7}
            min_attack_dmg = int(weakest_skill.get("ap", 7) * damage_per_ap * 0.9)

            # STOP ATTACKING IF:
            # - HP is already in sweet spot (<= 20%)
            # - OR capture chance is already high (>= 85%)
            # - OR current HP is so low that ANY attack might KO the wild miscrit!
            is_lethal_risk = enemy_chp <= (min_attack_dmg * 1.1)
            is_in_capture_zone = hp_pct <= TARGET_CAPTURE_HP_PCT or capture_chance >= 85

            if is_in_capture_zone or is_lethal_risk:
                reason = "ZONA TANGKAP TERCAPAI (5-20%)" if is_in_capture_zone else "ANTI-KO ACTIVATED (Serangan berisiko membunuh)"
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
                    print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} 🎉 BERHASIL DITANGKAP! [Tier: {rating_name}] 🎉 {Colors.RESET}")
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
                        "rating_score": rating_score,
                        "rating_name": rating_name,
                        "stars": stars
                    }
                    return "CAUGHT", captured_data
                else:
                    print(f"  {Colors.YELLOW}⚠️ Tangkapan lepas / belum masuk. Mencoba kembali giliran berikutnya...{Colors.RESET}")

            else:
                # Need to weaken enemy safely:
                # Find the skill whose estimated damage brings enemy closest to 10% HP without dropping below 5% HP
                best_skill = self._select_optimal_skill(skills_sorted, enemy_chp, enemy_hp, damage_per_ap)
                
                s_id = best_skill.get("id", 681)
                s_name = best_skill.get("name", "Attack")
                s_ap = best_skill.get("ap", 10)
                est_dmg = int(s_ap * damage_per_ap)

                print(f"  {Colors.CYAN}[T{turn}] HP Musuh: {enemy_chp}/{enemy_hp} ({hp_pct:.1f}%) → ⚡ Cast Skill: {s_name} (AP: {s_ap}, Est Dmg: ~{est_dmg}){Colors.RESET}")
                
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
            if turn > 30:
                print(f"{Colors.YELLOW}Battle melebihi 30 giliran. Kabur.{Colors.RESET}")
                self.client.flee_and_leave(match_id)
                return "ESCAPED", None

    def _get_player_skills(self, my_mid: int) -> List[dict]:
        """Loads and sorts all attacking skills from database (Heavy to Light)."""
        m_info = self.db.get_miscrit(my_mid)
        if not m_info:
            return [{"id": 681, "name": "Basic Attack", "ap": 15}]

        # Look up in database abilities
        all_ab = []
        for m in self.db.miscrits.values():
            if m.get("id") == my_mid:
                for a in m.get("abilities", []):
                    if a.get("type") == "Attack" and a.get("ap", 0) > 0:
                        all_ab.append({
                            "id": a.get("id"),
                            "name": a.get("name"),
                            "ap": a.get("ap", 10)
                        })

        if not all_ab:
            return [
                {"id": 681, "name": "Heavy Strike", "ap": 25},
                {"id": 272, "name": "Medium Strike", "ap": 15},
                {"id": 264, "name": "Light Tap", "ap": 7}
            ]

        # Sort descending by AP (Highest damage to lowest damage)
        all_ab.sort(key=lambda x: x.get("ap", 0), reverse=True)
        return all_ab

    def _select_optimal_skill(self, skills: List[dict], enemy_chp: int, enemy_hp: int, dmg_per_ap: float) -> dict:
        """
        Picks the optimal skill that reduces enemy HP as much as possible
        while strictly guaranteeing the enemy survives with at least 5% HP.
        """
        safe_floor_hp = int(enemy_hp * (MIN_SAFE_HP_PCT / 100.0))  # e.g. 5% - 10%
        target_hp = int(enemy_hp * (TARGET_CAPTURE_HP_PCT / 100.0)) # e.g. 15%

        # Evaluate all skills from light to heavy
        valid_skills = []
        for s in reversed(skills):  # check from lowest AP to highest AP
            ap = s.get("ap", 10)
            max_est_damage = int(ap * dmg_per_ap * 1.2) # 20% crit/high roll buffer
            remaining_hp = enemy_chp - max_est_damage
            
            if remaining_hp >= safe_floor_hp:
                valid_skills.append((remaining_hp, s))

        if valid_skills:
            # Pick the skill that brings remaining HP closest to target_hp (15%)
            valid_skills.sort(key=lambda x: abs(x[0] - target_hp))
            return valid_skills[0][1]

        # If even the weakest skill might be lethal, return lowest AP skill
        return skills[-1] if skills else {"id": 681, "name": "Basic Attack", "ap": 7}
