"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚔️  BOTMISC — ADVANCED BATTLE & CAPTURE PROTOCOL SNIFFER (MITM)    ║
║                                                                      ║
║  Tujuan:                                                             ║
║  - Merekam & mendekode seluruh aksi pertarungan di Miscrits          ║
║  - Mendeteksi OpCode & Payload untuk:                                ║
║      1. Serangan / Cast Ability (Attack)                             ║
║      2. Ganti Miscrit (Switch)                                       ║
║      3. Gunakan Item / Menangkap Miscrit (Capture / Miscrum Trap)    ║
║      4. Kabur (Flee)                                                 ║
║  - Menghasilkan contoh kode Python siap pakai untuk Auto-Attack      ║
║    dan Auto-Capture di bot Anda!                                     ║
║                                                                      ║
║  Cara Menjalankan:                                                   ║
║    mitmdump -s battle_sniffer.py --ssl-insecure                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import os
import sys
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from mitmproxy import http, ctx

# ─────────────────────────────────────────────
#  Directories & Paths
# ─────────────────────────────────────────────
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(CURRENT_DIR, "captured_battles")
os.makedirs(CAPTURE_DIR, exist_ok=True)

DATABASE_FILE = os.path.join(CURRENT_DIR, "..", "data", "miscrits.json")

# ─────────────────────────────────────────────
#  ANSI Colors
# ─────────────────────────────────────────────
class C:
    RESET       = "\033[0m"
    BOLD        = "\033[1m"
    DIM         = "\033[2m"
    RED         = "\033[91m"
    GREEN       = "\033[92m"
    YELLOW      = "\033[93m"
    BLUE        = "\033[94m"
    MAGENTA     = "\033[95m"
    CYAN        = "\033[96m"
    WHITE       = "\033[97m"
    BG_BLUE     = "\033[44m"
    BG_GREEN    = "\033[42m"
    BG_MAGENTA  = "\033[45m"
    BG_RED      = "\033[41m"
    BG_YELLOW   = "\033[43m"


# ─────────────────────────────────────────────
#  Load Database for Name Resolution
# ─────────────────────────────────────────────
MISCRIT_NAMES = {}
ABILITY_NAMES = {}

if os.path.exists(DATABASE_FILE):
    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            for m in json.load(f):
                mid = m.get("id")
                name = m.get("names", ["?"])[0]
                MISCRIT_NAMES[mid] = name
                for ab in m.get("abilities", []):
                    aid = ab.get("id")
                    if aid:
                        ABILITY_NAMES[aid] = ab.get("name", f"Skill #{aid}")
    except Exception:
        pass


def get_ts() -> str:
    tz = timezone(timedelta(hours=7))
    return datetime.now(tz).strftime("%H:%M:%S.%f")[:-3]


def get_miscrit_name(mid: int) -> str:
    return f"{MISCRIT_NAMES.get(mid, 'Unknown')} (#{mid})"


def get_ability_name(aid: int) -> str:
    return f"{ABILITY_NAMES.get(aid, 'Skill')} (#{aid})"


# ─────────────────────────────────────────────
#  Battle Session Tracker
# ─────────────────────────────────────────────
class BattleSession:
    def __init__(self, match_id: str, object_id: Optional[int] = None):
        self.match_id = match_id
        self.object_id = object_id
        self.start_time = get_ts()
        self.actions = []
        self.p1_name = "Player"
        self.p2_name = "Wild Miscrit"
        self.p2_mid = 0
        self.is_active = True

    def log_action(self, action_type: str, direction: str, opcode: Any, payload: Any, raw_b64: str = ""):
        self.actions.append({
            "time": get_ts(),
            "direction": direction,
            "action_type": action_type,
            "op_code": opcode,
            "payload": payload,
            "raw_base64": raw_b64
        })

    def save(self):
        filename = f"battle_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.match_id[:8]}.json"
        filepath = os.path.join(CAPTURE_DIR, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "match_id": self.match_id,
                    "object_id": self.object_id,
                    "start_time": self.start_time,
                    "enemy": f"{self.p2_name} (#{self.p2_mid})",
                    "total_actions": len(self.actions),
                    "action_log": self.actions
                }, f, indent=2, ensure_ascii=False)
            ctx.log.info(f"{C.DIM}[*] Battle session log tersimpan di: {filename}{C.RESET}")
        except Exception as e:
            ctx.log.error(f"Gagal menyimpan session: {e}")


# ─────────────────────────────────────────────
#  Main Sniffer Addon
# ─────────────────────────────────────────────
class BattleProtocolSniffer:
    def __init__(self):
        self.current_session: Optional[BattleSession] = None
        self.pending_object_id: Optional[int] = None
        self.turn_number = 1
        self._print_banner()

    def _print_banner(self):
        banner = f"""
{C.CYAN}{C.BOLD}
╔══════════════════════════════════════════════════════════════════════╗
║        ⚔️  BOTMISC — ADVANCED BATTLE PROTOCOL SNIFFER ⚔️            ║
║        Reverse Engineering Tool for Attack & Capture Actions         ║
╠══════════════════════════════════════════════════════════════════════╣
║  • Otomatis mendekode OpCode & Base64 pertarungan secara Live        ║
║  • Menangkap payload: Attack, Cast Skill, Use Trap/Capture, Flee     ║
║  • Menyimpan riwayat pertarungan ke folder /captured_battles         ║
╚══════════════════════════════════════════════════════════════════════╝
{C.RESET}"""
        for line in banner.strip().split("\n"):
            ctx.log.info(line)

    def websocket_message(self, flow: http.HTTPFlow):
        if flow.websocket is None:
            return

        msg = flow.websocket.messages[-1]
        if not msg.is_text:
            return

        try:
            data = json.loads(msg.text)
        except Exception:
            return

        ts = get_ts()

        # ════════════════════════════════════════════════════════════
        #  1. CLIENT ➔ SERVER ACTIONS
        # ════════════════════════════════════════════════════════════
        if msg.from_client:
            # (A) Create Battle RPC
            rpc = data.get("rpc", {})
            if rpc.get("id") == "create_battle":
                try:
                    payload = json.loads(rpc.get("payload", "{}"))
                    obj_id = payload.get("payload", {}).get("objectId")
                    btype = payload.get("type", "Wild")
                    self.pending_object_id = obj_id
                    ctx.log.info(f"\n{C.CYAN}{C.BOLD}▶ [INIT BATTLE] Memulai pertarungan di ObjectID: {obj_id} ({btype}){C.RESET}")
                except Exception:
                    pass
                return

            # (B) Match Join RPC
            if "match_join" in data:
                m_id = data["match_join"].get("match_id", "")
                self.current_session = BattleSession(m_id, self.pending_object_id)
                self.turn_number = 1
                ctx.log.info(f"{C.GREEN}{C.BOLD}▶ [MATCH JOIN] Bergabung ke Room: {m_id}{C.RESET}")
                return

            # (C) Match Data Send (ATTACK, CAPTURE, SWITCH, FLEE)
            if "match_data_send" in data:
                m_send = data["match_data_send"]
                match_id = m_send.get("match_id", "")
                op_code = m_send.get("op_code", 0)
                raw_b64 = m_send.get("data", "")

                decoded_payload = {}
                try:
                    decoded_str = base64.b64decode(raw_b64).decode("utf-8")
                    decoded_payload = json.loads(decoded_str)
                except Exception:
                    decoded_payload = {"raw": raw_b64}

                action_name = self._resolve_client_opcode(op_code, decoded_payload)

                ctx.log.info(f"\n{C.YELLOW}{C.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                ctx.log.info(f"📤 [AKSI ANDA - T{self.turn_number}] {action_name} (OpCode: {op_code})")
                ctx.log.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
                ctx.log.info(f"{C.YELLOW}  Decoded Payload JSON:{C.RESET}")
                ctx.log.info(f"{C.DIM}{json.dumps(decoded_payload, indent=4)}{C.RESET}")
                ctx.log.info(f"{C.YELLOW}  Base64 Payload:{C.RESET} {raw_b64}")
                
                # Print ready-to-use Python snippet
                self._print_python_snippet(match_id, op_code, raw_b64, decoded_payload, action_name)

                if self.current_session:
                    self.current_session.log_action(action_name, "CLIENT_TO_SERVER", op_code, decoded_payload, raw_b64)

                self.turn_number += 1
                return

            # (D) Match Leave
            if "match_leave" in data:
                ctx.log.info(f"{C.BLUE}▶ [MATCH LEAVE] Meninggalkan room pertarungan.{C.RESET}\n")
                if self.current_session:
                    self.current_session.save()
                    self.current_session = None
                return

        # ════════════════════════════════════════════════════════════
        #  2. SERVER ➔ CLIENT RESPONSES
        # ════════════════════════════════════════════════════════════
        else:
            # (A) Match Data Incoming (Battle State, Health, Damage, Enemy Info)
            if "match_data" in data:
                m_data = data["match_data"]
                op_code = m_data.get("op_code", 0)
                raw_b64 = m_data.get("data", "")

                try:
                    decoded_str = base64.b64decode(raw_b64).decode("utf-8")
                    d_json = json.loads(decoded_str)
                except Exception:
                    return

                # (1) Initial Encounter Info
                if "player2" in d_json and "player1" in d_json:
                    p1 = d_json["player1"]
                    p2 = d_json["player2"]

                    my_miscrit = p1.get("miscrits", [{}])[0]
                    enemy_miscrit = p2.get("miscrits", [{}])[0]

                    enemy_mid = enemy_miscrit.get("mId", 0)
                    enemy_name = enemy_miscrit.get("name", get_miscrit_name(enemy_mid))
                    enemy_hp = enemy_miscrit.get("hp", "?")
                    enemy_max_hp = enemy_miscrit.get("maxHp", enemy_hp)

                    my_name = my_miscrit.get("name", "Miscrit Anda")
                    my_hp = my_miscrit.get("hp", "?")

                    if self.current_session:
                        self.current_session.p2_name = enemy_name
                        self.current_session.p2_mid = enemy_mid

                    ctx.log.info(f"\n{C.GREEN}{C.BOLD}═════════════════════════════════════════════════════")
                    ctx.log.info(f"⚔️  [BATTLE DIMULAI] Musuh: {enemy_name} (#{enemy_mid})")
                    ctx.log.info(f"═════════════════════════════════════════════════════{C.RESET}")
                    ctx.log.info(f"  🟢 {C.BOLD}Miscrit Anda:{C.RESET} {my_name} [HP: {my_hp}]")
                    ctx.log.info(f"  🔴 {C.BOLD}Miscrit Musuh:{C.RESET} {enemy_name} [HP: {enemy_hp}/{enemy_max_hp}]")
                    
                    # Log available abilities of player miscrit
                    abilities = my_miscrit.get("abilities", [])
                    if abilities:
                        ctx.log.info(f"  ⚡ {C.BOLD}Skill Anda yang Siap Dipakai:{C.RESET}")
                        for ab in abilities:
                            aid = ab.get("id")
                            aname = ab.get("name", get_ability_name(aid))
                            ctx.log.info(f"     • ID {aid:4d}: {aname}")
                    ctx.log.info("")

                # (2) Turn Action Results (Damage, Capture Status, Faint, etc.)
                if "actions" in d_json or "action" in d_json:
                    actions = d_json.get("actions", [d_json.get("action")])
                    for act in actions:
                        if not act:
                            continue
                        atype = act.get("type", "Unknown")
                        dmg = act.get("damage", 0)
                        target = act.get("target", "")
                        
                        if atype == "Attack":
                            ctx.log.info(f"{C.RED}  💥 Damage: -{dmg} HP ke {target}{C.RESET}")
                        elif atype in ("Capture", "Item", "Catch"):
                            success = act.get("success", False)
                            status_text = f"{C.GREEN}BERHASIL DITANGKAP! 🎉{C.RESET}" if success else f"{C.YELLOW}Gagal Menangkap (Kabur/Lepas){C.RESET}"
                            ctx.log.info(f"{C.MAGENTA}{C.BOLD}  📦 [STATUS CAPTURE] {status_text}{C.RESET}")
                        elif atype == "Faint":
                            ctx.log.info(f"{C.RED}{C.BOLD}  💀 Miscrit KO / Faint!{C.RESET}")

                if self.current_session:
                    self.current_session.log_action("SERVER_UPDATE", "SERVER_TO_CLIENT", op_code, d_json, raw_b64)

    def _resolve_client_opcode(self, op_code: int, payload: dict) -> str:
        """Translates numeric OpCode to human-readable action name."""
        if op_code == 1:
            aid = payload.get("abilityId", payload.get("ability_id", payload.get("id", "?")))
            aname = get_ability_name(aid) if isinstance(aid, int) else f"Skill #{aid}"
            return f"⚡ SERANGAN / CAST ABILITY [{aname}]"
        elif op_code == 2:
            return "🔄 GANTI MISCRIT (SWITCH)"
        elif op_code == 3:
            item_id = payload.get("itemId", payload.get("item_id", "?"))
            return f"📦 GUNAKAN ITEM / TANGKAP (CAPTURE) [Item #{item_id}]"
        elif op_code == 4:
            return "🏃 KABUR DARI PERTARUNGAN (FLEE)"
        elif op_code == 5:
            return "⏭️ LEWATI GILIRAN (PASS / SURRENDER)"
        else:
            return f"❓ OP_CODE_{op_code}"

    def _print_python_snippet(self, match_id: str, op_code: int, raw_b64: str, payload: dict, action_name: str):
        """Prints copy-paste ready Python code snippet for bot development."""
        snippet = f"""
{C.CYAN}# ── Contoh Kode Python untuk {action_name} ──
ws.send(json.dumps({{
    "cid": str(cid_counter),
    "match_data_send": {{
        "match_id": "{match_id}",
        "op_code": {op_code},
        "data": "{raw_b64}"  # Decoded: {json.dumps(payload)}
    }}
}}))
{C.RESET}"""
        ctx.log.info(snippet)


# Register Addon
addons = [BattleProtocolSniffer()]
