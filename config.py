"""
╔══════════════════════════════════════════════════════════════════════╗
║  🎮 BotMisc — Configuration Module                                   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os

# Project Root Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SPOTS_FILE = os.path.join(DATA_DIR, "spots.json")
MISCRITS_FILE = os.path.join(DATA_DIR, "miscrits.json")
ACCOUNT_FILE = os.path.join(DATA_DIR, "account.json")

# ================= NAKAMA SERVER CONFIG =================
HOST = "63.183.56.199:7350"
AUTH_BASE_URL = "https://worldofmiscrits.com/v2/account/authenticate/email"
SERVER_BASIC_AUTH = "Basic YTFjNzM3Y2MxODhmNTRhYjM2NThiYTVkYTBlMTJlZTU6"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Authorization": SERVER_BASIC_AUTH,
    "User-Agent": "GodotEngine/4.6.stable.custom_build (Windows)",
    "Content-Type": "application/json"
}

# ================= RATING & TIER SETTINGS =================
# Server 'rating' field is Total Stars (6 to 18 stars)
# Score = Total Stars - 6 (Score 0 to 12, exactly 13 tiers, S+ is highest!)
STAR_TO_TIER = {
    6:  ("F-", 0),
    7:  ("F",  1),
    8:  ("F+", 2),
    9:  ("D",  3),
    10: ("D+", 4),
    11: ("C",  5),
    12: ("C+", 6),
    13: ("B",  7),
    14: ("B+", 8),
    15: ("A",  9),
    16: ("A+", 10),
    17: ("S",  11),
    18: ("S+", 12),
}

# Minimum score to capture (10 = A+, 11 = S, 12 = S+) -> Star count >= 16
MIN_TARGET_SCORE = 10
MIN_TARGET_STARS = 16

def get_tier_info(server_rating: int):
    """
    Converts server rating (total stars 6-18) to exact Tier name and Score (0-12).
    S+ (Score 12 / 18 stars) is the absolute highest tier!
    """
    if server_rating in STAR_TO_TIER:
        return STAR_TO_TIER[server_rating]
    if server_rating <= 6:
        return ("F-", 0)
    if server_rating >= 18:
        return ("S+", 12)
    # Fallback formula: score = rating - 6
    score = max(0, min(12, server_rating - 6))
    tier_names = ["F-", "F", "F+", "D", "D+", "C", "C+", "B", "B+", "A", "A+", "S", "S+"]
    return (tier_names[score], score)


# Target HP percentage to weaken enemy down to before throwing capture crate (5% - 20%)
TARGET_CAPTURE_HP_PCT = 15.0

# Minimum safe HP percentage (never attack if below this to avoid killing the target)
MIN_SAFE_HP_PCT = 10.0

# Keep or release caught miscrits (True = Keep, False = Release)
AUTO_KEEP_CAUGHT = True

# ================= HUNTING TIMINGS & DELAYS =================
# Delay between attacks on different objects in rotation (seconds)
STEP_DELAY = 1.0

# Delay between battle turns / animations (seconds)
TURN_DELAY = 0.5

# Delay after sending flee before sending match_leave
FLEE_DELAY = 0.2

# Delay after match_leave before next action
LEAVE_DELAY = 0.8

# Per-object search cooldown on same object (seconds)
OBJECT_COOLDOWN = 15.0

# Token refresh safety buffer (seconds before expiry to auto-refresh)
TOKEN_REFRESH_BUFFER = 300  # 5 minutes

# ================= NOTIFICATIONS =================
# Optional webhook for Discord/Telegram notifications on Bingo
WEBHOOK_URL = ""
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
