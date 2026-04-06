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
WEBSITE_LOGO_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png?ex=69d4788d&is=69d3270d&hm=b2bd6f9958e64ece4ba574875ba2c5c225c539dfe58bf831b63e2946a7059288&=&format=webp&quality=lossless&width=548&height=548" 
WELCOME_THUMBNAIL_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png"
WELCOME_BANNER_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371157432467577/analyst.jpg"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371157432467577/analyst.jpg?ex=69d4788d&is=69d3270d&hm=68f7da51ae2a3eb59d3bbfb8242799a0da4d5f47c0cf1c250d6d2e4cea7a7ebc&=&format=webp&width=548&height=548"

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
SESSIONS_FILE = "sessions.json"

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

# =========================================================
# UTILS & DB FUNCTIONS
# =========================================================
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f)
        return default
    with open(path, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except Exception: return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Lade alle Datenbanken global
ticket_data = load_json(TICKETS_FILE, {})
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
web_sessions = load_json(SESSIONS_FILE, {})

def log_activity(action, user="System"):
    global activity_db
    activity_db.insert(0, {"time": iso_now(), "user": str(user), "action": action})
    activity_db = activity_db[:50]
    save_json(ACTIVITY_FILE, activity_db)

def now_utc(): return datetime.now(timezone.utc)
def iso_now(): return now_utc().isoformat()
def random_block(length=4): return uuid.uuid4().hex[:length].upper()

def build_invoice_id() -> str:
    return f"GEN-{uuid.uuid4().hex[:10].upper()}"

def is_blacklisted(user_id: int): return str(user_id) in blacklist_db

# =========================================================
# BOT SETUP
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

class ValeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        self.loop.create_task(start_web_server())

        self.add_view(MainTicketPanelView())
        self.add_view(RedeemPanelView())
        self.add_view(PaymentSummaryView())
        self.add_view(TicketManageView(owner_id=0))
        self.add_view(BuySetupView(owner_id=0))
        self.add_view(ProductSelectView())
        self.add_view(PaymentSelectView())
        self.add_view(PaymentActionView(owner_id=0))
        self.add_view(ReviewView(target_channel_id=0, buyer_id=0))
        self.add_view(AdminPanelView(owner_id=0, ticket_channel_id=0))

bot = ValeBot()

# =========================================================
# 🌍 WEB DASHBOARD HTML (NEUES NEON 3D DESIGN)
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
        body { font-family: 'Inter', sans-serif; background-color: #050505; color: #e5e7eb; margin: 0; }
        
        /* KRASSES LILA NEON SYNTHWAVE DESIGN */
        .synthwave-bg {
            background: linear-gradient(to bottom, #090014, #2a0845, #140024);
        }
        .synthwave-sun {
            position: absolute;
            bottom: 30%;
            left: 50%;
            transform: translateX(-50%);
            width: 400px;
            height: 400px;
            background: linear-gradient(to bottom, #f9a8d4, #9333ea);
            border-radius: 50%;
            box-shadow: 0 0 80px #a855f7;
            z-index: 1;
            opacity: 0.8;
        }
        .synthwave-grid {
            position: absolute;
            bottom: 0;
            left: -50%;
            width: 200%;
            height: 40%;
            background-image: 
                linear-gradient(rgba(168, 85, 247, 0.5) 2px, transparent 2px),
                linear-gradient(90deg, rgba(168, 85, 247, 0.5) 2px, transparent 2px);
            background-size: 60px 60px;
            transform: perspective(600px) rotateX(60deg);
            animation: gridMove 2s linear infinite;
            z-index: 2;
        }
        @keyframes gridMove {
            0% { background-position: 0 0; }
            100% { background-position: 0 60px; }
        }

        .glass { background: rgba(10, 5, 20, 0.8); backdrop-filter: blur(20px); border: 1px solid rgba(168, 85, 247, 0.3); }
        .glow-text { text-shadow: 0 0 20px rgba(168, 85, 247, 0.9); }
        .glow-box { box-shadow: 0 0 40px rgba(147, 51, 234, 0.4); }
        .hidden-view { display: none !important; }
        .tab-content { display: none; } 
        .tab-content.active { display: block; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: #050505; } ::-webkit-scrollbar-thumb { background: #9333ea; border-radius: 4px; }
    </style>
</head>
<body class="flex h-screen overflow-hidden selection:bg-purple-500 selection:text-white">

    <div id="reconnect-overlay" class="fixed inset-0 bg-[#050505] z-[999] flex flex-col items-center justify-center hidden-view">
        <i class="fa-solid fa-satellite-dish animate-pulse text-purple-500 text-6xl mb-6 drop-shadow-[0_0_15px_rgba(168,85,247,0.8)]"></i>
        <h2 class="text-3xl font-black text-white tracking-widest glow-text">RECONNECTING</h2>
        <p class="text-gray-400 mt-3 font-bold">Verbindung zum Server wird wiederhergestellt...</p>
    </div>

    <div id="view-auth" class="flex w-full h-full items-center justify-center relative synthwave-bg">
        <div class="synthwave-sun"></div>
        <div class="synthwave-grid"></div>
        
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
                <input type="text" id="l-user" class="w-full bg-black/60 border border-purple-500/50 rounded-xl px-4 py-3 text-white focus:border-purple-400 outline-none transition" placeholder="Username">
                <input type="password" id="l-pass" class="w-full bg-black/60 border border-purple-500/50 rounded-xl px-4 py-3 text-white focus:border-purple-400 outline-none transition" placeholder="Password">
                <button onclick="login()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-3 rounded-xl transition shadow-[0_0_15px_rgba(147,51,234,0.6)]">LOGIN</button>
            </div>

            <div id="form-register" class="space-y-4 hidden-view">
                <input type="text" id="r-user" class="w-full bg-black/60 border border-purple-500/50 rounded-xl px-4 py-3 text-white focus:border-purple-400 outline-none transition" placeholder="Choose Username">
                <input type="password" id="r-pass" class="w-full bg-black/60 border border-purple-500/50 rounded-xl px-4 py-3 text-white focus:border-purple-400 outline-none transition" placeholder="Choose Password">
                <input type="text" id="r-key" class="w-full bg-black/60 border border-purple-500/50 rounded-xl px-4 py-3 text-purple-400 font-mono focus:border-purple-400 outline-none transition" placeholder="Invitation Key (VALE-...)">
                <button onclick="register()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-3 rounded-xl transition shadow-[0_0_15px_rgba(147,51,234,0.6)]">CREATE ACCOUNT</button>
            </div>
            
            <p id="auth-error" class="text-red-400 mt-4 text-sm text-center font-bold hidden"></p>
        </div>
    </div>

    <div id="view-admin" class="flex w-full h-full hidden-view synthwave-bg">
        <div class="absolute inset-0 z-0 opacity-20"><div class="synthwave-grid"></div></div>
        <aside class="w-64 glass border-r border-purple-500/30 flex flex-col justify-between z-10 relative">
            <div>
                <div class="h-32 flex items-center justify-center border-b border-purple-500/30 px-4">
                    <img src="LOGO_URL_PLACEHOLDER" class="h-16 mr-3 drop-shadow-[0_0_10px_rgba(168,85,247,0.8)] object-contain">
                    <span class="text-xl font-black text-white glow-text">ADMIN</span>
                </div>
                <nav class="p-4 space-y-2 mt-2">
                    <button onclick="nav('dash')" id="btn-dash" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-purple-300 bg-purple-600/30 font-bold border border-purple-500/50 transition">
                        <i class="fa-solid fa-chart-pie w-6"></i> Dashboard
                    </button>
                    <button onclick="nav('gen')" id="btn-gen" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-bolt w-6"></i> Generator
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
            <div class="p-6 border-t border-purple-500/30 text-center">
                <button onclick="logout()" class="text-red-400 hover:text-red-300 font-bold transition bg-black/40 px-6 py-2 rounded-xl border border-red-500/30 shadow-[0_0_10px_rgba(220,38,38,0.3)]">
                    <i class="fa-solid fa-power-off mr-1"></i> LOGOUT
                </button>
            </div>
        </aside>

        <main class="flex-1 overflow-y-auto p-8 relative z-10">
            <div class="max-w-7xl mx-auto">
                <header class="flex justify-between items-center mb-8 glass p-4 rounded-2xl">
                    <h2 id="page-title" class="text-3xl font-black text-white tracking-wide uppercase">Dashboard</h2>
                    <div class="flex items-center gap-3">
                        <span class="text-sm text-gray-300">Logged in as <span id="admin-name" class="text-purple-400 font-bold">Admin</span></span>
                        <span class="bg-purple-500/20 text-purple-400 border border-purple-500/50 text-xs font-bold px-3 py-1 rounded-full flex items-center shadow-[0_0_10px_rgba(168,85,247,0.5)]">
                            <span class="w-2 h-2 rounded-full bg-purple-400 animate-pulse mr-2"></span> LIVE
                        </span>
                    </div>
                </header>

                <div id="dash" class="tab-content active">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                        <div class="glass p-6 rounded-2xl border-l-4 border-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                            <p class="text-sm font-bold text-gray-400 uppercase">Total Revenue</p>
                            <h3 class="text-4xl font-black text-white mt-1 glow-text" id="stat-rev">0.00€</h3>
                        </div>
                        <div class="glass p-6 rounded-2xl border-l-4 border-pink-500 shadow-[0_0_15px_rgba(236,72,153,0.2)]">
                            <p class="text-sm font-bold text-gray-400 uppercase">Orders Today</p>
                            <h3 class="text-4xl font-black text-white mt-1" id="stat-orders">0</h3>
                        </div>
                        <div class="glass p-6 rounded-2xl border-l-4 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.2)]">
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
                
                <div id="gen" class="tab-content">
                    <div class="glass p-6 rounded-2xl border-t-2 border-purple-500 max-w-2xl shadow-[0_0_20px_rgba(168,85,247,0.3)]">
                        <h2 class="text-xl font-bold mb-6 text-white"><i class="fa-solid fa-bolt mr-2 text-purple-400"></i>Generate Access Keys (Admin)</h2>
                        <div class="space-y-4">
                            <button onclick="genAdminKey('day_1')" class="w-full bg-black/60 hover:bg-purple-600/30 border border-purple-500/50 p-4 rounded-xl flex justify-between items-center transition text-white shadow-lg">
                                <span class="font-bold">1 Day Key</span><i class="fa-solid fa-plus text-purple-400"></i>
                            </button>
                            <button onclick="genAdminKey('week_1')" class="w-full bg-black/60 hover:bg-purple-600/30 border border-purple-500/50 p-4 rounded-xl flex justify-between items-center transition text-white shadow-lg">
                                <span class="font-bold">1 Week Key</span><i class="fa-solid fa-plus text-purple-400"></i>
                            </button>
                            <button onclick="genAdminKey('lifetime')" class="w-full bg-gradient-to-r from-purple-700 to-pink-600 hover:from-purple-600 hover:to-pink-500 p-4 rounded-xl flex justify-between items-center text-white transition shadow-[0_0_20px_rgba(168,85,247,0.6)]">
                                <span class="font-bold">Lifetime Key</span><i class="fa-solid fa-star text-yellow-300"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <div id="keys" class="tab-content">
                    <div class="glass rounded-2xl overflow-hidden shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                        <div class="p-6 border-b border-purple-500/30">
                            <h3 class="text-lg font-bold text-white"><i class="fa-solid fa-key mr-2 text-purple-400"></i>Generated Keys</h3>
                        </div>
                        <div class="overflow-x-auto max-h-[600px]">
                            <table class="w-full text-left text-sm whitespace-nowrap">
                                <thead class="bg-black/60 border-b border-purple-500/30 sticky top-0 backdrop-blur-md">
                                    <tr>
                                        <th class="px-6 py-4 text-purple-300">Key</th>
                                        <th class="px-6 py-4 text-purple-300">Type</th>
                                        <th class="px-6 py-4 text-purple-300">Creator</th>
                                        <th class="px-6 py-4 text-purple-300">Used By (ID)</th>
                                        <th class="px-6 py-4 text-purple-300">Status</th>
                                        <th class="px-6 py-4 text-right text-purple-300">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="table-keys" class="divide-y divide-purple-500/20"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="promos" class="tab-content">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="md:col-span-1 glass p-6 rounded-2xl border-t-2 border-pink-500 shadow-[0_0_15px_rgba(236,72,153,0.2)]">
                            <h3 class="text-lg font-bold text-white mb-4">New Promo</h3>
                            <input type="text" id="p-code" placeholder="Code (e.g. SUMMER50)" class="w-full bg-black/60 border border-purple-500/50 rounded-lg px-4 py-2 mb-3 text-white uppercase outline-none focus:border-pink-400">
                            <input type="number" id="p-disc" placeholder="Discount %" class="w-full bg-black/60 border border-purple-500/50 rounded-lg px-4 py-2 mb-3 text-white outline-none focus:border-pink-400">
                            <input type="number" id="p-uses" placeholder="Max Uses" class="w-full bg-black/60 border border-purple-500/50 rounded-lg px-4 py-2 mb-4 text-white outline-none focus:border-pink-400">
                            <button onclick="createPromo()" class="w-full bg-pink-600 hover:bg-pink-500 text-white font-bold py-2 rounded-lg transition shadow-[0_0_15px_rgba(236,72,153,0.5)]">Create Code</button>
                        </div>
                        <div class="md:col-span-2 glass rounded-2xl overflow-hidden">
                            <div class="p-6 border-b border-purple-500/30">
                                <h3 class="text-lg font-bold text-white">Active Promos</h3>
                            </div>
                            <table class="w-full text-left text-sm">
                                <thead class="text-purple-300 border-b border-purple-500/30 bg-black/60">
                                    <tr>
                                        <th class="p-4">Code</th>
                                        <th class="p-4">Discount</th>
                                        <th class="p-4">Uses Left</th>
                                        <th class="p-4 text-right">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="table-promos" class="divide-y divide-purple-500/20"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="lookup" class="tab-content">
                    <div class="glass p-6 rounded-2xl mb-6 flex gap-4 shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                        <input type="text" id="lookup-id" placeholder="Discord User ID..." class="flex-1 bg-black/60 border border-purple-500/50 rounded-xl px-4 py-3 text-white focus:border-purple-400 outline-none transition">
                        <button onclick="lookupUser()" class="bg-purple-600 hover:bg-purple-500 text-white px-8 font-bold rounded-xl transition shadow-[0_0_15px_rgba(147,51,234,0.5)]">
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
                            <div class="p-4 border-b border-purple-500/30 font-bold bg-black/60 text-white">Purchase History</div>
                            <table class="w-full text-left text-sm">
                                <thead class="text-purple-300 border-b border-purple-500/30">
                                    <tr>
                                        <th class="p-4">Invoice</th>
                                        <th class="p-4">Product</th>
                                        <th class="p-4">Price</th>
                                        <th class="p-4">Date</th>
                                    </tr>
                                </thead>
                                <tbody id="lu-table" class="divide-y divide-purple-500/20"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="announce" class="tab-content">
                    <div class="glass p-6 rounded-2xl border-t-2 border-blue-500 max-w-3xl shadow-[0_0_15px_rgba(59,130,246,0.2)]">
                        <h3 class="text-xl font-bold text-white mb-4"><i class="fa-solid fa-satellite-dish mr-2 text-blue-400"></i>Server Broadcast</h3>
                        <input type="text" id="ann-title" placeholder="Title (e.g. 🚀 MEGA UPDATE)" class="w-full bg-black/60 border border-purple-500/50 rounded-lg px-4 py-3 mb-4 text-white font-bold outline-none focus:border-blue-400 transition">
                        <textarea id="ann-desc" placeholder="Message content..." rows="6" class="w-full bg-black/60 border border-purple-500/50 rounded-lg px-4 py-3 mb-4 text-white resize-none outline-none focus:border-blue-400 transition"></textarea>
                        <input type="text" id="ann-img" placeholder="Image URL (Optional)" class="w-full bg-black/60 border border-purple-500/50 rounded-lg px-4 py-2 mb-6 text-white text-sm outline-none focus:border-blue-400 transition">
                        <button onclick="sendAnnounce()" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition shadow-[0_0_20px_rgba(37,99,235,0.5)]">
                            <i class="fa-solid fa-paper-plane mr-2"></i>Send to Discord
                        </button>
                    </div>
                </div>

                <div id="blacklist" class="tab-content">
                    <div class="glass p-6 rounded-2xl mb-6 border-l-4 border-red-500 flex gap-4 items-center shadow-[0_0_15px_rgba(239,68,68,0.2)]">
                        <input type="text" id="bl-id" placeholder="Discord User ID..." class="flex-1 bg-black/60 border border-purple-500/50 rounded-lg px-4 py-3 text-white outline-none focus:border-red-400 transition">
                        <input type="text" id="bl-reason" placeholder="Reason..." class="flex-1 bg-black/60 border border-purple-500/50 rounded-lg px-4 py-3 text-white outline-none focus:border-red-400 transition">
                        <button onclick="addBlacklist()" class="bg-red-600 hover:bg-red-500 text-white px-8 py-3 font-bold rounded-lg transition shadow-[0_0_15px_rgba(220,38,38,0.5)]">Ban</button>
                    </div>
                    <div class="glass rounded-2xl overflow-hidden">
                        <table class="w-full text-left text-sm">
                            <thead class="text-red-300 border-b border-red-500/30 bg-black/60">
                                <tr>
                                    <th class="p-4">User ID</th>
                                    <th class="p-4">Reason</th>
                                    <th class="p-4 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody id="table-blacklist" class="divide-y divide-purple-500/20"></tbody>
                        </table>
                    </div>
                </div>
                
            </div>
        </main>
    </div>

    <div id="view-reseller" class="flex w-full h-full hidden-view p-8 synthwave-bg">
        <div class="absolute inset-0 z-0 opacity-20"><div class="synthwave-grid"></div></div>
        <div class="max-w-4xl mx-auto w-full relative z-10">
            <header class="flex justify-between items-center mb-8 glass p-6 rounded-2xl glow-box">
                <div class="flex items-center">
                    <img src="LOGO_URL_PLACEHOLDER" class="h-16 mr-4 drop-shadow-[0_0_10px_rgba(168,85,247,0.8)] object-contain">
                    <div>
                        <h1 class="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500">Reseller Portal</h1>
                        <p class="text-sm text-purple-300 font-bold" id="r-name">Loading...</p>
                    </div>
                </div>
                <button onclick="logout()" class="bg-black/40 border border-red-500/50 hover:bg-red-600 text-red-400 hover:text-white px-6 py-2 rounded-lg transition font-bold shadow-[0_0_10px_rgba(220,38,38,0.3)]">
                    <i class="fa-solid fa-power-off mr-2"></i>Logout
                </button>
            </header>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div class="glass p-6 rounded-2xl border-t-2 border-purple-500 shadow-[0_0_20px_rgba(168,85,247,0.3)]">
                    <h2 class="text-xl font-bold mb-6 text-white"><i class="fa-solid fa-bolt mr-2 text-purple-400"></i>Generate Access</h2>
                    <div class="space-y-4">
                        <button onclick="genKey('day_1')" class="w-full bg-black/60 hover:bg-purple-600/30 border border-purple-500/50 p-4 rounded-xl flex justify-between items-center transition text-white shadow-lg">
                            <span class="font-bold">1 Day Key</span><i class="fa-solid fa-plus text-purple-400"></i>
                        </button>
                        <button onclick="genKey('week_1')" class="w-full bg-black/60 hover:bg-purple-600/30 border border-purple-500/50 p-4 rounded-xl flex justify-between items-center transition text-white shadow-lg">
                            <span class="font-bold">1 Week Key</span><i class="fa-solid fa-plus text-purple-400"></i>
                        </button>
                        <button onclick="genKey('lifetime')" class="w-full bg-gradient-to-r from-purple-700 to-pink-600 hover:from-purple-600 hover:to-pink-500 p-4 rounded-xl flex justify-between items-center text-white transition shadow-[0_0_20px_rgba(168,85,247,0.6)]">
                            <span class="font-bold">Lifetime Key</span><i class="fa-solid fa-star text-yellow-300"></i>
                        </button>
                    </div>
                </div>
                <div class="glass p-6 rounded-2xl shadow-[0_0_15px_rgba(168,85,247,0.1)]">
                    <h2 class="text-xl font-bold mb-4 text-white">Your Stock</h2>
                    <div class="overflow-y-auto h-64 pr-2 space-y-3" id="my-keys"></div>
                </div>
            </div>
        </div>
    </div>

    <div id="key-modal" class="fixed inset-0 bg-black/90 flex items-center justify-center hidden-view z-50">
        <div class="glass p-10 rounded-3xl text-center border-2 border-purple-500 shadow-[0_0_80px_rgba(168,85,247,0.6)] max-w-md w-full relative overflow-hidden">
            <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(168,85,247,0.2),transparent)]"></div>
            <h3 class="text-3xl font-black text-white mb-2 glow-text relative z-10">ACCESS GRANTED</h3>
            <p class="text-purple-300 mb-6 font-bold relative z-10">Key successfully generated.</p>
            <input type="text" id="new-key" class="w-full bg-black border border-purple-500 p-4 rounded-xl text-purple-400 font-mono text-center mb-6 text-xl tracking-wider glow-box relative z-10 outline-none" readonly>
            <button onclick="closeModal()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-4 rounded-xl transition shadow-[0_0_20px_rgba(147,51,234,0.6)] relative z-10 tracking-widest uppercase">Close</button>
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
            
            try {
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
            } catch (e) {
                console.error("API Call Error:", e);
                // Zeigt Reconnect-Screen, wenn Server offline ist
                if (endpoint !== '/api/verify') {
                    document.getElementById('reconnect-overlay').classList.remove('hidden-view');
                    setTimeout(checkAuthOnLoad, 2500);
                }
                throw e;
            }
        }

        function showError(msg) { 
            const e = document.getElementById('auth-error'); 
            e.innerText = msg; 
            e.classList.remove('hidden'); 
        }

        async function login() {
            const u = document.getElementById('l-user').value;
            const p = document.getElementById('l-pass').value;
            if (!u || !p) return showError("Bitte fülle alle Felder aus.");
            
            try {
                const res = await apiCall('/api/login', {user: u, pass: p});
                if (res.ok) { 
                    const d = await res.json(); 
                    localStorage.setItem('v_token', d.token); 
                    initApp(d.role, d.user); 
                } else {
                    showError("Falscher Username oder falsches Passwort!");
                }
            } catch (e) {
                showError("Server offline. Versuch es gleich nochmal.");
            }
        }

        async function register() {
            const u = document.getElementById('r-user').value;
            const p = document.getElementById('r-pass').value;
            const k = document.getElementById('r-key').value;
            
            if (!u || !p || !k) return showError("Bitte fülle alle Felder aus.");
            
            try {
                const res = await apiCall('/api/register', {user: u, pass: p, key: k});
                if (res.ok) { 
                    const d = await res.json(); 
                    localStorage.setItem('v_token', d.token); 
                    initApp(d.role, d.user); 
                } else { 
                    const e = await res.json(); 
                    showError(e.error || "Fehler bei der Registrierung!"); 
                }
            } catch (e) {
                showError("Server offline. Versuch es gleich nochmal.");
            }
        }

        function logout() { 
            localStorage.removeItem('v_token'); 
            location.reload(); 
        }

        async function checkAuthOnLoad() {
            const t = localStorage.getItem('v_token');
            if (t) {
                // Verhindert das kurze Aufblitzen der Login-Seite
                document.getElementById('view-auth').classList.add('hidden-view');
                document.getElementById('reconnect-overlay').classList.remove('hidden-view');
                
                try {
                    const res = await fetch('/api/verify', {
                        method: 'POST', 
                        headers: {'Authorization': t, 'Content-Type': 'application/json'}, 
                        body: JSON.stringify({})
                    });
                    
                    if (res.ok) { 
                        // Server ist erreichbar -> Overlay weg, App starten!
                        document.getElementById('reconnect-overlay').classList.add('hidden-view');
                        const d = await res.json(); 
                        initApp(d.role, d.user); 
                    } else if (res.status === 401) {
                        logout(); 
                    } else {
                        // Railway startet gerade neu (502/503 Error). Nicht ausloggen! Einfach warten.
                        console.log("Server temporarily offline, retrying...");
                        setTimeout(checkAuthOnLoad, 3000);
                    }
                } catch(e) {
                    // Netzwerkfehler (Server down). Nicht ausloggen!
                    console.log("Network error, retrying...");
                    setTimeout(checkAuthOnLoad, 3000);
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
            document.getElementById('btn-' + tabId).className = "nav-btn w-full text-left py-3 px-4 rounded-xl text-purple-300 bg-purple-600/30 font-bold border border-purple-500/50 shadow-[inset_0_0_15px_rgba(168,85,247,0.3)]";
            
            const titles = {
                'dash': 'Overview', 
                'gen': 'Key Generator',
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
            try {
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
            } catch(e) { console.error("Could not load stats"); }
        }

        async function loadActivity() {
            try {
                const res = await apiCall('/api/activity', {}); 
                const data = await res.json();
                document.getElementById('activity-feed').innerHTML = data.map(a => `
                    <div class="p-4 bg-black/60 rounded-xl border border-purple-500/30 flex justify-between items-center hover:border-purple-500/60 transition">
                        <div>
                            <span class="font-black text-purple-400 text-sm mr-2">${a.user}</span>
                            <span class="text-sm text-gray-300 font-bold">${a.action}</span>
                        </div>
                        <span class="text-xs text-gray-500 font-mono">${a.time.split('T')[1].substring(0,5)}</span>
                    </div>
                `).join('');
            } catch(e) {}
        }

        async function loadKeys() {
            try {
                const res = await apiCall('/api/keys', {}); 
                const data = await res.json(); 
                const tb = document.getElementById('table-keys');
                
                if (Object.keys(data).length === 0) {
                    return tb.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-gray-500 font-bold">No keys generated</td></tr>';
                }
                
                tb.innerHTML = Object.entries(data).reverse().map(([key, info]) => {
                    let badge = info.used ? '<span class="px-3 py-1 rounded-md bg-red-500/20 text-red-400 text-xs border border-red-500/40 font-bold tracking-wider uppercase">Used</span>' : '<span class="px-3 py-1 rounded-md bg-green-500/20 text-green-400 text-xs border border-green-500/40 font-bold tracking-wider uppercase">Active</span>';
                    if (info.revoked) {
                        badge = '<span class="px-3 py-1 rounded-md bg-gray-500/20 text-gray-400 text-xs border border-gray-500/40 font-bold tracking-wider uppercase">Banned</span>';
                    }
                    
                    const creator = info.created_by ? `<span class="text-blue-400 font-bold">${info.created_by}</span>` : 'System';
                    const usedBy = info.used_by ? `<span class="text-pink-400 font-mono text-xs font-bold">${info.used_by}</span>` : '-';
                    const act = !info.revoked ? `<button onclick="revokeKey('${key}')" class="text-xs font-bold bg-black/50 text-red-400 border border-red-500/30 hover:bg-red-600 hover:text-white px-3 py-2 rounded-lg transition shadow-[0_0_10px_rgba(220,38,38,0.2)]">BAN KEY</button>` : '-';
                    
                    return `
                        <tr class="hover:bg-purple-500/20 transition border-b border-purple-500/10">
                            <td class="px-6 py-4 font-mono text-purple-300 font-bold tracking-wider">${key}</td>
                            <td class="px-6 py-4 text-gray-300 font-bold">${info.type}</td>
                            <td class="px-6 py-4">${creator}</td>
                            <td class="px-6 py-4">${usedBy}</td>
                            <td class="px-6 py-4">${badge}</td>
                            <td class="px-6 py-4 text-right">${act}</td>
                        </tr>
                    `;
                }).join('');
            } catch(e) {}
        }

        async function revokeKey(k) { 
            if (confirm('Möchtest du diesen Key bannen und dem User die Rolle entfernen?')) { 
                await apiCall('/api/keys/revoke', {key: k}); 
                loadKeys(); 
            } 
        }

        async function loadPromos() {
            try {
                const res = await apiCall('/api/promos', {}); 
                const data = await res.json(); 
                const tb = document.getElementById('table-promos');
                
                if (Object.keys(data).length === 0) {
                    return tb.innerHTML = '<tr><td colspan="4" class="p-6 text-center text-gray-500 font-bold">No active promos.</td></tr>';
                }
                
                tb.innerHTML = Object.entries(data).map(([code, info]) => `
                    <tr class="hover:bg-purple-500/20 transition border-b border-purple-500/10">
                        <td class="p-4 font-mono font-black text-pink-400 tracking-wider">${code}</td>
                        <td class="p-4 text-purple-300 font-bold">-${info.discount}%</td>
                        <td class="p-4 text-gray-300 font-bold">${info.uses}</td>
                        <td class="p-4 text-right">
                            <button onclick="rmPromo('${code}')" class="text-red-400 bg-black/50 border border-red-500/30 p-2 rounded hover:bg-red-600 hover:text-white transition shadow-lg">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } catch(e) {}
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
            
            try {
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
                    tb.innerHTML = '<tr><td colspan="4" class="p-6 text-center text-gray-500 font-bold">No purchases found.</td></tr>';
                } else {
                    tb.innerHTML = data.invoices.map(i => `
                        <tr class="hover:bg-purple-500/20 transition border-b border-purple-500/10">
                            <td class="p-4 font-mono text-xs text-gray-400 font-bold tracking-wider">${i.id}</td>
                            <td class="p-4 text-purple-300 font-bold">${i.product}</td>
                            <td class="p-4 font-black text-green-400">${i.price}€</td>
                            <td class="p-4 text-xs text-gray-400 font-bold">${i.date.split('T')[0]}</td>
                        </tr>
                    `).join('');
                }
            } catch(e) {}
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
            try {
                const res = await apiCall('/api/blacklist', {}); 
                const data = await res.json(); 
                const tb = document.getElementById('table-blacklist');
                
                if (Object.keys(data).length === 0) {
                    return tb.innerHTML = '<tr><td colspan="3" class="p-6 text-center text-gray-500 font-bold">Blacklist is empty.</td></tr>';
                }
                
                tb.innerHTML = Object.entries(data).map(([uid, info]) => `
                    <tr class="hover:bg-red-500/20 transition border-b border-purple-500/10">
                        <td class="p-4 font-mono text-red-300 font-bold tracking-wider">${uid}</td>
                        <td class="p-4 text-gray-300 font-bold">${info.reason}</td>
                        <td class="p-4 text-right">
                            <button onclick="rmBlacklist('${uid}')" class="text-red-400 bg-black/50 border border-red-500/30 p-2 rounded hover:bg-red-600 hover:text-white transition shadow-lg">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } catch(e) {}
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

        // RESELLER & ADMIN GENERATOR FUNCTIONS
        async function loadResellerKeys() {
            try {
                const res = await apiCall('/api/reseller/data', {}); 
                const data = await res.json();
                
                if (data.my_keys.length === 0) {
                    document.getElementById('my-keys').innerHTML = '<p class="text-gray-500 p-6 text-center font-bold">Noch keine Keys generiert.</p>';
                } else {
                    document.getElementById('my-keys').innerHTML = data.my_keys.reverse().map(k => `
                        <div class="bg-black/60 p-4 rounded-xl border border-purple-500/30 flex justify-between items-center transition hover:border-purple-500/70 shadow-lg">
                            <span class="font-mono text-sm text-purple-300 font-bold tracking-wider">${k.key}</span>
                            <span class="text-xs font-black px-3 py-1 bg-purple-500/20 text-purple-300 rounded-md border border-purple-500/40 uppercase">${k.type}</span>
                        </div>
                    `).join('');
                }
            } catch(e) {}
        }

        async function genKey(type) {
            const res = await apiCall('/api/reseller/generate', {t: type}); 
            const d = await res.json();
            
            document.getElementById('new-key').value = d.key; 
            document.getElementById('key-modal').classList.remove('hidden-view'); 
            loadResellerKeys();
        }

        async function genAdminKey(type) {
            const res = await apiCall('/api/admin/generate', {t: type}); 
            const d = await res.json();
            
            document.getElementById('new-key').value = d.key; 
            document.getElementById('key-modal').classList.remove('hidden-view'); 
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
        return web.json_response({"error": "Bitte fülle alle Felder aus!"}, status=400)
        
    if username in users_db: 
        return web.json_response({"error": f"Der Name '{username}' ist leider schon vergeben!"}, status=400)
        
    if inv_key not in webkeys_db:
        return web.json_response({"error": "Dieser Einladungs-Key existiert nicht!"}, status=400)
        
    if webkeys_db[inv_key].get("used"): 
        return web.json_response({"error": "Dieser Einladungs-Key wurde bereits benutzt!"}, status=400)
    
    role = webkeys_db[inv_key]["role"]
    users_db[username] = {"pass": password, "role": role}
    webkeys_db[inv_key]["used"] = True
    
    save_json(USERS_FILE, users_db)
    save_json(WEBKEYS_FILE, webkeys_db)
    log_activity(f"New User Registered ({role})", username)
    
    token = str(uuid.uuid4())
    web_sessions[token] = {"user": username, "role": role}
    save_json(SESSIONS_FILE, web_sessions)
    
    return web.json_response({"ok": True, "token": token, "role": role, "user": username})

async def api_login(request):
    data = await request.json()
    username = data.get("user")
    password = data.get("pass")
    
    if username in users_db and users_db[username]["pass"] == password:
        token = str(uuid.uuid4())
        role = users_db[username]["role"]
        web_sessions[token] = {"user": username, "role": role}
        save_json(SESSIONS_FILE, web_sessions)
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
        "created_by": user_info["user"],
        "revoked": False
    }
    save_json(KEYS_FILE, keys_db)
    log_activity(f"Reseller {user_info['user']} created {ptype} Key", user_info["user"])
    
    return web.json_response({"key": new_key})

async def api_admin_gen(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": 
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
        "created_by": user_info["user"],
        "revoked": False
    }
    save_json(KEYS_FILE, keys_db)
    log_activity(f"Admin {user_info['user']} created {ptype} Key", user_info["user"])
    
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
    
    app.router.add_post('/api/admin/generate', api_admin_gen)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Web Server läuft auf Port {port}")

# =========================================================
# BOT COMMANDS & TICKET LOGIC
# =========================================================
def premium_divider() -> str: 
    return "━━━━━━━━━━━━━━━━━━━━━━━━"

def short_txid(txid: str) -> str: 
    return txid if len(txid) < 20 else f"{txid[:14]}...{txid[-14:]}"

def format_price(value: float) -> str: 
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"

def is_reseller_dc(member: discord.Member | None) -> bool: 
    return member and any(role.id == RESELLER_ROLE_ID for role in member.roles)

def get_price(product_key: str, member: discord.Member | None = None, promo_discount: int = 0) -> float:
    base_price = PRODUCTS[product_key]["price_eur"]
    if is_reseller_dc(member): 
        base_price = round(base_price * 0.5, 2)
    if promo_discount > 0: 
        base_price = round(base_price * (1 - (promo_discount / 100.0)), 2)
    return float(base_price)

async def dm_user_safe(user: discord.abc.User, content: str = None, embed: discord.Embed = None):
    try: 
        await user.send(content=content, embed=embed)
    except Exception: 
        pass

def generate_key(product_type: str, ticket_id: str | None = None, creator="System") -> str:
    prefix = PRODUCTS[product_type]["key_prefix"]
    while True:
        key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
        if key not in keys_db:
            keys_db[key] = {
                "type": product_type, 
                "used": False, 
                "used_by": None, 
                "bound_user_id": None, 
                "created_at": iso_now(), 
                "redeemed_at": None, 
                "approved_in_ticket": ticket_id, 
                "created_by": creator,
                "revoked": False
            }
            save_json(KEYS_FILE, keys_db)
            log_activity("Generierte einen Key", creator)
            return key

def create_invoice_record(invoice_id, buyer_id, product_type, payment_key, key, ticket_id, final_price_eur, reseller_discount):
    invoices_db[invoice_id] = {
        "buyer_id": str(buyer_id), 
        "product_type": product_type, 
        "payment_key": payment_key, 
        "key": key, 
        "ticket_id": str(ticket_id), 
        "created_at": iso_now(), 
        "final_price_eur": final_price_eur, 
        "reseller_discount": reseller_discount
    }
    save_json(INVOICES_FILE, invoices_db)
    log_activity(f"Neue Order ({final_price_eur}€)", buyer_id)

def extract_possible_paysafe_codes(text: str): 
    return re.findall(r"\b[A-Z0-9]{4,8}(?:-[A-Z0-9]{4,8}){1,5}\b", text.upper())

def extract_possible_amazon_codes(text: str): 
    return re.findall(r"\b[A-Z0-9]{4,8}(?:-[A-Z0-9]{4,8}){1,5}\b", text.upper())

def litoshi_to_ltc(value: int) -> float: 
    return value / 100_000_000

def tx_matches_our_address(tx_data: dict, expected_address: str) -> tuple[bool, int]:
    total_received = 0
    found = False
    for output in tx_data.get("outputs", []):
        if expected_address in output.get("addresses", []): 
            found = True
            total_received += int(output.get("value", 0))
    return found, total_received

async def fetch_ltc_tx(txid: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=20) as resp:
            if resp.status != 200: 
                return None, f"API error"
            return await resp.json(), None

async def fetch_ltc_price_eur():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=eur", timeout=20) as resp:
            if resp.status != 200: 
                return None
            return (await resp.json()).get("litecoin", {}).get("eur")

async def find_existing_ticket(guild: discord.Guild, user: discord.Member):
    for channel in guild.text_channels:
        if channel.topic == f"ticket_owner:{user.id}": 
            return channel
    return None

# --- EMBEDS ---
def build_order_summary(product_key: str, payment_key: str, user: discord.Member, ltc_price_eur: float | None = None) -> discord.Embed:
    product = PRODUCTS[product_key]
    payment = PAYMENTS[payment_key]
    price = get_price(product_key, user)
    price_header = f"💶 **Price:** {format_price(price)}€"
    
    if is_reseller_dc(user): 
        price_header += " (**Reseller 50% OFF**)"
        
    if payment_key == "paypal": 
        extra = f"## 💸 PayPal Payment\n**Send payment to:**\n`{PAYPAL_EMAIL}`\n\n**After payment:**\n• Send screenshot / proof in this ticket\n• Click **Payment Sent**"
    elif payment_key == "litecoin":
        extra = f"## 🪙 Litecoin Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{LITECOIN_ADDRESS}`\n\n"
        if ltc_price_eur and ltc_price_eur > 0: 
            extra += f"**Approx LTC amount:** `{price / ltc_price_eur:.6f} LTC`\n**Market rate:** `{ltc_price_eur:.2f} EUR/LTC`\n\n"
        extra += "**After payment:**\n• Click **Submit TXID**\n• Paste your TXID in the popup\n• Bot checks it automatically"
    elif payment_key == "ethereum": 
        extra = f"## 🔷 Ethereum Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{ETHEREUM_ADDRESS}`\n\n**After payment:**\n• Click **Submit Crypto TXID**"
    elif payment_key == "solana": 
        extra = f"## 🟣 Solana Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{SOLANA_ADDRESS}`\n\n**After payment:**\n• Click **Submit Crypto TXID**"
    elif payment_key == "paysafecard": 
        extra = f"## 💳 Paysafecard Payment\n**Main price:** `{format_price(price)}€`\n\n**After buying your code:**\n• Click **Submit Paysafecard Code**"
    else: 
        extra = f"## 🎁 Amazon Card Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{LITECOIN_ADDRESS}`\n\n**After buying your Amazon card:**\n• Click **Submit Amazon Code**"
        
    return discord.Embed(
        title="✦ ORDER SETUP COMPLETE ✦", 
        description=f"{premium_divider()}\n{user.mention}\n\n📦 **Product:** {product['label']}\n{price_header}\n{payment['emoji']} **Method:** {payment['label']}\n\n{extra}\n{premium_divider()}", 
        color=COLOR_MAIN
    )

def build_payment_summary_embed(channel_id: int) -> discord.Embed:
    data = ticket_data.get(str(channel_id), {})
    user = bot.get_guild(GUILD_ID).get_member(data.get("user_id")) if bot.get_guild(GUILD_ID) and data.get("user_id") else None
    
    product_key = data.get("product_key")
    promo_code = data.get("applied_promo")
    
    promo_discount = promos_db[promo_code]["discount"] if promo_code and promo_code in promos_db else 0
    if product_key in PRODUCTS:
        price_text = f"{format_price(get_price(product_key, user, promo_discount))}€"
        if is_reseller_dc(user): 
            price_text += " (Reseller)"
        if promo_discount > 0: 
            price_text += f" (Promo -{promo_discount}%)"
    else: 
        price_text = "—"
        
    status_map = {"waiting": "🟡 Waiting", "reviewing": "🟠 Reviewing", "approved": "✅ Approved", "denied": "❌ Denied"}
    
    embed = discord.Embed(title="📋 Payment Summary", description=f"{premium_divider()}\n**Live order status**\n{premium_divider()}", color=COLOR_INFO)
    embed.add_field(name="Product", value=PRODUCTS[product_key]["label"] if product_key in PRODUCTS else "Not selected", inline=True)
    embed.add_field(name="Price", value=price_text, inline=True)
    embed.add_field(name="Method", value=PAYMENTS[data.get("payment_key")]["label"] if data.get("payment_key") in PAYMENTS else "Not selected", inline=True)
    embed.add_field(name="Status", value=status_map.get(data.get("status", "waiting"), data.get("status", "waiting")), inline=True)
    embed.add_field(name="TXID", value=f"`{short_txid(data.get('last_txid'))}`" if data.get('last_txid') else "Not submitted", inline=True)
    embed.add_field(name="Invoice", value=f"`{data.get('invoice_id')}`" if data.get('invoice_id') else "Not created", inline=False)
    
    if promo_code: 
        embed.add_field(name="Gutschein", value=f"`{promo_code}`", inline=True)
        
    return embed

async def update_payment_summary_message(channel: discord.TextChannel):
    data = ticket_data.get(str(channel.id))
    if data and data.get("summary_message_id"):
        try: 
            msg = await channel.fetch_message(data["summary_message_id"])
            await msg.edit(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
        except Exception: 
            pass

async def send_admin_panel_to_channel(guild: discord.Guild, owner_id: int, ticket_channel_id: int):
    admin_channel = guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
    if isinstance(admin_channel, discord.TextChannel):
        msg = await admin_channel.send(
            embed=discord.Embed(title="🛠️ GEN ADMIN PANEL", description=f"{premium_divider()}\n**Buyer ID:** `{owner_id}`\n**Ticket ID:** `{ticket_channel_id}`\n{premium_divider()}", color=COLOR_ADMIN), 
            view=AdminPanelView()
        )
        if str(ticket_channel_id) in ticket_data: 
            ticket_data[str(ticket_channel_id)]["admin_message_id"] = msg.id
            save_json(TICKETS_FILE, ticket_data)

async def send_summary_and_admin_panels(channel: discord.TextChannel, owner_id: int):
    summary_msg = await channel.send(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
    ticket_data[str(channel.id)]["summary_message_id"] = summary_msg.id
    save_json(TICKETS_FILE, ticket_data)
    await send_admin_panel_to_channel(channel.guild, owner_id, channel.id)

# --- REDEEM LOGIC ---
async def redeem_key_for_user(guild: discord.Guild, member: discord.Member, key: str):
    if is_blacklisted(member.id): return False, "You are blacklisted."
    if key not in keys_db: return False, "Key not found."
    if keys_db[key].get("revoked"): return False, "This key has been banned."
    if keys_db[key]["used"]: return False, "Already used."
    pt = keys_db[key]["type"]
    r = guild.get_role(REDEEM_ROLE_ID)
    if not r: return False, "Role not found."
    
    keys_db[key].update({"used": True, "used_by": str(member.id)})
    save_json(KEYS_FILE, keys_db)
    
    redeemed_db[str(member.id)] = {"key": key, "type": pt, "role_id": REDEEM_ROLE_ID, "expires_at": (now_utc() + PRODUCTS[pt]["duration"]).isoformat() if PRODUCTS[pt]["duration"] else None}
    save_json(REDEEMED_FILE, redeemed_db)
    
    await member.add_roles(r)
    return True, pt

# --- VIEWS & MODALS ---

class CloseConfirmView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=60)
        
    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        data = ticket_data.get(str(interaction.channel.id))
        if data and data.get("admin_message_id"):
            admin_channel = interaction.guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
            if isinstance(admin_channel, discord.TextChannel):
                try: 
                    msg = await admin_channel.fetch_message(data["admin_message_id"])
                    await msg.delete()
                except Exception: 
                    pass
                    
        ticket_data.pop(str(interaction.channel.id), None)
        save_json(TICKETS_FILE, ticket_data)
        await asyncio.sleep(2)
        await interaction.channel.delete()

class TicketManageView(discord.ui.View):
    def __init__(self, owner_id=None): 
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="claim_ticket_button")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.")
        
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(str(interaction.channel.id))
        owner_id = data.get("user_id") if data else None
        if owner_id and interaction.user.id != owner_id and not interaction.user.guild_permissions.manage_channels: 
            return await interaction.response.send_message("No permission.", ephemeral=True)
        await interaction.response.send_message("Are you sure you want to close this ticket?", view=CloseConfirmView(), ephemeral=True)

class PromoCodeModal(discord.ui.Modal, title="Gutscheincode einlösen"):
    code_input = discord.ui.TextInput(label="Promo Code", placeholder="z.B. VALE20", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data:
            return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
            
        owner_id = data.get("user_id")
        if interaction.user.id != owner_id and not interaction.user.guild_permissions.manage_channels: 
            return await interaction.response.send_message("Only buyer.", ephemeral=True)
            
        code = str(self.code_input).strip().upper()
        if code not in promos_db or promos_db[code]["uses"] <= 0: 
            return await interaction.response.send_message("❌ Ungültiger Code.", ephemeral=True)
            
        data["applied_promo"] = code
        save_json(TICKETS_FILE, ticket_data)
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message(f"✅ Gutschein `{code}` angewendet! (-{promos_db[code]['discount']}%)", ephemeral=True)

class GenericCryptoTxidModal(discord.ui.Modal, title="Paste your Crypto TXID here"):
    txid_input = discord.ui.TextInput(label="Transaction Hash (TXID)", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data:
            return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
            
        txid = str(self.txid_input).strip()
        data["last_txid"] = txid
        data["status"] = "reviewing"
        save_json(TICKETS_FILE, ticket_data)
        
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if review_channel: 
            embed = discord.Embed(title="🪙 Crypto TXID Submitted", description=f"**Buyer:** {interaction.user.mention}\n**Ticket:** <#{interaction.channel.id}>\n**TXID:** `{txid}`", color=COLOR_PENDING)
            await review_channel.send(content=f"<@&{STAFF_ROLE_ID}> Review needed.", embed=embed, view=ReviewView())
            
        await interaction.channel.send(embed=discord.Embed(title="✅ TXID Submitted", description="Sent to staff.", color=COLOR_SUCCESS))
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("Submitted.", ephemeral=True)

class LitecoinTxidModal(discord.ui.Modal, title="Paste your Litecoin TXID here"):
    txid_input = discord.ui.TextInput(label="Litecoin TXID", required=True, min_length=64, max_length=64)
    
    async def on_submit(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data:
            return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
            
        txid = str(self.txid_input).strip()
        
        if txid in used_txids_db: 
            return await interaction.response.send_message("Already submitted.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True, thinking=True)
        tx_data, err = await fetch_ltc_tx(txid)
        
        if err or not tx_data: 
            return await interaction.followup.send(f"API Error. {err}", ephemeral=True)
            
        conf = int(tx_data.get("confirmations", 0))
        f_addr, tot_litoshi = tx_matches_our_address(tx_data, LITECOIN_ADDRESS)
        tot_ltc = litoshi_to_ltc(tot_litoshi)
        
        used_txids_db[txid] = {"user_id": str(interaction.user.id), "used_at": iso_now()}
        save_json(USED_TXIDS_FILE, used_txids_db)
        
        data["last_txid"] = txid
        data["status"] = "reviewing"
        save_json(TICKETS_FILE, ticket_data)
        
        emb = discord.Embed(title="🪙 Litecoin TXID Result", description=f"**Address Match:** {'Yes' if f_addr else 'No'}\n**Confirmations:** {conf}\n**Received:** {tot_ltc:.8f} LTC", color=COLOR_SUCCESS if f_addr and conf >= LTC_MIN_CONFIRMATIONS else COLOR_PENDING)
        await interaction.channel.send(embed=emb)
        await update_payment_summary_message(interaction.channel)
        await interaction.followup.send("TXID Check done.", ephemeral=True)

class PaymentActionView(discord.ui.View):
    def __init__(self, owner_id=None): 
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Promo Code", style=discord.ButtonStyle.secondary, emoji="🎟️", custom_id="apply_promo_button")
    async def apply_promo(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.send_modal(PromoCodeModal())
        
    @discord.ui.button(label="Payment Sent", style=discord.ButtonStyle.success, emoji="✅", custom_id="payment_sent_button")
    async def payment_sent(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(str(interaction.channel.id))
        if not data:
            return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
            
        data["status"] = "reviewing"
        save_json(TICKETS_FILE, ticket_data)
        
        buyer = interaction.guild.get_member(data["user_id"])
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        
        if review_channel: 
            embed = discord.Embed(title="🧾 Payment Review", description=f"Buyer: {buyer.mention if buyer else 'Unknown'}\nTicket: <#{interaction.channel.id}>", color=COLOR_WARN)
            await review_channel.send(content=f"<@&{STAFF_ROLE_ID}> New payment to review.", embed=embed, view=ReviewView())
            
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("Staff notified.", ephemeral=True)
        
    @discord.ui.button(label="Submit LTC TXID", style=discord.ButtonStyle.primary, emoji="🪙", custom_id="submit_txid_button")
    async def submit_txid(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.send_modal(LitecoinTxidModal())
        
    @discord.ui.button(label="Submit Crypto TXID", style=discord.ButtonStyle.primary, emoji="🔗", custom_id="submit_generic_txid_button")
    async def submit_generic_txid(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.send_modal(GenericCryptoTxidModal())

class PaymentSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="PayPal", value="paypal", emoji="💸"), 
            discord.SelectOption(label="Litecoin", value="litecoin", emoji="🪙"), 
            discord.SelectOption(label="Ethereum", value="ethereum", emoji="🔷"), 
            discord.SelectOption(label="Solana", value="solana", emoji="🟣"), 
            discord.SelectOption(label="Paysafecard", value="paysafecard", emoji="💳"), 
            discord.SelectOption(label="Amazon Card", value="amazoncard", emoji="🎁")
        ]
        super().__init__(placeholder="💳 Choose payment method", min_values=1, max_values=1, options=options, custom_id="buy_payment_select")
        
    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data:
            return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
            
        data["payment_key"] = self.values[0]
        save_json(TICKETS_FILE, ticket_data)
        
        buyer = interaction.guild.get_member(data["user_id"])
        ltc_price = await fetch_ltc_price_eur() if self.values[0] == "litecoin" else None
        
        await interaction.response.send_message(embed=build_order_summary(data["product_key"], self.values[0], buyer, ltc_price), view=PaymentActionView())
        await update_payment_summary_message(interaction.channel)

class PaymentSelectView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
        self.add_item(PaymentSelect())

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1 Day", description="5€", value="day_1", emoji="📅"), 
            discord.SelectOption(label="1 Week", description="15€", value="week_1", emoji="🗓️"), 
            discord.SelectOption(label="Lifetime", description="30€", value="lifetime", emoji="♾️")
        ]
        super().__init__(placeholder="📦 Choose your product", min_values=1, max_values=1, options=options, custom_id="buy_product_select")
        
    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data:
            return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
            
        data["product_key"] = self.values[0]
        save_json(TICKETS_FILE, ticket_data)
        
        embed = discord.Embed(title="📦 Product Selected", description=f"**{PRODUCTS[self.values[0]]['label']}** selected.\nNow choose your payment method below.", color=COLOR_INFO)
        await interaction.response.send_message(embed=embed, view=PaymentSelectView())
        await update_payment_summary_message(interaction.channel)

class ProductSelectView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
        self.add_item(ProductSelect())

class BuySetupView(discord.ui.View):
    def __init__(self, owner_id=None): 
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Choose Product", style=discord.ButtonStyle.primary, emoji="📦", custom_id="choose_product_button")
    async def choose_product(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.send_message("Select product:", view=ProductSelectView(), ephemeral=True)
        
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_buy_ticket_button")
    async def close_buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.send_message("Are you sure?", view=CloseConfirmView(), ephemeral=True)

class PaymentSummaryView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="refresh_payment_summary")
    async def refresh_summary(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.edit_message(embed=build_payment_summary_embed(interaction.channel.id), view=PaymentSummaryView())

async def process_approve(interaction: discord.Interaction, target_channel_id: int, buyer_id: int):
    try:
        channel = interaction.guild.get_channel(target_channel_id)
        data = ticket_data.get(str(target_channel_id))
        
        if not data:
            return await interaction.response.send_message("❌ Ticket-Daten nicht gefunden. Ticket wurde evtl. gelöscht.", ephemeral=True)
        if data.get("status") == "approved":
            return await interaction.response.send_message("✅ Bereits genehmigt.", ephemeral=True)

        buyer = interaction.guild.get_member(buyer_id)
        
        invoice_id = build_invoice_id()
        data["invoice_id"] = invoice_id
        data["status"] = "approved"
        save_json(TICKETS_FILE, ticket_data)
        
        promo_code = data.get("applied_promo")
        promo_discount = promos_db[promo_code]["discount"] if promo_code and promo_code in promos_db else 0
        if promo_code and promo_code in promos_db: 
            promos_db[promo_code]["uses"] -= 1
            save_json(PROMOS_FILE, promos_db)

        generated_key = generate_key(data["product_key"], ticket_id=str(target_channel_id))
        keys_db[generated_key]["bound_user_id"] = str(buyer.id) if buyer else "Unknown"
        save_json(KEYS_FILE, keys_db)
        
        final_price = get_price(data["product_key"], buyer, promo_discount)
        create_invoice_record(invoice_id, buyer_id, data["product_key"], data["payment_key"], generated_key, target_channel_id, final_price, is_reseller_dc(buyer))
        
        if channel:
            await channel.send(embed=discord.Embed(title="🧾 Payment Approved", description=f"**Invoice:** `{invoice_id}`\n**Price:** {final_price}€\n**Key:** `{generated_key}`", color=COLOR_SUCCESS))
            await update_payment_summary_message(channel)
        
        if buyer: 
            await dm_user_safe(buyer, embed=discord.Embed(title="🔑 Purchase Approved", description=f"**Key:** `{generated_key}`", color=COLOR_SUCCESS))
            
        await interaction.response.send_message("✅ Approved. Key wurde generiert und ans Ticket gesendet.", ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Ein Fehler ist aufgetreten: {str(e)}", ephemeral=True)

async def process_deny(interaction: discord.Interaction, target_channel_id: int):
    try:
        channel = interaction.guild.get_channel(target_channel_id)
        if str(target_channel_id) in ticket_data: 
            ticket_data[str(target_channel_id)]["status"] = "denied"
            save_json(TICKETS_FILE, ticket_data)
            
        if channel:
            await channel.send(embed=discord.Embed(title="❌ Denied", description="Payment was denied.", color=COLOR_DENY))
            await update_payment_summary_message(channel)
            
        await interaction.response.send_message("✅ Denied.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Fehler: {str(e)}", ephemeral=True)


class AdminPanelView(discord.ui.View):
    def __init__(self, owner_id=None, ticket_channel_id=None): 
        super().__init__(timeout=None)

    async def _get_data(self, interaction):
        embed = interaction.message.embeds[0]
        desc = embed.description
        b_match = re.search(r"\*\*Buyer ID:\*\* `?(\d+)`?", desc)
        t_match = re.search(r"\*\*Ticket ID:\*\* `?(\d+)`?", desc)
        if not b_match or not t_match: return None, None
        return int(t_match.group(1)), int(b_match.group(1))
        
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="adminpanel_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Daten konnten nicht gelesen werden.", ephemeral=True)
        await process_approve(interaction, t_id, b_id)
        
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="adminpanel_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Daten konnten nicht gelesen werden.", ephemeral=True)
        await process_deny(interaction, t_id)

class ReviewView(discord.ui.View):
    def __init__(self, target_channel_id=None, buyer_id=None): 
        super().__init__(timeout=None)

    async def _get_data(self, interaction):
        embed = interaction.message.embeds[0]
        desc = embed.description
        b_match = re.search(r"<@!?(\d+)>", desc)
        t_match = re.search(r"<#(\d+)>", desc)
        if not b_match or not t_match: return None, None
        return int(t_match.group(1)), int(b_match.group(1))

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="review_approve_button")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Fehler beim Lesen der Ticket-ID.", ephemeral=True)
        await process_approve(interaction, t_id, b_id)
        
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="review_deny_button")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Fehler beim Lesen der Ticket-ID.", ephemeral=True)
        await process_deny(interaction, t_id)

class MainTicketPanelView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="💠", custom_id="main_support_ticket_button")
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await self.create_ticket_channel(interaction, "support")
        
    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, emoji="🛒", custom_id="main_buy_ticket_button")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await self.create_ticket_channel(interaction, "buy")
        
    async def create_ticket_channel(self, interaction: discord.Interaction, ticket_type: str):
        guild, user = interaction.guild, interaction.user
        
        if is_blacklisted(user.id): 
            return await interaction.response.send_message("Blacklisted.", ephemeral=True)
            
        existing = await find_existing_ticket(guild, user)
        if existing: 
            return await interaction.response.send_message(f"Ticket open: {existing.mention}", ephemeral=True)
            
        category = guild.get_channel(BUY_CATEGORY_ID if ticket_type == "buy" else SUPPORT_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False), 
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        
        bot_member = guild.get_member(bot.user.id)
        if bot_member: 
            overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            
        staff_role = guild.get_role(STAFF_ROLE_ID)
        if staff_role: 
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)

        channel_name = f"{ticket_type}-{user.name}"[:90]
        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=f"ticket_owner:{user.id}")

        if ticket_type == "support":
            await channel.send(content=f"{user.mention} <@&{STAFF_ROLE_ID}>", embed=discord.Embed(title="💠 Support Ticket", description="Please describe your issue.", color=COLOR_SUPPORT), view=TicketManageView())
        else:
            ticket_data[str(channel.id)] = {
                "user_id": user.id, 
                "product_key": None, 
                "payment_key": None, 
                "last_txid": None, 
                "invoice_id": None, 
                "status": "waiting", 
                "applied_promo": None
            }
            save_json(TICKETS_FILE, ticket_data)
            
            await channel.send(content=f"{user.mention} <@&{STAFF_ROLE_ID}>", embed=discord.Embed(title="🛒 Buy Ticket", description="Click 'Choose Product' below.", color=COLOR_BUY), view=BuySetupView())
            await send_summary_and_admin_panels(channel, user.id)

        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)


class RedeemKeyModal(discord.ui.Modal, title="Paste your key here"):
    key_input = discord.ui.TextInput(label="Key", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, res = await redeem_key_for_user(interaction.guild, interaction.user, str(self.key_input).strip().upper())
        if ok: 
            await interaction.followup.send(f"✅ Success! You received the {PRODUCTS[res]['label']} role.", ephemeral=True)
        else: 
            await interaction.followup.send(f"❌ {res}", ephemeral=True)

class RedeemPanelView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Redeem", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="redeem_key_button")
    async def redeem_button(self, interaction: discord.Interaction, button: discord.ui.Button): 
        await interaction.response.send_modal(RedeemKeyModal())

# =========================================================
# EVENTS
# =========================================================
@bot.event
async def on_member_join(member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel): 
        return
        
    embed = discord.Embed(
        title="Welcome!", 
        description=f"Welcome {member.mention} to **{SERVER_NAME}**.\n\nRead the rules in <#{RULES_CHANNEL_ID}> to get started!", 
        color=COLOR_WELCOME
    )
    embed.set_author(name=SERVER_NAME, icon_url=WELCOME_THUMBNAIL_URL)
    embed.set_thumbnail(url=WELCOME_THUMBNAIL_URL)
    embed.set_image(url=WELCOME_BANNER_URL)
    
    try: 
        await channel.send(embed=embed)
    except Exception: 
        pass

# =========================================================
# SLASH COMMANDS
# =========================================================
@bot.tree.command(name="gen_admin_key", description="Generiert einen ADMIN-Einladungs-Key für die Website")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gen_admin_key(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("Admins only.", ephemeral=True)
        
    new_key = f"VALE-ADMIN-{random_block(6)}"
    webkeys_db[new_key] = {
        "role": "admin", 
        "used": False, 
        "created_by": str(interaction.user.name), 
        "created_at": iso_now()
    }
    save_json(WEBKEYS_FILE, webkeys_db)
    
    ch = interaction.guild.get_channel(WEB_KEY_CHANNEL_ID)
    if ch: 
        embed = discord.Embed(
            title="🔐 Admin Registration Key", 
            description=f"**Erstellt von:** {interaction.user.mention}\n**Key:** `{new_key}`\n\nNutze diesen Key, um dir einen Admin-Account auf der Website zu erstellen.", 
            color=COLOR_MAIN
        )
        await ch.send(embed=embed)
        
    await interaction.response.send_message(f"Admin Invite Key generiert: `{new_key}`", ephemeral=True)


@bot.tree.command(name="gen_reseller_key", description="Generiert einen RESELLER-Einladungs-Key für die Website")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gen_reseller_key(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("Admins only.", ephemeral=True)
        
    new_key = f"VALE-RES-{random_block(6)}"
    webkeys_db[new_key] = {
        "role": "reseller", 
        "used": False, 
        "created_for": str(user.name), 
        "created_at": iso_now()
    }
    save_json(WEBKEYS_FILE, webkeys_db)
    
    ch = interaction.guild.get_channel(WEB_KEY_CHANNEL_ID)
    if ch: 
        embed = discord.Embed(
            title="🔐 Reseller Registration Key", 
            description=f"**Für User:** {user.mention}\n**Key:** `{new_key}`\n\nMit diesem Key kannst du dich registrieren.", 
            color=COLOR_SUCCESS
        )
        await ch.send(embed=embed)
        
    await interaction.response.send_message(f"Reseller Invite Key generiert: `{new_key}`", ephemeral=True)


@bot.tree.command(name="ticket", description="Open the Gen ticket panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✦ VALE GEN TICKET CENTER ✦", 
        description=f"{premium_divider()}\n**Open a private ticket below**\n\n💠 **Support**\n> Help, questions, issues\n\n🛒 **Buy**\n> Orders, payments, purchase setup\n\n{premium_divider()}\n**Fast • Private • Premium**", 
        color=COLOR_MAIN
    )
    embed.set_image(url=PANEL_IMAGE_URL)
    await interaction.response.send_message(embed=embed, view=MainTicketPanelView())


@bot.tree.command(name="send_redeem_panel", description="Send the redeem panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_redeem_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🎟️ VALE GEN REDEEM CENTER", description="Click to redeem your key.", color=COLOR_MAIN)
    await interaction.response.send_message(embed=embed, view=RedeemPanelView())


@bot.tree.command(name="vouch", description="Hinterlasse eine Bewertung für deinen Kauf!")
@app_commands.describe(sterne="Wie viele Sterne gibst du?", produkt="Was hast du gekauft?", bewertung="Deine Erfahrung")
@app_commands.choices(sterne=[
    app_commands.Choice(name="⭐⭐⭐⭐⭐", value=5), 
    app_commands.Choice(name="⭐⭐⭐⭐", value=4), 
    app_commands.Choice(name="⭐⭐⭐", value=3)
])
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def vouch(interaction: discord.Interaction, sterne: app_commands.Choice[int], produkt: str, bewertung: str):
    ch = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if ch: 
        embed = discord.Embed(title=f"Vouch: {sterne.name}", description=f'"{bewertung}"', color=COLOR_MAIN)
        embed.add_field(name="Käufer", value=interaction.user.mention)
        embed.add_field(name="Produkt", value=produkt)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await ch.send(embed=embed)
    await interaction.response.send_message("✅ Danke für deine Bewertung!", ephemeral=True)


@bot.tree.command(name="send_rules", description="Postet das Regelwerk")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_rules(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("Admins only.", ephemeral=True)
        
    embed = discord.Embed(
        title="📜 Server Rules", 
        description="**1. Be Respectful**\nBehandel alle Mitglieder mit Respekt. Keine Beleidigungen, kein Rassismus, kein Spam.\n\n**2. No DM Advertising**\nKeine Werbung für andere Server oder Dienste in den DMs unserer Nutzer.\n\n**3. Support & Tickets**\nBitte eröffne für alle Anfragen oder Käufe ein Ticket im <#1490336321913356459> Bereich. Kein Support in normalen Chats.\n\n**4. Scam & Fraud**\nBetrugsversuche beim Kauf führen zu einem permanenten Ban und Blacklist.", 
        color=COLOR_WELCOME
    )
    embed.set_image(url=WELCOME_BANNER_URL)
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("Regelwerk gepostet!", ephemeral=True)


@bot.tree.command(name="test_welcome", description="Testet die Welcome-Nachricht")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def test_welcome(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("Admins only.", ephemeral=True)
        
    await interaction.response.send_message("Simuliere Server-Beitritt...", ephemeral=True)
    bot.dispatch('member_join', interaction.user)

# =========================================================
# MAIN STARTUP
# =========================================================
if __name__ == "__main__":
    bot.run(TOKEN)
