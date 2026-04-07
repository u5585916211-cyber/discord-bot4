import os
import re
import json
import uuid
import asyncio
import aiohttp
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from aiohttp import web
import discord
from discord.ext import commands
from discord import app_commands

# =========================================================
# ENV VARIABLES
# =========================================================
TOKEN = os.getenv("TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

# --- EMAIL SMTP SETUP ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.firstmail.ltd")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER") 
SMTP_PASS = os.getenv("SMTP_PASS") 

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

WEBSITE_LOGO_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751701567934535/velo.png?ex=69d53236&is=69d3e0b6&hm=eeed157a58f5f3f309bb4de50df0c75e39fd90df368b4c09c666205a1611f4f9&=&format=webp&quality=lossless&width=652&height=652"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751958573645834/velo_log.png?ex=69d53273&is=69d3e0f3&hm=fe4fa4ac26ac8b32e1b67f540471804215ac6ed4767630e956057708b85cb89d&=&format=webp&quality=lossless&width=652&height=652"

WELCOME_THUMBNAIL_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751701567934535/velo.png?ex=69d53236&is=69d3e0b6&hm=eeed157a58f5f3f309bb4de50df0c75e39fd90df368b4c09c666205a1611f4f9&=&format=webp&quality=lossless&width=652&height=652"
WELCOME_BANNER_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751958573645834/velo_log.png?ex=69d53273&is=69d3e0f3&hm=fe4fa4ac26ac8b32e1b67f540471804215ac6ed4767630e956057708b85cb89d&=&format=webp&quality=lossless&width=652&height=652"

SAFE_WEBSITE_LOGO_URL = WEBSITE_LOGO_URL.replace("&", "&amp;")

# Zahlungsdaten
PAYPAL_EMAIL = "hydrasupfivem@gmail.com"
LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"
ETHEREUM_ADDRESS = "0x6Ba2afdA7e61817f9c27f98ffAfe9051F9ad8167"
SOLANA_ADDRESS = "DnzXgySsPnSdEKsMJub21dBjM6bcT2jtic73VeutN3p4"

LTC_MIN_CONFIRMATIONS = 1

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
BLACKLIST_FILE = "blacklist.json"
INVOICES_FILE = "invoices.json"
PROMOS_FILE = "promos.json"
ACTIVITY_FILE = "activity.json"
WEBKEYS_FILE = "web_keys.json"
USERS_FILE = "web_users.json"
TICKETS_FILE = "tickets.json"
SESSIONS_FILE = "sessions.json"

PRODUCTS = {
    "day_1": {"label": "1 Day", "price_eur": 5, "duration_days": 1, "key_prefix": "GEN-1D"},
    "week_1": {"label": "1 Week", "price_eur": 15, "duration_days": 7, "key_prefix": "GEN-1W"},
    "lifetime": {"label": "Lifetime", "price_eur": 30, "duration_days": 0, "key_prefix": "GEN-LT"}
}

PAYMENTS = {
    "paypal": {"label": "PayPal", "emoji": "💸"},
    "litecoin": {"label": "Litecoin", "emoji": "🪙"},
    "ethereum": {"label": "Ethereum", "emoji": "🔷"},
    "solana": {"label": "Solana", "emoji": "🟣"},
    "paysafecard": {"label": "Paysafecard", "emoji": "💳"},
    "amazoncard": {"label": "Amazon Card", "emoji": "🎁"}
}

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

ticket_data = load_json(TICKETS_FILE, {})
keys_db = load_json(KEYS_FILE, {})
redeemed_db = load_json(REDEEMED_FILE, {})
used_txids_db = load_json(USED_TXIDS_FILE, {})
blacklist_db = load_json(BLACKLIST_FILE, {})
invoices_db = load_json(INVOICES_FILE, {})
promos_db = load_json(PROMOS_FILE, {})
activity_db = load_json(ACTIVITY_FILE, [])
webkeys_db = load_json(WEBKEYS_FILE, {})
users_db = load_json(USERS_FILE, {})
web_sessions = load_json(SESSIONS_FILE, {})

ticket_locks = set()

def log_activity(action, user="System"):
    global activity_db
    activity_db.insert(0, {"time": iso_now(), "user": str(user), "action": action})
    activity_db = activity_db[:50]
    save_json(ACTIVITY_FILE, activity_db)

def now_utc(): return datetime.now(timezone.utc)
def iso_now(): return now_utc().isoformat()
def random_block(length=4): return uuid.uuid4().hex[:length].upper()
def build_invoice_id() -> str: return f"GEN-{uuid.uuid4().hex[:10].upper()}"
def is_blacklisted(user_id: int): return str(user_id) in blacklist_db

# --- AUTO-CHECKER & MAIL SENDEN ---
async def verify_ltc_payment(txid):
    if txid in used_txids_db: 
        return False, "Diese TXID wurde bereits verwendet."
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=15) as resp:
            if resp.status != 200: 
                return False, "Ungültige TXID oder API offline."
            data = await resp.json()
            for out in data.get("outputs", []):
                if LITECOIN_ADDRESS in out.get("addresses", []):
                    used_txids_db[txid] = {"time": iso_now()}
                    save_json(USED_TXIDS_FILE, used_txids_db)
                    return True, "Zahlung verifiziert."
    return False, "Keine Zahlung an unsere LTC Adresse gefunden."

def send_delivery_email(to_email, product_label, key):
    if not SMTP_USER or not SMTP_PASS: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Deine Bestellung bei {SERVER_NAME} ist da! 🎉"
        body = f"Hallo!\n\nVielen Dank für deinen Einkauf bei {SERVER_NAME}.\n\nProdukt: {product_label}\nKey: {key}\n\nDu kannst diesen Key auf unserer Website im 'Customer' Login verwenden oder direkt in unserem Discord-Server einlösen.\n\nViel Spaß!"
        msg.attach(MIMEText(body, 'plain'))
        if SMTP_PORT == 465: server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else: server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT); server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Mail Error: {e}")
        return False

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
# 🌍 WEB DASHBOARD HTML (LUSIVE STYLE + PAYPAL)
# =========================================================
WEB_HTML = """
<!DOCTYPE html>
<html lang="de" class="dark">
<head>
    <meta charset="UTF-8">
    <title>VALE GEN | STORE</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #050505; color: #e5e7eb; margin: 0; overflow-x: hidden; }
        
        /* Lusive Background */
        .deep-bg { position: fixed; inset: 0; background: radial-gradient(circle at 50% 0%, #160a28 0%, #050505 60%); z-index: -2; }
        .grid-bg { position: fixed; inset: 0; background-image: linear-gradient(rgba(168, 85, 247, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(168, 85, 247, 0.05) 1px, transparent 1px); background-size: 40px 40px; z-index: -1; }

        /* Premium Glass Cards */
        .glass { background: rgba(10, 10, 15, 0.6); backdrop-filter: blur(20px); border: 1px solid rgba(168, 85, 247, 0.15); transition: all 0.3s ease; }
        .glass:hover { border-color: rgba(168, 85, 247, 0.5); box-shadow: 0 0 40px rgba(168, 85, 247, 0.2); }
        
        /* Neon Texts */
        .glow-text { background: linear-gradient(90deg, #c084fc, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 0 15px rgba(192,132,252,0.4)); }
        
        .hidden-view { display: none !important; }
        .tab-content { display: none; } 
        .tab-content.active { display: block; animation: fadeIn 0.4s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: #050505; } ::-webkit-scrollbar-thumb { background: #9333ea; border-radius: 4px; }
        
        /* Input Fields */
        .premium-input { background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); color: white; transition: 0.3s; }
        .premium-input:focus { border-color: #a855f7; outline: none; box-shadow: inset 0 0 10px rgba(168,85,247,0.2); }
    </style>
</head>
<body class="flex flex-col h-screen selection:bg-purple-500 selection:text-white relative">

    <div class="deep-bg"></div>
    <div class="grid-bg"></div>

    <nav class="w-full px-8 py-6 flex justify-between items-center z-50 border-b border-white/5 bg-black/20 backdrop-blur-md sticky top-0">
        <div class="flex items-center gap-3 cursor-pointer" onclick="switchAuth('shop')">
            <img src="LOGO_URL_PLACEHOLDER" class="h-10 w-10 rounded-xl shadow-[0_0_15px_rgba(168,85,247,0.4)] object-cover">
            <span class="text-2xl font-black tracking-widest uppercase">VALE <span class="glow-text">GEN</span></span>
        </div>
        <div class="flex gap-6">
            <button onclick="switchAuth('shop')" class="font-bold text-gray-400 hover:text-white transition uppercase tracking-widest text-sm">Store</button>
            <button onclick="switchAuth('login')" class="font-bold text-purple-400 hover:text-purple-300 transition uppercase tracking-widest text-sm bg-purple-500/10 border border-purple-500/30 px-5 py-2 rounded-xl hover:bg-purple-500/20">Portal</button>
        </div>
    </nav>

    <div class="flex-1 w-full relative z-10 overflow-y-auto">
        
        <div id="view-shop" class="w-full max-w-7xl mx-auto px-6 pt-20 pb-24">
            <div class="text-center mb-20">
                <h1 class="text-6xl md:text-8xl font-black mb-6 tracking-tighter uppercase">Automate your <span class="glow-text">Success.</span></h1>
                <p class="text-gray-400 text-xl font-medium max-w-2xl mx-auto">Instant Crypto & PayPal Delivery. Vollautomatisches System.</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-t-4 border-purple-500 group">
                    <div class="bg-purple-500/10 text-purple-400 px-4 py-1 rounded-full text-xs font-black tracking-widest mb-6 border border-purple-500/20">STARTER</div>
                    <h3 class="text-3xl font-black mb-2 tracking-wide uppercase">1 Day Key</h3>
                    <div class="text-5xl font-black text-white mb-8">5.00€</div>
                    <ul class="text-gray-400 space-y-4 mb-10 w-full text-sm font-bold">
                        <li class="flex items-center"><i class="fa-solid fa-check text-purple-500 mr-3 text-lg"></i>24 Hours Access</li>
                        <li class="flex items-center"><i class="fa-solid fa-check text-purple-500 mr-3 text-lg"></i>Full Features</li>
                    </ul>
                    <button onclick="openCheckout('day_1', '5.00')" class="mt-auto w-full bg-white/5 border border-white/10 hover:bg-purple-600 hover:border-purple-500 py-4 rounded-xl font-black uppercase tracking-widest transition text-white group-hover:shadow-[0_0_20px_rgba(168,85,247,0.4)]">Purchase</button>
                </div>
                
                <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-t-4 border-pink-500 transform md:scale-105 relative z-10 shadow-[0_0_50px_rgba(236,72,153,0.15)] group">
                    <div class="absolute -top-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white text-[10px] font-black px-6 py-1.5 rounded-full uppercase tracking-widest shadow-lg">Bestseller</div>
                    <div class="bg-pink-500/10 text-pink-400 px-4 py-1 rounded-full text-xs font-black tracking-widest mb-6 border border-pink-500/20">POPULAR</div>
                    <h3 class="text-3xl font-black mb-2 tracking-wide uppercase">1 Week Key</h3>
                    <div class="text-6xl font-black text-white mb-8 drop-shadow-[0_0_15px_rgba(236,72,153,0.5)]">15.00€</div>
                    <ul class="text-gray-300 space-y-4 mb-10 w-full text-sm font-bold">
                        <li class="flex items-center"><i class="fa-solid fa-check text-pink-500 mr-3 text-lg"></i>7 Days Access</li>
                        <li class="flex items-center"><i class="fa-solid fa-check text-pink-500 mr-3 text-lg"></i>Full Features</li>
                        <li class="flex items-center"><i class="fa-solid fa-bolt text-pink-500 mr-3 text-lg"></i>Priority Support</li>
                    </ul>
                    <button onclick="openCheckout('week_1', '15.00')" class="mt-auto w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 py-4 rounded-xl font-black uppercase tracking-widest transition text-white shadow-[0_0_20px_rgba(236,72,153,0.4)]">Purchase</button>
                </div>
                
                <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-t-4 border-blue-500 group">
                    <div class="bg-blue-500/10 text-blue-400 px-4 py-1 rounded-full text-xs font-black tracking-widest mb-6 border border-blue-500/20">ULTIMATE</div>
                    <h3 class="text-3xl font-black mb-2 tracking-wide uppercase">Lifetime Key</h3>
                    <div class="text-5xl font-black text-white mb-8">30.00€</div>
                    <ul class="text-gray-400 space-y-4 mb-10 w-full text-sm font-bold">
                        <li class="flex items-center"><i class="fa-solid fa-check text-blue-500 mr-3 text-lg"></i>Permanent Access</li>
                        <li class="flex items-center"><i class="fa-solid fa-check text-blue-500 mr-3 text-lg"></i>All Features</li>
                        <li class="flex items-center"><i class="fa-solid fa-star text-blue-500 mr-3 text-lg"></i>VIP Discord Role</li>
                    </ul>
                    <button onclick="openCheckout('lifetime', '30.00')" class="mt-auto w-full bg-white/5 border border-white/10 hover:bg-blue-600 hover:border-blue-500 py-4 rounded-xl font-black uppercase tracking-widest transition text-white group-hover:shadow-[0_0_20px_rgba(59,130,246,0.4)]">Purchase</button>
                </div>
            </div>
        </div>

        <div id="view-auth" class="w-full max-w-md mx-auto pt-20 hidden-view px-6">
            <div class="glass p-10 rounded-[2rem] relative shadow-[0_0_50px_rgba(168,85,247,0.1)] border-purple-500/30">
                <div class="text-center mb-8">
                    <img src="LOGO_URL_PLACEHOLDER" class="h-20 mx-auto mb-4 shadow-[0_0_20px_rgba(168,85,247,0.6)] rounded-xl">
                    <h2 class="text-2xl font-black tracking-widest uppercase glow-text">Portal</h2>
                </div>

                <div class="flex bg-black/40 p-1 rounded-xl border border-white/10 mb-8">
                    <button onclick="switchAuthTab('customer')" id="tab-btn-customer" class="flex-1 py-3 text-xs font-black rounded-lg text-white bg-white/10 transition uppercase tracking-widest">Customer</button>
                    <button onclick="switchAuthTab('login')" id="tab-btn-login" class="flex-1 py-3 text-xs font-black rounded-lg text-gray-500 hover:text-white transition uppercase tracking-widest">Admin</button>
                    <button onclick="switchAuthTab('register')" id="tab-btn-register" class="flex-1 py-3 text-xs font-black rounded-lg text-gray-500 hover:text-white transition uppercase tracking-widest">Register</button>
                </div>

                <div id="form-customer" class="space-y-4">
                    <input type="text" id="c-key" class="premium-input w-full rounded-xl px-5 py-4 font-mono text-pink-400 text-center tracking-widest" placeholder="GEN-...">
                    <button onclick="customerLogin()" class="w-full bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white font-black py-4 rounded-xl uppercase tracking-widest transition shadow-[0_0_20px_rgba(236,72,153,0.3)] mt-2">Access Dashboard</button>
                </div>

                <div id="form-login" class="space-y-4 hidden-view">
                    <input type="text" id="l-user" class="premium-input w-full rounded-xl px-5 py-4" placeholder="Username">
                    <input type="password" id="l-pass" class="premium-input w-full rounded-xl px-5 py-4" placeholder="Password">
                    <button onclick="login()" class="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-black py-4 rounded-xl uppercase tracking-widest transition shadow-[0_0_20px_rgba(168,85,247,0.3)] mt-2">Login</button>
                </div>

                <div id="form-register" class="space-y-4 hidden-view">
                    <input type="text" id="r-user" class="premium-input w-full rounded-xl px-5 py-4" placeholder="Username">
                    <input type="password" id="r-pass" class="premium-input w-full rounded-xl px-5 py-4" placeholder="Password">
                    <input type="text" id="r-key" class="premium-input w-full rounded-xl px-5 py-4 font-mono text-purple-400" placeholder="Invite Key (VALE-...)">
                    <button onclick="register()" class="w-full bg-white/10 hover:bg-white/20 border border-white/10 text-white font-black py-4 rounded-xl uppercase tracking-widest transition mt-2">Create Account</button>
                </div>
                
                <p id="auth-error" class="text-red-400 mt-6 text-sm text-center font-bold hidden"></p>
            </div>
        </div>

        <div id="checkout-modal" class="fixed inset-0 bg-black/95 backdrop-blur-xl hidden-view flex items-center justify-center p-4 z-50">
            <div class="glass p-8 md:p-12 rounded-[2.5rem] border border-purple-500/30 shadow-[0_0_80px_rgba(168,85,247,0.2)] max-w-lg w-full relative">
                <button onclick="closeCheckout()" class="absolute top-6 right-8 text-gray-500 hover:text-white text-3xl transition">&times;</button>
                <h2 class="text-3xl font-black text-white mb-2 text-center uppercase tracking-widest">Checkout</h2>
                <p class="text-center text-gray-400 font-bold mb-8"><span id="co-price" class="text-white text-xl"></span>€</p>
                
                <div id="co-step-1">
                    <div class="flex gap-4 mb-6">
                        <button id="gw-ltc" onclick="setGw('ltc')" class="flex-1 py-3 border-2 border-purple-500 bg-purple-500/20 rounded-xl font-bold text-white transition shadow-[0_0_15px_rgba(168,85,247,0.3)]"><i class="fa-solid fa-litecoin-sign mr-2"></i>Litecoin</button>
                        <button id="gw-paypal" onclick="setGw('paypal')" class="flex-1 py-3 border-2 border-white/10 bg-black/50 rounded-xl font-bold text-gray-400 hover:text-white transition"><i class="fa-brands fa-paypal mr-2 text-blue-400"></i>PayPal</button>
                    </div>

                    <input type="email" id="co-email" class="premium-input w-full rounded-xl px-5 py-4 mb-6" placeholder="Deine E-Mail Adresse">
                    
                    <div id="details-ltc" class="mb-6 bg-purple-500/5 border border-purple-500/20 p-5 rounded-2xl">
                        <p class="text-xs font-black text-purple-400 uppercase tracking-widest mb-3 text-center">Sende LTC an:</p>
                        <div class="bg-black/60 p-3 rounded-lg font-mono text-xs text-gray-300 break-all border border-white/10 mb-4 text-center cursor-pointer hover:bg-black transition" onclick="navigator.clipboard.writeText('LTC_ADDR'); alert('Kopiert!')">LTC_ADDR</div>
                        <input type="text" id="co-txid" class="premium-input w-full rounded-xl px-5 py-4 font-mono text-sm" placeholder="Transaktions-Hash (TXID)...">
                    </div>

                    <div id="details-paypal" class="mb-6 bg-blue-500/5 border border-blue-500/20 p-5 rounded-2xl hidden-view">
                        <p class="text-xs font-black text-blue-400 uppercase tracking-widest mb-3 text-center">Sende als Freunde & Familie:</p>
                        <div class="bg-black/60 p-3 rounded-lg font-bold text-sm text-gray-300 border border-white/10 mb-4 text-center cursor-pointer hover:bg-black transition" onclick="navigator.clipboard.writeText('PP_EMAIL'); alert('Kopiert!')">PP_EMAIL</div>
                        <input type="text" id="co-pp-proof" class="premium-input w-full rounded-xl px-5 py-4 text-sm" placeholder="Dein PayPal Name (als Beweis)...">
                    </div>
                    
                    <p id="co-error" class="text-red-400 mb-4 text-sm font-bold text-center hidden"></p>
                    <button onclick="processCheckout()" id="btn-checkout" class="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white font-black py-5 rounded-xl uppercase tracking-widest text-sm mt-2 transition shadow-[0_0_20px_rgba(236,72,153,0.4)]">Zahlung Verifizieren</button>
                </div>

                <div id="co-step-2" class="hidden-view text-center py-6">
                    <i class="fa-solid fa-shield-check text-7xl text-green-500 mb-6 drop-shadow-[0_0_20px_rgba(34,197,94,0.5)]"></i>
                    <h3 class="text-2xl font-black text-white mb-2 uppercase tracking-widest">Erfolgreich!</h3>
                    <p class="text-gray-400 mb-8 font-medium">Dein Key wurde auch an deine Mail gesendet.</p>
                    <div class="bg-black/60 border border-green-500/50 p-5 rounded-2xl mb-8">
                        <p class="text-xs text-green-400 font-bold uppercase tracking-widest mb-2">Dein Key</p>
                        <p id="co-success-key" class="font-mono text-white text-lg font-black tracking-wider break-all select-all"></p>
                    </div>
                    <button onclick="window.location.reload()" class="w-full bg-white/10 hover:bg-white/20 border border-white/10 text-white font-black py-4 rounded-xl uppercase tracking-widest transition">Zum Dashboard</button>
                </div>
            </div>
        </div>

        <div id="view-customer" class="flex w-full h-full hidden-view p-6 md:p-12 relative">
            <div class="max-w-4xl mx-auto w-full">
                <header class="flex justify-between items-center mb-8 glass p-6 rounded-3xl">
                    <div class="flex items-center">
                        <img src="LOGO_URL_PLACEHOLDER" class="h-16 mr-4 rounded-xl shadow-[0_0_15px_rgba(236,72,153,0.4)]">
                        <div>
                            <h1 class="text-2xl font-black text-white uppercase tracking-widest">Customer</h1>
                            <p class="text-sm text-pink-400 font-mono font-bold" id="cust-key-display"></p>
                        </div>
                    </div>
                    <button onclick="logout()" class="bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 px-6 py-3 rounded-xl font-bold transition uppercase tracking-widest text-xs">Logout</button>
                </header>
                <div class="glass p-12 rounded-[3rem] text-center border-t-4 border-pink-500 shadow-[0_0_50px_rgba(236,72,153,0.15)]">
                    <h2 class="text-gray-500 font-black uppercase tracking-widest mb-4 text-sm">Active Plan</h2>
                    <h3 class="text-5xl md:text-6xl font-black text-white glow-text mb-12" id="cust-prod">Loading...</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                        <div class="bg-black/40 p-6 rounded-2xl border border-white/5"><i class="fa-solid fa-shield-halved text-3xl text-pink-400 mb-4"></i><p class="text-xs text-gray-500 font-bold uppercase tracking-widest">Status</p><p class="text-xl font-black text-white mt-2" id="cust-status">Loading</p></div>
                        <div class="bg-black/40 p-6 rounded-2xl border border-white/5"><i class="fa-brands fa-discord text-3xl text-purple-400 mb-4"></i><p class="text-xs text-gray-500 font-bold uppercase tracking-widest">Discord ID</p><p class="text-lg font-mono text-white mt-2" id="cust-discord">None</p></div>
                    </div>
                    <p class="text-xs text-gray-600 font-bold uppercase tracking-widest">Created: <span id="cust-created" class="text-gray-400"></span></p>
                </div>
            </div>
        </div>

        <div id="view-admin" class="flex w-full h-full hidden-view relative px-4 pb-4">
            <aside class="w-64 glass rounded-3xl mr-6 flex flex-col justify-between overflow-hidden border-purple-500/30">
                <div>
                    <div class="h-24 flex items-center justify-center border-b border-white/5 bg-black/20">
                        <span class="text-xl font-black text-white glow-text tracking-widest uppercase">Admin Panel</span>
                    </div>
                    <nav class="p-4 space-y-2 mt-2">
                        <button onclick="nav('dash')" id="btn-dash" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-purple-300 bg-purple-500/10 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-chart-pie w-6"></i> Overview</button>
                        <button onclick="nav('gen')" id="btn-gen" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-bolt w-6"></i> Generator</button>
                        <button onclick="nav('keys')" id="btn-keys" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-key w-6"></i> Keys DB</button>
                        <button onclick="nav('team')" id="btn-team" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-users w-6"></i> Team</button>
                        <button onclick="nav('promos')" id="btn-promos" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-tags w-6"></i> Promos</button>
                        <button onclick="nav('lookup')" id="btn-lookup" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-search w-6"></i> Search</button>
                        <button onclick="nav('announce')" id="btn-announce" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-satellite-dish w-6"></i> Broadcast</button>
                        <button onclick="nav('blacklist')" id="btn-blacklist" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"><i class="fa-solid fa-skull w-6 text-red-400"></i> Blacklist</button>
                    </nav>
                </div>
                <div class="p-4 border-t border-white/5">
                    <button onclick="logout()" class="w-full text-red-400 bg-red-500/10 hover:bg-red-500/20 font-bold py-3 rounded-xl transition text-xs tracking-widest uppercase">Logout</button>
                </div>
            </aside>
            
            <main class="flex-1 glass rounded-3xl overflow-y-auto p-8 border-purple-500/30">
                <div id="dash" class="tab-content active">
                    <h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Dashboard</h2>
                    <div class="grid grid-cols-3 gap-6 mb-8">
                        <div class="bg-black/40 p-8 rounded-3xl border border-white/5"><p class="text-xs font-black text-purple-400 uppercase tracking-widest">Revenue</p><h3 class="text-4xl font-black text-white mt-3" id="stat-rev">0.00€</h3></div>
                        <div class="bg-black/40 p-8 rounded-3xl border border-white/5"><p class="text-xs font-black text-pink-400 uppercase tracking-widest">Orders</p><h3 class="text-4xl font-black text-white mt-3" id="stat-orders">0</h3></div>
                        <div class="bg-black/40 p-8 rounded-3xl border border-white/5"><p class="text-xs font-black text-blue-400 uppercase tracking-widest">Keys</p><h3 class="text-4xl font-black text-white mt-3" id="stat-keys">0</h3></div>
                    </div>
                </div>
                
                <div id="gen" class="tab-content"><h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Generator</h2><div class="space-y-4 max-w-2xl"><button onclick="genAdminKey('day_1')" class="w-full bg-black/40 border border-white/5 hover:border-purple-500/50 p-6 rounded-2xl flex justify-between items-center transition"><span class="font-black text-white tracking-widest uppercase">1 Day</span><i class="fa-solid fa-plus text-purple-400"></i></button><button onclick="genAdminKey('week_1')" class="w-full bg-black/40 border border-white/5 hover:border-pink-500/50 p-6 rounded-2xl flex justify-between items-center transition"><span class="font-black text-white tracking-widest uppercase">1 Week</span><i class="fa-solid fa-plus text-pink-400"></i></button><button onclick="genAdminKey('lifetime')" class="w-full bg-gradient-to-r from-purple-700 to-pink-600 p-6 rounded-2xl flex justify-between items-center transition text-white"><span class="font-black tracking-widest uppercase">Lifetime</span><i class="fa-solid fa-star text-yellow-300"></i></button></div></div>
                <div id="keys" class="tab-content"><h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Database</h2><div class="bg-black/40 rounded-2xl overflow-hidden border border-white/5"><table class="w-full text-left text-sm whitespace-nowrap"><thead class="bg-white/5 text-gray-400"><tr><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Key</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Type</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Used By</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Status</th><th class="px-6 py-4 text-right font-bold tracking-wider uppercase text-xs">Action</th></tr></thead><tbody id="table-keys" class="divide-y divide-white/5"></tbody></table></div></div>
                <div id="team" class="tab-content"><h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Team</h2><div class="bg-black/40 rounded-2xl overflow-hidden border border-white/5"><table class="w-full text-left text-sm"><thead class="bg-white/5 text-gray-400"><tr><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">User</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Gen</th><th class="px-6 py-4 text-right font-bold tracking-wider uppercase text-xs">Del</th></tr></thead><tbody id="table-team" class="divide-y divide-white/5"></tbody></table></div></div>
                <div id="promos" class="tab-content"><h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Promos</h2><div class="flex gap-6"><div class="w-1/3 bg-black/40 p-6 rounded-2xl border border-white/5"><input type="text" id="p-code" placeholder="Code" class="premium-input w-full rounded-xl px-4 py-3 mb-3 uppercase text-sm"><input type="number" id="p-disc" placeholder="Discount %" class="premium-input w-full rounded-xl px-4 py-3 mb-3 text-sm"><input type="number" id="p-uses" placeholder="Uses" class="premium-input w-full rounded-xl px-4 py-3 mb-4 text-sm"><button onclick="createPromo()" class="w-full bg-purple-600 text-white font-bold py-3 rounded-xl text-sm uppercase tracking-widest">Create</button></div><div class="w-2/3 bg-black/40 rounded-2xl overflow-hidden border border-white/5"><table class="w-full text-left text-sm"><thead class="bg-white/5 text-gray-400"><tr><th class="p-4 font-bold text-xs uppercase tracking-widest">Code</th><th class="p-4 font-bold text-xs uppercase tracking-widest">Disc</th><th class="p-4 font-bold text-xs uppercase tracking-widest">Uses</th><th class="p-4 text-right font-bold text-xs uppercase tracking-widest">Del</th></tr></thead><tbody id="table-promos" class="divide-y divide-white/5"></tbody></table></div></div></div>
                <div id="lookup" class="tab-content"><h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Lookup</h2><div class="flex gap-4 mb-8"><input type="text" id="lookup-id" placeholder="Discord ID..." class="flex-1 premium-input rounded-xl px-5 py-4 font-mono"><button onclick="lookupUser()" class="bg-purple-600 px-8 rounded-xl font-bold text-white uppercase tracking-widest">Search</button></div><div id="lookup-result" class="hidden"><div class="grid grid-cols-3 gap-6 mb-8"><div class="bg-black/40 p-6 rounded-2xl border border-white/5"><p class="text-xs font-bold text-gray-500 uppercase">Spent</p><h3 id="lu-spent" class="text-2xl font-black mt-2 text-white">0€</h3></div><div class="bg-black/40 p-6 rounded-2xl border border-white/5"><p class="text-xs font-bold text-gray-500 uppercase">Orders</p><h3 id="lu-orders" class="text-2xl font-black mt-2 text-white">0</h3></div><div class="bg-black/40 p-6 rounded-2xl border border-white/5"><p class="text-xs font-bold text-gray-500 uppercase">Status</p><h3 id="lu-banned" class="text-xl font-black mt-2">Clean</h3></div></div></div></div>
                <div id="announce" class="tab-content"><h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Broadcast</h2><div class="max-w-2xl"><input type="text" id="ann-title" placeholder="Title" class="premium-input w-full rounded-xl px-5 py-4 mb-4"><textarea id="ann-desc" placeholder="Message..." rows="5" class="premium-input w-full rounded-xl px-5 py-4 mb-4"></textarea><button onclick="sendAnnounce()" class="w-full bg-blue-600 text-white font-bold py-4 rounded-xl uppercase tracking-widest">Send Discord</button></div></div>
                <div id="blacklist" class="tab-content"><h2 class="text-2xl font-black text-white tracking-widest uppercase mb-8">Blacklist</h2><div class="flex gap-4 mb-8"><input type="text" id="bl-id" placeholder="Discord ID..." class="flex-1 premium-input rounded-xl px-5 py-4 font-mono"><button onclick="addBlacklist()" class="bg-red-600 px-8 rounded-xl font-bold text-white uppercase tracking-widest">Ban</button></div><div class="bg-black/40 rounded-2xl overflow-hidden border border-white/5"><table class="w-full text-left text-sm"><thead class="bg-white/5 text-gray-400"><tr><th class="p-4 font-bold text-xs uppercase tracking-widest">ID</th><th class="p-4 font-bold text-xs uppercase tracking-widest">Reason</th><th class="p-4 text-right font-bold text-xs uppercase tracking-widest">Del</th></tr></thead><tbody id="table-blacklist" class="divide-y divide-white/5"></tbody></table></div></div>
            </main>
        </div>

    </div>

    <div id="key-modal" class="fixed inset-0 bg-black/90 backdrop-blur-xl flex items-center justify-center hidden-view z-50">
        <div class="glass p-10 rounded-[2rem] text-center max-w-sm w-full border border-purple-500/50 shadow-[0_0_50px_rgba(168,85,247,0.3)] relative">
            <h3 class="text-2xl font-black text-white mb-2 uppercase tracking-widest glow-text">Erstellt!</h3>
            <input type="text" id="new-key" class="w-full bg-black/80 border border-white/10 p-4 rounded-xl text-purple-400 font-mono text-center mb-6 text-sm outline-none mt-6" readonly>
            <button onclick="document.getElementById('key-modal').classList.add('hidden-view')" class="w-full bg-white/10 hover:bg-white/20 text-white font-black py-3 rounded-xl uppercase tracking-widest transition text-xs">Schließen</button>
        </div>
    </div>

    <script>
        let selectedProduct = "";
        let currentGw = "ltc";

        // GATEWAY LOGIC
        function setGw(gw) {
            currentGw = gw;
            document.getElementById('gw-ltc').className = gw === 'ltc' ? "flex-1 py-3 border-2 border-purple-500 bg-purple-500/20 rounded-xl font-bold text-white transition shadow-[0_0_15px_rgba(168,85,247,0.3)]" : "flex-1 py-3 border-2 border-white/10 bg-black/50 rounded-xl font-bold text-gray-400 hover:text-white transition";
            document.getElementById('gw-paypal').className = gw === 'paypal' ? "flex-1 py-3 border-2 border-blue-500 bg-blue-500/20 rounded-xl font-bold text-white transition shadow-[0_0_15px_rgba(59,130,246,0.3)]" : "flex-1 py-3 border-2 border-white/10 bg-black/50 rounded-xl font-bold text-gray-400 hover:text-white transition";
            
            document.getElementById('details-ltc').classList.toggle('hidden-view', gw !== 'ltc');
            document.getElementById('details-paypal').classList.toggle('hidden-view', gw !== 'paypal');
        }

        // SHOP UI LOGIC
        function switchAuth(type) {
            document.getElementById('view-shop').classList.add('hidden-view');
            document.getElementById('view-auth').classList.add('hidden-view');
            if(type === 'shop') { document.getElementById('view-shop').classList.remove('hidden-view'); } 
            else { document.getElementById('view-auth').classList.remove('hidden-view'); switchAuthTab('customer'); }
        }

        function switchAuthTab(type) {
            ['customer', 'login', 'register'].forEach(t => {
                document.getElementById('form-' + t).classList.add('hidden-view');
                document.getElementById('tab-btn-' + t).className = "flex-1 py-3 text-xs font-black rounded-lg text-gray-500 hover:text-white transition uppercase tracking-widest";
            });
            document.getElementById('form-' + type).classList.remove('hidden-view');
            document.getElementById('tab-btn-' + type).className = "flex-1 py-3 text-xs font-black rounded-lg text-white bg-white/10 transition uppercase tracking-widest";
            document.getElementById('auth-error').classList.add('hidden');
        }

        function openCheckout(id, price) {
            selectedProduct = id; document.getElementById('co-price').innerText = price;
            document.getElementById('co-step-1').classList.remove('hidden-view');
            document.getElementById('co-step-2').classList.add('hidden-view');
            document.getElementById('checkout-modal').classList.remove('hidden-view');
            setGw('ltc'); // Default
        }
        function closeCheckout() { document.getElementById('checkout-modal').classList.add('hidden-view'); }

        async function processCheckout() {
            const email = document.getElementById('co-email').value;
            const proof = currentGw === 'ltc' ? document.getElementById('co-txid').value : document.getElementById('co-pp-proof').value;
            const btn = document.getElementById('btn-checkout');
            const err = document.getElementById('co-error');

            if(!email || !email.includes('@') || !proof) { err.innerText = "Bitte fülle alle Felder korrekt aus!"; err.classList.remove('hidden'); return; }

            err.classList.add('hidden'); btn.disabled = true; btn.innerHTML = '<span class="loader"></span> Loading...';

            try {
                const res = await fetch('/api/web_buy', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email, proof: proof, gateway: currentGw, product: selectedProduct})
                });
                const data = await res.json();
                
                if(data.ok) {
                    document.getElementById('co-success-key').innerText = data.key;
                    document.getElementById('co-step-1').classList.add('hidden-view');
                    document.getElementById('co-step-2').classList.remove('hidden-view');
                } else {
                    err.innerText = data.error; err.classList.remove('hidden');
                    btn.disabled = false; btn.innerText = "Zahlung Verifizieren";
                }
            } catch(e) { err.innerText = "Server Error"; err.classList.remove('hidden'); btn.disabled = false; btn.innerText = "Zahlung Verifizieren"; }
        }

        // AUTH / ADMIN Logic
        async function apiCall(endpoint, data) {
            const token = localStorage.getItem('v_token');
            const headers = {'Content-Type': 'application/json'};
            if (token) headers['Authorization'] = token;
            const res = await fetch(endpoint, { method: 'POST', headers: headers, body: JSON.stringify(data) });
            if (res.status === 401 && !endpoint.includes('login') && !endpoint.includes('register')) { logout(); throw new Error('Unauth'); }
            return res;
        }

        function showError(msg) { const e = document.getElementById('auth-error'); e.innerHTML = msg; e.classList.remove('hidden'); }
        async function login() { const u = document.getElementById('l-user').value, p = document.getElementById('l-pass').value; if (!u || !p) return showError("Felder ausfüllen."); const res = await apiCall('/api/login', {user: u, pass: p}); if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else showError("Falsche Daten!"); }
        async function customerLogin() { const k = document.getElementById('c-key').value; if (!k) return showError("Key eingeben."); const res = await apiCall('/api/customer_login', {key: k}); if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else { const e = await res.json(); showError(e.error || "Falscher Key"); } }
        async function register() { const u = document.getElementById('r-user').value, p = document.getElementById('r-pass').value, k = document.getElementById('r-key').value; if (!u || !p || !k) return showError("Felder ausfüllen."); const res = await apiCall('/api/register', {user: u, pass: p, key: k}); if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else { const e = await res.json(); showError(e.error || "Fehler"); } }
        function logout() { localStorage.removeItem('v_token'); location.reload(); }

        window.onload = async () => {
            const t = localStorage.getItem('v_token');
            if (t) { try { const res = await fetch('/api/verify', { method: 'POST', headers: {'Authorization': t, 'Content-Type': 'application/json'} }); if (res.ok) { const d = await res.json(); initApp(d.role, d.user); } else if (res.status === 401) { logout(); } } catch(e) {} }
            else switchAuth('shop');
        };

        function initApp(role, name) {
            document.getElementById('view-shop').classList.add('hidden-view');
            document.getElementById('view-auth').classList.add('hidden-view');
            document.querySelector('nav').classList.add('hidden-view'); // Hide main nav when logged in
            if (role === 'admin') { document.getElementById('view-admin').classList.remove('hidden-view'); nav('dash'); }
            else if (role === 'customer') { document.getElementById('view-customer').classList.remove('hidden-view'); document.getElementById('cust-key-display').innerText = name; loadCustomerData(); }
        }

        function nav(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            document.querySelectorAll('.nav-btn').forEach(el => { el.className = "nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 font-bold tracking-widest uppercase text-xs transition"; });
            document.getElementById('btn-' + tabId).className = "nav-btn w-full text-left py-3 px-4 rounded-xl text-purple-300 bg-purple-500/10 font-bold tracking-widest uppercase text-xs transition";
            if (tabId === 'dash') loadDashboard(); if (tabId === 'keys') loadKeys(); if (tabId === 'team') loadTeam(); if (tabId === 'promos') loadPromos(); if (tabId === 'blacklist') loadBlacklist();
        }

        async function loadDashboard() { try { const res = await apiCall('/api/stats', {}); const data = await res.json(); document.getElementById('stat-rev').innerText = data.total_revenue.toFixed(2) + '€'; document.getElementById('stat-orders').innerText = data.buyers_today; document.getElementById('stat-keys').innerText = data.active_keys; } catch(e) {} }
        async function loadKeys() { try { const res = await apiCall('/api/keys', {}); const data = await res.json(); const tb = document.getElementById('table-keys'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500 text-xs">EMPTY</td></tr>'; tb.innerHTML = Object.entries(data).reverse().map(([key, info]) => { if(typeof info !== 'object') return ''; let badge = info.used ? '<span class="text-red-400">Used</span>' : '<span class="text-green-400">Active</span>'; if (info.revoked) badge = '<span class="text-gray-500">Banned</span>'; const act = !info.revoked ? `<button onclick="revokeKey('${key}')" class="text-red-400 hover:text-red-300">Ban</button>` : '-'; return `<tr><td class="px-6 py-4 font-mono text-purple-300">${key}</td><td class="px-6 py-4">${info.type}</td><td class="px-6 py-4">${info.used_by || '-'}</td><td class="px-6 py-4">${badge}</td><td class="px-6 py-4 text-right">${act}</td></tr>`; }).join(''); } catch(e) {} }
        async function loadTeam() { try { const res = await apiCall('/api/team', {}); const data = await res.json(); const tb = document.getElementById('table-team'); if (data.length === 0) return tb.innerHTML = '<tr><td colspan="3" class="px-6 py-8 text-center text-gray-500 text-xs">EMPTY</td></tr>'; tb.innerHTML = data.map(u => `<tr><td class="px-6 py-4 text-blue-400">${u.username}</td><td class="px-6 py-4">${u.keys_generated}</td><td class="px-6 py-4 text-right"><button onclick="deleteReseller('${u.username}')" class="text-red-400"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e){} }
        async function deleteReseller(u) { if(confirm(`Delete ${u}?`)) { await apiCall('/api/team/delete', {username: u}); loadTeam(); } }
        async function revokeKey(k) { if (confirm('Ban key?')) { await apiCall('/api/keys/revoke', {key: k}); loadKeys(); } }
        async function loadPromos() { try { const res = await apiCall('/api/promos', {}); const data = await res.json(); const tb = document.getElementById('table-promos'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-gray-500 text-xs">EMPTY</td></tr>'; tb.innerHTML = Object.entries(data).map(([code, info]) => `<tr><td class="p-4 font-mono text-pink-400">${code}</td><td class="p-4">${info.discount}%</td><td class="p-4">${info.uses}</td><td class="p-4 text-right"><button onclick="rmPromo('${code}')" class="text-red-400"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e) {} }
        async function createPromo() { const c = document.getElementById('p-code').value.toUpperCase(), d = document.getElementById('p-disc').value, u = document.getElementById('p-uses').value; if (!c || !d || !u) return; await apiCall('/api/promos/add', {code: c, discount: parseInt(d), uses: parseInt(u)}); loadPromos(); }
        async function rmPromo(c) { await apiCall('/api/promos/remove', {code: c}); loadPromos(); }
        async function lookupUser() { const uid = document.getElementById('lookup-id').value; if (!uid) return; try { const res = await apiCall('/api/lookup', {user_id: uid}); const data = await res.json(); document.getElementById('lookup-result').classList.remove('hidden'); document.getElementById('lu-spent').innerText = data.total_spent.toFixed(2) + '€'; document.getElementById('lu-orders').innerText = data.total_orders; const b = document.getElementById('lu-banned'); if (data.is_banned) { b.innerText = "BANNED"; b.className = "text-xl font-black mt-2 text-red-500"; } else { b.innerText = "CLEAN"; b.className = "text-xl font-black mt-2 text-green-400"; } const tb = document.getElementById('lu-table'); if (data.invoices.length === 0) tb.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-gray-500 text-xs">EMPTY</td></tr>'; else tb.innerHTML = data.invoices.map(i => `<tr><td class="p-4 font-mono text-xs text-gray-500">${i.id}</td><td class="p-4 text-xs">${i.product}</td><td class="p-4 text-xs text-green-400">${i.price}€</td><td class="p-4 text-xs">${i.date.split('T')[0]}</td></tr>`).join(''); } catch(e) {} }
        async function sendAnnounce() { const t = document.getElementById('ann-title').value, d = document.getElementById('ann-desc').value, i = document.getElementById('ann-img').value; if (!t || !d) return; await apiCall('/api/announce', {title: t, desc: d, img: i}); alert("Broadcast Sent!"); }
        async function loadBlacklist() { try { const res = await apiCall('/api/blacklist', {}); const data = await res.json(); const tb = document.getElementById('table-blacklist'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-gray-500 text-xs">EMPTY</td></tr>'; tb.innerHTML = Object.entries(data).map(([uid, info]) => `<tr><td class="p-4 font-mono text-red-400">${uid}</td><td class="p-4 text-xs">${info.reason}</td><td class="p-4 text-right"><button onclick="rmBlacklist('${uid}')" class="text-red-400"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e) {} }
        async function addBlacklist() { const uid = document.getElementById('bl-id').value, rsn = document.getElementById('bl-reason').value || "Web Ban"; if (!uid) return; await apiCall('/api/blacklist/add', {user_id: uid, reason: rsn}); loadBlacklist(); }
        async function rmBlacklist(uid) { await apiCall('/api/blacklist/remove', {user_id: uid}); loadBlacklist(); }
        async function genAdminKey(type) { const res = await apiCall('/api/admin/generate', {t: type}); const d = await res.json(); document.getElementById('new-key').value = d.key; document.getElementById('key-modal').classList.remove('hidden-view'); }
        async function loadCustomerData() { try { const res = await apiCall('/api/customer_data', {}); const data = await res.json(); document.getElementById('cust-prod').innerText = data.type; document.getElementById('cust-status').innerText = data.status; document.getElementById('cust-discord').innerText = data.used_by; document.getElementById('cust-created').innerText = data.created_at.split('T')[0]; if(data.status === "Banned") document.getElementById('cust-status').className = "text-xl font-black mt-2 text-red-500"; else if(data.status === "Active") document.getElementById('cust-status').className = "text-xl font-black mt-2 text-green-400"; } catch(e){} }
    </script>
</body>
</html>
""".replace("LOGO_URL_PLACEHOLDER", SAFE_WEBSITE_LOGO_URL).replace("LTC_ADDR", LITECOIN_ADDRESS).replace("PP_EMAIL", PAYPAL_EMAIL)

# =========================================================
# 🌍 API ENDPOINTS (WEB SERVER)
# =========================================================
def get_user_from_token(request):
    token = request.headers.get("Authorization")
    if not token or token not in web_sessions: return None
    return web_sessions[token]

async def handle_index(request): return web.Response(text=WEB_HTML, content_type='text/html')

async def api_web_buy(request):
    try:
        data = await request.json()
        email = data.get("email")
        proof = data.get("proof")
        gateway = data.get("gateway", "ltc")
        ptype = data.get("product")
        
        if not email or not proof or ptype not in PRODUCTS:
            return web.json_response({"ok": False, "error": "Fehlende Daten."})
            
        if gateway == "ltc":
            ok, reason = await verify_ltc_payment(proof)
            if not ok: return web.json_response({"ok": False, "error": reason})
        elif gateway == "paypal":
            # Hier simuliertes PayPal "Auto-Delivery" basierend auf dem Namen/Mail Input als Proof.
            # In einem echten System bräuchte man hier die PayPal API
            pass
        else:
            return web.json_response({"ok": False, "error": "Ungültiges Gateway."})
            
        prefix = PRODUCTS[ptype]["key_prefix"]
        key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
        
        keys_db[key] = {
            "type": ptype, "used": False, "used_by": None, "bound_user_id": None, 
            "created_at": iso_now(), "redeemed_at": None, "approved_in_ticket": f"WEB-{gateway.upper()}", 
            "created_by": "System-Auto", "revoked": False
        }
        save_json(KEYS_FILE, keys_db)
        
        invoice_id = build_invoice_id()
        invoices_db[invoice_id] = {
            "buyer_id": email, "product_type": ptype, "payment_key": gateway, 
            "key": key, "ticket_id": "WEB", "created_at": iso_now(), 
            "final_price_eur": PRODUCTS[ptype]["price_eur"], "reseller_discount": False
        }
        save_json(INVOICES_FILE, invoices_db)
        
        send_delivery_email(email, PRODUCTS[ptype]["label"], key)
        log_activity(f"Web Order via {gateway.upper()} ({PRODUCTS[ptype]['price_eur']}€)", "Auto-Shop")
        
        return web.json_response({"ok": True, "key": key})
    except Exception as e:
        return web.json_response({"ok": False, "error": "Server Fehler."})

async def api_register(request):
    data = await request.json(); u, p, k = data.get("user"), data.get("pass"), data.get("key", "").upper()
    if not u or not p or not k: return web.json_response({"error": "Bitte fülle alle Felder aus!"}, status=400)
    if u in users_db: return web.json_response({"error": f"Der Name '{u}' ist leider schon vergeben!"}, status=400)
    if k not in webkeys_db or webkeys_db[k].get("used"): return web.json_response({"error": "Ungültiger oder benutzter Invite Key!"}, status=400)
    role = webkeys_db[k]["role"]; users_db[u] = {"pass": p, "role": role}; webkeys_db[k]["used"] = True
    save_json(USERS_FILE, users_db); save_json(WEBKEYS_FILE, webkeys_db); log_activity(f"New User ({role})", u)
    token = str(uuid.uuid4()); web_sessions[token] = {"user": u, "role": role}; save_json(SESSIONS_FILE, web_sessions)
    return web.json_response({"ok": True, "token": token, "role": role, "user": u})

async def api_login(request):
    data = await request.json(); u, p = data.get("user"), data.get("pass")
    if u in users_db and users_db[u]["pass"] == p:
        token = str(uuid.uuid4()); role = users_db[u]["role"]; web_sessions[token] = {"user": u, "role": role}
        save_json(SESSIONS_FILE, web_sessions)
        return web.json_response({"ok": True, "token": token, "role": role, "user": u})
    return web.Response(status=401)

async def api_customer_login(request):
    data = await request.json(); k = data.get("key", "").strip().upper()
    if not k or k not in keys_db: return web.json_response({"error": "Key existiert nicht."}, status=400)
    token = str(uuid.uuid4()); web_sessions[token] = {"user": k, "role": "customer"}; save_json(SESSIONS_FILE, web_sessions)
    return web.json_response({"ok": True, "token": token, "role": "customer", "user": k})

async def api_customer_data(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "customer": return web.Response(status=401)
    key = user_info["user"]; kdata = keys_db.get(key, {})
    ptype = kdata.get("type", "day_1") if isinstance(kdata, dict) else "day_1"
    status = "Active"
    if isinstance(kdata, dict):
        if kdata.get("revoked"): status = "Banned"
        elif not kdata.get("used"): status = "Unused"
    return web.json_response({"key": key, "type": PRODUCTS.get(ptype, {"label": "Unknown"}).get("label"), "status": status, "created_at": kdata.get("created_at", "Unknown"), "used_by": kdata.get("used_by", "None")})

async def api_verify(request):
    u = get_user_from_token(request)
    return web.json_response({"ok": True, "role": u["role"], "user": u["user"]}) if u else web.Response(status=401)

async def api_stats(request):
    total_rev = sum(float(data.get("final_price_eur", 0)) for data in invoices_db.values() if isinstance(data, dict))
    today_buyers = set()
    active_k = sum(1 for v in keys_db.values() if isinstance(v, dict) and not v.get("used"))
    return web.json_response({"total_revenue": total_rev, "buyers_today": len(today_buyers), "active_keys": active_k, "chart_labels": [], "chart_data": []})

async def api_discord_stats(request): return web.json_response({"members": 0, "open_tickets": len(ticket_data)})
async def api_activity(request): return web.json_response(activity_db)
async def api_keys(request): return web.json_response(keys_db)

async def api_revoke_key(request):
    data = await request.json(); key = data.get("key")
    if key in keys_db: keys_db[key]["revoked"] = True; keys_db[key]["used"] = True; save_json(KEYS_FILE, keys_db)
    return web.json_response({"ok": True})

async def api_team(request): return web.json_response([{"username": u, "password": d["pass"], "keys_generated": 0} for u, d in users_db.items() if d.get("role") == "reseller"])
async def api_team_delete(request):
    u = (await request.json()).get("username")
    if u in users_db: del users_db[u]; save_json(USERS_FILE, users_db)
    return web.json_response({"ok": True})

async def api_promos(request): return web.json_response(promos_db)
async def api_add_promo(request):
    d = await request.json(); promos_db[d["code"]] = {"discount": d["discount"], "uses": d["uses"]}; save_json(PROMOS_FILE, promos_db); return web.json_response({"ok": True})
async def api_rm_promo(request):
    c = (await request.json()).get("code")
    if c in promos_db: del promos_db[c]; save_json(PROMOS_FILE, promos_db)
    return web.json_response({"ok": True})

async def api_lookup(request): return web.json_response({"total_spent": 0, "total_orders": 0, "is_banned": False, "invoices": []})
async def api_announce(request): return web.json_response({"ok": True})
async def api_blacklist(request): return web.json_response(blacklist_db)
async def api_add_blacklist(request):
    d = await request.json(); blacklist_db[d.get("user_id")] = {"reason": d.get("reason", "Ban")}; save_json(BLACKLIST_FILE, blacklist_db); return web.json_response({"ok": True})
async def api_rm_blacklist(request):
    u = (await request.json()).get("user_id")
    if u in blacklist_db: del blacklist_db[u]; save_json(BLACKLIST_FILE, blacklist_db)
    return web.json_response({"ok": True})

async def api_admin_gen(request):
    u = get_user_from_token(request)
    ptype = (await request.json()).get("t", "day_1")
    key = f"{PRODUCTS[ptype]['key_prefix']}-{random_block()}-{random_block()}"
    keys_db[key] = {"type": ptype, "used": False, "created_at": iso_now(), "created_by": u["user"] if u else "Admin", "revoked": False}
    save_json(KEYS_FILE, keys_db)
    return web.json_response({"key": key})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_post('/api/web_buy', api_web_buy)
    app.router.add_post('/api/register', api_register)
    app.router.add_post('/api/login', api_login)
    app.router.add_post('/api/customer_login', api_customer_login)
    app.router.add_post('/api/verify', api_verify)
    app.router.add_post('/api/stats', api_stats)
    app.router.add_post('/api/discord_stats', api_discord_stats)
    app.router.add_post('/api/activity', api_activity)
    app.router.add_post('/api/keys', api_keys)
    app.router.add_post('/api/keys/revoke', api_revoke_key)
    app.router.add_post('/api/team', api_team)
    app.router.add_post('/api/team/delete', api_team_delete)
    app.router.add_post('/api/promos', api_promos)
    app.router.add_post('/api/promos/add', api_add_promo)
    app.router.add_post('/api/promos/remove', api_rm_promo)
    app.router.add_post('/api/lookup', api_lookup)
    app.router.add_post('/api/announce', api_announce)
    app.router.add_post('/api/blacklist', api_blacklist)
    app.router.add_post('/api/blacklist/add', api_add_blacklist)
    app.router.add_post('/api/blacklist/remove', api_rm_blacklist)
    app.router.add_post('/api/admin/generate', api_admin_gen)
    app.router.add_post('/api/customer_data', api_customer_data)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🚀 Web Store & API online auf Port {port}!")

# =========================================================
# BOT COMMANDS & TICKET LOGIC (UNTOUCHED)
# =========================================================
def premium_divider() -> str: return "━━━━━━━━━━━━━━━━━━━━━━━━"
def short_txid(txid: str) -> str: return txid if len(txid) < 20 else f"{txid[:14]}...{txid[-14:]}"
def format_price(value: float) -> str: return str(int(value)) if float(value).is_integer() else f"{value:.2f}"
def is_reseller_dc(member: discord.Member | None) -> bool: return member and any(role.id == RESELLER_ROLE_ID for role in member.roles)

def get_price(product_key: str, member: discord.Member | None = None, promo_discount: int = 0) -> float:
    base_price = PRODUCTS[product_key]["price_eur"]
    if is_reseller_dc(member): base_price = round(base_price * 0.5, 2)
    if promo_discount > 0: base_price = round(base_price * (1 - (promo_discount / 100.0)), 2)
    return float(base_price)

async def dm_user_safe(user: discord.abc.User, content: str = None, embed: discord.Embed = None):
    try: await user.send(content=content, embed=embed)
    except Exception: pass

def generate_key(product_type: str, ticket_id: str | None = None, creator="System") -> str:
    prefix = PRODUCTS[product_type]["key_prefix"]
    while True:
        key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
        if key not in keys_db:
            keys_db[key] = {"type": product_type, "used": False, "used_by": None, "bound_user_id": None, "created_at": iso_now(), "redeemed_at": None, "approved_in_ticket": ticket_id, "created_by": creator, "revoked": False}
            save_json(KEYS_FILE, keys_db)
            log_activity("Generierte einen Key", creator)
            return key

def create_invoice_record(invoice_id, buyer_id, product_type, payment_key, key, ticket_id, final_price_eur, reseller_discount):
    invoices_db[invoice_id] = {"buyer_id": str(buyer_id), "product_type": product_type, "payment_key": payment_key, "key": key, "ticket_id": str(ticket_id), "created_at": iso_now(), "final_price_eur": final_price_eur, "reseller_discount": reseller_discount}
    save_json(INVOICES_FILE, invoices_db)

def extract_possible_paysafe_codes(text: str): return re.findall(r"\b[A-Z0-9]{4,8}(?:-[A-Z0-9]{4,8}){1,5}\b", text.upper())
def extract_possible_amazon_codes(text: str): return re.findall(r"\b[A-Z0-9]{4,8}(?:-[A-Z0-9]{4,8}){1,5}\b", text.upper())
def litoshi_to_ltc(value: int) -> float: return value / 100_000_000

def tx_matches_our_address(tx_data: dict, expected_address: str) -> tuple[bool, int]:
    total_received = 0; found = False
    for output in tx_data.get("outputs", []):
        if expected_address in output.get("addresses", []): found = True; total_received += int(output.get("value", 0))
    return found, total_received

async def fetch_ltc_tx(txid: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=20) as resp:
            if resp.status != 200: return None, f"API error"
            return await resp.json(), None

async def fetch_ltc_price_eur():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=eur", timeout=20) as resp:
            if resp.status != 200: return None
            return (await resp.json()).get("litecoin", {}).get("eur")

async def find_existing_ticket(guild: discord.Guild, user: discord.Member):
    for channel in guild.text_channels:
        if channel.topic == f"ticket_owner:{user.id}": return channel
    return None

def build_order_summary(product_key: str, payment_key: str, user: discord.Member, ltc_price_eur: float | None = None) -> discord.Embed:
    product = PRODUCTS[product_key]
    payment = PAYMENTS[payment_key]
    price = get_price(product_key, user)
    price_header = f"💶 **Price:** {format_price(price)}€"
    
    if is_reseller_dc(user): price_header += " (**Reseller 50% OFF**)"
    if payment_key == "paypal": extra = f"## 💸 PayPal Payment\n**Send payment to:**\n`{PAYPAL_EMAIL}`\n\n**After payment:**\n• Send screenshot / proof in this ticket\n• Click **Payment Sent**"
    elif payment_key == "litecoin":
        extra = f"## 🪙 Litecoin Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{LITECOIN_ADDRESS}`\n\n"
        if ltc_price_eur and ltc_price_eur > 0: extra += f"**Approx LTC amount:** `{price / ltc_price_eur:.6f} LTC`\n**Market rate:** `{ltc_price_eur:.2f} EUR/LTC`\n\n"
        extra += "**After payment:**\n• Click **Submit TXID**\n• Paste your TXID in the popup\n• Bot checks it automatically"
    elif payment_key == "ethereum": extra = f"## 🔷 Ethereum Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{ETHEREUM_ADDRESS}`\n\n**After payment:**\n• Click **Submit Crypto TXID**"
    elif payment_key == "solana": extra = f"## 🟣 Solana Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{SOLANA_ADDRESS}`\n\n**After payment:**\n• Click **Submit Crypto TXID**"
    elif payment_key == "paysafecard": extra = f"## 💳 Paysafecard Payment\n**Main price:** `{format_price(price)}€`\n\n**After buying your code:**\n• Click **Submit Paysafecard Code**"
    else: extra = f"## 🎁 Amazon Card Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{LITECOIN_ADDRESS}`\n\n**After buying your Amazon card:**\n• Click **Submit Amazon Code**"
        
    return discord.Embed(title="✦ ORDER SETUP COMPLETE ✦", description=f"{premium_divider()}\n{user.mention}\n\n📦 **Product:** {product['label']}\n{price_header}\n{payment['emoji']} **Method:** {payment['label']}\n\n{extra}\n{premium_divider()}", color=COLOR_MAIN)

def build_payment_summary_embed(channel_id: int) -> discord.Embed:
    data = ticket_data.get(str(channel_id), {})
    user = bot.get_guild(GUILD_ID).get_member(data.get("user_id")) if bot.get_guild(GUILD_ID) and data.get("user_id") else None
    product_key = data.get("product_key")
    promo_code = data.get("applied_promo")
    promo_discount = promos_db[promo_code]["discount"] if promo_code and promo_code in promos_db else 0
    if product_key in PRODUCTS:
        price_text = f"{format_price(get_price(product_key, user, promo_discount))}€"
        if is_reseller_dc(user): price_text += " (Reseller)"
        if promo_discount > 0: price_text += f" (Promo -{promo_discount}%)"
    else: price_text = "—"
    status_map = {"waiting": "🟡 Waiting", "reviewing": "🟠 Reviewing", "approved": "✅ Approved", "denied": "❌ Denied"}
    embed = discord.Embed(title="📋 Payment Summary", description=f"{premium_divider()}\n**Live order status**\n{premium_divider()}", color=COLOR_INFO)
    embed.add_field(name="Product", value=PRODUCTS[product_key]["label"] if product_key in PRODUCTS else "Not selected", inline=True)
    embed.add_field(name="Price", value=price_text, inline=True)
    embed.add_field(name="Method", value=PAYMENTS[data.get("payment_key")]["label"] if data.get("payment_key") in PAYMENTS else "Not selected", inline=True)
    embed.add_field(name="Status", value=status_map.get(data.get("status", "waiting"), data.get("status", "waiting")), inline=True)
    embed.add_field(name="TXID", value=f"`{short_txid(data.get('last_txid'))}`" if data.get('last_txid') else "Not submitted", inline=True)
    embed.add_field(name="Invoice", value=f"`{data.get('invoice_id')}`" if data.get('invoice_id') else "Not created", inline=False)
    if promo_code: embed.add_field(name="Gutschein", value=f"`{promo_code}`", inline=True)
    return embed

async def update_payment_summary_message(channel: discord.TextChannel):
    data = ticket_data.get(str(channel.id))
    if data and data.get("summary_message_id"):
        try: msg = await channel.fetch_message(data["summary_message_id"]); await msg.edit(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
        except Exception: pass

async def send_admin_panel_to_channel(guild: discord.Guild, owner_id: int, ticket_channel_id: int):
    admin_channel = guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
    if isinstance(admin_channel, discord.TextChannel):
        msg = await admin_channel.send(embed=discord.Embed(title="🛠️ GEN ADMIN PANEL", description=f"{premium_divider()}\n**Buyer ID:** `{owner_id}`\n**Ticket ID:** `{ticket_channel_id}`\n{premium_divider()}", color=COLOR_ADMIN), view=AdminPanelView())
        if str(ticket_channel_id) in ticket_data: ticket_data[str(ticket_channel_id)]["admin_message_id"] = msg.id; save_json(TICKETS_FILE, ticket_data)

async def send_summary_and_admin_panels(channel: discord.TextChannel, owner_id: int):
    summary_msg = await channel.send(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
    ticket_data[str(channel.id)]["summary_message_id"] = summary_msg.id; save_json(TICKETS_FILE, ticket_data)
    await send_admin_panel_to_channel(channel.guild, owner_id, channel.id)

async def redeem_key_for_user(guild: discord.Guild, member: discord.Member, key: str):
    if is_blacklisted(member.id): return False, "You are blacklisted."
    if key not in keys_db: return False, "Key not found."
    if keys_db[key].get("revoked"): return False, "This key has been banned."
    if keys_db[key]["used"]: return False, "Already used."
    pt = keys_db[key]["type"]; r = guild.get_role(REDEEM_ROLE_ID)
    if not r: return False, "Role not found."
    keys_db[key].update({"used": True, "used_by": str(member.id)}); save_json(KEYS_FILE, keys_db)
    dur_days = PRODUCTS.get(pt, {}).get("duration_days", 0)
    redeemed_db[str(member.id)] = {"key": key, "type": pt, "role_id": REDEEM_ROLE_ID, "expires_at": (now_utc() + timedelta(days=dur_days)).isoformat() if dur_days > 0 else None}
    save_json(REDEEMED_FILE, redeemed_db)
    await member.add_roles(r); return True, pt

class CloseConfirmView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        data = ticket_data.get(str(interaction.channel.id))
        if data and data.get("admin_message_id"):
            admin_channel = interaction.guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
            if isinstance(admin_channel, discord.TextChannel):
                try: msg = await admin_channel.fetch_message(data["admin_message_id"]); await msg.delete()
                except Exception: pass
        ticket_data.pop(str(interaction.channel.id), None); save_json(TICKETS_FILE, ticket_data)
        await asyncio.sleep(2); await interaction.channel.delete()

class TicketManageView(discord.ui.View):
    def __init__(self, owner_id=None): super().__init__(timeout=None)
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="claim_ticket_button")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.")
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(str(interaction.channel.id)); owner_id = data.get("user_id") if data else None
        if owner_id and interaction.user.id != owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("No permission.", ephemeral=True)
        await interaction.response.send_message("Are you sure you want to close this ticket?", view=CloseConfirmView(), ephemeral=True)

class PromoCodeModal(discord.ui.Modal, title="Gutscheincode einlösen"):
    code_input = discord.ui.TextInput(label="Promo Code", placeholder="z.B. VALE20", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        owner_id = data.get("user_id")
        if interaction.user.id != owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        code = str(self.code_input).strip().upper()
        if code not in promos_db or promos_db[code]["uses"] <= 0: return await interaction.response.send_message("❌ Ungültiger Code.", ephemeral=True)
        data["applied_promo"] = code; save_json(TICKETS_FILE, ticket_data)
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message(f"✅ Gutschein `{code}` angewendet! (-{promos_db[code]['discount']}%)", ephemeral=True)

class GenericCryptoTxidModal(discord.ui.Modal, title="Paste your Crypto TXID here"):
    txid_input = discord.ui.TextInput(label="Transaction Hash (TXID)", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        txid = str(self.txid_input).strip(); data["last_txid"] = txid; data["status"] = "reviewing"; save_json(TICKETS_FILE, ticket_data)
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if review_channel: 
            embed = discord.Embed(title="🪙 Crypto TXID Submitted", description=f"**Buyer:** {interaction.user.mention}\n**Ticket:** <#{interaction.channel.id}>\n**TXID:** `{txid}`", color=COLOR_WARN)
            await review_channel.send(content=f"<@&{STAFF_ROLE_ID}> Review needed.", embed=embed, view=ReviewView())
        await interaction.channel.send(embed=discord.Embed(title="✅ TXID Submitted", description="Sent to staff.", color=COLOR_SUCCESS))
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("Submitted.", ephemeral=True)

class LitecoinTxidModal(discord.ui.Modal, title="Paste your Litecoin TXID here"):
    txid_input = discord.ui.TextInput(label="Litecoin TXID", required=True, min_length=64, max_length=64)
    async def on_submit(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        txid = str(self.txid_input).strip()
        if txid in used_txids_db: return await interaction.response.send_message("Already submitted.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        tx_data, err = await fetch_ltc_tx(txid)
        if err or not tx_data: return await interaction.followup.send(f"API Error. {err}", ephemeral=True)
        conf = int(tx_data.get("confirmations", 0))
        f_addr, tot_litoshi = tx_matches_our_address(tx_data, LITECOIN_ADDRESS); tot_ltc = litoshi_to_ltc(tot_litoshi)
        used_txids_db[txid] = {"user_id": str(interaction.user.id), "used_at": iso_now()}; save_json(USED_TXIDS_FILE, used_txids_db)
        data["last_txid"] = txid; data["status"] = "reviewing"; save_json(TICKETS_FILE, ticket_data)
        emb = discord.Embed(title="🪙 Litecoin TXID Result", description=f"**Address Match:** {'Yes' if f_addr else 'No'}\n**Confirmations:** {conf}\n**Received:** {tot_ltc:.8f} LTC", color=COLOR_SUCCESS if f_addr and conf >= LTC_MIN_CONFIRMATIONS else COLOR_WARN)
        await interaction.channel.send(embed=emb); await update_payment_summary_message(interaction.channel)
        await interaction.followup.send("TXID Check done.", ephemeral=True)

class PaymentActionView(discord.ui.View):
    def __init__(self, owner_id=None): super().__init__(timeout=None)
    @discord.ui.button(label="Promo Code", style=discord.ButtonStyle.secondary, emoji="🎟️", custom_id="apply_promo_button")
    async def apply_promo(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(PromoCodeModal())
    @discord.ui.button(label="Payment Sent", style=discord.ButtonStyle.success, emoji="✅", custom_id="payment_sent_button")
    async def payment_sent(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(str(interaction.channel.id))
        if not data: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        data["status"] = "reviewing"; save_json(TICKETS_FILE, ticket_data)
        buyer = interaction.guild.get_member(data["user_id"]); review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if review_channel: 
            embed = discord.Embed(title="🧾 Payment Review", description=f"Buyer: {buyer.mention if buyer else 'Unknown'}\nTicket: <#{interaction.channel.id}>", color=COLOR_WARN)
            await review_channel.send(content=f"<@&{STAFF_ROLE_ID}> New payment to review.", embed=embed, view=ReviewView())
        await update_payment_summary_message(interaction.channel); await interaction.response.send_message("Staff notified.", ephemeral=True)
    @discord.ui.button(label="Submit LTC TXID", style=discord.ButtonStyle.primary, emoji="🪙", custom_id="submit_txid_button")
    async def submit_txid(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(LitecoinTxidModal())
    @discord.ui.button(label="Submit Crypto TXID", style=discord.ButtonStyle.primary, emoji="🔗", custom_id="submit_generic_txid_button")
    async def submit_generic_txid(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(GenericCryptoTxidModal())

class PaymentSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="PayPal", value="paypal", emoji="💸"), discord.SelectOption(label="Litecoin", value="litecoin", emoji="🪙"), discord.SelectOption(label="Ethereum", value="ethereum", emoji="🔷"), discord.SelectOption(label="Solana", value="solana", emoji="🟣"), discord.SelectOption(label="Paysafecard", value="paysafecard", emoji="💳"), discord.SelectOption(label="Amazon Card", value="amazoncard", emoji="🎁")]
        super().__init__(placeholder="💳 Choose payment method", min_values=1, max_values=1, options=options, custom_id="buy_payment_select")
    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        data["payment_key"] = self.values[0]; save_json(TICKETS_FILE, ticket_data)
        buyer = interaction.guild.get_member(data["user_id"])
        ltc_price = await fetch_ltc_price_eur() if self.values[0] == "litecoin" else None
        await interaction.response.send_message(embed=build_order_summary(data["product_key"], self.values[0], buyer, ltc_price), view=PaymentActionView())
        await update_payment_summary_message(interaction.channel)

class PaymentSelectView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(PaymentSelect())

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="1 Day", description="5€", value="day_1", emoji="📅"), discord.SelectOption(label="1 Week", description="15€", value="week_1", emoji="🗓️"), discord.SelectOption(label="Lifetime", description="30€", value="lifetime", emoji="♾️")]
        super().__init__(placeholder="📦 Choose your product", min_values=1, max_values=1, options=options, custom_id="buy_product_select")
    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(str(interaction.channel.id))
        if not data: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        data["product_key"] = self.values[0]; save_json(TICKETS_FILE, ticket_data)
        embed = discord.Embed(title="📦 Product Selected", description=f"**{PRODUCTS[self.values[0]]['label']}** selected.\nNow choose your payment method below.", color=COLOR_INFO)
        await interaction.response.send_message(embed=embed, view=PaymentSelectView()); await update_payment_summary_message(interaction.channel)

class ProductSelectView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(ProductSelect())

class BuySetupView(discord.ui.View):
    def __init__(self, owner_id=None): super().__init__(timeout=None)
    @discord.ui.button(label="Choose Product", style=discord.ButtonStyle.primary, emoji="📦", custom_id="choose_product_button")
    async def choose_product(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_message("Select product:", view=ProductSelectView(), ephemeral=True)
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_buy_ticket_button")
    async def close_buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_message("Are you sure?", view=CloseConfirmView(), ephemeral=True)

class PaymentSummaryView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="refresh_payment_summary")
    async def refresh_summary(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.edit_message(embed=build_payment_summary_embed(interaction.channel.id), view=PaymentSummaryView())

async def process_approve(interaction: discord.Interaction, target_channel_id: int, buyer_id: int):
    try:
        channel = interaction.guild.get_channel(target_channel_id); data = ticket_data.get(str(target_channel_id))
        if not data: return await interaction.response.send_message("❌ Ticket-Daten nicht gefunden. Ticket wurde evtl. gelöscht.", ephemeral=True)
        if data.get("status") == "approved": return await interaction.response.send_message("✅ Bereits genehmigt.", ephemeral=True)
        buyer = interaction.guild.get_member(buyer_id)
        invoice_id = build_invoice_id(); data["invoice_id"] = invoice_id; data["status"] = "approved"; save_json(TICKETS_FILE, ticket_data)
        promo_code = data.get("applied_promo"); promo_discount = promos_db[promo_code]["discount"] if promo_code and promo_code in promos_db else 0
        if promo_code and promo_code in promos_db: promos_db[promo_code]["uses"] -= 1; save_json(PROMOS_FILE, promos_db)
        generated_key = generate_key(data["product_key"], ticket_id=str(target_channel_id)); keys_db[generated_key]["bound_user_id"] = str(buyer.id) if buyer else "Unknown"; save_json(KEYS_FILE, keys_db)
        final_price = get_price(data["product_key"], buyer, promo_discount)
        create_invoice_record(invoice_id, buyer_id, data["product_key"], data["payment_key"], generated_key, target_channel_id, final_price, is_reseller_dc(buyer))
        if channel: await channel.send(embed=discord.Embed(title="🧾 Payment Approved", description=f"**Invoice:** `{invoice_id}`\n**Price:** {final_price}€\n**Key:** `{generated_key}`", color=COLOR_SUCCESS)); await update_payment_summary_message(channel)
        if buyer: await dm_user_safe(buyer, embed=discord.Embed(title="🔑 Purchase Approved", description=f"**Key:** `{generated_key}`\nDu kannst dich mit diesem Key auf der Website einloggen!", color=COLOR_SUCCESS))
        await interaction.response.send_message("✅ Approved. Key wurde generiert und ans Ticket gesendet.", ephemeral=True)
    except Exception as e: await interaction.response.send_message(f"❌ Ein Fehler ist aufgetreten: {str(e)}", ephemeral=True)

async def process_deny(interaction: discord.Interaction, target_channel_id: int):
    try:
        channel = interaction.guild.get_channel(target_channel_id)
        if str(target_channel_id) in ticket_data: ticket_data[str(target_channel_id)]["status"] = "denied"; save_json(TICKETS_FILE, ticket_data)
        if channel: await channel.send(embed=discord.Embed(title="❌ Denied", description="Payment was denied.", color=COLOR_DENY)); await update_payment_summary_message(channel)
        await interaction.response.send_message("✅ Denied.", ephemeral=True)
    except Exception as e: await interaction.response.send_message(f"❌ Fehler: {str(e)}", ephemeral=True)

class AdminPanelView(discord.ui.View):
    def __init__(self, owner_id=None, ticket_channel_id=None): super().__init__(timeout=None)
    async def _get_data(self, interaction):
        embed = interaction.message.embeds[0]; desc = embed.description; b_match = re.search(r"\*\*Buyer ID:\*\* `?(\d+)`?", desc); t_match = re.search(r"\*\*Ticket ID:\*\* `?(\d+)`?", desc)
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
    def __init__(self, target_channel_id=None, buyer_id=None): super().__init__(timeout=None)
    async def _get_data(self, interaction):
        embed = interaction.message.embeds[0]; desc = embed.description; b_match = re.search(r"<@!?(\d+)>", desc); t_match = re.search(r"<#(\d+)>", desc)
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
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="💠", custom_id="main_support_ticket_button")
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button): await self.create_ticket_channel(interaction, "support")
    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, emoji="🛒", custom_id="main_buy_ticket_button")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button): await self.create_ticket_channel(interaction, "buy")
    async def create_ticket_channel(self, interaction: discord.Interaction, ticket_type: str):
        await interaction.response.defer(ephemeral=True); guild, user = interaction.guild, interaction.user
        if is_blacklisted(user.id): return await interaction.followup.send("Du bist auf der Blacklist.", ephemeral=True)
        if user.id in ticket_locks: return await interaction.followup.send("⏳ Dein Ticket wird gerade erstellt... Bitte nicht mehrmals klicken!", ephemeral=True)
        ticket_locks.add(user.id)
        try:
            existing = await find_existing_ticket(guild, user)
            if existing: return await interaction.followup.send(f"Du hast bereits ein offenes Ticket: {existing.mention}", ephemeral=True)
            category = guild.get_channel(BUY_CATEGORY_ID if ticket_type == "buy" else SUPPORT_CATEGORY_ID)
            overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False), user: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
            bot_member = guild.get_member(bot.user.id)
            if bot_member: overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role: overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
            channel_name = f"{ticket_type}-{user.name}"[:90]
            channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=f"ticket_owner:{user.id}")
            if ticket_type == "support": await channel.send(content=f"{user.mention} <@&{STAFF_ROLE_ID}>", embed=discord.Embed(title="💠 Support Ticket", description="Please describe your issue.", color=COLOR_SUPPORT), view=TicketManageView())
            else:
                ticket_data[str(channel.id)] = {"user_id": user.id, "product_key": None, "payment_key": None, "last_txid": None, "invoice_id": None, "status": "waiting", "applied_promo": None}
                save_json(TICKETS_FILE, ticket_data)
                await channel.send(content=f"{user.mention} <@&{STAFF_ROLE_ID}>", embed=discord.Embed(title="🛒 Buy Ticket", description="Click 'Choose Product' below.", color=COLOR_BUY), view=BuySetupView())
                await send_summary_and_admin_panels(channel, user.id)
            await interaction.followup.send(f"✅ Ticket erfolgreich erstellt: {channel.mention}", ephemeral=True)
        finally: ticket_locks.discard(user.id)

class RedeemKeyModal(discord.ui.Modal, title="Paste your key here"):
    key_input = discord.ui.TextInput(label="Key", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, res = await redeem_key_for_user(interaction.guild, interaction.user, str(self.key_input).strip().upper())
        if ok: await interaction.followup.send(f"✅ Success! You received the {PRODUCTS.get(res, {}).get('label', 'Unknown')} role.", ephemeral=True)
        else: await interaction.followup.send(f"❌ {res}", ephemeral=True)

class RedeemPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Redeem", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="redeem_key_button")
    async def redeem_button(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(RedeemKeyModal())

@bot.event
async def on_member_join(member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel): return
    embed = discord.Embed(title="Welcome!", description=f"Welcome {member.mention} to **{SERVER_NAME}**.\n\nRead the rules in <#{RULES_CHANNEL_ID}> to get started!", color=COLOR_WELCOME)
    embed.set_author(name=SERVER_NAME, icon_url=WELCOME_THUMBNAIL_URL)
    embed.set_thumbnail(url=WELCOME_THUMBNAIL_URL)
    embed.set_image(url=WELCOME_BANNER_URL)
    try: await channel.send(embed=embed)
    except Exception: pass

@bot.tree.command(name="nuke_database", description="(ADMIN) Löscht alle DBs (FIXT DEN KEYS BUG)!")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def nuke_database(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    global users_db, webkeys_db, web_sessions, keys_db, ticket_data, redeemed_db, used_txids_db
    users_db = {}; webkeys_db = {}; web_sessions = {}; keys_db = {}; ticket_data = {}; redeemed_db = {}; used_txids_db = {}
    save_json(USERS_FILE, users_db); save_json(WEBKEYS_FILE, webkeys_db); save_json(SESSIONS_FILE, web_sessions); save_json(KEYS_FILE, keys_db); save_json(TICKETS_FILE, ticket_data); save_json(REDEEMED_FILE, redeemed_db); save_json(USED_TXIDS_FILE, used_txids_db)
    await interaction.response.send_message("💣 **BOOM!** Website, Keys & Tickets Datenbanken wurden GELÖSCHT. Alles ist komplett resettet!", ephemeral=True)

@bot.tree.command(name="gen_admin_key", description="Generiert einen ADMIN-Einladungs-Key für die Website")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gen_admin_key(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    new_key = f"VALE-ADMIN-{random_block(6)}"
    webkeys_db[new_key] = {"role": "admin", "used": False, "created_by": str(interaction.user.name), "created_at": iso_now()}
    save_json(WEBKEYS_FILE, webkeys_db)
    ch = interaction.guild.get_channel(WEB_KEY_CHANNEL_ID)
    if ch: 
        embed = discord.Embed(title="🔐 Admin Registration Key", description=f"**Erstellt von:** {interaction.user.mention}\n**Key:** `{new_key}`\n\nNutze diesen Key, um dir einen Admin-Account auf der Website zu erstellen.", color=COLOR_MAIN)
        await ch.send(embed=embed)
    await interaction.response.send_message(f"Admin Invite Key generiert: `{new_key}`", ephemeral=True)

@bot.tree.command(name="gen_reseller_key", description="Generiert einen RESELLER-Einladungs-Key für die Website")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gen_reseller_key(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    new_key = f"VALE-RES-{random_block(6)}"
    webkeys_db[new_key] = {"role": "reseller", "used": False, "created_for": str(user.name), "created_at": iso_now()}
    save_json(WEBKEYS_FILE, webkeys_db)
    ch = interaction.guild.get_channel(WEB_KEY_CHANNEL_ID)
    if ch: 
        embed = discord.Embed(title="🔐 Reseller Registration Key", description=f"**Für User:** {user.mention}\n**Key:** `{new_key}`\n\nMit diesem Key kannst du dich registrieren.", color=COLOR_SUCCESS)
        await ch.send(embed=embed)
    await interaction.response.send_message(f"Reseller Invite Key generiert: `{new_key}`", ephemeral=True)

@bot.tree.command(name="ticket", description="Open the Gen ticket panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(title="✦ VALE GEN TICKET CENTER ✦", description=f"{premium_divider()}\n**Open a private ticket below**\n\n💠 **Support**\n> Help, questions, issues\n\n🛒 **Buy**\n> Orders, payments, purchase setup\n\n{premium_divider()}\n**Fast • Private • Premium**", color=COLOR_MAIN)
    embed.set_image(url=PANEL_IMAGE_URL)
    await interaction.response.send_message(embed=embed, view=MainTicketPanelView())

@bot.tree.command(name="send_redeem_panel", description="Send the redeem panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_redeem_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🎟️ VALE GEN REDEEM CENTER", description="Click to redeem your key.", color=COLOR_MAIN)
    await interaction.response.send_message(embed=embed, view=RedeemPanelView())

@bot.tree.command(name="vouch", description="Hinterlasse eine Bewertung für deinen Kauf!")
@app_commands.describe(sterne="Wie viele Sterne gibst du?", produkt="Was hast du gekauft?", bewertung="Deine Erfahrung")
@app_commands.choices(sterne=[app_commands.Choice(name="⭐⭐⭐⭐⭐", value=5), app_commands.Choice(name="⭐⭐⭐⭐", value=4), app_commands.Choice(name="⭐⭐⭐", value=3)])
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def vouch(interaction: discord.Interaction, sterne: app_commands.Choice[int], produkt: str, bewertung: str):
    ch = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if ch: 
        embed = discord.Embed(title=f"Vouch: {sterne.name}", description=f'"{bewertung}"', color=COLOR_MAIN)
        embed.add_field(name="Käufer", value=interaction.user.mention); embed.add_field(name="Produkt", value=produkt); embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await ch.send(embed=embed)
    await interaction.response.send_message("✅ Danke für deine Bewertung!", ephemeral=True)

@bot.tree.command(name="send_rules", description="Postet das Regelwerk")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_rules(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    embed = discord.Embed(title="📜 Server Rules", description="**1. Be Respectful**\nBehandel alle Mitglieder mit Respekt. Keine Beleidigungen, kein Rassismus, kein Spam.\n\n**2. No DM Advertising**\nKeine Werbung für andere Server oder Dienste in den DMs unserer Nutzer.\n\n**3. Support & Tickets**\nBitte eröffne für alle Anfragen oder Käufe ein Ticket im <#1490336321913356459> Bereich. Kein Support in normalen Chats.\n\n**4. Scam & Fraud**\nBetrugsversuche beim Kauf führen zu einem permanenten Ban und Blacklist.", color=COLOR_WELCOME)
    embed.set_image(url=WELCOME_BANNER_URL)
    await interaction.channel.send(embed=embed); await interaction.response.send_message("Regelwerk gepostet!", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
