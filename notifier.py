"""
╔══════════════════════════════════════════════════════════════════════╗
║  📢 BotMisc — Cross-Platform Notifier & Terminal Styler             ║
║  Works on Windows, Linux, and Android Termux                         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import time
import subprocess
import requests

# Ensure UTF-8 output on all platforms (prevents Windows cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Try colorama for Windows terminal ANSI support
try:
    import colorama
    colorama.init(autoreset=True)
except ImportError:
    pass


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


RARITY_COLORS = {
    "Common": Colors.WHITE,
    "Rare": Colors.BLUE,
    "Epic": Colors.MAGENTA,
    "Exotic": Colors.YELLOW,
    "Legendary": Colors.RED,
}


class Notifier:
    @staticmethod
    def log(msg: str, tag: str = "INFO", color: str = Colors.WHITE):
        ts = time.strftime("%H:%M:%S")
        print(f"{Colors.DIM}[{ts}]{Colors.RESET} {color}[{tag}]{Colors.RESET} {msg}")

    @staticmethod
    def success(msg: str):
        Notifier.log(msg, "SUCCESS", Colors.GREEN)

    @staticmethod
    def warn(msg: str):
        Notifier.log(msg, "WARN", Colors.YELLOW)

    @staticmethod
    def error(msg: str):
        Notifier.log(msg, "ERROR", Colors.RED)

    @staticmethod
    def hunt(encounter_num: int, spot_name: str, enemy_name: str, enemy_mid: int, rarity: str, is_target: bool):
        ts = time.strftime("%H:%M:%S")
        rc = RARITY_COLORS.get(rarity, Colors.WHITE)
        if is_target:
            print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} 🌟 [BINGO #{encounter_num}] {spot_name} 🌟 {Colors.RESET}")
            print(f"{Colors.GREEN}{Colors.BOLD}  TARGET DITEMUKAN: {enemy_name} (#{enemy_mid}) [{rarity}]!{Colors.RESET}\n")
        else:
            print(
                f"{Colors.DIM}[{ts}]{Colors.RESET} "
                f"{Colors.CYAN}#{encounter_num:<4d}{Colors.RESET} "
                f"[{spot_name:<20s}] → "
                f"{rc}{enemy_name} (#{enemy_mid}) [{rarity}]{Colors.RESET} "
                f"{Colors.DIM}» Flee{Colors.RESET}"
            )

    @staticmethod
    def sound_alarm(times: int = 8):
        """Cross-platform alarm sound for Windows, Linux, and Android Termux."""
        # 1. Windows winsound
        if sys.platform == "win32":
            try:
                import winsound
                for _ in range(times):
                    winsound.Beep(1200, 250)
                    time.sleep(0.08)
                return
            except Exception:
                pass

        # 2. Android Termux sound / vibrate
        if os.path.exists("/data/data/com.termux"):
            try:
                subprocess.Popen(["termux-vibrate", "-d", "1000", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.Popen(["termux-notification", "--title", "🌟 MISCRIT BINGO!", "--content", "Target Exotic/Legendary Ditemukan!"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        # 3. Linux aplay / paplay / bell
        for _ in range(times):
            sys.stdout.write("\a")
            sys.stdout.flush()
            time.sleep(0.2)

    @staticmethod
    def send_external_alert(target_name: str, target_mid: int, rarity: str, spot_name: str, webhook_url: str = "", tg_token: str = "", tg_chat: str = ""):
        """Sends webhook or Telegram alert if configured."""
        msg = f"🌟 **MISCRITS BINGO!**\nTarget: **{target_name} (#{target_mid})** [{rarity}]\nLokasi: {spot_name}\nWaktu: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Discord / Custom Webhook
        if webhook_url:
            try:
                requests.post(webhook_url, json={"content": msg}, timeout=5)
            except Exception:
                pass

        # Telegram Bot
        if tg_token and tg_chat:
            try:
                tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                requests.post(tg_url, json={"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"}, timeout=5)
            except Exception:
                pass

    @staticmethod
    def print_banner(active_spots_count: int):
        plat = sys.platform.capitalize()
        banner = f"""
{Colors.CYAN}{Colors.BOLD}========================================================================
             [BOTMISC] UNIVERSAL AUTO HUNTER (CLI)
          Exotic & Legendary Rotation Farming Engine
========================================================================{Colors.RESET}
  * Platform                : {plat}
  * Active Spots in Cycle   : {active_spots_count}
  * Cooldown Evasion        : Multi-Spot Cycling (Zero Waiting)
  * Target Roster           : Exotic & Legendary Daily Resets
{Colors.CYAN}{Colors.BOLD}========================================================================{Colors.RESET}"""
        print(banner)
