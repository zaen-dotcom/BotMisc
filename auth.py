"""
╔══════════════════════════════════════════════════════════════════════╗
║  🔑 BotMisc — Dynamic Authentication & Account Manager              ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import base64
import json
import getpass
import urllib.parse
import requests
from typing import Optional, Dict
from config import AUTH_BASE_URL, DEFAULT_HEADERS, ACCOUNT_FILE, TOKEN_REFRESH_BUFFER
from notifier import Notifier, Colors


class TokenManager:
    def __init__(self):
        self.token: Optional[str] = None
        self.expires_at: float = 0
        self.username: str = ""
        self.password: str = ""
        self.email: str = ""
        self._load_saved_account()

    def _load_saved_account(self):
        """Loads saved account credentials from data/account.json if available."""
        if os.path.exists(ACCOUNT_FILE):
            try:
                with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.username = data.get("username", "")
                    self.password = data.get("password", "")
                    self.email = data.get("email", "")
            except Exception:
                pass

    def save_account(self):
        """Saves credentials locally to data/account.json."""
        try:
            os.makedirs(os.path.dirname(ACCOUNT_FILE), exist_ok=True)
            with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "username": self.username,
                    "password": self.password,
                    "email": self.email
                }, f, indent=2)
            return True
        except Exception as e:
            Notifier.warn(f"Gagal menyimpan account.json: {e}")
            return False

    def prompt_credentials(self, force: bool = False):
        """Prompts user interactively for username & password if not provided."""
        if not force and self.username and self.password:
            return

        print(f"\n{Colors.CYAN}{Colors.BOLD}==================================================")
        print(f"             LOGIN AKUN MISCRITS                  ")
        print(f"=================================================={Colors.RESET}")
        
        default_user_hint = f" [{self.username}]" if self.username else ""
        u_input = input(f"Username Miscrits{default_user_hint}: ").strip()
        if u_input:
            self.username = u_input

        # Password input (hidden if possible)
        try:
            p_input = getpass.getpass("Password: ").strip()
        except Exception:
            p_input = input("Password: ").strip()

        if p_input:
            self.password = p_input

        # Ask to save
        save_choice = input("Simpan info login di perangkat ini? [Y/n]: ").strip().lower()
        if save_choice in ("", "y", "yes"):
            self.save_account()
            Notifier.success("Info login tersimpan di data/account.json.")
        print()

    def get_token(self, force_refresh: bool = False) -> Optional[str]:
        now = time.time()
        # If token is missing, expired, or close to expiry, refresh
        if force_refresh or not self.token or (self.expires_at > 0 and now >= (self.expires_at - TOKEN_REFRESH_BUFFER)):
            return self._authenticate()
        return self.token

    def _authenticate(self) -> Optional[str]:
        if not self.username or not self.password:
            self.prompt_credentials()

        if not self.username or not self.password:
            Notifier.error("Username dan Password tidak boleh kosong!")
            return None

        Notifier.log(f"Mengautentikasi akun '{self.username}' ke server Nakama...", "AUTH")
        
        # Build URL with encoded username
        encoded_user = urllib.parse.quote(self.username)
        auth_url = f"{AUTH_BASE_URL}?create=false&username={encoded_user}&"
        
        payload = {
            "email": self.email,
            "password": self.password
        }

        try:
            resp = requests.post(auth_url, headers=DEFAULT_HEADERS, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                if token:
                    self.token = token
                    self._parse_jwt_expiry(token)
                    Notifier.success(f"Login Sukses! Akun: {self.username} (Token valid s/d {time.strftime('%H:%M:%S', time.localtime(self.expires_at))})")
                    return token
            elif resp.status_code in (400, 401, 404):
                Notifier.error(f"Login Gagal! Username atau Password salah (Status: {resp.status_code}).")
                # Retry prompt
                self.prompt_credentials(force=True)
                return self._authenticate()
            else:
                Notifier.error(f"Autentikasi Gagal! Status: {resp.status_code}, Respon: {resp.text[:100]}")
                return None
        except Exception as e:
            Notifier.error(f"Koneksi ke server auth gagal: {e}")
            return None

    def _parse_jwt_expiry(self, token: str):
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                payload_str = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
                payload = json.loads(payload_str)
                self.expires_at = float(payload.get("exp", time.time() + 3600))
                self.username = payload.get("usn", self.username)
        except Exception:
            self.expires_at = time.time() + 3600

    def logout(self):
        """Removes saved credentials."""
        self.username = ""
        self.password = ""
        self.token = None
        if os.path.exists(ACCOUNT_FILE):
            try:
                os.remove(ACCOUNT_FILE)
            except Exception:
                pass
        Notifier.success("Info login berhasil dihapus.")
