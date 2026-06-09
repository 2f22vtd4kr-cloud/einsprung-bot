"""Central configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
BOTTOKEN = os.getenv("BOTTOKEN", "")
TELEGRAMCHANNELID = int(os.getenv("TELEGRAMCHANNELID", "0"))  # e.g. -100123456789
ADMINTGID = int(os.getenv("ADMINTGID", "0"))
BOTUSERNAME = os.getenv("BOTUSERNAME", "einsprungbot")

# --- CryptoBot ---
CRYPTOBOTTOKEN = os.getenv("CRYPTOBOTTOKEN", "")
CRYPTOBOTAPI = "https://pay.crypt.bot/api"

# --- Economics ---
PLATFORMFEEPCT = 0.10
STARTOUSDTRATE = float(os.getenv("STARTOUSDTRATE", "0.02"))
MINTASKREWARD = 1.0
MAXTASKREWARD = 10000.0
MINWITHDRAWAL = 1.0

# --- Files ---
MAXATTACHMENTTOTALMB = 50
BLOCKEDEXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".scr", ".msi", ".vbs", ".js",
    ".jar", ".ps1", ".sh", ".apk", ".dll", ".dmg", ".pkg",
}

# --- Mini-App ---
MINIAPPURL = os.getenv("MINIAPPURL", "https://example.com/miniapp.html")

# --- Behavior ---
DISPUTERATIOTHRESHOLD = 0.30
RATELIMITFINANCIALSEC = 3
DBPATH = os.getenv("DBPATH", "einsprung.db")

# --- Categories ---
CATEGORIES = [
    "Programmierung",
    "Mathematik/Matlab",
    "Präsentationen",
    "Hausarbeiten",
    "Notizen/Zusammenfassungen",
    "Sonstiges",
]
