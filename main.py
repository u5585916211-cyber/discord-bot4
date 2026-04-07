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
SMTP_USER = os.getenv("genG1@firstmailler.com") # Deine Firstmail Adresse
SMTP_PASS = os.getenv("RAGEONtop0") # Dein Firstmail Passwort

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

# =========================================================
# 🔥 DEINE BILDER-LINKS (PERFEKT EINGEBUNDEN!)
# =========================================================
WEBSITE_LOGO_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751701567934535/velo.png?ex=69d53236&is=69d3e0b6&hm=eeed157a58f5f3f309bb4de50df0c75e39fd90df368b4c09c666205a1611f4f9&=&format=webp&quality=lossless&width=652&height=652"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751958573645834/velo_log.png?ex=69d53273&is=69d3e0f3&hm=fe4fa4ac26ac8b32e1b67f540471804215ac6ed4767630e956057708b85cb89d&=&format=webp&quality=lossless&width=652&height=652"

WELCOME_THUMBNAIL_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751701567934535/velo.png?ex=69d53236&is=69d3e0b6&hm=eeed157a58f5f3f309bb4de50df0c75e39fd90df368b4c09c666205a1611f4f9&=&format=webp&quality=lossless&width=652&height=652"
WELCOME_BANNER_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751958573645834/velo_log.png?ex=69d53273&is=69d3e0f3&hm=fe4fa4ac26ac8b32e1b67f540471804215ac6ed4767630e956057708b85cb89d&=&format=webp&quality=lossless&width=652&height=652"

# 🔥 DER FIX FÜR DEN ABSTURZ: Diese Variable hat im letzten Code gefehlt!
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

# Lade alle Datenbanken global
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

# Globale Sperre gegen Doppel-Klicks bei Tickets
ticket_locks = set()

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

# --- NEU: AUTO-CHECKER & MAIL SENDEN ---
async def verify_ltc_payment(txid):
    if txid in used_txids_db: 
        return False, "Diese TXID wurde bereits verwendet."
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=15) as resp:
            if resp.status != 200: 
                return False, "Ungültige TXID oder Blockchain-API offline."
            data = await resp.json()
            for out in data.get("outputs", []):
                if LITECOIN_ADDRESS in out.get("addresses", []):
                    used_txids_db[txid] = {"time": iso_now()}
                    save_json(USED_TXIDS_FILE, used_txids_db)
                    return True, "Zahlung verifiziert."
    return False, "Keine Zahlung an unsere LTC Adresse gefunden."

def send_delivery_email(to_email, product_label, key):
    if not SMTP_USER or not SMTP_PASS:
        print("⚠️ Email ERROR: SMTP_USER oder SMTP_PASS fehlen in den Variablen!")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Deine Bestellung bei {SERVER_NAME} ist da! 🎉"
        
        body = f"""Hallo!

Vielen Dank für deinen Einkauf bei {SERVER_NAME}.

Hier ist dein Produktschlüssel:
Produkt: {product_label}
Key: {key}

Du kannst diesen Key auf unserer Website im 'Customer' Login verwenden oder direkt in unserem Discord-Server einlösen.

Viel Spaß!
Dein {SERVER_NAME} Team"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            
        server.login(SMTP_USER, SMTP_PASS)
        text = msg.as_string()
        server.sendmail(SMTP_USER, to_email, text)
        server.quit()
        print(f"✅ Email erfolgreich an {to_email} gesendet!")
        return True
    except Exception as e:
        print(f"⚠️ FEHLER BEIM SENDEN DER EMAIL an {to_email}: {e}")
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
# 🌍 WEB DASHBOARD HTML (ULTRA PREMIUM DESIGN)
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
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;500;700;900&display=swap');
        body { font-family: 'Space Grotesk', sans-serif; background-color: #030305; color: #e5e7eb; margin: 0; overflow-x: hidden; }
        
        .synthwave-bg { background: radial-gradient(circle at 50% -20%, #2a0845, #030305 60%); position: fixed; inset: 0; z-index: -2; }
        .synthwave-grid {
            position: fixed; bottom: 0; left: -50%; width: 200%; height: 50%;
            background-image: linear-gradient(rgba(147, 51, 234, 0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(147, 51, 234, 0.15) 1px, transparent 1px);
            background-size: 40px 40px; transform: perspective(1000px) rotateX(70deg);
            animation: gridMove 3s linear infinite; z-index: -1;
        }
        @keyframes gridMove { 0% { background-position: 0 0; } 100% { background-position: 0 40px; } }

        .glass { background: rgba(10, 10, 15, 0.6); backdrop-filter: blur(20px); border: 1px solid rgba(147, 51, 234, 0.2); box-shadow: 0 0 30px rgba(0,0,0,0.5); }
        .glow-text { background: linear-gradient(to right, #c084fc, #e879f9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 0 10px rgba(168,85,247,0.5)); }
        .glow-box { box-shadow: 0 0 40px rgba(147, 51, 234, 0.3); }
        .hidden-view { display: none !important; }
        .tab-content { display: none; } 
        .tab-content.active { display: block; animation: fadeIn 0.4s ease forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: rgba(0,0,0,0.5); } ::-webkit-scrollbar-thumb { background: #9333ea; border-radius: 4px; }
        
        .premium-btn { background: linear-gradient(90deg, #9333ea, #db2777); transition: all 0.3s; }
        .premium-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px -5px rgba(219, 39, 119, 0.5); }
    </style>
</head>
<body class="flex h-screen selection:bg-purple-500 selection:text-white relative">

    <div class="synthwave-bg"></div>
    <div class="synthwave-grid"></div>

    <nav class="absolute top-0 w-full z-50 px-8 py-6 flex justify-between items-center bg-black/20 backdrop-blur-md border-b border-purple-500/20">
        <div class="flex items-center gap-4 cursor-pointer" onclick="switchAuth('shop')">
            <img src="LOGO_URL_PLACEHOLDER" class="h-12 w-12 rounded-xl shadow-[0_0_15px_rgba(168,85,247,0.5)] object-cover">
            <span class="text-2xl font-black tracking-widest uppercase">VALE <span class="glow-text">GEN</span></span>
        </div>
        <div class="flex gap-6">
            <button onclick="switchAuth('shop')" class="font-bold text-gray-300 hover:text-white transition uppercase tracking-wider text-sm">Store</button>
            <button onclick="switchAuth('login')" class="font-bold text-purple-400 hover:text-purple-300 transition uppercase tracking-wider text-sm border border-purple-500/50 px-4 py-2 rounded-lg hover:bg-purple-500/10">Login</button>
        </div>
    </nav>

    <div id="view-auth" class="w-full h-full flex flex-col pt-24 pb-10 px-4 relative z-10 overflow-y-auto">
        
        <div id="form-shop" class="max-w-6xl w-full mx-auto mt-10">
            <div class="text-center mb-16">
                <h1 class="text-5xl md:text-7xl font-black mb-6 tracking-tighter uppercase">Unlock the <span class="glow-text">Future.</span></h1>
                <p class="text-gray-400 text-lg font-medium max-w-2xl mx-auto">Kaufe deinen Premium Key, verifiziere automatisch via Blockchain und erhalte direkten Zugang per E-Mail & Dashboard.</p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-t-4 border-green-500 hover:-translate-y-2 transition duration-300">
                    <div class="bg-green-500/10 text-green-400 px-4 py-1 rounded-full text-xs font-black tracking-widest mb-6 border border-green-500/20">STARTER</div>
                    <h3 class="text-3xl font-bold mb-2">1 Day Access</h3>
                    <div class="text-5xl font-black text-white mb-8">5.00€</div>
                    <ul class="text-gray-400 space-y-3 mb-10 w-full text-sm font-medium">
                        <li><i class="fa-solid fa-check text-green-500 mr-2"></i>24 Hours Access</li>
                        <li><i class="fa-solid fa-check text-green-500 mr-2"></i>All Features</li>
                    </ul>
                    <button onclick="openCheckout('day_1', '5.00')" class="mt-auto w-full bg-white/5 border border-white/10 hover:bg-green-500 hover:border-green-500 py-4 rounded-xl font-black uppercase tracking-widest transition">Buy Now</button>
                </div>
                
                <div class="glass p-10 rounded-[2.5rem] flex flex-col items-center border-t-4 border-purple-500 scale-100 md:scale-110 relative shadow-[0_0_50px_rgba(168,85,247,0.15)] z-10">
                    <div class="absolute top-4 right-6 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-[10px] font-black px-4 py-1 rounded-full uppercase shadow-lg">Most Popular</div>
                    <div class="bg-purple-500/10 text-purple-400 px-4 py-1 rounded-full text-xs font-black tracking-widest mb-6 border border-purple-500/20">PREMIUM</div>
                    <h3 class="text-3xl font-bold mb-2">1 Week Access</h3>
                    <div class="text-5xl font-black text-white mb-8">15.00€</div>
                    <ul class="text-gray-300 space-y-3 mb-10 w-full text-sm font-medium">
                        <li><i class="fa-solid fa-check text-purple-400 mr-2"></i>7 Days Access</li>
                        <li><i class="fa-solid fa-check text-purple-400 mr-2"></i>All Features</li>
                        <li><i class="fa-solid fa-bolt text-purple-400 mr-2"></i>Priority Support</li>
                    </ul>
                    <button onclick="openCheckout('week_1', '15.00')" class="mt-auto w-full premium-btn text-white py-4 rounded-xl font-black uppercase tracking-widest">Buy Now</button>
                </div>
                
                <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-t-4 border-yellow-500 hover:-translate-y-2 transition duration-300">
                    <div class="bg-yellow-500/10 text-yellow-500 px-4 py-1 rounded-full text-xs font-black tracking-widest mb-6 border border-yellow-500/20">ULTIMATE</div>
                    <h3 class="text-3xl font-bold mb-2">Lifetime Access</h3>
                    <div class="text-5xl font-black text-white mb-8">30.00€</div>
                    <ul class="text-gray-400 space-y-3 mb-10 w-full text-sm font-medium">
                        <li><i class="fa-solid fa-check text-yellow-500 mr-2"></i>Permanent Access</li>
                        <li><i class="fa-solid fa-check text-yellow-500 mr-2"></i>All Features</li>
                        <li><i class="fa-solid fa-star text-yellow-500 mr-2"></i>VIP Discord Role</li>
                    </ul>
                    <button onclick="openCheckout('lifetime', '30.00')" class="mt-auto w-full bg-white/5 border border-white/10 hover:bg-yellow-500 hover:border-yellow-500 py-4 rounded-xl font-black uppercase tracking-widest transition text-white">Buy Now</button>
                </div>
            </div>
        </div>

        <div id="auth-forms-container" class="max-w-md w-full mx-auto mt-20 hidden-view">
            <div class="glass p-10 rounded-[2rem] relative glow-box">
                <div class="flex border-b border-white/10 mb-8">
                    <button onclick="switchAuth('login')" id="auth-tab-login" class="flex-1 pb-4 text-purple-400 font-bold border-b-2 border-purple-500 transition tracking-widest uppercase text-sm">Admin</button>
                    <button onclick="switchAuth('customer')" id="auth-tab-customer" class="flex-1 pb-4 text-gray-500 font-bold hover:text-white transition border-b-2 border-transparent tracking-widest uppercase text-sm">Customer</button>
                    <button onclick="switchAuth('register')" id="auth-tab-register" class="flex-1 pb-4 text-gray-500 font-bold hover:text-white transition border-b-2 border-transparent tracking-widest uppercase text-sm">Register</button>
                </div>

                <div id="form-login" class="space-y-5">
                    <input type="text" id="l-user" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-4 text-white outline-none focus:border-purple-500 transition" placeholder="Username">
                    <input type="password" id="l-pass" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-4 text-white outline-none focus:border-purple-500 transition" placeholder="Password">
                    <button onclick="login()" class="w-full premium-btn text-white font-black py-4 rounded-xl uppercase tracking-widest mt-4">Login</button>
                </div>

                <div id="form-customer" class="space-y-5 hidden-view">
                    <p class="text-sm text-gray-400 text-center mb-4">Logge dich mit deinem gekauften Key ein.</p>
                    <input type="text" id="c-key" class="w-full bg-black/50 border border-pink-500/50 rounded-xl px-5 py-4 text-pink-400 font-mono focus:border-pink-500 outline-none transition text-center tracking-widest" placeholder="GEN-...">
                    <button onclick="customerLogin()" class="w-full bg-gradient-to-r from-pink-600 to-rose-500 hover:from-pink-500 hover:to-rose-400 text-white font-black py-4 rounded-xl uppercase tracking-widest shadow-[0_0_20px_rgba(236,72,153,0.3)] mt-4 transition">Access Dashboard</button>
                </div>

                <div id="form-register" class="space-y-5 hidden-view">
                    <input type="text" id="r-user" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-4 text-white outline-none focus:border-purple-500 transition" placeholder="Username">
                    <input type="password" id="r-pass" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-4 text-white outline-none focus:border-purple-500 transition" placeholder="Password">
                    <input type="text" id="r-key" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-4 text-purple-400 font-mono focus:border-purple-500 outline-none transition" placeholder="Invite Key (VALE-...)">
                    <button onclick="register()" class="w-full bg-white/10 hover:bg-white/20 border border-white/10 text-white font-black py-4 rounded-xl uppercase tracking-widest mt-4 transition">Create Account</button>
                </div>
                
                <p id="auth-error" class="text-red-400 mt-6 text-sm text-center font-bold hidden"></p>
            </div>
        </div>
    </div>

    <div id="checkout-modal" class="fixed inset-0 bg-black/95 backdrop-blur-xl hidden-view flex items-center justify-center p-4 z-50">
        <div class="glass p-8 md:p-12 rounded-[2.5rem] border border-purple-500/30 shadow-[0_0_80px_rgba(168,85,247,0.2)] max-w-lg w-full relative">
            <button onclick="closeCheckout()" class="absolute top-6 right-8 text-gray-500 hover:text-white text-3xl transition">&times;</button>
            <h2 class="text-3xl font-black text-white mb-8 text-center uppercase tracking-widest">Secure <span class="glow-text">Checkout</span></h2>
            
            <div id="co-step-1">
                <div class="space-y-6">
                    <div>
                        <label class="text-[11px] font-black text-gray-500 uppercase tracking-widest ml-1">1. Delivery Email</label>
                        <input type="email" id="co-email" class="w-full bg-black/60 border border-white/10 rounded-xl px-5 py-4 mt-2 text-white outline-none focus:border-purple-500 transition" placeholder="deine@email.com">
                    </div>
                    
                    <div class="bg-purple-500/5 border border-purple-500/20 p-5 rounded-2xl text-center">
                        <label class="text-[11px] font-black text-purple-400 uppercase tracking-widest">2. Send Litecoin (LTC)</label>
                        <p class="text-2xl font-black text-white my-2"><span id="co-price"></span>€</p>
                        <div class="bg-black/50 p-3 rounded-lg border border-white/5 font-mono text-[11px] text-gray-300 break-all cursor-pointer hover:bg-black/80 transition" onclick="navigator.clipboard.writeText('LTC_ADDR'); alert('Kopiert!')">
                            LTC_ADDR <i class="fa-regular fa-copy ml-2"></i>
                        </div>
                    </div>
                    
                    <div>
                        <label class="text-[11px] font-black text-gray-500 uppercase tracking-widest ml-1">3. Litecoin TXID (Hash)</label>
                        <input type="text" id="co-txid" class="w-full bg-black/60 border border-white/10 rounded-xl px-5 py-4 mt-2 text-white outline-none focus:border-blue-500 transition font-mono text-sm" placeholder="Paste TXID here...">
                    </div>
                </div>
                
                <p id="co-error" class="text-red-400 mt-6 mb-2 text-sm font-bold text-center hidden"></p>
                <button onclick="processCheckout()" id="btn-checkout" class="w-full premium-btn text-white font-black py-5 rounded-xl uppercase tracking-widest text-sm mt-8">Verify Payment & Get Key</button>
            </div>

            <div id="co-step-2" class="hidden-view text-center py-6">
                <i class="fa-solid fa-shield-check text-7xl text-green-500 mb-6 drop-shadow-[0_0_20px_rgba(34,197,94,0.5)]"></i>
                <h3 class="text-3xl font-black text-white mb-2 uppercase tracking-widest">Payment Verified</h3>
                <p class="text-gray-400 mb-8 font-medium">Dein Key wurde an deine E-Mail gesendet.</p>
                <div class="bg-black/60 border border-green-500/50 p-5 rounded-2xl mb-8">
                    <p class="text-xs text-green-400 font-bold uppercase tracking-widest mb-2">Dein Key</p>
                    <p id="co-success-key" class="font-mono text-white text-xl font-black tracking-wider break-all select-all"></p>
                </div>
                <button onclick="window.location.reload()" class="w-full bg-white/10 hover:bg-white/20 border border-white/10 text-white font-black py-4 rounded-xl uppercase tracking-widest transition">Zum Dashboard</button>
            </div>
        </div>
    </div>

    <div id="view-customer" class="flex w-full h-full hidden-view p-8 z-10 relative">
        <div class="max-w-3xl mx-auto w-full">
            <header class="flex justify-between items-center mb-8 glass p-6 rounded-3xl">
                <div class="flex items-center">
                    <img src="LOGO_URL_PLACEHOLDER" class="h-16 mr-4 rounded-xl">
                    <div>
                        <h1 class="text-2xl font-black text-white uppercase tracking-widest">Customer Portal</h1>
                        <p class="text-sm text-pink-400 font-mono font-bold" id="cust-key-display">GEN-...</p>
                    </div>
                </div>
                <button onclick="logout()" class="bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 px-6 py-3 rounded-xl font-bold transition">Logout</button>
            </header>
            
            <div class="glass p-10 rounded-[2.5rem] text-center border-t-4 border-pink-500">
                <h2 class="text-gray-500 font-bold uppercase tracking-widest mb-2 text-sm">Your Product</h2>
                <h3 class="text-5xl font-black text-white glow-text mb-12" id="cust-prod">Loading...</h3>
                
                <div class="grid grid-cols-2 gap-6 mb-8">
                    <div class="bg-black/40 p-6 rounded-2xl border border-white/5">
                        <i class="fa-solid fa-shield-halved text-3xl text-pink-400 mb-4"></i>
                        <p class="text-xs text-gray-500 font-bold uppercase tracking-widest">Status</p>
                        <p class="text-xl font-black text-white mt-2" id="cust-status">Loading</p>
                    </div>
                    <div class="bg-black/40 p-6 rounded-2xl border border-white/5">
                        <i class="fa-brands fa-discord text-3xl text-purple-400 mb-4"></i>
                        <p class="text-xs text-gray-500 font-bold uppercase tracking-widest">Bound To</p>
                        <p class="text-lg font-mono text-white mt-2" id="cust-discord">None</p>
                    </div>
                </div>
                <p class="text-xs text-gray-600 font-bold uppercase tracking-widest">Created: <span id="cust-created" class="text-gray-400"></span></p>
            </div>
        </div>
    </div>

    <div id="view-admin" class="flex w-full h-full hidden-view z-10 relative">
        <aside class="w-64 glass border-r border-white/5 flex flex-col justify-between">
            <div>
                <div class="h-32 flex items-center justify-center border-b border-white/5 px-4">
                    <span class="text-2xl font-black text-white glow-text tracking-widest uppercase">ADMIN</span>
                </div>
                <nav class="p-4 space-y-2 mt-4">
                    <button onclick="nav('dash')" id="btn-dash" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 bg-purple-500/10 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-chart-pie w-6"></i> Dashboard</button>
                    <button onclick="nav('gen')" id="btn-gen" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-bolt w-6 text-yellow-400"></i> Generator</button>
                    <button onclick="nav('keys')" id="btn-keys" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-key w-6 text-purple-400"></i> Keys</button>
                    <button onclick="nav('team')" id="btn-team" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-users w-6 text-blue-400"></i> Team</button>
                    <button onclick="nav('promos')" id="btn-promos" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-tags w-6 text-pink-400"></i> Promos</button>
                    <button onclick="nav('lookup')" id="btn-lookup" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-search w-6 text-green-400"></i> Database</button>
                    <button onclick="nav('announce')" id="btn-announce" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-satellite-dish w-6 text-orange-400"></i> Broadcast</button>
                    <button onclick="nav('blacklist')" id="btn-blacklist" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"><i class="fa-solid fa-skull w-6 text-red-500"></i> Blacklist</button>
                </nav>
            </div>
            <div class="p-6 border-t border-white/5">
                <button onclick="logout()" class="w-full text-red-400 bg-red-500/10 hover:bg-red-500/20 font-bold py-3 rounded-xl transition text-sm tracking-widest uppercase">Logout</button>
            </div>
        </aside>

        <main class="flex-1 overflow-y-auto p-8">
            <div class="max-w-7xl mx-auto">
                <header class="flex justify-between items-center mb-8 glass p-6 rounded-3xl">
                    <h2 id="page-title" class="text-2xl font-black text-white tracking-widest uppercase glow-text">Dashboard</h2>
                    <div class="flex items-center gap-4">
                        <span class="text-sm text-gray-500 font-bold uppercase tracking-widest">Admin <span id="admin-name" class="text-white ml-2"></span></span>
                    </div>
                </header>

                <div id="dash" class="tab-content active">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                        <div class="glass p-8 rounded-3xl border-t-4 border-purple-500"><p class="text-xs font-bold text-gray-500 uppercase tracking-widest">Total Revenue</p><h3 class="text-4xl font-black text-white mt-3" id="stat-rev">0.00€</h3></div>
                        <div class="glass p-8 rounded-3xl border-t-4 border-pink-500"><p class="text-xs font-bold text-gray-500 uppercase tracking-widest">Orders Today</p><h3 class="text-4xl font-black text-white mt-3" id="stat-orders">0</h3></div>
                        <div class="glass p-8 rounded-3xl border-t-4 border-blue-500"><p class="text-xs font-bold text-gray-500 uppercase tracking-widest">Active Keys</p><h3 class="text-4xl font-black text-white mt-3" id="stat-keys">0</h3></div>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                        <div class="lg:col-span-2 glass p-8 rounded-3xl"><h3 class="text-sm font-bold text-gray-500 uppercase tracking-widest mb-6">Revenue Chart</h3><canvas id="revenueChart" height="100"></canvas></div>
                        <div class="lg:col-span-1 glass p-8 rounded-3xl flex flex-col"><h3 class="text-sm font-bold text-gray-500 uppercase tracking-widest mb-6">Activity Log</h3><div id="activity-feed" class="flex-1 overflow-y-auto space-y-3 pr-2"></div></div>
                    </div>
                </div>
                
                <div id="gen" class="tab-content">
                    <div class="glass p-10 rounded-3xl border-t-4 border-purple-500 max-w-2xl mx-auto mt-10">
                        <h2 class="text-xl font-black mb-8 text-center text-white uppercase tracking-widest">Generator</h2>
                        <div class="space-y-4">
                            <button onclick="genAdminKey('day_1')" class="w-full bg-white/5 hover:bg-white/10 p-5 rounded-2xl flex justify-between items-center transition border border-white/5">
                                <span class="font-black tracking-widest uppercase text-sm">1 Day Key</span><i class="fa-solid fa-plus text-purple-400"></i>
                            </button>
                            <button onclick="genAdminKey('week_1')" class="w-full bg-white/5 hover:bg-white/10 p-5 rounded-2xl flex justify-between items-center transition border border-white/5">
                                <span class="font-black tracking-widest uppercase text-sm">1 Week Key</span><i class="fa-solid fa-plus text-pink-400"></i>
                            </button>
                            <button onclick="genAdminKey('lifetime')" class="w-full premium-btn p-5 rounded-2xl flex justify-between items-center text-white transition">
                                <span class="font-black tracking-widest uppercase text-sm">Lifetime Key</span><i class="fa-solid fa-star text-yellow-300"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <div id="keys" class="tab-content">
                    <div class="glass rounded-3xl overflow-hidden">
                        <div class="p-6 border-b border-white/10 bg-black/20"><h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest">Key Database</h3></div>
                        <div class="overflow-x-auto max-h-[600px] p-2">
                            <table class="w-full text-left text-sm whitespace-nowrap">
                                <thead class="text-gray-500 sticky top-0 bg-black/90 backdrop-blur-md z-10">
                                    <tr><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Key</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Type</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Creator</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Used By (ID)</th><th class="px-6 py-4 font-bold tracking-wider uppercase text-xs">Status</th><th class="px-6 py-4 text-right font-bold tracking-wider uppercase text-xs">Action</th></tr>
                                </thead>
                                <tbody id="table-keys" class="divide-y divide-white/5"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="team" class="tab-content"><div class="glass rounded-3xl overflow-hidden"><div class="p-6 border-b border-white/10"><h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest">Reseller Management</h3></div><div class="p-2"><table class="w-full text-left text-sm"><thead class="text-gray-500"><tr><th class="px-6 py-4 text-xs font-bold uppercase">Username</th><th class="px-6 py-4 text-xs font-bold uppercase">Password</th><th class="px-6 py-4 text-xs font-bold uppercase">Keys</th><th class="px-6 py-4 text-right text-xs font-bold uppercase">Action</th></tr></thead><tbody id="table-team" class="divide-y divide-white/5"></tbody></table></div></div></div>
                <div id="promos" class="tab-content"><div class="grid grid-cols-1 md:grid-cols-3 gap-6"><div class="md:col-span-1 glass p-8 rounded-3xl"><h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest mb-6">New Promo</h3><input type="text" id="p-code" placeholder="Code" class="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 mb-4 text-white uppercase outline-none"><input type="number" id="p-disc" placeholder="Discount %" class="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 mb-4 text-white outline-none"><input type="number" id="p-uses" placeholder="Max Uses" class="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 mb-6 text-white outline-none"><button onclick="createPromo()" class="w-full premium-btn py-3 rounded-xl font-bold uppercase tracking-widest text-sm text-white">Create</button></div><div class="md:col-span-2 glass rounded-3xl overflow-hidden"><div class="p-6 border-b border-white/10"><h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest">Active Promos</h3></div><div class="p-2"><table class="w-full text-left text-sm"><thead class="text-gray-500"><tr><th class="p-4 text-xs font-bold uppercase">Code</th><th class="p-4 text-xs font-bold uppercase">Discount</th><th class="p-4 text-xs font-bold uppercase">Uses Left</th><th class="p-4 text-right text-xs font-bold uppercase">Action</th></tr></thead><tbody id="table-promos" class="divide-y divide-white/5"></tbody></table></div></div></div></div>
                <div id="lookup" class="tab-content"><div class="glass p-6 rounded-3xl mb-6 flex gap-4"><input type="text" id="lookup-id" placeholder="Discord ID..." class="flex-1 bg-black/50 border border-white/10 rounded-xl px-5 py-3 outline-none font-mono"><button onclick="lookupUser()" class="premium-btn px-8 font-bold rounded-xl text-white uppercase tracking-widest text-sm">Search</button></div><div id="lookup-result" class="hidden"><div class="grid grid-cols-3 gap-6 mb-6"><div class="glass p-6 rounded-2xl"><p class="text-xs text-gray-500 font-bold uppercase tracking-widest">Spent</p><h3 id="lu-spent" class="text-2xl font-black mt-2">0.00€</h3></div><div class="glass p-6 rounded-2xl"><p class="text-xs text-gray-500 font-bold uppercase tracking-widest">Orders</p><h3 id="lu-orders" class="text-2xl font-black mt-2">0</h3></div><div class="glass p-6 rounded-2xl"><p class="text-xs text-gray-500 font-bold uppercase tracking-widest">Status</p><h3 id="lu-banned" class="text-xl font-black mt-2">Clean</h3></div></div><div class="glass rounded-3xl overflow-hidden"><div class="p-6 border-b border-white/10"><h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest">History</h3></div><table class="w-full text-left text-sm"><thead class="text-gray-500"><tr><th class="p-4 text-xs font-bold uppercase">Invoice</th><th class="p-4 text-xs font-bold uppercase">Product</th><th class="p-4 text-xs font-bold uppercase">Price</th><th class="p-4 text-xs font-bold uppercase">Date</th></tr></thead><tbody id="lu-table" class="divide-y divide-white/5"></tbody></table></div></div></div>
                <div id="announce" class="tab-content"><div class="glass p-8 rounded-3xl max-w-2xl mx-auto mt-10"><h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest mb-6 text-center">Broadcast</h3><input type="text" id="ann-title" placeholder="Titel" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-3 mb-4 outline-none"><textarea id="ann-desc" placeholder="Nachricht..." rows="5" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-3 mb-4 outline-none"></textarea><input type="text" id="ann-img" placeholder="Bild URL (Optional)" class="w-full bg-black/50 border border-white/10 rounded-xl px-5 py-3 mb-6 outline-none"><button onclick="sendAnnounce()" class="w-full premium-btn py-4 rounded-xl font-bold uppercase tracking-widest text-sm text-white">Senden</button></div></div>
                <div id="blacklist" class="tab-content"><div class="glass p-6 rounded-3xl mb-6 flex gap-4"><input type="text" id="bl-id" placeholder="Discord ID..." class="flex-1 bg-black/50 border border-white/10 rounded-xl px-5 py-3 outline-none font-mono"><input type="text" id="bl-reason" placeholder="Grund" class="flex-1 bg-black/50 border border-white/10 rounded-xl px-5 py-3 outline-none"><button onclick="addBlacklist()" class="bg-red-600 hover:bg-red-500 px-8 font-bold rounded-xl text-white uppercase tracking-widest text-sm transition">Ban</button></div><div class="glass rounded-3xl overflow-hidden"><div class="p-6 border-b border-white/10"><h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest">Banned Users</h3></div><table class="w-full text-left text-sm"><thead class="text-gray-500"><tr><th class="p-4 text-xs font-bold uppercase">ID</th><th class="p-4 text-xs font-bold uppercase">Reason</th><th class="p-4 text-right text-xs font-bold uppercase">Action</th></tr></thead><tbody id="table-blacklist" class="divide-y divide-white/5"></tbody></table></div></div>
                
            </div>
        </main>
    </div>

    <div id="key-modal" class="fixed inset-0 bg-black/95 backdrop-blur-xl hidden-view flex items-center justify-center p-4 z-50">
        <div class="glass p-12 rounded-[3rem] text-center max-w-md w-full relative">
            <h3 class="text-2xl font-black text-white mb-2 uppercase tracking-widest">Erfolgreich</h3>
            <p class="text-gray-400 mb-8 text-sm font-bold">Key generiert & kopiert.</p>
            <input type="text" id="new-key" class="w-full bg-black/50 border border-white/10 p-5 rounded-2xl text-purple-400 font-mono text-center mb-8 text-sm outline-none" readonly>
            <button onclick="document.getElementById('key-modal').classList.add('hidden-view')" class="w-full bg-white/10 hover:bg-white/20 text-white font-black py-4 rounded-xl transition uppercase tracking-widest text-sm border border-white/10">Schließen</button>
        </div>
    </div>

    <script>
        let myChart = null;
        let selectedProduct = "";

        // UI Logic
        function switchAuth(type) {
            document.getElementById('view-shop').classList.add('hidden-view');
            document.getElementById('auth-forms-container').classList.add('hidden-view');
            
            if(type === 'shop') {
                document.getElementById('view-shop').classList.remove('hidden-view');
            } else {
                document.getElementById('auth-forms-container').classList.remove('hidden-view');
                document.getElementById('form-login').classList.add('hidden-view'); 
                document.getElementById('form-register').classList.add('hidden-view');
                document.getElementById('form-customer').classList.add('hidden-view');
                
                document.getElementById('auth-tab-login').className = "flex-1 pb-4 text-gray-500 font-bold hover:text-white transition border-b-2 border-transparent tracking-widest uppercase text-sm";
                document.getElementById('auth-tab-customer').className = "flex-1 pb-4 text-gray-500 font-bold hover:text-white transition border-b-2 border-transparent tracking-widest uppercase text-sm";
                document.getElementById('auth-tab-register').className = "flex-1 pb-4 text-gray-500 font-bold hover:text-white transition border-b-2 border-transparent tracking-widest uppercase text-sm";
                
                document.getElementById('form-' + type).classList.remove('hidden-view');
                let color = type === 'customer' ? 'pink' : 'purple';
                document.getElementById('auth-tab-' + type).className = `flex-1 pb-4 text-${color}-400 font-bold border-b-2 border-${color}-500 transition tracking-widest uppercase text-sm`;
                document.getElementById('auth-error').classList.add('hidden');
            }
        }

        // Shop Logic
        function openCheckout(id, price) {
            selectedProduct = id;
            document.getElementById('co-price').innerText = price;
            document.getElementById('co-step-1').classList.remove('hidden-view');
            document.getElementById('co-step-2').classList.add('hidden-view');
            document.getElementById('checkout-modal').classList.remove('hidden-view');
        }
        
        function closeCheckout() { 
            document.getElementById('checkout-modal').classList.add('hidden-view'); 
        }

        async function processCheckout() {
            const email = document.getElementById('co-email').value;
            const txid = document.getElementById('co-txid').value;
            const btn = document.getElementById('btn-checkout');
            const err = document.getElementById('co-error');

            if(!email || !email.includes('@')) { err.innerText = "Bitte gültige E-Mail eingeben."; err.classList.remove('hidden'); return; }
            if(!txid) { err.innerText = "Bitte TXID eingeben."; err.classList.remove('hidden'); return; }

            err.classList.add('hidden');
            btn.disabled = true;
            btn.innerHTML = '<span class="loader"></span> Prüfe Blockchain...';

            try {
                const res = await fetch('/api/web_buy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email, txid: txid, product: selectedProduct})
                });
                const data = await res.json();
                
                if(data.ok) {
                    document.getElementById('co-success-key').value = data.key;
                    document.getElementById('co-step-1').classList.add('hidden-view');
                    document.getElementById('co-step-2').classList.remove('hidden-view');
                } else {
                    err.innerText = data.error;
                    err.classList.remove('hidden');
                    btn.disabled = false;
                    btn.innerText = "Zahlung Verifizieren";
                }
            } catch(e) {
                err.innerText = "Server Fehler.";
                err.classList.remove('hidden');
                btn.disabled = false;
                btn.innerText = "Zahlung Verifizieren";
            }
        }

        // Auth Logic (Unverändert, greift auf Original-Endpoints zu)
        async function apiCall(endpoint, data) {
            const token = localStorage.getItem('v_token');
            const headers = {'Content-Type': 'application/json'};
            if (token) headers['Authorization'] = token;
            try {
                const res = await fetch(endpoint, { method: 'POST', headers: headers, body: JSON.stringify(data) });
                if (res.status === 401 && endpoint !== '/api/login' && endpoint !== '/api/register' && endpoint !== '/api/customer_login') { logout(); throw new Error('Unauthorized'); }
                return res;
            } catch (e) { throw e; }
        }

        function showError(msg) { const e = document.getElementById('auth-error'); e.innerHTML = msg; e.classList.remove('hidden'); }

        async function login() {
            const u = document.getElementById('l-user').value, p = document.getElementById('l-pass').value;
            if (!u || !p) return showError("Bitte fülle alle Felder aus.");
            try {
                const res = await apiCall('/api/login', {user: u, pass: p});
                if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } 
                else { showError("Falscher Username oder Passwort!"); }
            } catch (e) {}
        }

        async function customerLogin() {
            const k = document.getElementById('c-key').value;
            if (!k) return showError("Bitte gib einen Key ein.");
            try {
                const res = await apiCall('/api/customer_login', {key: k});
                if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } 
                else { const e = await res.json(); showError(e.error || "Key nicht gefunden."); }
            } catch (e) {}
        }

        async function register() {
            const u = document.getElementById('r-user').value, p = document.getElementById('r-pass').value, k = document.getElementById('r-key').value;
            if (!u || !p || !k) return showError("Bitte fülle alle Felder aus.");
            try {
                const res = await apiCall('/api/register', {user: u, pass: p, key: k});
                if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } 
                else { const e = await res.json(); showError(e.error || "Fehler bei Registrierung!"); }
            } catch (e) {}
        }

        function logout() { localStorage.removeItem('v_token'); location.reload(); }

        async function checkAuthOnLoad() {
            switchAuth('shop'); // Default view
            const t = localStorage.getItem('v_token');
            if (t) {
                try {
                    const res = await fetch('/api/verify', { method: 'POST', headers: {'Authorization': t, 'Content-Type': 'application/json'}, body: JSON.stringify({}) });
                    if (res.ok) { const d = await res.json(); initApp(d.role, d.user); } 
                    else if (res.status === 401) { logout(); } 
                } catch(e) {}
            }
        }

        function initApp(role, name) {
            document.getElementById('view-shop').classList.add('hidden-view');
            document.getElementById('auth-forms-container').classList.add('hidden-view');
            
            if (role === 'admin') { 
                document.getElementById('view-admin').classList.remove('hidden-view'); 
                document.getElementById('admin-name').innerText = name; 
                nav('dash'); loadDiscordStats(); setInterval(loadDiscordStats, 10000);
            } else if (role === 'customer') {
                document.getElementById('view-customer').classList.remove('hidden-view'); 
                document.getElementById('cust-key-display').innerText = name;
                loadCustomerData();
            }
        }

        function nav(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            document.querySelectorAll('.nav-btn').forEach(el => { el.className = "nav-btn w-full text-left py-4 px-5 rounded-xl text-gray-400 hover:bg-white/5 font-bold text-sm tracking-wide transition"; });
            document.getElementById('btn-' + tabId).className = "nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 bg-purple-500/10 font-bold text-sm tracking-wide transition";
            const titles = {'dash': 'Overview', 'gen': 'Key Generator', 'keys': 'Keys Database', 'team': 'Team Management', 'promos': 'Promo Codes', 'lookup': 'User Lookup', 'announce': 'Broadcast', 'blacklist': 'Blacklist'};
            document.getElementById('page-title').innerText = titles[tabId];
            
            if (tabId === 'dash') { loadDashboard(); loadActivity(); }
            if (tabId === 'keys') loadKeys();
            if (tabId === 'team') loadTeam();
            if (tabId === 'promos') loadPromos();
            if (tabId === 'blacklist') loadBlacklist();
        }

        // Admin API Calls (Original Logik beibehalten)
        async function loadDiscordStats() { try { const res = await apiCall('/api/discord_stats', {}); const data = await res.json(); document.getElementById('dc-members').innerText = data.members; document.getElementById('dc-tickets').innerText = data.open_tickets; } catch(e){} }
        async function loadDashboard() {
            try {
                const res = await apiCall('/api/stats', {}); const data = await res.json();
                document.getElementById('stat-rev').innerText = data.total_revenue.toFixed(2) + '€'; document.getElementById('stat-orders').innerText = data.buyers_today; document.getElementById('stat-keys').innerText = data.active_keys;
                const ctx = document.getElementById('revenueChart').getContext('2d');
                if (myChart) myChart.destroy();
                myChart = new Chart(ctx, { type: 'line', data: { labels: data.chart_labels, datasets: [{ label: 'Revenue', data: data.chart_data, borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.1)', borderWidth: 3, fill: true, tension: 0.4 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: {display: false} }, scales: { y: {grid: {color: 'rgba(255,255,255,0.05)'}}, x: {grid: {color: 'rgba(255,255,255,0.05)'}} } } });
            } catch(e) {}
        }
        async function loadActivity() { try { const res = await apiCall('/api/activity', {}); const data = await res.json(); document.getElementById('activity-feed').innerHTML = data.map(a => `<div class="p-4 bg-white/5 rounded-xl flex justify-between items-center border border-white/5"><div><span class="font-bold text-purple-400 text-xs mr-2 uppercase tracking-wide">${a.user}</span><span class="text-xs text-gray-300 font-medium">${a.action}</span></div><span class="text-[10px] text-gray-500 font-mono">${a.time.split('T')[1].substring(0,5)}</span></div>`).join(''); } catch(e) {} }
        async function loadKeys() { try { const res = await apiCall('/api/keys', {}); const data = await res.json(); const tb = document.getElementById('table-keys'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-gray-500 text-xs font-bold uppercase">Empty</td></tr>'; tb.innerHTML = Object.entries(data).reverse().map(([key, info]) => { if(typeof info !== 'object' || info === null) return ''; let badge = info.used ? '<span class="text-red-400">Used</span>' : '<span class="text-green-400">Active</span>'; if (info.revoked) badge = '<span class="text-gray-500">Banned</span>'; const act = !info.revoked ? `<button onclick="revokeKey('${key}')" class="text-red-400 hover:text-red-300">Ban</button>` : '-'; return `<tr><td class="px-6 py-4 font-mono text-purple-300 text-xs">${key}</td><td class="px-6 py-4 text-xs">${info.type}</td><td class="px-6 py-4 text-xs">${info.created_by || 'System'}</td><td class="px-6 py-4 text-xs">${info.used_by || '-'}</td><td class="px-6 py-4 text-xs font-bold">${badge}</td><td class="px-6 py-4 text-right text-xs font-bold">${act}</td></tr>`; }).join(''); } catch(e) {} }
        async function loadTeam() { try { const res = await apiCall('/api/team', {}); const data = await res.json(); const tb = document.getElementById('table-team'); if (data.length === 0) return tb.innerHTML = '<tr><td colspan="4" class="px-6 py-8 text-center text-gray-500 text-xs font-bold uppercase">Empty</td></tr>'; tb.innerHTML = data.map(u => `<tr><td class="px-6 py-4 text-xs text-blue-400">${u.username}</td><td class="px-6 py-4 text-xs font-mono text-gray-500">${u.password}</td><td class="px-6 py-4 text-xs">${u.keys_generated}</td><td class="px-6 py-4 text-right"><button onclick="deleteReseller('${u.username}')" class="text-red-400"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e){} }
        async function deleteReseller(u) { if(confirm(`Delete ${u}?`)) { await apiCall('/api/team/delete', {username: u}); loadTeam(); } }
        async function revokeKey(k) { if (confirm('Ban key?')) { await apiCall('/api/keys/revoke', {key: k}); loadKeys(); } }
        async function loadPromos() { try { const res = await apiCall('/api/promos', {}); const data = await res.json(); const tb = document.getElementById('table-promos'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-gray-500 text-xs font-bold uppercase">Empty</td></tr>'; tb.innerHTML = Object.entries(data).map(([code, info]) => `<tr><td class="p-4 font-mono text-pink-400 text-sm">${code}</td><td class="p-4 text-sm">${info.discount}%</td><td class="p-4 text-sm">${info.uses}</td><td class="p-4 text-right"><button onclick="rmPromo('${code}')" class="text-red-400"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e) {} }
        async function createPromo() { const c = document.getElementById('p-code').value.toUpperCase(), d = document.getElementById('p-disc').value, u = document.getElementById('p-uses').value; if (!c || !d || !u) return; await apiCall('/api/promos/add', {code: c, discount: parseInt(d), uses: parseInt(u)}); document.getElementById('p-code').value = ''; document.getElementById('p-disc').value = ''; document.getElementById('p-uses').value = ''; loadPromos(); }
        async function rmPromo(c) { await apiCall('/api/promos/remove', {code: c}); loadPromos(); }
        async function lookupUser() { const uid = document.getElementById('lookup-id').value; if (!uid) return; try { const res = await apiCall('/api/lookup', {user_id: uid}); const data = await res.json(); document.getElementById('lookup-result').classList.remove('hidden'); document.getElementById('lu-spent').innerText = data.total_spent.toFixed(2) + '€'; document.getElementById('lu-orders').innerText = data.total_orders; const b = document.getElementById('lu-banned'); if (data.is_banned) { b.innerText = "BANNED"; b.className = "text-xl font-black mt-2 text-red-500"; } else { b.innerText = "CLEAN"; b.className = "text-xl font-black mt-2 text-green-400"; } const tb = document.getElementById('lu-table'); if (data.invoices.length === 0) tb.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-gray-500 text-xs font-bold uppercase">Empty</td></tr>'; else tb.innerHTML = data.invoices.map(i => `<tr><td class="p-4 font-mono text-xs text-gray-500">${i.id}</td><td class="p-4 text-xs">${i.product}</td><td class="p-4 text-xs text-green-400">${i.price}€</td><td class="p-4 text-xs">${i.date.split('T')[0]}</td></tr>`).join(''); } catch(e) {} }
        async function sendAnnounce() { const t = document.getElementById('ann-title').value, d = document.getElementById('ann-desc').value, i = document.getElementById('ann-img').value; if (!t || !d) return; await apiCall('/api/announce', {title: t, desc: d, img: i}); alert("Sent!"); document.getElementById('ann-title').value = ''; document.getElementById('ann-desc').value = ''; document.getElementById('ann-img').value = ''; }
        async function loadBlacklist() { try { const res = await apiCall('/api/blacklist', {}); const data = await res.json(); const tb = document.getElementById('table-blacklist'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-gray-500 text-xs font-bold uppercase">Empty</td></tr>'; tb.innerHTML = Object.entries(data).map(([uid, info]) => `<tr><td class="p-4 font-mono text-red-400 text-sm">${uid}</td><td class="p-4 text-xs">${info.reason}</td><td class="p-4 text-right"><button onclick="rmBlacklist('${uid}')" class="text-red-400"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e) {} }
        async function addBlacklist() { const uid = document.getElementById('bl-id').value, rsn = document.getElementById('bl-reason').value || "Web Ban"; if (!uid) return; await apiCall('/api/blacklist/add', {user_id: uid, reason: rsn}); document.getElementById('bl-id').value = ''; document.getElementById('bl-reason').value = ''; loadBlacklist(); }
        async function rmBlacklist(uid) { await apiCall('/api/blacklist/remove', {user_id: uid}); loadBlacklist(); }
        async function genAdminKey(type) { const res = await apiCall('/api/admin/generate', {t: type}); const d = await res.json(); document.getElementById('new-key').value = d.key; document.getElementById('key-modal').classList.remove('hidden-view'); }
        async function loadCustomerData() { try { const res = await apiCall('/api/customer_data', {}); const data = await res.json(); document.getElementById('cust-prod').innerText = data.type; document.getElementById('cust-status').innerText = data.status; document.getElementById('cust-discord').innerText = data.used_by; document.getElementById('cust-created').innerText = data.created_at.split('T')[0]; if(data.status === "Banned") document.getElementById('cust-status').className = "text-xl font-black mt-2 text-red-500"; else if(data.status === "Active") document.getElementById('cust-status').className = "text-xl font-black mt-2 text-green-400"; } catch(e){} }

        window.onload = checkAuthOnLoad;
    </script>
</body>
</html>
""".replace("LOGO_URL_PLACEHOLDER", SAFE_WEBSITE_LOGO_URL).replace("LTC_ADDR", LITECOIN_ADDRESS)

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
        txid = data.get("txid")
        ptype = data.get("product")
        
        if not email or not txid or ptype not in PRODUCTS:
            return web.json_response({"ok": False, "error": "Fehlende Daten."})
            
        ok, reason = await verify_ltc_payment(txid)
        if not ok:
            return web.json_response({"ok": False, "error": reason})
            
        prefix = PRODUCTS[ptype]["key_prefix"]
        key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
        
        keys_db[key] = {
            "type": ptype, 
            "used": False, 
            "used_by": None, 
            "bound_user_id": None, 
            "created_at": iso_now(), 
            "redeemed_at": None, 
            "approved_in_ticket": "WEB-SHOP", 
            "created_by": "System-Auto",
            "revoked": False
        }
        save_json(KEYS_FILE, keys_db)
        
        invoice_id = build_invoice_id()
        invoices_db[invoice_id] = {
            "buyer_id": email, 
            "product_type": ptype, 
            "payment_key": "litecoin", 
            "key": key, 
            "ticket_id": "WEB", 
            "created_at": iso_now(), 
            "final_price_eur": PRODUCTS[ptype]["price_eur"], 
            "reseller_discount": False
        }
        save_json(INVOICES_FILE, invoices_db)
        
        send_delivery_email(email, PRODUCTS[ptype]["label"], key)
        log_activity(f"Web Order ({PRODUCTS[ptype]['price_eur']}€)", "Auto-Shop")
        
        return web.json_response({"ok": True, "key": key})
    except Exception as e:
        return web.json_response({"ok": False, "error": "Server Fehler."})

async def api_register(request):
    data = await request.json()
    username = data.get("user")
    password = data.get("pass")
    inv_key = data.get("key", "").upper()
    if not username or not password or not inv_key: return web.json_response({"error": "Bitte fülle alle Felder aus!"}, status=400)
    if username in users_db: return web.json_response({"error": f"Der Name '{username}' ist leider schon vergeben!"}, status=400)
    if inv_key not in webkeys_db: return web.json_response({"error": "Dieser Einladungs-Key existiert nicht!"}, status=400)
    if webkeys_db[inv_key].get("used"): return web.json_response({"error": "Dieser Einladungs-Key wurde bereits benutzt!"}, status=400)
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

async def api_customer_login(request):
    data = await request.json()
    key = data.get("key", "").strip().upper()
    if not key or key not in keys_db: return web.json_response({"error": "Key existiert nicht."}, status=400)
    token = str(uuid.uuid4())
    web_sessions[token] = {"user": key, "role": "customer"}
    save_json(SESSIONS_FILE, web_sessions)
    return web.json_response({"ok": True, "token": token, "role": "customer", "user": key})

async def api_customer_data(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "customer": return web.Response(status=401)
    key = user_info["user"]
    kdata = keys_db.get(key, {})
    ptype = kdata.get("type", "day_1") if isinstance(kdata, dict) else "day_1"
    prod = PRODUCTS.get(ptype, {"label": "Unknown"})
    status = "Active"
    if isinstance(kdata, dict):
        if kdata.get("revoked"): status = "Banned"
        elif not kdata.get("used"): status = "Unused"
    return web.json_response({
        "key": key, "type": prod.get("label", "Unknown"), "status": status,
        "created_at": kdata.get("created_at") if isinstance(kdata, dict) else "Unknown",
        "used_by": kdata.get("used_by", "None") if isinstance(kdata, dict) else "None"
    })

async def api_verify(request):
    user = get_user_from_token(request)
    if user: return web.json_response({"ok": True, "role": user["role"], "user": user["user"]})
    return web.Response(status=401)

async def api_stats(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
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
            if d == now.date(): today_buyers.add(data["buyer_id"])
            if d in rev_data: rev_data[d] += price
        except Exception: pass
    active_k = sum(1 for k, v in keys_db.items() if isinstance(v, dict) and not v.get("used"))
    return web.json_response({
        "total_revenue": total_rev, "buyers_today": len(today_buyers), 
        "active_keys": active_k, "chart_labels": labels, "chart_data": list(rev_data.values())
    })
    
async def api_discord_stats(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    guild = bot.get_guild(GUILD_ID)
    members = guild.member_count if guild else 0
    open_tickets = sum(1 for t in ticket_data.values() if isinstance(t, dict) and t.get("status") in ["waiting", "reviewing"])
    return web.json_response({"members": members, "open_tickets": open_tickets})

async def api_team(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    resellers = []
    for uname, data in users_db.items():
        if data.get("role") == "reseller":
            gen_count = sum(1 for k in keys_db.values() if isinstance(k, dict) and k.get("created_by") == uname)
            resellers.append({"username": uname, "password": data["pass"], "keys_generated": gen_count})
    return web.json_response(resellers)

async def api_team_delete(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    data = await request.json()
    uname = data.get("username")
    if uname in users_db and users_db[uname].get("role") == "reseller":
        del users_db[uname]
        save_json(USERS_FILE, users_db)
        log_activity(f"Deleted Reseller {uname}", user_info["user"])
    return web.json_response({"ok": True})

async def api_activity(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    return web.json_response(activity_db)

async def api_keys(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    return web.json_response(keys_db)

async def api_revoke_key(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    data = await request.json()
    key = data.get("key")
    if key in keys_db and isinstance(keys_db[key], dict):
        if keys_db[key].get("used") and keys_db[key].get("used_by"):
            uid = str(keys_db[key]["used_by"])
            guild = bot.get_guild(GUILD_ID)
            if guild:
                member = guild.get_member(int(uid))
                role = guild.get_role(REDEEM_ROLE_ID)
                if member and role:
                    try: await member.remove_roles(role, reason="Key banned by Admin")
                    except Exception: pass
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
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    return web.json_response(promos_db)

async def api_add_promo(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    data = await request.json()
    promos_db[data["code"]] = { "discount": data["discount"], "uses": data["uses"] }
    save_json(PROMOS_FILE, promos_db)
    log_activity(f"Created Promo {data['code']}", user_info["user"])
    return web.json_response({"ok": True})

async def api_rm_promo(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    data = await request.json()
    code = data["code"]
    if code in promos_db: 
        del promos_db[code]
        save_json(PROMOS_FILE, promos_db)
    return web.json_response({"ok": True})

async def api_lookup(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    target = (await request.json()).get("user_id")
    spent = 0.0
    invs = []
    for inv_id, data in invoices_db.items():
        if isinstance(data, dict) and data.get("buyer_id") == target:
            spent += float(data.get("final_price_eur", 0))
            invs.append({ "id": inv_id, "product": PRODUCTS.get(data.get("product_type"), {}).get("label", "Unknown"), "price": data.get("final_price_eur", 0), "date": data.get("created_at") })
    return web.json_response({ "total_spent": spent, "total_orders": len(invs), "is_banned": target in blacklist_db, "invoices": invs[::-1] })

async def api_announce(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    data = await request.json()
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title=data["title"], description=data["desc"], color=COLOR_MAIN)
        if data.get("img"): embed.set_image(url=data["img"])
        await channel.send(embed=embed)
        log_activity("Sent Discord Broadcast", user_info["user"])
    return web.json_response({"ok": True})

async def api_blacklist(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    return web.json_response(blacklist_db)

async def api_add_blacklist(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    data = await request.json()
    uid = data.get("user_id")
    rsn = data.get("reason", "Web Ban")
    if uid: 
        blacklist_db[uid] = { "reason": rsn, "added_by": user_info["user"], "added_at": iso_now() }
        save_json(BLACKLIST_FILE, blacklist_db)
        log_activity(f"Banned User {uid}", user_info["user"])
    return web.json_response({"ok": True})

async def api_rm_blacklist(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    uid = (await request.json()).get("user_id")
    if uid in blacklist_db: 
        del blacklist_db[uid]
        save_json(BLACKLIST_FILE, blacklist_db)
        log_activity(f"Unbanned User {uid}", user_info["user"])
    return web.json_response({"ok": True})

async def api_reseller_data(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "reseller": return web.Response(status=401)
    my_keys = [{ "key": k, "type": PRODUCTS.get(v.get("type"), {}).get("label", "Unknown") if isinstance(v, dict) else "Unknown" } for k, v in keys_db.items() if isinstance(v, dict) and v.get("created_by") == user_info["user"]]
    return web.json_response({"my_keys": my_keys})

async def api_reseller_gen(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "reseller": return web.Response(status=401)
    ptype = (await request.json()).get("t", "day_1")
    prefix = PRODUCTS[ptype]["key_prefix"]
    new_key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
    keys_db[new_key] = { "type": ptype, "used": False, "used_by": None, "bound_user_id": None, "created_at": iso_now(), "created_by": user_info["user"], "revoked": False }
    save_json(KEYS_FILE, keys_db)
    log_activity(f"Reseller {user_info['user']} created {ptype} Key", user_info["user"])
    return web.json_response({"key": new_key})

async def api_admin_gen(request):
    user_info = get_user_from_token(request)
    if not user_info or user_info.get("role") != "admin": return web.Response(status=401)
    ptype = (await request.json()).get("t", "day_1")
    prefix = PRODUCTS[ptype]["key_prefix"]
    new_key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
    keys_db[new_key] = { "type": ptype, "used": False, "used_by": None, "bound_user_id": None, "created_at": iso_now(), "created_by": user_info["user"], "revoked": False }
    save_json(KEYS_FILE, keys_db)
    log_activity(f"Admin {user_info['user']} created {ptype} Key", user_info["user"])
    return web.json_response({"key": new_key})


async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_post('/api/web_buy', api_web_buy)
    app.router.add_post('/api/login', api_login)
    app.router.add_post('/api/customer_login', api_customer_login)
    app.router.add_post('/api/register', api_register)
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
    app.router.add_post('/api/reseller/data', api_reseller_data)
    app.router.add_post('/api/reseller/generate', api_reseller_gen)
    app.router.add_post('/api/admin/generate', api_admin_gen)
    app.router.add_post('/api/customer_data', api_customer_data)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Web Server läuft auf Port {port}")

# =========================================================
# BOT COMMANDS & TICKET LOGIC (ORIGINAL UNTOUCHED)
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
    
    dur_days = PRODUCTS.get(pt, {}).get("duration_days", 0)
    redeemed_db[str(member.id)] = {"key": key, "type": pt, "role_id": REDEEM_ROLE_ID, "expires_at": (now_utc() + timedelta(days=dur_days)).isoformat() if dur_days > 0 else None}
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
            await dm_user_safe(buyer, embed=discord.Embed(title="🔑 Purchase Approved", description=f"**Key:** `{generated_key}`\nDu kannst dich mit diesem Key auf der Website einloggen!", color=COLOR_SUCCESS))
            
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
        # 🔥 ANTI-DOPPEL-TICKET SPERRE 🔥
        await interaction.response.defer(ephemeral=True)
        
        guild, user = interaction.guild, interaction.user
        
        if is_blacklisted(user.id): 
            return await interaction.followup.send("Du bist auf der Blacklist.", ephemeral=True)
            
        if user.id in ticket_locks:
            return await interaction.followup.send("⏳ Dein Ticket wird gerade erstellt... Bitte nicht mehrmals klicken!", ephemeral=True)
            
        ticket_locks.add(user.id)
        try:
            existing = await find_existing_ticket(guild, user)
            if existing: 
                return await interaction.followup.send(f"Du hast bereits ein offenes Ticket: {existing.mention}", ephemeral=True)
                
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

            await interaction.followup.send(f"✅ Ticket erfolgreich erstellt: {channel.mention}", ephemeral=True)
        finally:
            ticket_locks.discard(user.id)


class RedeemKeyModal(discord.ui.Modal, title="Paste your key here"):
    key_input = discord.ui.TextInput(label="Key", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, res = await redeem_key_for_user(interaction.guild, interaction.user, str(self.key_input).strip().upper())
        if ok: 
            await interaction.followup.send(f"✅ Success! You received the {PRODUCTS.get(res, {}).get('label', 'Unknown')} role.", ephemeral=True)
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

@bot.tree.command(name="nuke_database", description="(ADMIN) Löscht alle DBs (FIXT DEN KEYS BUG)!")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def nuke_database(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("Admins only.", ephemeral=True)
    
    global users_db, webkeys_db, web_sessions, keys_db, ticket_data, redeemed_db, used_txids_db
    users_db = {}
    webkeys_db = {}
    web_sessions = {}
    keys_db = {}
    ticket_data = {}
    redeemed_db = {}
    used_txids_db = {}
    
    save_json(USERS_FILE, users_db)
    save_json(WEBKEYS_FILE, webkeys_db)
    save_json(SESSIONS_FILE, web_sessions)
    save_json(KEYS_FILE, keys_db)
    save_json(TICKETS_FILE, ticket_data)
    save_json(REDEEMED_FILE, redeemed_db)
    save_json(USED_TXIDS_FILE, used_txids_db)
    
    await interaction.response.send_message("💣 **BOOM!** Website, Keys & Tickets Datenbanken wurden GELÖSCHT. Alles ist komplett resettet!", ephemeral=True)

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
