import os
import re
import json
import uuid
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone

from aiohttp import web
import discord
from discord.ext import commands
from discord import app_commands

# =========================================================
# ENV VARIABLES
# =========================================================
TOKEN = os.getenv("TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

if not TOKEN or not GUILD_ID_RAW: 
    raise ValueError("TOKEN oder GUILD_ID fehlt in den Railway Variablen.")

try: 
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError: 
    raise ValueError("GUILD_ID muss eine gültige Zahl sein.")

# =========================================================
# CONFIGURATION & LINKS
# =========================================================
BUY_CATEGORY_ID = 1490336321913356459
SUPPORT_CATEGORY_ID = 1490336154044727407

STAFF_ROLE_ID = 1490327988800065597
REVIEW_CHANNEL_ID = 1490334608695361707
PAYSAFE_CODES_CHANNEL_ID = 1490335565256851466
AMAZON_CODES_CHANNEL_ID = 1490335639357362298
INVOICE_CHANNEL_ID = 1490336085568524550
ADMIN_PANEL_CHANNEL_ID = 1490335327619911873

WELCOME_CHANNEL_ID = 1490374553183060090
RULES_CHANNEL_ID = 1490376004391272498
VOUCH_CHANNEL_ID = 1490372381791748176
ANNOUNCEMENT_CHANNEL_ID = 1490329714022289562 
WEB_KEY_CHANNEL_ID = 1490476535843393679

REDEEM_ROLE_ID = 1490321899266506913
RESELLER_ROLE_ID = 1490335130890534923

SERVER_NAME = "Vale Generator"

# Bilder-Links
WEBSITE_LOGO_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png?ex=69d3cfcd&is=69d27e4d&hm=a1683879f331ba73307cf9ad0e27cac43f02b2de553abd4e8f9e86dcadec0a48&=&format=webp&quality=lossless&width=548&height=548" 
WELCOME_THUMBNAIL_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png"
WELCOME_BANNER_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371157432467577/analyst.jpg"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1477646233563566080/1487826817925513306/ChatGPT_Image_29._Marz_2026_16_52_23.png"

# Zahlungsdaten
PAYPAL_EMAIL = "hydrasupfivem@gmail.com"
LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"
ETHEREUM_ADDRESS = "0x6Ba2afdA7e61817f9c27f98ffAfe9051F9ad8167"
SOLANA_ADDRESS = "DnzXgySsPnSdEKsMJub21dBjM6bcT2jtic73VeutN3p4"

LTC_MIN_CONFIRMATIONS = 1
EXPIRY_REMINDER_HOURS = 12

# Farben für Discord Embeds
COLOR_MAIN = 0x9333EA
COLOR_SUPPORT = 0x3BA7FF
COLOR_BUY = 0x57F287
COLOR_WARN = 0xFEE75C
COLOR_DENY = 0xED4245
COLOR_LOG = 0x2B2D31
COLOR_SUCCESS = 0x57F287
COLOR_INFO = 0x9333EA
COLOR_ADMIN = 0x9B59B6
COLOR_WELCOME = 0xDD0000

# =========================================================
# DATABASES & FILES
# =========================================================
KEYS_FILE = "keys.json"
REDEEMED_FILE = "redeemed.json"
USED_TXIDS_FILE = "used_txids.json"
USED_PAYSAFE_FILE = "used_paysafecodes.json"
USED_AMAZON_FILE = "used_amazoncodes.json"
BLACKLIST_FILE = "blacklist.json"
INVOICES_FILE = "invoices.json"
PROMOS_FILE = "promos.json"
ACTIVITY_FILE = "activity.json"
WEBKEYS_FILE = "web_keys.json"
USERS_FILE = "web_users.json"
TICKETS_FILE = "tickets.json"

PRODUCTS = {
    "day_1": {"label": "1 Day", "price_eur": 5, "duration": timedelta(days=1), "key_prefix": "GEN-1D"},
    "week_1": {"label": "1 Week", "price_eur": 15, "duration": timedelta(weeks=1), "key_prefix": "GEN-1W"},
    "lifetime": {"label": "Lifetime", "price_eur": 30, "duration": None, "key_prefix": "GEN-LT"}
}

PAYMENTS = {
    "paypal": {"label": "PayPal", "emoji": "💸"},
    "litecoin": {"label": "Litecoin", "emoji": "🪙"},
    "ethereum": {"label": "Ethereum", "emoji": "🔷"},
    "solana": {"label": "Solana", "emoji": "🟣"},
    "paysafecard": {"label": "Paysafecard", "emoji": "💳"},
    "amazoncard": {"label": "Amazon Card", "emoji": "🎁"}
}

# Bot Setup
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Datenstrukturen im Speicher
ticket_data = {}
keys_db = {}
redeemed_db = {}
used_txids_db = {}
used_paysafe_db = {}
used_amazon_db = {}
blacklist_db = {}
invoices_db = {}
promos_db = {}
activity_db = []
webkeys_db = {}
users_db = {}
web_sessions = {}

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f)
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def log_activity(action, user="System"):
    global activity_db
    activity_db.insert(0, {
        "time": iso_now(), 
        "user": str(user), 
        "action": action
    })
    activity_db = activity_db[:50]
    save_json(ACTIVITY_FILE, activity_db)

def now_utc(): 
    return datetime.now(timezone.utc)

def iso_now(): 
    return now_utc().isoformat()

def random_block(length=4): 
    return uuid.uuid4().hex[:length].upper()

def build_invoice_id() -> str:
    """FIX: Diese Funktion hat gefehlt und den Crash beim Approve verursacht!"""
    return f"GEN-{uuid.uuid4().hex[:10].upper()}"

def is_blacklisted(user_id: int): 
    return str(user_id) in blacklist_db

# =========================================================
# 🌍 WEB DASHBOARD HTML
# =========================================================
WEB_HTML = """
<!DOCTYPE html>
<html lang="de" class="dark">
<head>
    <meta charset="UTF-8">
    <title>Vale Gen | System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
        body { 
            font-family: 'Inter', sans-serif; 
            background-color: #050505; 
            color: #e5e7eb; 
        }
        .glass { 
            background: rgba(20, 10, 30, 0.7); 
            backdrop-filter: blur(15px); 
            border: 1px solid rgba(168, 85, 247, 0.2); 
        }
        .glow-text { text-shadow: 0 0 20px rgba(168, 85, 247, 0.8); }
        .glow-box { box-shadow: 0 0 30px rgba(147, 51, 234, 0.3); }
        .hidden-view { display: none !important; }
        .tab-content { display: none; } 
        .tab-content.active { display: block; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { 
            from { opacity: 0; transform: translateY(10px); } 
            to { opacity: 1; transform: translateY(0); } 
        }
        ::-webkit-scrollbar { width: 6px; } 
        ::-webkit-scrollbar-track { background: #050505; } 
        ::-webkit-scrollbar-thumb { background: #9333ea; border-radius: 4px; }
    </style>
</head>
<body class="flex h-screen overflow-hidden selection:bg-purple-500 selection:text-white">

    <div id="view-auth" class="flex w-full h-full items-center justify-center relative">
        <div class="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-5"></div>
        <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-purple-600/20 rounded-full blur-[100px]"></div>
        
        <div class="glass p-10 rounded-3xl max-w-md w-full relative z-10 glow-box">
            <div class="text-center mb-8">
                <img src="LOGO_URL_PLACEHOLDER" alt="Logo" class="h-32 mx-auto mb-4 drop-shadow-[0_0_20px_rgba(168,85,247,0.8)] object-contain">
                <h1 class="text-3xl font-black text-white tracking-widest glow-text mt-4">VALE GEN</h1>
            </div>

            <div class="flex border-b border-purple-500/30 mb-6">
                <button onclick="switchAuth('login')" id="auth-tab-login" class="flex-1 pb-3 text-purple-400 font-bold border-b-2 border-purple-500 transition">LOGIN</button>
                <button onclick="switchAuth('register')" id="auth-tab-register" class="flex-1 pb-3 text-gray-500 font-bold hover:text-gray-300 transition border-b-2 border-transparent">REGISTER</button>
            </div>

            <div id="form-login" class="space-y-4">
                <input type="text" id="l-user" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white focus:border-purple-500 outline-none transition" placeholder="Username">
                <input type="password" id="l-pass" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white focus:border-purple-500 outline-none transition" placeholder="Password">
                <button onclick="login()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-3 rounded-xl transition shadow-[0_0_15px_rgba(147,51,234,0.5)]">LOGIN</button>
            </div>

            <div id="form-register" class="space-y-4 hidden-view">
                <input type="text" id="r-user" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white focus:border-purple-500 outline-none transition" placeholder="Choose Username">
                <input type="password" id="r-pass" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white focus:border-purple-500 outline-none transition" placeholder="Choose Password">
                <input type="text" id="r-key" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-purple-400 font-mono focus:border-purple-500 outline-none transition" placeholder="Invitation Key (VALE-...)">
                <button onclick="register()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-3 rounded-xl transition shadow-[0_0_15px_rgba(147,51,234,0.5)]">CREATE ACCOUNT</button>
            </div>
            
            <p id="auth-error" class="text-red-400 mt-4 text-sm text-center font-bold hidden"></p>
        </div>
    </div>

    <div id="view-admin" class="flex w-full h-full hidden-view">
        <aside class="w-64 glass border-r border-purple-500/20 flex flex-col justify-between z-10">
            <div>
                <div class="h-32 flex items-center justify-center border-b border-purple-500/20 px-4">
                    <img src="LOGO_URL_PLACEHOLDER" class="h-16 mr-3 drop-shadow-[0_0_10px_rgba(168,85,247,0.8)] object-contain">
                    <span class="text-xl font-black text-white glow-text">ADMIN</span>
                </div>
                <nav class="p-4 space-y-2 mt-2">
                    <button onclick="nav('dash')" id="btn-dash" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-purple-300 bg-purple-600/20 font-bold border border-purple-500/30 transition">
                        <i class="fa-solid fa-chart-pie w-6"></i> Dashboard
                    </button>
                    <button onclick="nav('keys')" id="btn-keys" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-key w-6"></i> Key Manager
                    </button>
                    <button onclick="nav('promos')" id="btn-promos" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-tags w-6"></i> Promos
                    </button>
                    <button onclick="nav('lookup')" id="btn-lookup" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-search w-6"></i> Database
                    </button>
                    <button onclick="nav('announce')" id="btn-announce" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-satellite-dish w-6"></i> Broadcast
                    </button>
                    <button onclick="nav('blacklist')" id="btn-blacklist" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-skull w-6"></i> Blacklist
                    </button>
                </nav>
            </div>
            <div class="p-6 border-t border-purple-500/20 text-center">
                <button onclick="logout()" class="text-red-400 hover:text-red-300 font-bold transition">
                    <i class="fa-solid fa-power-off mr-1"></i> LOGOUT
                </button>
            </div>
        </aside>

        <main class="flex-1 overflow-y-auto p-8 relative">
            <div class="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-purple-900/20 to-transparent pointer-events-none z-0"></div>
            
            <div class="z-10 relative max-w-7xl mx-auto">
                <header class="flex justify-between items-center mb-8">
                    <h2 id="page-title" class="text-3xl font-black text-white tracking-wide uppercase">Dashboard</h2>
                    <div class="flex items-center gap-3">
                        <span class="text-sm text-gray-400">Logged in as <span id="admin-name" class="text-purple-400 font-bold">Admin</span></span>
                        <span class="bg-purple-500/20 text-purple-400 border border-purple-500/50 text-xs font-bold px-3 py-1 rounded-full flex items-center shadow-[0_0_10px_rgba(168,85,247,0.3)]">
                            <span class="w-2 h-2 rounded-full bg-purple-400 animate-pulse mr-2"></span> LIVE
                        </span>
                    </div>
                </header>

                <div id="dash" class="tab-content active">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                        <div class="glass p-6 rounded-2xl border-l-4 border-purple-500">
                            <p class="text-sm font-bold text-gray-400 uppercase">Total Revenue</p>
                            <h3 class="text-4xl font-black text-white mt-1 glow-text" id="stat-rev">0.00€</h3>
                        </div>
                        <div class="glass p-6 rounded-2xl border-l-4 border-pink-500">
                            <p class="text-sm font-bold text-gray-400 uppercase">Orders Today</p>
                            <h3 class="text-4xl font-black text-white mt-1" id="stat-orders">0</h3>
                        </div>
                        <div class="glass p-6 rounded-2xl border-l-4 border-blue-500">
                            <p class="text-sm font-bold text-gray-400 uppercase">Active Keys</p>
                            <h3 class="text-4xl font-black text-white mt-1" id="stat-keys">0</h3>
                        </div>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                        <div class="lg:col-span-2 glass p-6 rounded-2xl">
                            <h3 class="text-lg font-bold text-white mb-4"><i class="fa-solid fa-chart-line mr-2 text-purple-400"></i>Revenue Chart</h3>
                            <canvas id="revenueChart" height="100"></canvas>
                        </div>
                        <div class="lg:col-span-1 glass p-6 rounded-2xl flex flex-col">
                            <h3 class="text-lg font-bold text-white mb-4"><i class="fa-solid fa-clock-rotate-left mr-2 text-pink-400"></i>Activity Log</h3>
                            <div id="activity-feed" class="flex-1 overflow-y-auto space-y-3 pr-2"></div>
                        </div>
                    </div>
                </div>

                <div id="keys" class="tab-content">
                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="p-6 border-b border-purple-500/20">
                            <h3 class="text-lg font-bold text-white"><i class="fa-solid fa-key mr-2 text-purple-400"></i>Generated Keys</h3>
                        </div>
                        <div class="overflow-x-auto max-h-[600px]">
                            <table class="w-full text-left text-sm whitespace-nowrap">
                                <thead class="bg-black/40 border-b border-purple-500/20 sticky top-0">
                                    <tr>
                                        <th class="px-6 py-4 text-purple-300">Key</th>
                                        <th class="px-6 py-4 text-purple-300">Type</th>
                                        <th class="px-6 py-4 text-purple-300">Creator</th>
                                        <th class="px-6 py-4 text-purple-300">Used By (ID)</th>
                                        <th class="px-6 py-4 text-purple-300">Status</th>
                                        <th class="px-6 py-4 text-right text-purple-300">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="table-keys" class="divide-y divide-purple-500/10"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="promos" class="tab-content">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="md:col-span-1 glass p-6 rounded-2xl border-t-2 border-pink-500">
                            <h3 class="text-lg font-bold text-white mb-4">New Promo</h3>
                            <input type="text" id="p-code" placeholder="Code (e.g. SUMMER50)" class="w-full bg-black/50 border border-purple-500/30 rounded-lg px-4 py-2 mb-3 text-white uppercase outline-none focus:border-pink-500">
                            <input type="number" id="p-disc" placeholder="Discount %" class="w-full bg-black/50 border border-purple-500/30 rounded-lg px-4 py-2 mb-3 text-white outline-none focus:border-pink-500">
                            <input type="number" id="p-uses" placeholder="Max Uses" class="w-full bg-black/50 border border-purple-500/30 rounded-lg px-4 py-2 mb-4 text-white outline-none focus:border-pink-500">
                            <button onclick="createPromo()" class="w-full bg-pink-600 hover:bg-pink-500 text-white font-bold py-2 rounded-lg transition shadow-lg">Create Code</button>
                        </div>
                        <div class="md:col-span-2 glass rounded-2xl overflow-hidden">
                            <div class="p-6 border-b border-purple-500/20">
                                <h3 class="text-lg font-bold text-white">Active Promos</h3>
                            </div>
                            <table class="w-full text-left text-sm">
                                <thead class="text-purple-300 border-b border-purple-500/20 bg-black/40">
                                    <tr>
                                        <th class="p-4">Code</th>
                                        <th class="p-4">Discount</th>
                                        <th class="p-4">Uses Left</th>
                                        <th class="p-4 text-right">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="table-promos" class="divide-y divide-purple-500/10"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="lookup" class="tab-content">
                    <div class="glass p-6 rounded-2xl mb-6 flex gap-4">
                        <input type="text" id="lookup-id" placeholder="Discord User ID..." class="flex-1 bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white focus:border-purple-500 outline-none transition">
                        <button onclick="lookupUser()" class="bg-purple-600 hover:bg-purple-500 text-white px-8 font-bold rounded-xl transition">
                            <i class="fa-solid fa-search mr-2"></i>Search
                        </button>
                    </div>
                    <div id="lookup-result" class="hidden">
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                            <div class="glass p-6 rounded-2xl border-l-4 border-purple-500">
                                <p class="text-gray-400 text-sm font-bold">Total Spent</p>
                                <h3 id="lu-spent" class="text-3xl font-black text-white glow-text">0.00€</h3>
                            </div>
                            <div class="glass p-6 rounded-2xl border-l-4 border-blue-500">
                                <p class="text-gray-400 text-sm font-bold">Total Orders</p>
                                <h3 id="lu-orders" class="text-3xl font-black text-white">0</h3>
                            </div>
                            <div class="glass p-6 rounded-2xl border-l-4 border-red-500">
                                <p class="text-gray-400 text-sm font-bold">Blacklist Status</p>
                                <h3 id="lu-banned" class="text-xl font-bold mt-2">Clean</h3>
                            </div>
                        </div>
                        <div class="glass rounded-2xl overflow-hidden">
                            <div class="p-4 border-b border-purple-500/20 font-bold bg-black/40">Purchase History</div>
                            <table class="w-full text-left text-sm">
                                <thead class="text-purple-300 border-b border-purple-500/20">
                                    <tr>
                                        <th class="p-4">Invoice</th>
                                        <th class="p-4">Product</th>
                                        <th class="p-4">Price</th>
                                        <th class="p-4">Date</th>
                                    </tr>
                                </thead>
                                <tbody id="lu-table" class="divide-y divide-purple-500/10"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="announce" class="tab-content">
                    <div class="glass p-6 rounded-2xl border-t-2 border-blue-500 max-w-3xl">
                        <h3 class="text-xl font-bold text-white mb-4"><i class="fa-solid fa-satellite-dish mr-2 text-blue-400"></i>Server Broadcast</h3>
                        <input type="text" id="ann-title" placeholder="Title (e.g. 🚀 MEGA UPDATE)" class="w-full bg-black/50 border border-purple-500/30 rounded-lg px-4 py-3 mb-4 text-white font-bold outline-none focus:border-blue-500 transition">
                        <textarea id="ann-desc" placeholder="Message content..." rows="6" class="w-full bg-black/50 border border-purple-500/30 rounded-lg px-4 py-3 mb-4 text-white resize-none outline-none focus:border-blue-500 transition"></textarea>
                        <input type="text" id="ann-img" placeholder="Image URL (Optional)" class="w-full bg-black/50 border border-purple-500/30 rounded-lg px-4 py-2 mb-6 text-white text-sm outline-none focus:border-blue-500 transition">
                        <button onclick="sendAnnounce()" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition shadow-[0_0_20px_rgba(37,99,235,0.4)]">
                            <i class="fa-solid fa-paper-plane mr-2"></i>Send to Discord
                        </button>
                    </div>
                </div>

                <div id="blacklist" class="tab-content">
                    <div class="glass p-6 rounded-2xl mb-6 border-l-4 border-red-500 flex gap-4 items-center">
                        <input type="text" id="bl-id" placeholder="Discord User ID..." class="flex-1 bg-black/50 border border-purple-500/30 rounded-lg px-4 py-2 text-white outline-none focus:border-red-500 transition">
                        <input type="text" id="bl-reason" placeholder="Reason..." class="flex-1 bg-black/50 border border-purple-500/30 rounded-lg px-4 py-2 text-white outline-none focus:border-red-500 transition">
                        <button onclick="addBlacklist()" class="bg-red-600 hover:bg-red-500 text-white px-6 py-2 font-bold rounded-lg transition shadow-[0_0_15px_rgba(220,38,38,0.5)]">Ban</button>
                    </div>
                    <div class="glass rounded-2xl overflow-hidden">
                        <table class="w-full text-left text-sm">
                            <thead class="text-red-300 border-b border-red-500/20 bg-black/40">
                                <tr>
                                    <th class="p-4">User ID</th>
                                    <th class="p-4">Reason</th>
                                    <th class="p-4 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody id="table-blacklist" class="divide-y divide-purple-500/10"></tbody>
                        </table>
                    </div>
                </div>
                
            </div>
        </main>
    </div>

    <div id="view-reseller" class="flex w-full h-full hidden-view p-8">
        <div class="max-w-4xl mx-auto w-full">
            <header class="flex justify-between items-center mb-8 glass p-6 rounded-2xl glow-box">
                <div class="flex items-center">
                    <img src="LOGO_URL_PLACEHOLDER" class="h-16 mr-4 drop-shadow-[0_0_10px_rgba(168,85,247,0.8)] object-contain">
                    <div>
                        <h1 class="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500">Reseller Portal</h1>
                        <p class="text-sm text-purple-300 font-bold" id="r-name">Loading...</p>
                    </div>
                </div>
                <button onclick="logout()" class="bg-red-500/10 hover:bg-red-600 border border-red-500/30 hover:border-red-500 text-red-400 hover:text-white px-4 py-2 rounded-lg transition font-bold">
                    <i class="fa-solid fa-power-off mr-2"></i>Logout
                </button>
            </header>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div class="glass p-6 rounded-2xl border-t-2 border-purple-500">
                    <h2 class="text-xl font-bold mb-6 text-white"><i class="fa-solid fa-bolt mr-2 text-purple-400"></i>Generate Access</h2>
                    <div class="space-y-4">
                        <button onclick="genKey('day_1')" class="w-full bg-black/40 hover:bg-purple-600/20 border border-purple-500/30 p-4 rounded-xl flex justify-between items-center transition text-white">
                            <span class="font-bold">1 Day Key</span><i class="fa-solid fa-plus text-purple-400"></i>
                        </button>
                        <button onclick="genKey('week_1')" class="w-full bg-black/40 hover:bg-purple-600/20 border border-purple-500/30 p-4 rounded-xl flex justify-between items-center transition text-white">
                            <span class="font-bold">1 Week Key</span><i class="fa-solid fa-plus text-purple-400"></i>
                        </button>
                        <button onclick="genKey('lifetime')" class="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 p-4 rounded-xl flex justify-between items-center text-white transition shadow-[0_0_15px_rgba(168,85,247,0.4)]">
                            <span class="font-bold">Lifetime Key</span><i class="fa-solid fa-star"></i>
                        </button>
                    </div>
                </div>
                <div class="glass p-6 rounded-2xl">
                    <h2 class="text-xl font-bold mb-4 text-white">Your Stock</h2>
                    <div class="overflow-y-auto h-64 pr-2 space-y-2" id="my-keys"></div>
                </div>
            </div>
        </div>
    </div>

    <div id="key-modal" class="fixed inset-0 bg-black/90 flex items-center justify-center hidden-view z-50">
        <div class="glass p-8 rounded-2xl text-center border border-purple-500 shadow-[0_0_50px_rgba(168,85,247,0.5)]">
            <h3 class="text-2xl font-black text-white mb-2 glow-text">ACCESS GRANTED</h3>
            <p class="text-gray-400 mb-4">Key successfully generated.</p>
            <input type="text" id="new-key" class="w-full bg-black/80 border border-purple-500 p-4 rounded-xl text-purple-400 font-mono text-center mb-6 text-xl tracking-wider glow-box" readonly>
            <button onclick="closeModal()" class="bg-purple-600 hover:bg-purple-500 text-white font-bold px-8 py-3 rounded-xl transition shadow-[0_0_15px_rgba(147,51,234,0.5)]">Close</button>
        </div>
    </div>

    <script>
        let myChart = null;

        function switchAuth(type) {
            document.getElementById('form-login').classList.add('hidden-view'); 
            document.getElementById('form-register').classList.add('hidden-view');
            document.getElementById('auth-tab-login').className = "flex-1 pb-3 text-gray-500 font-bold hover:text-gray-300 transition border-b-2 border-transparent";
            document.getElementById('auth-tab-register').className = "flex-1 pb-3 text-gray-500 font-bold hover:text-gray-300 transition border-b-2 border-transparent";
            
            document.getElementById('form-' + type).classList.remove('hidden-view');
            document.getElementById('auth-tab-' + type).className = "flex-1 pb-3 text-purple-400 font-bold border-b-2 border-purple-500 transition";
            document.getElementById('auth-error').classList.add('hidden');
        }

        async function apiCall(endpoint, data) {
            const token = localStorage.getItem('v_token');
            const headers = {'Content-Type': 'application/json'};
            if (token) headers['Authorization'] = token;
            
            const res = await fetch(endpoint, {
                method: 'POST', 
                headers: headers, 
                body: JSON.stringify(data)
            });
            
            if (res.status === 401 && endpoint !== '/api/login' && endpoint !== '/api/register') { 
                logout(); 
                throw new Error('Unauthorized'); 
            }
            return res;
        }

        function showError(msg) { 
            const e = document.getElementById('auth-error'); 
            e.innerText = msg; 
            e.classList.remove('hidden'); 
        }

        async function login() {
            const u = document.getElementById('l-user').value;
            const p = document.getElementById('l-pass').value;
            if (!u || !p) return showError("Please fill all fields");
            
            const res = await apiCall('/api/login', {user: u, pass: p});
            if (res.ok) { 
                const d = await res.json(); 
                localStorage.setItem('v_token', d.token); 
                initApp(d.role, d.user); 
            } else {
                showError("Invalid username or password");
            }
        }

        async function register() {
            const u = document.getElementById('r-user').value;
            const p = document.getElementById('r-pass').value;
            const k = document.getElementById('r-key').value;
            
            if (!u || !p || !k) return showError("Please fill all fields");
            
            const res = await apiCall('/api/register', {user: u, pass: p, key: k});
            if (res.ok) { 
                const d = await res.json(); 
                localStorage.setItem('v_token', d.token); 
                initApp(d.role, d.user); 
            } else { 
                const e = await res.json(); 
                showError(e.error || "Registration failed"); 
            }
        }

        function logout() { 
            localStorage.removeItem('v_token'); 
            location.reload(); 
        }

        async function checkAuthOnLoad() {
            const t = localStorage.getItem('v_token');
            if (t) {
                const res = await fetch('/api/verify', {
                    method: 'POST', 
                    headers: {'Authorization': t, 'Content-Type': 'application/json'}, 
                    body: JSON.stringify({})
                });
                if (res.ok) { 
                    const d = await res.json(); 
                    initApp(d.role, d.user); 
                } else {
                    logout();
                }
            }
        }

        function initApp(role, name) {
            document.getElementById('view-auth').classList.add('hidden-view');
            if (role === 'admin') { 
                document.getElementById('view-admin').classList.remove('hidden-view'); 
                document.getElementById('admin-name').innerText = name; 
                nav('dash'); 
            } else if (role === 'reseller') { 
                document.getElementById('view-reseller').classList.remove('hidden-view'); 
                document.getElementById('r-name').innerText = name; 
                loadResellerKeys(); 
            }
        }

        function nav(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            
            document.querySelectorAll('.nav-btn').forEach(el => { 
                el.className = "nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition"; 
            });
            document.getElementById('btn-' + tabId).className = "nav-btn w-full text-left py-3 px-4 rounded-xl text-purple-300 bg-purple-600/20 font-bold border border-purple-500/30 shadow-inner";
            
            const titles = {
                'dash': 'Overview', 
                'keys': 'Keys & Logs', 
                'promos': 'Promo Codes', 
                'lookup': 'User Lookup', 
                'announce': 'Broadcast', 
                'blacklist': 'Blacklist'
            };
            document.getElementById('page-title').innerText = titles[tabId];
            
            if (tabId === 'dash') { loadDashboard(); loadActivity(); }
            if (tabId === 'keys') loadKeys();
            if (tabId === 'promos') loadPromos();
            if (tabId === 'blacklist') loadBlacklist();
        }

        async function loadDashboard() {
            const res = await apiCall('/api/stats', {}); 
            const data = await res.json();
            
            document.getElementById('stat-rev').innerText = data.total_revenue.toFixed(2) + '€'; 
            document.getElementById('stat-orders').innerText = data.buyers_today; 
            document.getElementById('stat-keys').innerText = data.active_keys;
            
            const ctx = document.getElementById('revenueChart').getContext('2d');
            if (myChart) myChart.destroy();
            
            myChart = new Chart(ctx, {
                type: 'line', 
                data: { 
                    labels: data.chart_labels, 
                    datasets: [{ 
                        label: 'Revenue (€)', 
                        data: data.chart_data, 
                        borderColor: '#a855f7', 
                        backgroundColor: 'rgba(168, 85, 247, 0.1)', 
                        borderWidth: 3, 
                        fill: true, 
                        tension: 0.4 
                    }] 
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    plugins: { legend: {display: false} }, 
                    scales: { 
                        y: {beginAtZero: true, grid: {color: 'rgba(168,85,247,0.1)'}}, 
                        x: {grid: {color: 'rgba(168,85,247,0.1)'}} 
                    } 
                }
            });
        }

        async function loadActivity() {
            const res = await apiCall('/api/activity', {}); 
            const data = await res.json();
            document.getElementById('activity-feed').innerHTML = data.map(a => `
                <div class="p-3 bg-black/40 rounded-lg border border-purple-500/10 flex justify-between items-center">
                    <div>
                        <span class="font-bold text-purple-400 text-xs mr-2">${a.user}</span>
                        <span class="text-sm text-gray-300">${a.action}</span>
                    </div>
                    <span class="text-xs text-gray-600">${a.time.split('T')[1].substring(0,5)}</span>
                </div>
            `).join('');
        }

        async function loadKeys() {
            const res = await apiCall('/api/keys', {}); 
            const data = await res.json(); 
            const tb = document.getElementById('table-keys');
            
            if (Object.keys(data).length === 0) {
                return tb.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500">No keys generated</td></tr>';
            }
            
            tb.innerHTML = Object.entries(data).reverse().map(([key, info]) => {
                let badge = info.used ? '<span class="px-2 py-1 rounded bg-red-500/10 text-red-400 text-xs border border-red-500/20">Used</span>' : '<span class="px-2 py-1 rounded bg-green-500/10 text-green-400 text-xs border border-green-500/20">Active</span>';
                if (info.revoked) {
                    badge = '<span class="px-2 py-1 rounded bg-gray-500/10 text-gray-400 text-xs border border-gray-500/20">Banned</span>';
                }
                
                const creator = info.created_by ? `<span class="text-blue-400 font-bold">${info.created_by}</span>` : 'System';
                const usedBy = info.used_by ? `<span class="text-pink-400 font-mono text-xs">${info.used_by}</span>` : '-';
                const act = !info.revoked ? `<button onclick="revokeKey('${key}')" class="text-xs bg-red-600/20 text-red-400 hover:bg-red-600 hover:text-white px-2 py-1 rounded transition shadow-lg">Ban Key</button>` : '-';
                
                return `
                    <tr class="hover:bg-purple-500/10 transition">
                        <td class="px-6 py-4 font-mono text-purple-300">${key}</td>
                        <td class="px-6 py-4 text-gray-300">${info.type}</td>
                        <td class="px-6 py-4">${creator}</td>
                        <td class="px-6 py-4">${usedBy}</td>
                        <td class="px-6 py-4">${badge}</td>
                        <td class="px-6 py-4 text-right">${act}</td>
                    </tr>
                `;
            }).join('');
        }

        async function revokeKey(k) { 
            if (confirm('Möchtest du diesen Key bannen und dem User die Rolle entfernen?')) { 
                await apiCall('/api/keys/revoke', {key: k}); 
                loadKeys(); 
            } 
        }

        async function loadPromos() {
            const res = await apiCall('/api/promos', {}); 
            const data = await res.json(); 
            const tb = document.getElementById('table-promos');
            
            if (Object.keys(data).length === 0) {
                return tb.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-gray-500">No active promos.</td></tr>';
            }
            
            tb.innerHTML = Object.entries(data).map(([code, info]) => `
                <tr class="hover:bg-purple-500/10 transition">
                    <td class="p-4 font-mono font-bold text-pink-400">${code}</td>
                    <td class="p-4 text-purple-300">-${info.discount}%</td>
                    <td class="p-4 text-gray-300">${info.uses}</td>
                    <td class="p-4 text-right">
                        <button onclick="rmPromo('${code}')" class="text-red-400 hover:text-red-300 transition">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        async function createPromo() {
            const c = document.getElementById('p-code').value.toUpperCase();
            const d = document.getElementById('p-disc').value;
            const u = document.getElementById('p-uses').value;
            
            if (!c || !d || !u) return alert("Please fill all fields"); 
            await apiCall('/api/promos/add', {code: c, discount: parseInt(d), uses: parseInt(u)});
            
            document.getElementById('p-code').value = ''; 
            document.getElementById('p-disc').value = ''; 
            document.getElementById('p-uses').value = ''; 
            loadPromos();
        }

        async function rmPromo(code) { 
            await apiCall('/api/promos/remove', {code: code}); 
            loadPromos(); 
        }
        
        async function lookupUser() {
            const uid = document.getElementById('lookup-id').value; 
            if (!uid) return;
            
            const res = await apiCall('/api/lookup', {user_id: uid}); 
            const data = await res.json();
            
            document.getElementById('lookup-result').classList.remove('hidden');
            document.getElementById('lu-spent').innerText = data.total_spent.toFixed(2) + '€'; 
            document.getElementById('lu-orders').innerText = data.total_orders;
            
            const b = document.getElementById('lu-banned');
            if (data.is_banned) { 
                b.innerText = "BANNED"; 
                b.className = "text-xl font-black text-red-500 mt-2 glow-text"; 
            } else { 
                b.innerText = "Clean"; 
                b.className = "text-xl font-bold text-green-400 mt-2"; 
            }
            
            const tb = document.getElementById('lu-table');
            if (data.invoices.length === 0) {
                tb.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-gray-500">No purchases found.</td></tr>';
            } else {
                tb.innerHTML = data.invoices.map(i => `
                    <tr class="hover:bg-white/5 transition">
                        <td class="p-4 font-mono text-xs text-gray-500">${i.id}</td>
                        <td class="p-4 text-purple-300">${i.product}</td>
                        <td class="p-4 font-bold text-green-400">${i.price}€</td>
                        <td class="p-4 text-xs text-gray-400">${i.date.split('T')[0]}</td>
                    </tr>
                `).join('');
            }
        }

        async function sendAnnounce() {
            const t = document.getElementById('ann-title').value;
            const d = document.getElementById('ann-desc').value;
            const i = document.getElementById('ann-img').value;
            
            if (!t || !d) return alert("Title and Description required!");
            
            await apiCall('/api/announce', {title: t, desc: d, img: i}); 
            alert("Broadcast sent successfully!");
            
            document.getElementById('ann-title').value = ''; 
            document.getElementById('ann-desc').value = ''; 
            document.getElementById('ann-img').value = '';
        }

        async function loadBlacklist() {
            const res = await apiCall('/api/blacklist', {}); 
            const data = await res.json(); 
            const tb = document.getElementById('table-blacklist');
            
            if (Object.keys(data).length === 0) {
                return tb.innerHTML = '<tr><td colspan="3" class="p-4 text-center text-gray-500">Blacklist is empty.</td></tr>';
            }
            
            tb.innerHTML = Object.entries(data).map(([uid, info]) => `
                <tr class="hover:bg-red-500/10 transition">
                    <td class="p-4 font-mono text-red-300">${uid}</td>
                    <td class="p-4 text-gray-400">${info.reason}</td>
                    <td class="p-4 text-right">
                        <button onclick="rmBlacklist('${uid}')" class="text-red-500 hover:text-red-400 transition">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        async function addBlacklist() {
            const uid = document.getElementById('bl-id').value;
            const rsn = document.getElementById('bl-reason').value || "Web Ban"; 
            
            if (!uid) return; 
            
            await apiCall('/api/blacklist/add', {user_id: uid, reason: rsn}); 
            document.getElementById('bl-id').value = ''; 
            document.getElementById('bl-reason').value = ''; 
            loadBlacklist();
        }

        async function rmBlacklist(uid) { 
            await apiCall('/api/blacklist/remove', {user_id: uid}); 
            loadBlacklist(); 
        }

        // RESELLER FUNCTIONS
        async function loadResellerKeys() {
            const res = await apiCall('/api/reseller/data', {}); 
            const data = await res.json();
            
            if (data.my_keys.length === 0) {
                document.getElementById('my-keys').innerHTML = '<p class="text-gray-500 p-4 text-center">Noch keine Keys generiert.</p>';
            } else {
                document.getElementById('my-keys').innerHTML = data.my_keys.reverse().map(k => `
                    <div class="bg-black/40 p-4 rounded-lg border border-purple-500/20 flex justify-between items-center transition hover:border-purple-500/50">
                        <span class="font-mono text-sm text-purple-300">${k.key}</span>
                        <span class="text-xs font-bold px-3 py-1 bg-purple-500/20 text-purple-300 rounded border border-purple-500/30">${k.type}</span>
                    </div>
                `).join('');
            }
        }

        async function genKey(type) {
            const res = await apiCall('/api/reseller/generate', {t: type}); 
            const d = await res.json();
            
            document.getElementById('new-key').value = d.key; 
            document.getElementById('key-modal').classList.remove('hidden-view'); 
            loadResellerKeys();
        }

        function closeModal() { 
            document.getElementById('key-modal').classList.add('hidden-view'); 
        }

        window.onload = checkAuthOnLoad;
    </script>
</body>
</html>
""".replace("LOGO_URL_PLACEHOLDER", WEBSITE_LOGO_URL)

# =========================================================
# 🌍 API ENDPOINTS (WEB SERVER)
# =========================================================
def get_user_from_token(request):
    token = request.headers.get("Authorization")
    if not token or token not in web_sessions: 
        return None
    return web_sessions[token]

async def handle_index(request): 
    return web.Response(text=WEB_HTML, content_type='text/html')

async def api_register(request):
    data = await request.json()
    username = data.get("user")
    password = data.get("pass")
    inv_key = data.get("key", "").upper()
    
    if not username or not password or not inv_key: 
        return web.json_response({"error": "Missing fields"}, status=400)
    if username in users_db: 
        return web.json_response({"error": "Username already exists"}, status=400)
    if inv_key not in webkeys_db or webkeys_db[inv_key].get("used"): 
        return web.json_response({"error": "Invalid or used invitation key"}, status=400)
    
    role = webkeys_db[inv_key]["role"]
    users_db[username] = {"pass": password, "role": role}
    webkeys_db[inv_key]["used"] = True
    
    save_json(USERS_FILE, users_db)
    save_json(WEBKEYS_FILE, webkeys_db)
    log_activity(f"New User Registered ({role})", username)
    
    token = str(uuid.uuid4())
    web_sessions[token] = {"user": username, "role": role}
    return web.json_response({"ok": True, "token": token, "role": role, "user": username})

async def api_login(request):
    data = await request.json()
    username = data.get("user")
    password = data.get("pass")
    
    if username in users_db and users_db[username]["pass"] == password:
        token = str(uuid.uuid4())
        role = users_db[username]["role"]
        web_sessions[token] = {"user": username, "role": role}
        return web.json_response({"ok": True, "token": token, "role": role, "user": username})
        
    return web.Response(status=401)

async def api_verify(request):
    user = get_user_from_token(request)
    if user: 
        return web.json_response({"ok": True, "role": user["role"], "user": user["user"]})
    return web.Response(status=401)

async def api_stats(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    now = now_utc()
    today_buyers = set()
    total_rev = 0.0
    days = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
    labels = [d.strftime("%a") for d in days]
    rev_data = {d: 0.0 for d in days}
    
    for inv_id, data in invoices_db.items():
        price = float(data.get("final_price_eur", 0))
        total_rev += price
        try:
            d = datetime.fromisoformat(data["created_at"]).date()
            if d == now.date(): 
                today_buyers.add(data["buyer_id"])
            if d in rev_data: 
                rev_data[d] += price
        except Exception: 
            pass
            
    active_k = sum(1 for k, v in keys_db.items() if not v.get("used"))
    
    return web.json_response({
        "total_revenue": total_rev, 
        "buyers_today": len(today_buyers), 
        "active_keys": active_k, 
        "chart_labels": labels, 
        "chart_data": list(rev_data.values())
    })

async def api_activity(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
    return web.json_response(activity_db)

async def api_keys(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
    return web.json_response(keys_db)

async def api_revoke_key(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    data = await request.json()
    key = data.get("key")
    
    if key in keys_db:
        if keys_db[key].get("used") and keys_db[key].get("used_by"):
            uid = str(keys_db[key]["used_by"])
            guild = bot.get_guild(GUILD_ID)
            if guild:
                member = guild.get_member(int(uid))
                role = guild.get_role(REDEEM_ROLE_ID)
                if member and role:
                    try: 
                        await member.remove_roles(role, reason="Key banned by Admin")
                    except Exception: 
                        pass
                        
            if uid in redeemed_db: 
                del redeemed_db[uid]
                save_json(REDEEMED_FILE, redeemed_db)
                
        keys_db[key]["revoked"] = True
        keys_db[key]["used"] = True
        save_json(KEYS_FILE, keys_db)
        log_activity(f"Banned Key {key}", user_info["user"])
        
    return web.json_response({"ok": True})

async def api_promos(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
    return web.json_response(promos_db)

async def api_add_promo(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    data = await request.json()
    promos_db[data["code"]] = {
        "discount": data["discount"], 
        "uses": data["uses"]
    }
    save_json(PROMOS_FILE, promos_db)
    log_activity(f"Created Promo {data['code']}", user_info["user"])
    return web.json_response({"ok": True})

async def api_rm_promo(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    data = await request.json()
    code = data["code"]
    if code in promos_db: 
        del promos_db[code]
        save_json(PROMOS_FILE, promos_db)
        
    return web.json_response({"ok": True})

async def api_lookup(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    target = (await request.json()).get("user_id")
    spent = 0.0
    invs = []
    
    for inv_id, data in invoices_db.items():
        if data["buyer_id"] == target:
            spent += float(data.get("final_price_eur", 0))
            invs.append({
                "id": inv_id, 
                "product": PRODUCTS.get(data["product_type"], {}).get("label", "Unknown"), 
                "price": data.get("final_price_eur", 0), 
                "date": data["created_at"]
            })
            
    return web.json_response({
        "total_spent": spent, 
        "total_orders": len(invs), 
        "is_banned": target in blacklist_db, 
        "invoices": invs[::-1]
    })

async def api_announce(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    data = await request.json()
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    
    if channel:
        embed = discord.Embed(title=data["title"], description=data["desc"], color=COLOR_MAIN)
        if data.get("img"): 
            embed.set_image(url=data["img"])
        await channel.send(embed=embed)
        log_activity("Sent Discord Broadcast", user_info["user"])
        
    return web.json_response({"ok": True})

async def api_blacklist(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
    return web.json_response(blacklist_db)

async def api_add_blacklist(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    data = await request.json()
    uid = data.get("user_id")
    rsn = data.get("reason", "Web Ban")
    
    if uid: 
        blacklist_db[uid] = {
            "reason": rsn, 
            "added_by": user_info["user"], 
            "added_at": iso_now()
        }
        save_json(BLACKLIST_FILE, blacklist_db)
        log_activity(f"Banned User {uid}", user_info["user"])
        
    return web.json_response({"ok": True})

async def api_rm_blacklist(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
        return web.Response(status=401)
        
    uid = (await request.json()).get("user_id")
    if uid in blacklist_db: 
        del blacklist_db[uid]
        save_json(BLACKLIST_FILE, blacklist_db)
        log_activity(f"Unbanned User {uid}", user_info["user"])
        
    return web.json_response({"ok": True})

async def api_reseller_data(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "reseller": 
        return web.Response(status=401)
        
    my_keys = [{
        "key": k, 
        "type": PRODUCTS.get(v["type"], {}).get("label", "Unknown")
    } for k, v in keys_db.items() if v.get("created_by") == user_info["user"]]
    
    return web.json_response({"my_keys": my_keys})

async def api_reseller_gen(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "reseller": 
        return web.Response(status=401)
        
    ptype = (await request.json()).get("t", "day_1")
    prefix = PRODUCTS[ptype]["key_prefix"]
    new_key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
    
    keys_db[new_key] = {
        "type": ptype, 
        "used": False, 
        "used_by": None, 
        "bound_user_id": None, 
        "created_at": iso_now(), 
        "created_by": user_info["user"]
    }
    save_json(KEYS_FILE, keys_db)
    log_activity(f"Created {ptype} Key", user_info["user"])
    
    return web.json_response({"key": new_key})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_post('/api/login', api_login)
    app.router.add_post('/api/register', api_register)
    app.router.add_post('/api/verify', api_verify)
    
    app.router.add_post('/api/stats', api_stats)
    app.router.add_post('/api/activity', api_activity)
    app.router.add_post('/api/keys', api_keys)
    app.router.add_post('/api/keys/revoke', api_revoke_key)
    
    app.router.add_post('/api/promos', api_promos)
    app.router.add_post('/api/promos/add', api_add_promo)
    app.router.add_post('/api/promos/remove', api_rm_promo)
    
    app.router.add_post('/api/lookup', api_lookup)
    app.router.add_post('/api/announce', api_announce)
    
    app.router.add_post('/api/blacklist', api_blacklist)
    app.router.add_post('/api/blacklist/add', api_add_blacklist)
    app.router.add_post('/api/blacklist/remove', api_rm_blacklist)
    
    app.router.add_post('/api/reseller/data', api_reseller_data)
    app.router.add_post('/api/reseller/generate', api_reseller_gen)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Web Server läuft auf Port {port}")

# =========================================================
# MAIN START (HILFT GEGEN RAILWAY TIMEOUTS)
# =========================================================
async def main():
    global keys_db, redeemed_db, used_txids_db, used_paysafe_db, used_amazon_db
    global blacklist_db, invoices_db, promos_db, activity_db, webkeys_db, users_db, ticket_data
    
    # Lade alle Datenbanken sofort beim Start
    keys_db = load_json(KEYS_FILE, {})
    redeemed_db = load_json(REDEEMED_FILE, {})
    used_txids_db = load_json(USED_TXIDS_FILE, {})
    used_paysafe_db = load_json(USED_PAYSAFE_FILE, {})
    used_amazon_db = load_json(USED_AMAZON_FILE, {})
    blacklist_db = load_json(BLACKLIST_FILE, {})
    invoices_db = load_json(INVOICES_FILE, {})
    promos_db = load_json(PROMOS_FILE, {})
    activity_db = load_json(ACTIVITY_FILE, [])
    webkeys_db = load_json(WEBKEYS_FILE, {})
    users_db = load_json(USERS_FILE, {})
    ticket_data = load_json(TICKETS_FILE, {})

    # Starte den Webserver, BEVOR Discord überhaupt probiert zu verbinden!
    await start_web_server()

    # Starte den Discord Bot
    async with bot:
        await bot.start(TOKEN)

@bot.event
async def on_ready():
    # Registriere die persistenten Views, damit Buttons nach Neustart funktionieren
    bot.add_view(MainTicketPanelView())
    bot.add_view(RedeemPanelView())
    bot.add_view(PaymentSummaryView())
    
    try: 
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("✅ SYNC ERFOLGREICH!")
    except Exception as e: 
        print(f"❌ Slash command sync error: {e}")
        
    print(f"Bot is ready. Logged in as: {bot.user}")

if __name__ == "__main__":
    asyncio.run(main())
