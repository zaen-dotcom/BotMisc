"""
╔══════════════════════════════════════════════════════════════════════╗
║  🔌 BotMisc — Nakama WebSocket Client & Battle Controller            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import time
import base64
import websocket
from typing import Optional, Dict, Any, Tuple
from config import HOST, FLEE_DELAY, LEAVE_DELAY
from auth import TokenManager
from notifier import Notifier


class NakamaClient:
    def __init__(self, token_mgr: TokenManager):
        self.token_mgr = token_mgr
        self.ws: Optional[websocket.WebSocket] = None
        self.cid_counter = 1
        self.is_connected = False

    def connect(self) -> bool:
        self.disconnect()
        token = self.token_mgr.get_token()
        if not token:
            Notifier.error("Gagal mendapatkan token untuk koneksi WebSocket.")
            return False

        ws_url = f"ws://{HOST}/ws?lang=en&status=true&token={token}"
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(ws_url, timeout=10)
            self.is_connected = True
            self.cid_counter = 1
            
            # Initial handshake
            self._send({"cid": str(self._next_cid()), "rpc": {"id": "join_global"}})
            time.sleep(0.3)
            return True
        except Exception as e:
            Notifier.error(f"Gagal menghubungkan WebSocket: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws = None
        self.is_connected = False

    def _next_cid(self) -> int:
        c = self.cid_counter
        self.cid_counter += 1
        return c

    def _send(self, payload: dict) -> bool:
        if not self.ws or not self.is_connected:
            return False
        try:
            self.ws.send(json.dumps(payload))
            return True
        except Exception as e:
            Notifier.warn(f"WebSocket kirim gagal: {e}")
            self.is_connected = False
            return False

    def send_match_data(self, match_id: str, op_code: int, payload_dict: dict) -> bool:
        """Encodes payload to base64 and sends match_data_send."""
        if not match_id:
            return False
        payload_str = json.dumps(payload_dict)
        raw_b64 = base64.b64encode(payload_str.encode("utf-8")).decode("utf-8")
        
        msg = {
            "cid": str(self._next_cid()),
            "match_data_send": {
                "match_id": match_id,
                "op_code": op_code,
                "data": raw_b64
            }
        }
        return self._send(msg)

    def cast_ability(self, match_id: str, ability_id: int):
        """OpCode 2: Cast Ability / Attack."""
        return self.send_match_data(match_id, 2, {"id": ability_id})

    def send_sync_animation(self, match_id: str):
        """OpCode 8: Animation Finished Sync Pulse."""
        return self.send_match_data(match_id, 8, {})

    def send_capture(self, match_id: str):
        """OpCode 10: Throw Capture Crate / Trap."""
        return self.send_match_data(match_id, 10, {})

    def send_keep_or_release(self, match_id: str, keep: bool = True):
        """OpCode 11: Keep or Release caught miscrit."""
        return self.send_match_data(match_id, 11, {"keep": keep, "name": ""})

    def send_match_leave(self, match_id: str):
        """Sends match_leave to cleanly terminate the match room."""
        if not match_id:
            return
        self._send({
            "cid": str(self._next_cid()),
            "match_leave": {"match_id": match_id}
        })
        time.sleep(LEAVE_DELAY)

    def flee_and_leave(self, match_id: str):
        """Clean 2-step teardown: Flee opcode 4 + match_leave."""
        if not match_id or not self.is_connected:
            return

        # 1. Send Flee Opcode (4)
        self._send({
            "cid": str(self._next_cid()),
            "match_data_send": {
                "match_id": match_id,
                "op_code": 4,
                "data": "e30="
            }
        })
        time.sleep(FLEE_DELAY)

        # 2. Send Match Leave
        self.send_match_leave(match_id)

    def recv_battle_message(self, timeout: float = 6.0) -> Optional[dict]:
        """Receives and decodes the next incoming match_data message."""
        if not self.ws or not self.is_connected:
            return None

        start = time.time()
        while time.time() - start < timeout:
            try:
                raw = self.ws.recv()
                if not raw:
                    continue
                data = json.loads(raw)
                
                if "match_data" in data:
                    raw_b64 = data["match_data"].get("data", "")
                    if raw_b64:
                        decoded_str = base64.b64decode(raw_b64).decode("utf-8")
                        return json.loads(decoded_str)
            except Exception:
                pass
        return None

    def probe_object(self, object_id: int) -> Tuple[str, Optional[int], Optional[str], Optional[str], Optional[dict], int]:
        """
        Interacts with an objectId on the server to trigger a battle encounter.
        
        Returns:
            (status, enemy_mid, enemy_name, match_id, initial_battle_data, cooldown_seconds)
            Status can be: "SUCCESS", "COOLDOWN", "EMPTY", "ERROR"
        """
        if not self.is_connected and not self.connect():
            return "ERROR", None, None, None, None, 5

        battle_payload = {
            "cid": str(self._next_cid()),
            "rpc": {
                "id": "create_battle",
                "payload": json.dumps({"payload": {"objectId": object_id}, "type": "Wild"})
            }
        }

        if not self._send(battle_payload):
            return "ERROR", None, None, None, None, 5

        match_id = None
        enemy_mid = None
        enemy_name = None
        initial_battle_data = None

        # Process messages with loop
        for _ in range(16):
            try:
                raw = self.ws.recv()
                if not raw:
                    continue
                data = json.loads(raw)
            except Exception as e:
                Notifier.warn(f"Error menerima data socket: {e}")
                self.is_connected = False
                return "ERROR", None, None, None, None, 5

            # 1. Check create_battle RPC response
            if "rpc" in data and data.get("rpc", {}).get("id") == "create_battle":
                p_data = json.loads(data["rpc"].get("payload", "{}"))
                if p_data.get("success") is True:
                    match_id = json.loads(p_data.get("data", "{}")).get("matchId")
                    if match_id:
                        # Join the match
                        self._send({"cid": str(self._next_cid()), "match_join": {"match_id": match_id}})
                else:
                    # Check if cooldown or empty
                    err_data = p_data.get("data", "")
                    try:
                        err_json = json.loads(err_data) if isinstance(err_data, str) else err_data
                        cd = err_json.get("cooldown", 0)
                        if cd > 0:
                            return "COOLDOWN", None, None, None, None, cd
                    except Exception:
                        pass
                    return "EMPTY", None, None, None, None, 0

            # 2. Check Match Data for enemy Miscrit
            if match_id and "match_data" in data:
                try:
                    d_str = base64.b64decode(data["match_data"].get("data", "")).decode("utf-8")
                    d_json = json.loads(d_str)
                    if "player2" in d_json:
                        enemy = d_json["player2"]["miscrits"][0]
                        enemy_mid = enemy.get("mId")
                        enemy_name = enemy.get("name", f"Miscrit #{enemy_mid}")
                        initial_battle_data = d_json
                        return "SUCCESS", enemy_mid, enemy_name, match_id, initial_battle_data, 0
                except Exception:
                    pass

        return "EMPTY", None, None, None, None, 0
