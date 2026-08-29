"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚔️  BOTMISC — ADVANCED BATTLE & MAP PROTOCOL SNIFFER (MITM)         ║
║                                                                      ║
║  Tujuan:                                                             ║
║  - Merekam & mendekode seluruh aksi pertarungan & perpindahan map    ║
║  - Mendeteksi OpCode & Payload untuk:                                ║
║      1. Pindah Map / Portal / Teleport                              ║
║      2. Serangan / Cast Ability (Attack)                             ║
║      3. Gunakan Item / Menangkap Miscrit (Capture / Trap)            ║
║      4. Keep / Simpan Hewan Tangkapan                                ║
║      5. Kabur (Flee)                                                 ║
║                                                                      ║
║  Cara Menjalankan:                                                   ║
║    python battle_sniffer.py                                          ║
║    (atau: mitmdump -s battle_sniffer.py --listen-port 8080)          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import os
import sys
import base64
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

# ─────────────────────────────────────────────
#  Directories & Paths
# ─────────────────────────────────────────────
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(CURRENT_DIR, "captured_battles")
EVENTS_FILE = os.path.join(CURRENT_DIR, "captured_events.json")
os.makedirs(CAPTURE_DIR, exist_ok=True)

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

def get_ts() -> str:
    tz_wib = timezone(timedelta(hours=7))
    return datetime.now(tz_wib).strftime("%H:%M:%S.%f")[:-3]

def safe_log(msg: str, level: str = "info"):
    """Safely logs to mitmproxy or standard stdout."""
    try:
        from mitmproxy import ctx
        if hasattr(ctx, "log"):
            log_fn = getattr(ctx.log, level, ctx.log.info)
            log_fn(msg)
            return
    except Exception:
        pass
    print(msg)

def append_event(event_type: str, data: dict):
    """Automatically records any detected event / RPC to captured_events.json."""
    event = {
        "timestamp": get_ts(),
        "type": event_type,
        "data": data
    }
    try:
        events = []
        if os.path.exists(EVENTS_FILE):
            try:
                with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                    events = json.load(f)
            except Exception:
                events = []
        events.append(event)
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
    except Exception as e:
        safe_log(f"Gagal mencatat event ke JSON: {e}", "error")



# ─────────────────────────────────────────────
#  Battle Session Logger
# ─────────────────────────────────────────────
class BattleSession:
    def __init__(self, match_id: str, object_id: Optional[int] = None):
        self.match_id = match_id
        self.object_id = object_id
        self.start_time = datetime.now().isoformat()
        self.enemy_name = "Unknown"
        self.enemy_mid = 0
        self.enemy_rating = 0
        self.action_log = []

    def log_action(self, action_type: str, direction: str, op_code: Optional[int], payload: dict, raw: str = ""):
        self.action_log.append({
            "timestamp": get_ts(),
            "direction": direction,
            "action_type": action_type,
            "op_code": op_code,
            "payload": payload,
            "raw_base64": raw
        })

    def save(self):
        tz_wib = timezone(timedelta(hours=7))
        time_str = datetime.now(tz_wib).strftime("%Y%m%d_%H%M%S")
        clean_id = self.match_id.split(".")[0][:8]
        filename = os.path.join(CAPTURE_DIR, f"battle_{time_str}_{clean_id}.json")
        data = {
            "match_id": self.match_id,
            "object_id": self.object_id,
            "start_time": self.start_time,
            "enemy": f"{self.enemy_name} (#{self.enemy_mid})",
            "enemy_rating": self.enemy_rating,
            "total_actions": len(self.action_log),
            "action_log": self.action_log
        }
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            safe_log(f"{C.DIM}[*] Battle session log tersimpan di: {filename}{C.RESET}")
        except Exception as e:
            safe_log(f"Gagal menyimpan session: {e}", "error")


# ─────────────────────────────────────────────
#  Main Sniffer Addon
# ─────────────────────────────────────────────
class BattleProtocolSniffer:
    def __init__(self):
        self.current_session: Optional[BattleSession] = None
        self.pending_object_id: Optional[int] = None
        self.turn_number = 1

    def load(self, loader):
        self._print_banner()

    def _print_banner(self):
        banner = f"""
{C.CYAN}{C.BOLD}
╔══════════════════════════════════════════════════════════════════════╗
║     ⚔️  BOTMISC — ADVANCED BATTLE & MAP PROTOCOL SNIFFER ⚔️           ║
║     Reverse Engineering Tool for Battles, Captures & Map Portals     ║
╠══════════════════════════════════════════════════════════════════════╣
║  • Otomatis mendekode OpCode & Base64 pertarungan secara Live        ║
║  • Mendeteksi paket Portal / Pindah Map secara real-time             ║
║  • Menangkap: Attack, Skills, Crate Capture, Keep, Flee, Movement   ║
║  • Menyimpan riwayat ke folder /captured_battles                     ║
╚══════════════════════════════════════════════════════════════════════╝
{C.RESET}"""
        for line in banner.strip().split("\n"):
            safe_log(line)

    def websocket_message(self, flow):
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
            # (A) RPC Requests (Battle, Map, Portal, Join)
            if "rpc" in data:
                rpc = data.get("rpc", {})
                rpc_id = rpc.get("id", "")
                raw_payload = rpc.get("payload", "")

                try:
                    payload_obj = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                except Exception:
                    payload_obj = raw_payload

                if rpc_id == "create_battle":
                    obj_id = payload_obj.get("payload", {}).get("objectId") if isinstance(payload_obj, dict) else None
                    btype = payload_obj.get("type", "Wild") if isinstance(payload_obj, dict) else "Wild"
                    self.pending_object_id = obj_id
                    safe_log(f"\n{C.CYAN}{C.BOLD}▶ [INIT BATTLE] Memulai pertarungan di ObjectID: {obj_id} ({btype}){C.RESET}")
                    append_event("INIT_BATTLE", {"objectId": obj_id, "type": btype, "raw": payload_obj})
                    return

                elif rpc_id in ("join_global", "join_chat"):
                    # Ignore spammy chat joins
                    return

                else:
                    # 🌟 POTENTIAL MAP / PORTAL / MOVEMENT RPC!
                    safe_log(f"\n{C.GREEN}{C.BOLD}🌟 [RPC TERDETEKSI: {rpc_id}] 🌟{C.RESET}")
                    safe_log(f"{C.GREEN}  Payload: {json.dumps(payload_obj, indent=2)}{C.RESET}\n")
                    append_event("MAP_OR_RPC", {"rpc_id": rpc_id, "payload": payload_obj})
                    return

            # (B) Match Join RPC
            if "match_join" in data:
                m_id = data["match_join"].get("match_id", "")
                self.current_session = BattleSession(m_id, self.pending_object_id)
                self.turn_number = 1
                safe_log(f"{C.GREEN}{C.BOLD}▶ [MATCH JOIN] Bergabung ke Room: {m_id}{C.RESET}")
                return

            # (C) Match Data Send (ATTACK, CAPTURE, KEEP, FLEE)
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

                safe_log(f"\n{C.YELLOW}{C.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                safe_log(f"📤 [AKSI ANDA - T{self.turn_number}] {action_name} (OpCode: {op_code})")
                safe_log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
                safe_log(f"{C.YELLOW}  Decoded Payload JSON:{C.RESET}")
                safe_log(f"{C.DIM}{json.dumps(decoded_payload, indent=4)}{C.RESET}")
                safe_log(f"{C.YELLOW}  Base64 Payload:{C.RESET} {raw_b64}")
                
                # Print ready-to-use Python snippet
                self._print_python_snippet(match_id, op_code, raw_b64, decoded_payload, action_name)

                if self.current_session:
                    self.current_session.log_action(action_name, "CLIENT_TO_SERVER", op_code, decoded_payload, raw_b64)

                self.turn_number += 1
                return

            # (D) Match Leave
            if "match_leave" in data:
                safe_log(f"{C.BLUE}▶ [MATCH LEAVE] Meninggalkan room pertarungan.{C.RESET}\n")
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
                    parsed_json = json.loads(decoded_str)
                except Exception:
                    parsed_json = {"raw": raw_b64}

                # Initial Battle Info (Enemy Miscrit, Level, Rating)
                if "player2" in parsed_json:
                    p2 = parsed_json.get("player2", {})
                    p2_miscrit = p2.get("miscrits", [{}])[0]
                    enemy_name = p2_miscrit.get("name", "Unknown")
                    enemy_mid = p2_miscrit.get("mId", 0)
                    enemy_lvl = p2_miscrit.get("level", 0)
                    enemy_hp = p2_miscrit.get("hp", 0)
                    enemy_rating = p2_miscrit.get("rating", 0)

                    if self.current_session:
                        self.current_session.enemy_name = enemy_name
                        self.current_session.enemy_mid = enemy_mid
                        self.current_session.enemy_rating = enemy_rating

                    safe_log(f"\n{C.MAGENTA}{C.BOLD}═════════════════════════════════════════════════════")
                    safe_log(f"👾 [DATA MUSUH] {enemy_name} (#{enemy_mid}) | Lvl: {enemy_lvl}")
                    safe_log(f"   Max HP: {enemy_hp} | Total Stars / Rating: {enemy_rating}")
                    safe_log(f"═════════════════════════════════════════════════════{C.RESET}\n")

                # Battle Updates / Actions (Damage dealt, status)
                if "actions" in parsed_json:
                    for act in parsed_json.get("actions", []):
                        atype = act.get("type", "")
                        atarget = act.get("target", "")
                        admg = act.get("damage", 0)
                        if atype == "Attack":
                            safe_log(f"{C.RED}  💥 Damage Deal: -{admg} HP ke {atarget}{C.RESET}")
                        elif atype == "Faint":
                            safe_log(f"{C.RED}{C.BOLD}  💀 {atarget} KO / Pingsan!{C.RESET}")

                # Capture Result
                if "captured" in parsed_json:
                    is_captured = parsed_json.get("captured")
                    stars = parsed_json.get("stars", {})
                    if is_captured:
                        safe_log(f"\n{C.GREEN}{C.BOLD}🎉 [HASIL TANGKAPAN] MISCRIT BERHASIL DITANGKAP! 🎉{C.RESET}")
                        safe_log(f"{C.GREEN}  Stars (IVs): {json.dumps(stars)}{C.RESET}\n")
                    else:
                        safe_log(f"\n{C.YELLOW}[!] Miscrit gagal ditangkap / kabur dari crate.{C.RESET}\n")

                if self.current_session:
                    self.current_session.log_action("SERVER_UPDATE", "SERVER_TO_CLIENT", op_code, parsed_json, raw_b64)

    def _resolve_client_opcode(self, op_code: int, payload: dict) -> str:
        if op_code == 2:
            skill_id = payload.get("id")
            return f"⚡ CAST ABILITY (Skill ID: {skill_id})"
        elif op_code == 8:
            return "🔄 ANIMATION SYNC"
        elif op_code == 10:
            return "📦 USE CAPTURE CRATE"
        elif op_code == 11:
            keep = payload.get("keep", True)
            return f"💾 {'KEEP' if keep else 'RELEASE'} CAUGHT MISCRIT"
        elif op_code == 4:
            return "🏃 FLEE / RUN AWAY"
        elif op_code == 5:
            return f"🔄 SWITCH MISCRIT (Slot: {payload.get('id')})"
        return f"UNKNOWN ACTION (OpCode {op_code})"

    def _print_python_snippet(self, match_id: str, op_code: int, raw_b64: str, payload: dict, action_name: str):
        snippet = f"""{C.CYAN}# ── Contoh Kode Python untuk {action_name} ──
ws.send(json.dumps({{
    "cid": str(cid_counter),
    "match_data_send": {{
        "match_id": "{match_id}",
        "op_code": {op_code},
        "data": "{raw_b64}"  # Decoded: {json.dumps(payload)}
    }}
}}))
{C.RESET}"""
        safe_log(snippet)


# Register Addon for mitmproxy
addons = [BattleProtocolSniffer()]


# Allow direct execution via: python battle_sniffer.py
if __name__ == "__main__":
    print(f"{C.GREEN}[*] Meluncurkan Mitmproxy Packet Sniffer di Port 8080...{C.RESET}")
    cmd = [
        "mitmdump",
        "-s", os.path.abspath(__file__),
        "--listen-port", "8080",
        "--ssl-insecure"
    ]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[*] Sniffer dihentikan.")
    except Exception as e:
        print(f"\n[!] Gagal menjalankan mitmdump: {e}")
        print("Pastikan mitmproxy terinstall: pip install mitmproxy")
