import os, re, json, uuid, asyncio, aiohttp, smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from aiohttp import web
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.firstmail.ltd")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER") 
SMTP_PASS = os.getenv("SMTP_PASS") 

if not TOKEN or not GUILD_ID_RAW: raise ValueError("TOKEN oder GUILD_ID fehlt.")
try: GUILD_ID = int(GUILD_ID_RAW)
except ValueError: raise ValueError("GUILD_ID muss eine gültige Zahl sein.")

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
WEBSITE_LOGO_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751701567934535/velo.png"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751958573645834/velo_log.png"
SAFE_WEBSITE_LOGO_URL = WEBSITE_LOGO_URL.replace("&", "&amp;")
WELCOME_THUMBNAIL_URL = WEBSITE_LOGO_URL
WELCOME_BANNER_URL = PANEL_IMAGE_URL

PAYPAL_EMAIL = "hydrasupfivem@gmail.com"
LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"
ETHEREUM_ADDRESS = "0x6Ba2afdA7e61817f9c27f98ffAfe9051F9ad8167"
SOLANA_ADDRESS = "DnzXgySsPnSdEKsMJub21dBjM6bcT2jtic73VeutN3p4"
LTC_MIN_CONFIRMATIONS = 1

COLOR_MAIN, COLOR_SUPPORT, COLOR_BUY, COLOR_WARN = 0x9333EA, 0x3BA7FF, 0x57F287, 0xFEE75C
COLOR_DENY, COLOR_LOG, COLOR_SUCCESS, COLOR_INFO = 0xED4245, 0x2B2D31, 0x57F287, 0x9333EA
COLOR_ADMIN, COLOR_WELCOME = 0x9B59B6, 0xDD0000

KEYS_FILE, REDEEMED_FILE, USED_TXIDS_FILE = "keys.json", "redeemed.json", "used_txids.json"
BLACKLIST_FILE, INVOICES_FILE, PROMOS_FILE = "blacklist.json", "invoices.json", "promos.json"
ACTIVITY_FILE, WEBKEYS_FILE, USERS_FILE = "activity.json", "web_keys.json", "web_users.json"
TICKETS_FILE, SESSIONS_FILE = "tickets.json", "sessions.json"

PRODUCTS = {
    "day_1": {"label": "1 Day", "price_eur": 5, "duration_days": 1, "key_prefix": "GEN-1D"},
    "week_1": {"label": "1 Week", "price_eur": 15, "duration_days": 7, "key_prefix": "GEN-1W"},
    "lifetime": {"label": "Lifetime", "price_eur": 30, "duration_days": 0, "key_prefix": "GEN-LT"}
}

PAYMENTS = {"paypal": {"label": "PayPal", "emoji": "💸"}, "litecoin": {"label": "Litecoin", "emoji": "🪙"}, "ethereum": {"label": "Ethereum", "emoji": "🔷"}, "solana": {"label": "Solana", "emoji": "🟣"}, "paysafecard": {"label": "Paysafecard", "emoji": "💳"}, "amazoncard": {"label": "Amazon Card", "emoji": "🎁"}}

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f: json.dump(default, f); return default
    with open(path, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

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
    global activity_db; activity_db.insert(0, {"time": iso_now(), "user": str(user), "action": action}); activity_db = activity_db[:50]; save_json(ACTIVITY_FILE, activity_db)

def now_utc(): return datetime.now(timezone.utc)
def iso_now(): return now_utc().isoformat()
def random_block(length=4): return uuid.uuid4().hex[:length].upper()
def build_invoice_id() -> str: return f"GEN-{uuid.uuid4().hex[:10].upper()}"
def is_blacklisted(user_id: int): return str(user_id) in blacklist_db

async def verify_ltc_payment(txid):
    if txid in used_txids_db: return False, "TXID wurde bereits verwendet."
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=15) as resp:
            if resp.status != 200: return False, "Ungültige TXID oder API offline."
            data = await resp.json()
            for out in data.get("outputs", []):
                if LITECOIN_ADDRESS in out.get("addresses", []):
                    used_txids_db[txid] = {"time": iso_now()}; save_json(USED_TXIDS_FILE, used_txids_db)
                    return True, "Zahlung verifiziert."
    return False, "Keine Zahlung an unsere LTC Adresse gefunden."

def send_delivery_email(to_email, product_label, key):
    if not SMTP_USER or not SMTP_PASS: return False
    try:
        msg = MIMEMultipart(); msg['From'] = SMTP_USER; msg['To'] = to_email; msg['Subject'] = f"Deine Bestellung bei {SERVER_NAME} ist da! 🎉"
        body = f"Hallo!\n\nVielen Dank für deinen Einkauf bei {SERVER_NAME}.\n\nProdukt: {product_label}\nKey: {key}\n\nDu kannst diesen Key auf unserer Website im 'Customer' Login verwenden oder in unserem Discord-Server einlösen.\n\nViel Spaß!"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) if SMTP_PORT == 465 else smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        if SMTP_PORT != 465: server.starttls()
        server.login(SMTP_USER, SMTP_PASS); server.sendmail(SMTP_USER, to_email, msg.as_string()); server.quit()
        return True
    except Exception as e: print(f"Mail Error: {e}"); return False

# =========================================================
# WEB DASHBOARD HTML (NEON LILA KRASSES UI)
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
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;500;700;900&display=swap');
        body { font-family: 'Space Grotesk', sans-serif; background-color: #0c0414; color: #fff; margin: 0; overflow-x: hidden; }
        
        /* Bright Neon Purple Background & Grid */
        .neon-bg { position: fixed; inset: 0; background: radial-gradient(circle at 50% 0%, #3b0764 0%, #0c0414 70%); z-index: -2; }
        .grid-bg { position: fixed; inset: 0; background-image: linear-gradient(rgba(216, 180, 254, 0.1) 2px, transparent 2px), linear-gradient(90deg, rgba(216, 180, 254, 0.1) 2px, transparent 2px); background-size: 50px 50px; z-index: -1; animation: slide 20s linear infinite; }
        @keyframes slide { 0% { background-position: 0 0; } 100% { background-position: 50px 50px; } }

        /* Bright Glass Cards */
        .glass { background: rgba(30, 10, 50, 0.7); backdrop-filter: blur(20px); border: 2px solid rgba(216, 180, 254, 0.3); transition: all 0.3s ease; box-shadow: 0 0 30px rgba(168, 85, 247, 0.2); }
        .glass:hover { border-color: rgba(216, 180, 254, 0.8); box-shadow: 0 0 50px rgba(168, 85, 247, 0.5); transform: translateY(-5px); }
        
        .glow-text { background: linear-gradient(90deg, #d8b4fe, #f0abfc, #d8b4fe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 0 20px rgba(216,180,254,0.8)); background-size: 200% auto; animation: shine 3s linear infinite; }
        @keyframes shine { to { background-position: 200% center; } }

        .btn-neon { background: linear-gradient(90deg, #a855f7, #ec4899); box-shadow: 0 0 20px rgba(168,85,247,0.6); transition: 0.3s; color: white; font-weight: 900; }
        .btn-neon:hover { box-shadow: 0 0 40px rgba(236,72,153,0.8); transform: scale(1.02); }

        .hidden-view { display: none !important; }
        .tab-content { display: none; } 
        .tab-content.active { display: block; animation: fadeIn 0.4s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .premium-input { background: rgba(0,0,0,0.6); border: 2px solid rgba(168,85,247,0.3); color: white; transition: 0.3s; }
        .premium-input:focus { border-color: #d8b4fe; outline: none; box-shadow: 0 0 20px rgba(168,85,247,0.5); }
        
        /* Modal Animation for Checkout */
        .modal-zoom { animation: zoomIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; }
        @keyframes zoomIn { from { opacity: 0; transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }
        
        ::-webkit-scrollbar { width: 8px; } ::-webkit-scrollbar-track { background: #0c0414; } ::-webkit-scrollbar-thumb { background: #a855f7; border-radius: 4px; box-shadow: 0 0 10px #a855f7; }
    </style>
</head>
<body class="flex flex-col h-screen relative">
    <div class="neon-bg"></div>
    <div class="grid-bg"></div>

    <nav class="w-full px-8 py-5 flex justify-between items-center z-50 bg-black/40 backdrop-blur-xl border-b border-purple-500/40 shadow-[0_0_30px_rgba(168,85,247,0.3)] sticky top-0">
        <div class="flex items-center gap-4 cursor-pointer" onclick="switchAuth('shop')">
            <img src="LOGO_URL" class="h-12 w-12 rounded-xl shadow-[0_0_20px_rgba(216,180,254,0.6)] object-cover">
            <span class="text-3xl font-black tracking-widest uppercase">VALE <span class="glow-text">GEN</span></span>
        </div>
        <div class="flex gap-6">
            <button onclick="switchAuth('shop')" class="font-black text-purple-200 hover:text-white transition uppercase tracking-widest text-sm drop-shadow-[0_0_10px_rgba(216,180,254,0.5)]">Store</button>
            <button onclick="switchAuth('login')" class="font-black text-white transition uppercase tracking-widest text-sm bg-purple-600/40 border border-purple-400 px-6 py-2 rounded-xl hover:bg-purple-500/60 shadow-[0_0_15px_rgba(168,85,247,0.5)]">Portal</button>
        </div>
    </nav>

    <div class="flex-1 w-full relative z-10 overflow-y-auto pb-20">
        
        <div id="view-shop" class="w-full max-w-7xl mx-auto px-6 pt-16">
            <div class="text-center mb-20">
                <h1 class="text-6xl md:text-8xl font-black mb-4 tracking-tighter uppercase glow-text">Premium Access</h1>
                <p class="text-purple-200 text-xl font-bold max-w-2xl mx-auto drop-shadow-[0_0_10px_rgba(216,180,254,0.5)]">Wähle deinen Plan. Instant LTC & PayPal Delivery.</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-10">
                <div class="glass p-10 rounded-[2.5rem] flex flex-col items-center">
                    <div class="bg-purple-500/20 text-purple-300 px-5 py-1 rounded-full text-sm font-black tracking-widest mb-6 border border-purple-400 shadow-[0_0_15px_rgba(168,85,247,0.4)]">STARTER</div>
                    <h3 class="text-4xl font-black mb-2 uppercase text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.5)]">1 Day Key</h3>
                    <div class="text-6xl font-black text-white mb-8 glow-text">5€</div>
                    <button onclick="openCheckout('day_1', '5.00')" class="mt-auto w-full btn-neon py-5 rounded-2xl uppercase tracking-widest text-lg">Purchase</button>
                </div>
                
                <div class="glass p-12 rounded-[3rem] flex flex-col items-center transform md:scale-110 relative z-10 border-pink-400 shadow-[0_0_80px_rgba(236,72,153,0.4)] bg-purple-900/40">
                    <div class="absolute -top-5 bg-gradient-to-r from-pink-500 to-purple-500 text-white text-xs font-black px-8 py-2 rounded-full uppercase tracking-widest shadow-[0_0_20px_rgba(236,72,153,0.8)]">Best Value</div>
                    <div class="bg-pink-500/20 text-pink-300 px-5 py-1 rounded-full text-sm font-black tracking-widest mb-6 border border-pink-400 shadow-[0_0_15px_rgba(236,72,153,0.4)]">POPULAR</div>
                    <h3 class="text-4xl font-black mb-2 uppercase text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.5)]">1 Week Key</h3>
                    <div class="text-7xl font-black text-white mb-8 glow-text" style="background: linear-gradient(90deg, #f0abfc, #ec4899); -webkit-background-clip: text;">15€</div>
                    <button onclick="openCheckout('week_1', '15.00')" class="mt-auto w-full btn-neon py-5 rounded-2xl uppercase tracking-widest text-xl shadow-[0_0_30px_rgba(236,72,153,0.8)]">Purchase</button>
                </div>
                
                <div class="glass p-10 rounded-[2.5rem] flex flex-col items-center">
                    <div class="bg-blue-500/20 text-blue-300 px-5 py-1 rounded-full text-sm font-black tracking-widest mb-6 border border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.4)]">ULTIMATE</div>
                    <h3 class="text-4xl font-black mb-2 uppercase text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.5)]">Lifetime</h3>
                    <div class="text-6xl font-black text-white mb-8 glow-text" style="background: linear-gradient(90deg, #93c5fd, #3b82f6); -webkit-background-clip: text;">30€</div>
                    <button onclick="openCheckout('lifetime', '30.00')" class="mt-auto w-full btn-neon py-5 rounded-2xl uppercase tracking-widest text-lg" style="background: linear-gradient(90deg, #3b82f6, #8b5cf6);">Purchase</button>
                </div>
            </div>
        </div>

        <div id="view-auth" class="w-full max-w-lg mx-auto pt-16 hidden-view px-6">
            <div class="glass p-12 rounded-[3rem] relative shadow-[0_0_60px_rgba(168,85,247,0.3)]">
                <h2 class="text-4xl font-black tracking-widest uppercase text-center mb-8 glow-text">Portal</h2>
                <div class="flex bg-black/60 p-2 rounded-2xl border border-purple-500/30 mb-8 shadow-inner">
                    <button onclick="switchAuthTab('customer')" id="tab-btn-customer" class="flex-1 py-3 text-sm font-black rounded-xl text-white bg-purple-600 shadow-[0_0_15px_rgba(168,85,247,0.5)] transition uppercase tracking-widest">Customer</button>
                    <button onclick="switchAuthTab('login')" id="tab-btn-login" class="flex-1 py-3 text-sm font-black rounded-xl text-purple-300 hover:text-white transition uppercase tracking-widest">Admin</button>
                    <button onclick="switchAuthTab('register')" id="tab-btn-register" class="flex-1 py-3 text-sm font-black rounded-xl text-purple-300 hover:text-white transition uppercase tracking-widest">Register</button>
                </div>

                <div id="form-customer" class="space-y-5">
                    <input type="text" id="c-key" class="premium-input w-full rounded-2xl px-6 py-5 font-mono text-pink-300 text-center tracking-widest text-lg" placeholder="GEN-...">
                    <button onclick="customerLogin()" class="w-full btn-neon py-5 rounded-2xl uppercase tracking-widest text-lg mt-4">Access Dashboard</button>
                </div>

                <div id="form-login" class="space-y-5 hidden-view">
                    <input type="text" id="l-user" class="premium-input w-full rounded-2xl px-6 py-5 text-lg" placeholder="Username">
                    <input type="password" id="l-pass" class="premium-input w-full rounded-2xl px-6 py-5 text-lg" placeholder="Password">
                    <button onclick="login()" class="w-full btn-neon py-5 rounded-2xl uppercase tracking-widest text-lg mt-4">Login</button>
                </div>

                <div id="form-register" class="space-y-5 hidden-view">
                    <input type="text" id="r-user" class="premium-input w-full rounded-2xl px-6 py-5 text-lg" placeholder="Username">
                    <input type="password" id="r-pass" class="premium-input w-full rounded-2xl px-6 py-5 text-lg" placeholder="Password">
                    <input type="text" id="r-key" class="premium-input w-full rounded-2xl px-6 py-5 font-mono text-purple-300 text-lg" placeholder="Invite Key (VALE-...)">
                    <button onclick="register()" class="w-full bg-purple-900/50 hover:bg-purple-800 border-2 border-purple-500 text-white font-black py-5 rounded-2xl uppercase tracking-widest transition mt-4 shadow-[0_0_20px_rgba(168,85,247,0.3)]">Create Account</button>
                </div>
                <p id="auth-error" class="text-red-400 mt-6 text-center font-bold text-lg hidden drop-shadow-[0_0_5px_rgba(239,68,68,0.8)]"></p>
            </div>
        </div>

        <div id="checkout-modal" class="fixed inset-0 bg-black/90 backdrop-blur-xl hidden-view flex items-center justify-center p-4 z-50">
            <div class="glass p-10 md:p-14 rounded-[3rem] border-2 border-purple-400 shadow-[0_0_100px_rgba(168,85,247,0.5)] max-w-xl w-full relative modal-zoom bg-purple-900/20">
                <button onclick="closeCheckout()" class="absolute top-6 right-8 text-purple-300 hover:text-white text-4xl font-black transition drop-shadow-[0_0_10px_rgba(216,180,254,0.8)]">&times;</button>
                <h2 class="text-4xl font-black text-white mb-2 text-center uppercase tracking-widest glow-text">Checkout</h2>
                <p class="text-center text-purple-200 font-black mb-10 text-2xl drop-shadow-[0_0_10px_rgba(216,180,254,0.5)]"><span id="co-price"></span>€</p>
                
                <div id="co-step-1">
                    <div class="flex gap-4 mb-8 bg-black/50 p-2 rounded-2xl border border-purple-500/30">
                        <button id="gw-ltc" onclick="setGw('ltc')" class="flex-1 py-4 bg-purple-600 rounded-xl font-black text-white transition shadow-[0_0_20px_rgba(168,85,247,0.6)] uppercase tracking-widest"><i class="fa-solid fa-litecoin-sign mr-2"></i>Litecoin</button>
                        <button id="gw-paypal" onclick="setGw('paypal')" class="flex-1 py-4 rounded-xl font-black text-purple-300 hover:text-white hover:bg-white/10 transition uppercase tracking-widest"><i class="fa-brands fa-paypal mr-2"></i>PayPal</button>
                    </div>

                    <input type="email" id="co-email" class="premium-input w-full rounded-2xl px-6 py-5 mb-8 text-lg" placeholder="Deine E-Mail Adresse">
                    
                    <div id="details-ltc" class="mb-8 bg-purple-900/40 border-2 border-purple-500 p-6 rounded-3xl shadow-[inset_0_0_20px_rgba(168,85,247,0.3)]">
                        <p class="text-sm font-black text-purple-200 uppercase tracking-widest mb-3 text-center">Sende LTC an:</p>
                        <div class="bg-black/80 p-4 rounded-xl font-mono text-sm text-white break-all border border-purple-400 mb-5 text-center cursor-pointer hover:bg-purple-900/80 transition shadow-[0_0_15px_rgba(168,85,247,0.4)]" onclick="navigator.clipboard.writeText('LTC_ADDR'); alert('Kopiert!')">LTC_ADDR <i class="fa-regular fa-copy ml-2"></i></div>
                        <input type="text" id="co-txid" class="premium-input w-full rounded-xl px-5 py-4 font-mono text-center" placeholder="Transaktions-Hash (TXID)...">
                    </div>

                    <div id="details-paypal" class="mb-8 bg-blue-900/40 border-2 border-blue-500 p-6 rounded-3xl shadow-[inset_0_0_20px_rgba(59,130,246,0.3)] hidden-view">
                        <p class="text-sm font-black text-blue-200 uppercase tracking-widest mb-3 text-center">Sende als Freunde & Familie:</p>
                        <div class="bg-black/80 p-4 rounded-xl font-bold text-lg text-white border border-blue-400 mb-5 text-center cursor-pointer hover:bg-blue-900/80 transition shadow-[0_0_15px_rgba(59,130,246,0.4)]" onclick="navigator.clipboard.writeText('PP_EMAIL'); alert('Kopiert!')">PP_EMAIL <i class="fa-regular fa-copy ml-2"></i></div>
                        <input type="text" id="co-pp-proof" class="premium-input w-full rounded-xl px-5 py-4 text-center" placeholder="Dein PayPal Name (als Beweis)...">
                    </div>
                    
                    <p id="co-error" class="text-red-400 mb-6 text-lg font-black text-center hidden drop-shadow-[0_0_5px_rgba(239,68,68,0.8)]"></p>
                    <button onclick="processCheckout()" id="btn-checkout" class="w-full btn-neon py-6 rounded-2xl uppercase tracking-widest text-xl">Zahlung Verifizieren</button>
                </div>

                <div id="co-step-2" class="hidden-view text-center py-8">
                    <i class="fa-solid fa-shield-check text-8xl text-green-400 mb-8 drop-shadow-[0_0_30px_rgba(74,222,128,0.8)]"></i>
                    <h3 class="text-4xl font-black text-white mb-4 uppercase tracking-widest drop-shadow-[0_0_10px_rgba(255,255,255,0.5)]">Erfolgreich!</h3>
                    <p class="text-purple-200 mb-8 font-bold text-lg">Dein Key wurde an deine Mail gesendet.</p>
                    <div class="bg-black/60 border-2 border-green-500 p-6 rounded-3xl mb-10 shadow-[inset_0_0_20px_rgba(74,222,128,0.3),0_0_20px_rgba(74,222,128,0.3)]">
                        <p class="text-sm text-green-400 font-black uppercase tracking-widest mb-3">Dein Key</p>
                        <p id="co-success-key" class="font-mono text-white text-2xl font-black tracking-wider break-all select-all"></p>
                    </div>
                    <button onclick="window.location.reload()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-5 rounded-2xl uppercase tracking-widest text-lg shadow-[0_0_20px_rgba(168,85,247,0.5)] transition">Zum Dashboard</button>
                </div>
            </div>
        </div>

        <div id="view-customer" class="flex w-full h-full hidden-view p-6 md:p-12 relative z-10">
            <div class="max-w-4xl mx-auto w-full">
                <header class="flex justify-between items-center mb-10 glass p-8 rounded-[2.5rem]">
                    <div class="flex items-center">
                        <img src="LOGO_URL_PLACEHOLDER" class="h-20 mr-6 rounded-xl shadow-[0_0_20px_rgba(216,180,254,0.5)]">
                        <div>
                            <h1 class="text-3xl font-black text-white uppercase tracking-widest glow-text">Customer</h1>
                            <p class="text-lg text-pink-300 font-mono font-bold mt-1" id="cust-key-display"></p>
                        </div>
                    </div>
                    <button onclick="logout()" class="bg-red-500/20 border-2 border-red-500 hover:bg-red-500/40 text-red-300 hover:text-white px-8 py-4 rounded-xl font-black transition uppercase tracking-widest shadow-[0_0_20px_rgba(239,68,68,0.4)]">Logout</button>
                </header>
                <div class="glass p-14 rounded-[3.5rem] text-center border-t-4 border-pink-500 shadow-[0_0_80px_rgba(236,72,153,0.3)] bg-purple-900/20">
                    <h2 class="text-purple-300 font-black uppercase tracking-widest mb-4 text-lg">Active Plan</h2>
                    <h3 class="text-6xl md:text-7xl font-black text-white glow-text mb-14" id="cust-prod">Loading...</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                        <div class="bg-black/60 p-8 rounded-3xl border-2 border-purple-500/50 shadow-[inset_0_0_20px_rgba(168,85,247,0.2)]"><i class="fa-solid fa-shield-halved text-5xl text-pink-400 mb-6 drop-shadow-[0_0_15px_rgba(236,72,153,0.6)]"></i><p class="text-sm text-purple-300 font-black uppercase tracking-widest">Status</p><p class="text-3xl font-black text-white mt-3" id="cust-status">Loading</p></div>
                        <div class="bg-black/60 p-8 rounded-3xl border-2 border-purple-500/50 shadow-[inset_0_0_20px_rgba(168,85,247,0.2)]"><i class="fa-brands fa-discord text-5xl text-blue-400 mb-6 drop-shadow-[0_0_15px_rgba(59,130,246,0.6)]"></i><p class="text-sm text-purple-300 font-black uppercase tracking-widest">Discord ID</p><p class="text-2xl font-mono text-white mt-3" id="cust-discord">None</p></div>
                    </div>
                    <p class="text-sm text-purple-400 font-black uppercase tracking-widest">Created: <span id="cust-created" class="text-white"></span></p>
                </div>
            </div>
        </div>

        <div id="view-admin" class="flex w-full h-full hidden-view relative px-6 pb-6 z-10">
            <aside class="w-72 glass rounded-[2.5rem] mr-8 flex flex-col justify-between overflow-hidden border-2 border-purple-500/50 shadow-[0_0_40px_rgba(168,85,247,0.2)] bg-black/40">
                <div>
                    <div class="h-32 flex items-center justify-center border-b border-purple-500/30 bg-purple-900/30">
                        <span class="text-2xl font-black text-white glow-text tracking-widest uppercase">Admin Panel</span>
                    </div>
                    <nav class="p-6 space-y-3 mt-2">
                        <button onclick="nav('dash')" id="btn-dash" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-white bg-purple-600 font-black tracking-widest uppercase text-sm shadow-[0_0_15px_rgba(168,85,247,0.6)] transition"><i class="fa-solid fa-chart-pie w-6"></i> Overview</button>
                        <button onclick="nav('gen')" id="btn-gen" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"><i class="fa-solid fa-bolt w-6"></i> Generator</button>
                        <button onclick="nav('keys')" id="btn-keys" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"><i class="fa-solid fa-key w-6"></i> Keys DB</button>
                        <button onclick="nav('team')" id="btn-team" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"><i class="fa-solid fa-users w-6"></i> Team</button>
                        <button onclick="nav('promos')" id="btn-promos" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"><i class="fa-solid fa-tags w-6"></i> Promos</button>
                        <button onclick="nav('lookup')" id="btn-lookup" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"><i class="fa-solid fa-search w-6"></i> Search</button>
                        <button onclick="nav('announce')" id="btn-announce" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"><i class="fa-solid fa-satellite-dish w-6"></i> Broadcast</button>
                        <button onclick="nav('blacklist')" id="btn-blacklist" class="nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"><i class="fa-solid fa-skull w-6 text-red-400"></i> Blacklist</button>
                    </nav>
                </div>
                <div class="p-6 border-t border-purple-500/30 bg-black/40">
                    <button onclick="logout()" class="w-full text-red-300 border-2 border-red-500/50 bg-red-500/10 hover:bg-red-500 hover:text-white font-black py-4 rounded-xl transition text-sm tracking-widest uppercase shadow-[0_0_15px_rgba(239,68,68,0.3)]">Logout</button>
                </div>
            </aside>
            
            <main class="flex-1 glass rounded-[2.5rem] overflow-y-auto p-10 border-2 border-purple-500/50 shadow-[0_0_50px_rgba(168,85,247,0.2)] bg-black/40">
                <div id="dash" class="tab-content active">
                    <h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Dashboard</h2>
                    <div class="grid grid-cols-3 gap-8 mb-10">
                        <div class="bg-purple-900/30 p-10 rounded-3xl border-2 border-purple-500/50 shadow-[inset_0_0_20px_rgba(168,85,247,0.2)]"><p class="text-sm font-black text-purple-300 uppercase tracking-widest">Revenue</p><h3 class="text-5xl font-black text-white mt-4 glow-text" id="stat-rev">0.00€</h3></div>
                        <div class="bg-pink-900/30 p-10 rounded-3xl border-2 border-pink-500/50 shadow-[inset_0_0_20px_rgba(236,72,153,0.2)]"><p class="text-sm font-black text-pink-300 uppercase tracking-widest">Orders</p><h3 class="text-5xl font-black text-white mt-4" id="stat-orders" style="text-shadow: 0 0 15px rgba(236,72,153,0.8);">0</h3></div>
                        <div class="bg-blue-900/30 p-10 rounded-3xl border-2 border-blue-500/50 shadow-[inset_0_0_20px_rgba(59,130,246,0.2)]"><p class="text-sm font-black text-blue-300 uppercase tracking-widest">Keys</p><h3 class="text-5xl font-black text-white mt-4" id="stat-keys" style="text-shadow: 0 0 15px rgba(59,130,246,0.8);">0</h3></div>
                    </div>
                </div>
                
                <div id="gen" class="tab-content"><h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Generator</h2><div class="space-y-6 max-w-3xl"><button onclick="genAdminKey('day_1')" class="w-full bg-black/60 border-2 border-purple-500/50 hover:border-purple-400 hover:bg-purple-900/40 p-8 rounded-3xl flex justify-between items-center transition shadow-[0_0_20px_rgba(168,85,247,0.2)]"><span class="font-black text-white tracking-widest uppercase text-xl">1 Day</span><i class="fa-solid fa-plus text-3xl text-purple-400"></i></button><button onclick="genAdminKey('week_1')" class="w-full bg-black/60 border-2 border-pink-500/50 hover:border-pink-400 hover:bg-pink-900/40 p-8 rounded-3xl flex justify-between items-center transition shadow-[0_0_20px_rgba(236,72,153,0.2)]"><span class="font-black text-white tracking-widest uppercase text-xl">1 Week</span><i class="fa-solid fa-plus text-3xl text-pink-400"></i></button><button onclick="genAdminKey('lifetime')" class="w-full btn-neon p-8 rounded-3xl flex justify-between items-center transition text-white"><span class="font-black tracking-widest uppercase text-xl">Lifetime</span><i class="fa-solid fa-star text-3xl text-yellow-300"></i></button></div></div>
                <div id="keys" class="tab-content"><h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Database</h2><div class="bg-black/60 rounded-3xl overflow-hidden border-2 border-purple-500/30 shadow-[0_0_30px_rgba(168,85,247,0.2)]"><table class="w-full text-left text-base whitespace-nowrap"><thead class="bg-purple-900/40 text-purple-200"><tr><th class="px-8 py-5 font-black tracking-widest uppercase">Key</th><th class="px-8 py-5 font-black tracking-widest uppercase">Type</th><th class="px-8 py-5 font-black tracking-widest uppercase">Used By</th><th class="px-8 py-5 font-black tracking-widest uppercase">Status</th><th class="px-8 py-5 text-right font-black tracking-widest uppercase">Action</th></tr></thead><tbody id="table-keys" class="divide-y divide-purple-500/20"></tbody></table></div></div>
                <div id="team" class="tab-content"><h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Team</h2><div class="bg-black/60 rounded-3xl overflow-hidden border-2 border-purple-500/30 shadow-[0_0_30px_rgba(168,85,247,0.2)]"><table class="w-full text-left text-base"><thead class="bg-purple-900/40 text-purple-200"><tr><th class="px-8 py-5 font-black tracking-widest uppercase">User</th><th class="px-8 py-5 font-black tracking-widest uppercase">Gen</th><th class="px-8 py-5 text-right font-black tracking-widest uppercase">Del</th></tr></thead><tbody id="table-team" class="divide-y divide-purple-500/20"></tbody></table></div></div>
                <div id="promos" class="tab-content"><h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Promos</h2><div class="flex gap-8"><div class="w-1/3 bg-black/60 p-8 rounded-3xl border-2 border-pink-500/40 shadow-[0_0_30px_rgba(236,72,153,0.2)]"><input type="text" id="p-code" placeholder="Code" class="premium-input w-full rounded-2xl px-6 py-5 mb-4 uppercase font-bold text-lg"><input type="number" id="p-disc" placeholder="Discount %" class="premium-input w-full rounded-2xl px-6 py-5 mb-4 font-bold text-lg"><input type="number" id="p-uses" placeholder="Uses" class="premium-input w-full rounded-2xl px-6 py-5 mb-6 font-bold text-lg"><button onclick="createPromo()" class="w-full btn-neon py-5 rounded-2xl text-lg uppercase tracking-widest">Create</button></div><div class="w-2/3 bg-black/60 rounded-3xl overflow-hidden border-2 border-pink-500/40 shadow-[0_0_30px_rgba(236,72,153,0.2)]"><table class="w-full text-left text-base"><thead class="bg-pink-900/40 text-pink-200"><tr><th class="p-6 font-black uppercase tracking-widest">Code</th><th class="p-6 font-black uppercase tracking-widest">Disc</th><th class="p-6 font-black uppercase tracking-widest">Uses</th><th class="p-6 text-right font-black uppercase tracking-widest">Del</th></tr></thead><tbody id="table-promos" class="divide-y divide-pink-500/20"></tbody></table></div></div></div>
                <div id="lookup" class="tab-content"><h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Lookup</h2><div class="flex gap-6 mb-10"><input type="text" id="lookup-id" placeholder="Discord ID..." class="flex-1 premium-input rounded-2xl px-8 py-5 font-mono text-xl"><button onclick="lookupUser()" class="btn-neon px-10 rounded-2xl uppercase tracking-widest text-lg">Search</button></div><div id="lookup-result" class="hidden"><div class="grid grid-cols-3 gap-8 mb-10"><div class="bg-black/60 p-8 rounded-3xl border-2 border-purple-500/40 shadow-[inset_0_0_20px_rgba(168,85,247,0.2)]"><p class="text-sm font-black text-purple-300 uppercase tracking-widest">Spent</p><h3 id="lu-spent" class="text-4xl font-black mt-3 text-white glow-text">0€</h3></div><div class="bg-black/60 p-8 rounded-3xl border-2 border-purple-500/40 shadow-[inset_0_0_20px_rgba(168,85,247,0.2)]"><p class="text-sm font-black text-purple-300 uppercase tracking-widest">Orders</p><h3 id="lu-orders" class="text-4xl font-black mt-3 text-white glow-text">0</h3></div><div class="bg-black/60 p-8 rounded-3xl border-2 border-purple-500/40 shadow-[inset_0_0_20px_rgba(168,85,247,0.2)]"><p class="text-sm font-black text-purple-300 uppercase tracking-widest">Status</p><h3 id="lu-banned" class="text-3xl font-black mt-3">Clean</h3></div></div><div class="bg-black/60 rounded-3xl overflow-hidden border-2 border-purple-500/30 shadow-[0_0_30px_rgba(168,85,247,0.2)]"><div class="p-6 border-b border-purple-500/30 bg-purple-900/30"><h3 class="text-sm font-black text-purple-200 uppercase tracking-widest">History</h3></div><table class="w-full text-left text-base"><thead class="text-purple-300"><tr><th class="p-6 font-black uppercase">Invoice</th><th class="p-6 font-black uppercase">Product</th><th class="p-6 font-black uppercase">Price</th><th class="p-6 font-black uppercase">Date</th></tr></thead><tbody id="lu-table" class="divide-y divide-purple-500/20"></tbody></table></div></div></div>
                <div id="announce" class="tab-content"><h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Broadcast</h2><div class="max-w-3xl"><input type="text" id="ann-title" placeholder="Title" class="premium-input w-full rounded-2xl px-6 py-5 mb-5 text-lg font-bold"><textarea id="ann-desc" placeholder="Message..." rows="6" class="premium-input w-full rounded-2xl px-6 py-5 mb-5 text-lg font-bold"></textarea><button onclick="sendAnnounce()" class="w-full btn-neon py-6 rounded-2xl uppercase tracking-widest text-xl">Send to Discord</button></div></div>
                <div id="blacklist" class="tab-content"><h2 class="text-4xl font-black text-white tracking-widest uppercase mb-10 glow-text">Blacklist</h2><div class="flex gap-6 mb-10"><input type="text" id="bl-id" placeholder="Discord ID..." class="flex-1 premium-input rounded-2xl px-8 py-5 font-mono text-xl"><button onclick="addBlacklist()" class="bg-red-600 hover:bg-red-500 shadow-[0_0_20px_rgba(239,68,68,0.5)] px-10 rounded-2xl font-black text-white uppercase tracking-widest text-lg transition">Ban</button></div><div class="bg-black/60 rounded-3xl overflow-hidden border-2 border-red-500/30 shadow-[0_0_30px_rgba(239,68,68,0.2)]"><table class="w-full text-left text-base"><thead class="bg-red-900/30 text-red-300"><tr><th class="p-6 font-black uppercase tracking-widest">ID</th><th class="p-6 font-black uppercase tracking-widest">Reason</th><th class="p-6 text-right font-black uppercase tracking-widest">Del</th></tr></thead><tbody id="table-blacklist" class="divide-y divide-red-500/20"></tbody></table></div></div>
            </main>
        </div>
    </div>

    <div id="key-modal" class="fixed inset-0 bg-black/90 backdrop-blur-xl flex items-center justify-center hidden-view z-50">
        <div class="glass p-12 rounded-[3rem] text-center max-w-lg w-full border-2 border-purple-500 shadow-[0_0_80px_rgba(168,85,247,0.5)] relative">
            <h3 class="text-4xl font-black text-white mb-4 uppercase tracking-widest glow-text">Key Erstellt</h3>
            <input type="text" id="new-key" class="w-full bg-black/80 border-2 border-purple-400 p-6 rounded-2xl text-purple-300 font-mono text-center mb-8 text-xl font-bold outline-none mt-6" readonly>
            <button onclick="document.getElementById('key-modal').classList.add('hidden-view')" class="w-full btn-neon py-5 rounded-2xl uppercase tracking-widest text-lg">Schließen</button>
        </div>
    </div>

    <script>
        let selectedProduct = "", currentGw = "ltc";

        function setGw(gw) {
            currentGw = gw;
            document.getElementById('gw-ltc').className = gw === 'ltc' ? "flex-1 py-4 bg-purple-600 rounded-xl font-black text-white transition shadow-[0_0_20px_rgba(168,85,247,0.6)] uppercase tracking-widest" : "flex-1 py-4 rounded-xl font-black text-purple-300 hover:text-white hover:bg-white/10 transition uppercase tracking-widest";
            document.getElementById('gw-paypal').className = gw === 'paypal' ? "flex-1 py-4 bg-blue-600 rounded-xl font-black text-white transition shadow-[0_0_20px_rgba(59,130,246,0.6)] uppercase tracking-widest" : "flex-1 py-4 rounded-xl font-black text-purple-300 hover:text-white hover:bg-white/10 transition uppercase tracking-widest";
            document.getElementById('details-ltc').classList.toggle('hidden-view', gw !== 'ltc');
            document.getElementById('details-paypal').classList.toggle('hidden-view', gw !== 'paypal');
        }

        function switchAuth(type) {
            document.getElementById('view-shop').classList.add('hidden-view'); document.getElementById('view-auth').classList.add('hidden-view');
            if(type === 'shop') document.getElementById('view-shop').classList.remove('hidden-view');
            else { document.getElementById('view-auth').classList.remove('hidden-view'); switchAuthTab('customer'); }
        }

        function switchAuthTab(type) {
            ['customer', 'login', 'register'].forEach(t => { document.getElementById('form-' + t).classList.add('hidden-view'); document.getElementById('tab-btn-' + t).className = "flex-1 py-3 text-sm font-black rounded-xl text-purple-300 hover:text-white transition uppercase tracking-widest"; });
            document.getElementById('form-' + type).classList.remove('hidden-view'); document.getElementById('tab-btn-' + type).className = "flex-1 py-3 text-sm font-black rounded-xl text-white bg-purple-600 shadow-[0_0_15px_rgba(168,85,247,0.5)] transition uppercase tracking-widest"; document.getElementById('auth-error').classList.add('hidden');
        }

        function openCheckout(id, price) { selectedProduct = id; document.getElementById('co-price').innerText = price; document.getElementById('co-step-1').classList.remove('hidden-view'); document.getElementById('co-step-2').classList.add('hidden-view'); document.getElementById('checkout-modal').classList.remove('hidden-view'); setGw('ltc'); }
        function closeCheckout() { document.getElementById('checkout-modal').classList.add('hidden-view'); }

        async function processCheckout() {
            const email = document.getElementById('co-email').value, proof = currentGw === 'ltc' ? document.getElementById('co-txid').value : document.getElementById('co-pp-proof').value, btn = document.getElementById('btn-checkout'), err = document.getElementById('co-error');
            if(!email || !email.includes('@') || !proof) { err.innerText = "Bitte fülle alle Felder korrekt aus!"; err.classList.remove('hidden'); return; }
            err.classList.add('hidden'); btn.disabled = true; btn.innerHTML = 'Lädt...';
            try {
                const res = await fetch('/api/web_buy', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: email, proof: proof, gateway: currentGw, product: selectedProduct}) });
                const data = await res.json();
                if(data.ok) { document.getElementById('co-success-key').innerText = data.key; document.getElementById('co-step-1').classList.add('hidden-view'); document.getElementById('co-step-2').classList.remove('hidden-view'); } 
                else { err.innerText = data.error; err.classList.remove('hidden'); btn.disabled = false; btn.innerText = "Zahlung Verifizieren"; }
            } catch(e) { err.innerText = "Server Error"; err.classList.remove('hidden'); btn.disabled = false; btn.innerText = "Zahlung Verifizieren"; }
        }

        async function apiCall(endpoint, data) { const t = localStorage.getItem('v_token'); const h = {'Content-Type': 'application/json'}; if (t) h['Authorization'] = t; const res = await fetch(endpoint, { method: 'POST', headers: h, body: JSON.stringify(data) }); if (res.status === 401 && !endpoint.includes('login') && !endpoint.includes('register')) { logout(); throw new Error('Unauth'); } return res; }
        function showError(msg) { const e = document.getElementById('auth-error'); e.innerHTML = msg; e.classList.remove('hidden'); }
        async function login() { const u = document.getElementById('l-user').value, p = document.getElementById('l-pass').value; if (!u || !p) return showError("Felder ausfüllen."); const res = await apiCall('/api/login', {user: u, pass: p}); if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else showError("Falsche Daten!"); }
        async function customerLogin() { const k = document.getElementById('c-key').value; if (!k) return showError("Key eingeben."); const res = await apiCall('/api/customer_login', {key: k}); if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else { const e = await res.json(); showError(e.error || "Falscher Key"); } }
        async function register() { const u = document.getElementById('r-user').value, p = document.getElementById('r-pass').value, k = document.getElementById('r-key').value; if (!u || !p || !k) return showError("Felder ausfüllen."); const res = await apiCall('/api/register', {user: u, pass: p, key: k}); if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else { const e = await res.json(); showError(e.error || "Fehler"); } }
        function logout() { localStorage.removeItem('v_token'); location.reload(); }

        window.onload = async () => { const t = localStorage.getItem('v_token'); if (t) { try { const res = await fetch('/api/verify', { method: 'POST', headers: {'Authorization': t, 'Content-Type': 'application/json'} }); if (res.ok) { const d = await res.json(); initApp(d.role, d.user); } else if (res.status === 401) { logout(); } } catch(e) {} } else switchAuth('shop'); };

        function initApp(role, name) {
            document.getElementById('view-shop').classList.add('hidden-view'); document.getElementById('view-auth').classList.add('hidden-view'); document.querySelector('nav').classList.add('hidden-view');
            if (role === 'admin') { document.getElementById('view-admin').classList.remove('hidden-view'); nav('dash'); }
            else if (role === 'customer') { document.getElementById('view-customer').classList.remove('hidden-view'); document.getElementById('cust-key-display').innerText = name; loadCustomerData(); }
        }

        function nav(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active')); document.getElementById(tabId).classList.add('active');
            document.querySelectorAll('.nav-btn').forEach(el => { el.className = "nav-btn w-full text-left py-4 px-5 rounded-xl text-purple-300 hover:text-white hover:bg-purple-500/20 font-black tracking-widest uppercase text-sm transition"; });
            document.getElementById('btn-' + tabId).className = "nav-btn w-full text-left py-4 px-5 rounded-xl text-white bg-purple-600 font-black tracking-widest uppercase text-sm shadow-[0_0_15px_rgba(168,85,247,0.6)] transition";
            if (tabId === 'dash') loadDashboard(); if (tabId === 'keys') loadKeys(); if (tabId === 'team') loadTeam(); if (tabId === 'promos') loadPromos(); if (tabId === 'blacklist') loadBlacklist();
        }

        async function loadDashboard() { try { const res = await apiCall('/api/stats', {}); const data = await res.json(); document.getElementById('stat-rev').innerText = data.total_revenue.toFixed(2) + '€'; document.getElementById('stat-orders').innerText = data.buyers_today; document.getElementById('stat-keys').innerText = data.active_keys; } catch(e) {} }
        async function loadKeys() { try { const res = await apiCall('/api/keys', {}); const data = await res.json(); const tb = document.getElementById('table-keys'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="5" class="px-8 py-10 text-center text-purple-400 text-sm font-black uppercase tracking-widest">EMPTY</td></tr>'; tb.innerHTML = Object.entries(data).reverse().map(([key, info]) => { if(typeof info !== 'object') return ''; let badge = info.used ? '<span class="text-red-400">Used</span>' : '<span class="text-green-400 drop-shadow-[0_0_5px_rgba(74,222,128,0.8)]">Active</span>'; if (info.revoked) badge = '<span class="text-gray-500">Banned</span>'; const act = !info.revoked ? `<button onclick="revokeKey('${key}')" class="text-red-400 hover:text-red-300 font-bold">Ban</button>` : '-'; return `<tr class="hover:bg-purple-500/10 transition"><td class="px-8 py-5 font-mono text-purple-300 font-bold tracking-wider">${key}</td><td class="px-8 py-5 font-bold">${info.type}</td><td class="px-8 py-5 font-mono text-xs">${info.used_by || '-'}</td><td class="px-8 py-5 font-black">${badge}</td><td class="px-8 py-5 text-right">${act}</td></tr>`; }).join(''); } catch(e) {} }
        async function loadTeam() { try { const res = await apiCall('/api/team', {}); const data = await res.json(); const tb = document.getElementById('table-team'); if (data.length === 0) return tb.innerHTML = '<tr><td colspan="3" class="px-8 py-10 text-center text-purple-400 text-sm font-black uppercase tracking-widest">EMPTY</td></tr>'; tb.innerHTML = data.map(u => `<tr class="hover:bg-purple-500/10 transition"><td class="px-8 py-5 text-blue-400 font-black uppercase tracking-wider">${u.username}</td><td class="px-8 py-5 font-black text-xl">${u.keys_generated}</td><td class="px-8 py-5 text-right"><button onclick="deleteReseller('${u.username}')" class="text-red-400 hover:text-red-300 text-xl"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e){} }
        async function deleteReseller(u) { if(confirm(`Delete ${u}?`)) { await apiCall('/api/team/delete', {username: u}); loadTeam(); } }
        async function revokeKey(k) { if (confirm('Ban key?')) { await apiCall('/api/keys/revoke', {key: k}); loadKeys(); } }
        async function loadPromos() { try { const res = await apiCall('/api/promos', {}); const data = await res.json(); const tb = document.getElementById('table-promos'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-pink-400 text-sm font-black uppercase tracking-widest">EMPTY</td></tr>'; tb.innerHTML = Object.entries(data).map(([code, info]) => `<tr class="hover:bg-pink-500/10 transition"><td class="p-6 font-mono text-pink-400 font-bold text-lg">${code}</td><td class="p-6 font-black text-white text-lg">-${info.discount}%</td><td class="p-6 font-black text-white text-lg">${info.uses}</td><td class="p-6 text-right"><button onclick="rmPromo('${code}')" class="text-red-400 hover:text-red-300 text-xl"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e) {} }
        async function createPromo() { const c = document.getElementById('p-code').value.toUpperCase(), d = document.getElementById('p-disc').value, u = document.getElementById('p-uses').value; if (!c || !d || !u) return; await apiCall('/api/promos/add', {code: c, discount: parseInt(d), uses: parseInt(u)}); loadPromos(); }
        async function rmPromo(c) { await apiCall('/api/promos/remove', {code: c}); loadPromos(); }
        async function lookupUser() { const uid = document.getElementById('lookup-id').value; if (!uid) return; try { const res = await apiCall('/api/lookup', {user_id: uid}); const data = await res.json(); document.getElementById('lookup-result').classList.remove('hidden'); document.getElementById('lu-spent').innerText = data.total_spent.toFixed(2) + '€'; document.getElementById('lu-orders').innerText = data.total_orders; const b = document.getElementById('lu-banned'); if (data.is_banned) { b.innerText = "BANNED"; b.className = "text-3xl font-black mt-3 text-red-500 glow-text"; } else { b.innerText = "CLEAN"; b.className = "text-3xl font-black mt-3 text-green-400 drop-shadow-[0_0_10px_rgba(74,222,128,0.8)]"; } const tb = document.getElementById('lu-table'); if (data.invoices.length === 0) tb.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-purple-400 text-sm font-black tracking-widest uppercase">EMPTY</td></tr>'; else tb.innerHTML = data.invoices.map(i => `<tr class="hover:bg-purple-500/10 transition"><td class="p-6 font-mono text-sm text-purple-300">${i.id}</td><td class="p-6 font-bold">${i.product}</td><td class="p-6 font-black text-green-400">${i.price}€</td><td class="p-6 font-bold text-gray-400">${i.date.split('T')[0]}</td></tr>`).join(''); } catch(e) {} }
        async function sendAnnounce() { const t = document.getElementById('ann-title').value, d = document.getElementById('ann-desc').value, i = document.getElementById('ann-img').value; if (!t || !d) return; await apiCall('/api/announce', {title: t, desc: d, img: i}); alert("Broadcast Sent!"); }
        async function loadBlacklist() { try { const res = await apiCall('/api/blacklist', {}); const data = await res.json(); const tb = document.getElementById('table-blacklist'); if (Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-red-400 text-sm font-black uppercase tracking-widest">EMPTY</td></tr>'; tb.innerHTML = Object.entries(data).map(([uid, info]) => `<tr class="hover:bg-red-500/10 transition"><td class="p-6 font-mono text-red-300 font-bold text-lg">${uid}</td><td class="p-6 font-bold text-white">${info.reason}</td><td class="p-6 text-right"><button onclick="rmBlacklist('${uid}')" class="text-red-400 hover:text-red-300 text-xl"><i class="fa-solid fa-trash"></i></button></td></tr>`).join(''); } catch(e) {} }
        async function addBlacklist() { const uid = document.getElementById('bl-id').value, rsn = document.getElementById('bl-reason').value || "Web Ban"; if (!uid) return; await apiCall('/api/blacklist/add', {user_id: uid, reason: rsn}); loadBlacklist(); }
        async function rmBlacklist(uid) { await apiCall('/api/blacklist/remove', {user_id: uid}); loadBlacklist(); }
        async function genAdminKey(type) { const res = await apiCall('/api/admin/generate', {t: type}); const d = await res.json(); document.getElementById('new-key').value = d.key; document.getElementById('key-modal').classList.remove('hidden-view'); }
        async function loadCustomerData() { try { const res = await apiCall('/api/customer_data', {}); const data = await res.json(); document.getElementById('cust-prod').innerText = data.type; document.getElementById('cust-status').innerText = data.status; document.getElementById('cust-discord').innerText = data.used_by; document.getElementById('cust-created').innerText = data.created_at.split('T')[0]; if(data.status === "Banned") document.getElementById('cust-status').className = "text-3xl font-black mt-3 text-red-500 drop-shadow-[0_0_10px_rgba(239,68,68,0.8)]"; else if(data.status === "Active") document.getElementById('cust-status').className = "text-3xl font-black mt-3 text-green-400 drop-shadow-[0_0_10px_rgba(74,222,128,0.8)]"; } catch(e){} }
    </script>
</body>
</html>
""".replace("LOGO_URL_PLACEHOLDER", SAFE_WEBSITE_LOGO_URL).replace("LTC_ADDR", LITECOIN_ADDRESS).replace("PP_EMAIL", PAYPAL_EMAIL)

# =========================================================
# 🌍 API ENDPOINTS (WEB SERVER)
# =========================================================
def get_user_from_token(request): return web_sessions.get(request.headers.get("Authorization"))
async def handle_index(request): return web.Response(text=WEB_HTML, content_type='text/html')

async def api_web_buy(request):
    try:
        data = await request.json(); email, proof, gateway, ptype = data.get("email"), data.get("proof"), data.get("gateway", "ltc"), data.get("product")
        if not email or not proof or ptype not in PRODUCTS: return web.json_response({"ok": False, "error": "Fehlende Daten."})
        if gateway == "ltc":
            ok, reason = await verify_ltc_payment(proof)
            if not ok: return web.json_response({"ok": False, "error": reason})
        key = f"{PRODUCTS[ptype]['key_prefix']}-{random_block()}-{random_block()}-{random_block()}"
        keys_db[key] = {"type": ptype, "used": False, "used_by": None, "bound_user_id": None, "created_at": iso_now(), "redeemed_at": None, "approved_in_ticket": f"WEB-{gateway.upper()}", "created_by": "System-Auto", "revoked": False}
        save_json(KEYS_FILE, keys_db)
        inv_id = build_invoice_id()
        invoices_db[inv_id] = {"buyer_id": email, "product_type": ptype, "payment_key": gateway, "key": key, "ticket_id": "WEB", "created_at": iso_now(), "final_price_eur": PRODUCTS[ptype]["price_eur"], "reseller_discount": False}
        save_json(INVOICES_FILE, invoices_db)
        send_delivery_email(email, PRODUCTS[ptype]["label"], key)
        log_activity(f"Web Order via {gateway.upper()} ({PRODUCTS[ptype]['price_eur']}€)", "Auto-Shop")
        return web.json_response({"ok": True, "key": key})
    except Exception as e: return web.json_response({"ok": False, "error": "Server Fehler."})

async def api_register(request):
    d = await request.json(); u, p, k = d.get("user"), d.get("pass"), d.get("key", "").upper()
    if not u or not p or not k: return web.json_response({"error": "Bitte fülle alle Felder aus!"}, status=400)
    if u in users_db: return web.json_response({"error": f"Der Name '{u}' ist leider schon vergeben!"}, status=400)
    if k not in webkeys_db or webkeys_db[k].get("used"): return web.json_response({"error": "Ungültiger oder benutzter Invite Key!"}, status=400)
    role = webkeys_db[k]["role"]; users_db[u] = {"pass": p, "role": role}; webkeys_db[k]["used"] = True; save_json(USERS_FILE, users_db); save_json(WEBKEYS_FILE, webkeys_db); log_activity(f"New User ({role})", u)
    token = str(uuid.uuid4()); web_sessions[token] = {"user": u, "role": role}; save_json(SESSIONS_FILE, web_sessions)
    return web.json_response({"ok": True, "token": token, "role": role, "user": u})

async def api_login(request):
    d = await request.json(); u, p = d.get("user"), d.get("pass")
    if u in users_db and users_db[u]["pass"] == p:
        token = str(uuid.uuid4()); role = users_db[u]["role"]; web_sessions[token] = {"user": u, "role": role}; save_json(SESSIONS_FILE, web_sessions)
        return web.json_response({"ok": True, "token": token, "role": role, "user": u})
    return web.Response(status=401)

async def api_customer_login(request):
    d = await request.json(); k = d.get("key", "").strip().upper()
    if not k or k not in keys_db: return web.json_response({"error": "Key existiert nicht."}, status=400)
    token = str(uuid.uuid4()); web_sessions[token] = {"user": k, "role": "customer"}; save_json(SESSIONS_FILE, web_sessions)
    return web.json_response({"ok": True, "token": token, "role": "customer", "user": k})

async def api_customer_data(request):
    u = get_user_from_token(request)
    if not u or u.get("role") != "customer": return web.Response(status=401)
    kdata = keys_db.get(u["user"], {}); ptype = kdata.get("type", "day_1") if isinstance(kdata, dict) else "day_1"; status = "Active"
    if isinstance(kdata, dict): status = "Banned" if kdata.get("revoked") else ("Unused" if not kdata.get("used") else "Active")
    return web.json_response({"key": u["user"], "type": PRODUCTS.get(ptype, {"label": "Unknown"}).get("label"), "status": status, "created_at": kdata.get("created_at", "Unknown"), "used_by": kdata.get("used_by", "None")})

async def api_verify(request):
    u = get_user_from_token(request)
    return web.json_response({"ok": True, "role": u["role"], "user": u["user"]}) if u else web.Response(status=401)

async def api_stats(request):
    if not get_user_from_token(request): return web.Response(status=401)
    total_rev = sum(float(d.get("final_price_eur", 0)) for d in invoices_db.values() if isinstance(d, dict)); active_k = sum(1 for v in keys_db.values() if isinstance(v, dict) and not v.get("used"))
    return web.json_response({"total_revenue": total_rev, "buyers_today": 0, "active_keys": active_k, "chart_labels": [], "chart_data": []})

async def api_discord_stats(request): return web.json_response({"members": bot.get_guild(GUILD_ID).member_count if bot.get_guild(GUILD_ID) else 0, "open_tickets": len(ticket_data)})
async def api_activity(request): return web.json_response(activity_db)
async def api_keys(request): return web.json_response(keys_db)
async def api_revoke_key(request):
    k = (await request.json()).get("key")
    if k in keys_db: keys_db[k]["revoked"] = True; keys_db[k]["used"] = True; save_json(KEYS_FILE, keys_db)
    return web.json_response({"ok": True})
async def api_team(request): return web.json_response([{"username": u, "password": d["pass"], "keys_generated": sum(1 for k in keys_db.values() if isinstance(k, dict) and k.get("created_by") == u)} for u, d in users_db.items() if d.get("role") == "reseller"])
async def api_team_delete(request):
    u = (await request.json()).get("username")
    if u in users_db: del users_db[u]; save_json(USERS_FILE, users_db)
    return web.json_response({"ok": True})
async def api_promos(request): return web.json_response(promos_db)
async def api_add_promo(request): d = await request.json(); promos_db[d["code"]] = {"discount": d["discount"], "uses": d["uses"]}; save_json(PROMOS_FILE, promos_db); return web.json_response({"ok": True})
async def api_rm_promo(request): c = (await request.json()).get("code"); promos_db.pop(c, None); save_json(PROMOS_FILE, promos_db); return web.json_response({"ok": True})
async def api_lookup(request):
    t = (await request.json()).get("user_id"); spent = sum(float(d.get("final_price_eur", 0)) for d in invoices_db.values() if isinstance(d, dict) and d.get("buyer_id") == t)
    invs = [{"id": i, "product": PRODUCTS.get(d.get("product_type"), {}).get("label", "Unknown"), "price": d.get("final_price_eur", 0), "date": d.get("created_at")} for i, d in invoices_db.items() if isinstance(d, dict) and d.get("buyer_id") == t]
    return web.json_response({"total_spent": spent, "total_orders": len(invs), "is_banned": t in blacklist_db, "invoices": invs[::-1]})
async def api_announce(request):
    d = await request.json(); ch = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if ch: emb = discord.Embed(title=d["title"], description=d["desc"], color=COLOR_MAIN); emb.set_image(url=d.get("img")) if d.get("img") else None; await ch.send(embed=emb)
    return web.json_response({"ok": True})
async def api_blacklist(request): return web.json_response(blacklist_db)
async def api_add_blacklist(request): d = await request.json(); blacklist_db[d.get("user_id")] = {"reason": d.get("reason", "Web Ban"), "added_by": "Admin", "added_at": iso_now()}; save_json(BLACKLIST_FILE, blacklist_db); return web.json_response({"ok": True})
async def api_rm_blacklist(request): u = (await request.json()).get("user_id"); blacklist_db.pop(u, None); save_json(BLACKLIST_FILE, blacklist_db); return web.json_response({"ok": True})
async def api_admin_gen(request):
    u = get_user_from_token(request); pt = (await request.json()).get("t", "day_1"); k = f"{PRODUCTS[pt]['key_prefix']}-{random_block()}-{random_block()}-{random_block()}"
    keys_db[k] = {"type": pt, "used": False, "used_by": None, "bound_user_id": None, "created_at": iso_now(), "redeemed_at": None, "approved_in_ticket": None, "created_by": u["user"] if u else "Admin", "revoked": False}
    save_json(KEYS_FILE, keys_db); return web.json_response({"key": k})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_index)
    routes = [('/api/web_buy', api_web_buy), ('/api/register', api_register), ('/api/login', api_login), ('/api/customer_login', api_customer_login), ('/api/verify', api_verify), ('/api/stats', api_stats), ('/api/discord_stats', api_discord_stats), ('/api/activity', api_activity), ('/api/keys', api_keys), ('/api/keys/revoke', api_revoke_key), ('/api/team', api_team), ('/api/team/delete', api_team_delete), ('/api/promos', api_promos), ('/api/promos/add', api_add_promo), ('/api/promos/remove', api_rm_promo), ('/api/lookup', api_lookup), ('/api/announce', api_announce), ('/api/blacklist', api_blacklist), ('/api/blacklist/add', api_add_blacklist), ('/api/blacklist/remove', api_rm_blacklist), ('/api/admin/generate', api_admin_gen), ('/api/customer_data', api_customer_data)]
    for path, handler in routes: app.router.add_post(path, handler)
    runner = web.AppRunner(app); await runner.setup(); await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start(); print("🚀 Web Server online!")

# =========================================================
# BOT COMMANDS & TICKET LOGIC (UNTOUCHED)
# =========================================================
def premium_divider(): return "━━━━━━━━━━━━━━━━━━━━━━━━"
def short_txid(txid): return txid if len(txid) < 20 else f"{txid[:14]}...{txid[-14:]}"
def format_price(value): return str(int(value)) if float(value).is_integer() else f"{value:.2f}"
def is_reseller_dc(member): return member and any(role.id == RESELLER_ROLE_ID for role in member.roles)

def get_price(product_key, member=None, promo_discount=0):
    bp = PRODUCTS[product_key]["price_eur"]
    if is_reseller_dc(member): bp = round(bp * 0.5, 2)
    if promo_discount > 0: bp = round(bp * (1 - (promo_discount / 100.0)), 2)
    return float(bp)

async def dm_user_safe(user, content=None, embed=None):
    try: await user.send(content=content, embed=embed)
    except: pass

def generate_key(product_type, ticket_id=None, creator="System"):
    k = f"{PRODUCTS[product_type]['key_prefix']}-{random_block()}-{random_block()}-{random_block()}"
    keys_db[k] = {"type": product_type, "used": False, "used_by": None, "bound_user_id": None, "created_at": iso_now(), "redeemed_at": None, "approved_in_ticket": ticket_id, "created_by": creator, "revoked": False}
    save_json(KEYS_FILE, keys_db); return k

def create_invoice_record(invoice_id, buyer_id, product_type, payment_key, key, ticket_id, final_price_eur, reseller_discount):
    invoices_db[invoice_id] = {"buyer_id": str(buyer_id), "product_type": product_type, "payment_key": payment_key, "key": key, "ticket_id": str(ticket_id), "created_at": iso_now(), "final_price_eur": final_price_eur, "reseller_discount": reseller_discount}
    save_json(INVOICES_FILE, invoices_db)

async def fetch_ltc_tx(txid):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=20) as resp:
            return (await resp.json(), None) if resp.status == 200 else (None, "API error")

async def fetch_ltc_price_eur():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=eur", timeout=20) as resp:
            return (await resp.json()).get("litecoin", {}).get("eur") if resp.status == 200 else None

def tx_matches_our_address(tx_data, expected_address):
    t = 0; f = False
    for o in tx_data.get("outputs", []):
        if expected_address in o.get("addresses", []): f = True; t += int(o.get("value", 0))
    return f, t

async def find_existing_ticket(guild, user):
    for c in guild.text_channels:
        if c.topic == f"ticket_owner:{user.id}": return c
    return None

def build_order_summary(product_key, payment_key, user, ltc_price_eur=None):
    product, payment, price = PRODUCTS[product_key], PAYMENTS[payment_key], get_price(product_key, user)
    price_header = f"💶 **Price:** {format_price(price)}€" + (" (**Reseller 50% OFF**)" if is_reseller_dc(user) else "")
    if payment_key == "paypal": extra = f"## 💸 PayPal Payment\n**Send payment to:**\n`{PAYPAL_EMAIL}`\n\n**After payment:**\n• Send screenshot in ticket\n• Click **Payment Sent**"
    elif payment_key == "litecoin": extra = f"## 🪙 Litecoin Payment\n**Send to:**\n`{LITECOIN_ADDRESS}`\n\n" + (f"**Approx LTC:** `{price / ltc_price_eur:.6f} LTC`\n\n" if ltc_price_eur else "") + "**After payment:** Click **Submit TXID**"
    elif payment_key == "ethereum": extra = f"## 🔷 Ethereum Payment\n**Send to:**\n`{ETHEREUM_ADDRESS}`\n\n**After payment:** Click **Submit Crypto TXID**"
    elif payment_key == "solana": extra = f"## 🟣 Solana Payment\n**Send to:**\n`{SOLANA_ADDRESS}`\n\n**After payment:** Click **Submit Crypto TXID**"
    elif payment_key == "paysafecard": extra = f"## 💳 Paysafecard\n**After buying code:** Click **Submit Code**"
    else: extra = f"## 🎁 Amazon Card\n**After buying code:** Click **Submit Code**"
    return discord.Embed(title="✦ ORDER SETUP COMPLETE ✦", description=f"{premium_divider()}\n{user.mention}\n\n📦 **Product:** {product['label']}\n{price_header}\n{payment['emoji']} **Method:** {payment['label']}\n\n{extra}\n{premium_divider()}", color=COLOR_MAIN)

def build_payment_summary_embed(channel_id):
    d = ticket_data.get(str(channel_id), {})
    u = bot.get_guild(GUILD_ID).get_member(d.get("user_id")) if bot.get_guild(GUILD_ID) else None
    pk, pc = d.get("product_key"), d.get("applied_promo")
    pd = promos_db[pc]["discount"] if pc and pc in promos_db else 0
    pt = f"{format_price(get_price(pk, u, pd))}€" + (" (Reseller)" if is_reseller_dc(u) else "") + (f" (-{pd}%)" if pd > 0 else "") if pk in PRODUCTS else "—"
    sm = {"waiting": "🟡 Waiting", "reviewing": "🟠 Reviewing", "approved": "✅ Approved", "denied": "❌ Denied"}
    e = discord.Embed(title="📋 Payment Summary", description=f"{premium_divider()}\n**Live order status**\n{premium_divider()}", color=COLOR_INFO)
    e.add_field(name="Product", value=PRODUCTS[pk]["label"] if pk in PRODUCTS else "None", inline=True)
    e.add_field(name="Price", value=pt, inline=True)
    e.add_field(name="Method", value=PAYMENTS[d.get("payment_key")]["label"] if d.get("payment_key") in PAYMENTS else "None", inline=True)
    e.add_field(name="Status", value=sm.get(d.get("status", "waiting"), d.get("status", "waiting")), inline=True)
    e.add_field(name="TXID", value=f"`{short_txid(d.get('last_txid'))}`" if d.get('last_txid') else "None", inline=True)
    e.add_field(name="Invoice", value=f"`{d.get('invoice_id')}`" if d.get('invoice_id') else "None", inline=False)
    if pc: e.add_field(name="Promo", value=f"`{pc}`", inline=True)
    return e

async def update_payment_summary_message(channel):
    d = ticket_data.get(str(channel.id))
    if d and d.get("summary_message_id"):
        try: msg = await channel.fetch_message(d["summary_message_id"]); await msg.edit(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
        except: pass

async def send_admin_panel_to_channel(guild, owner_id, ticket_channel_id):
    ac = guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
    if ac:
        msg = await ac.send(embed=discord.Embed(title="🛠️ GEN ADMIN PANEL", description=f"{premium_divider()}\n**Buyer ID:** `{owner_id}`\n**Ticket ID:** `{ticket_channel_id}`\n{premium_divider()}", color=COLOR_ADMIN), view=AdminPanelView())
        if str(ticket_channel_id) in ticket_data: ticket_data[str(ticket_channel_id)]["admin_message_id"] = msg.id; save_json(TICKETS_FILE, ticket_data)

async def send_summary_and_admin_panels(channel, owner_id):
    sm = await channel.send(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
    ticket_data[str(channel.id)]["summary_message_id"] = sm.id; save_json(TICKETS_FILE, ticket_data)
    await send_admin_panel_to_channel(channel.guild, owner_id, channel.id)

async def redeem_key_for_user(guild, member, key):
    if is_blacklisted(member.id): return False, "You are blacklisted."
    if key not in keys_db: return False, "Key not found."
    if keys_db[key].get("revoked"): return False, "This key has been banned."
    if keys_db[key]["used"]: return False, "Already used."
    pt = keys_db[key]["type"]; r = guild.get_role(REDEEM_ROLE_ID)
    if not r: return False, "Role not found."
    keys_db[key].update({"used": True, "used_by": str(member.id)}); save_json(KEYS_FILE, keys_db)
    dur = PRODUCTS.get(pt, {}).get("duration_days", 0)
    redeemed_db[str(member.id)] = {"key": key, "type": pt, "role_id": REDEEM_ROLE_ID, "expires_at": (now_utc() + timedelta(days=dur)).isoformat() if dur > 0 else None}
    save_json(REDEEMED_FILE, redeemed_db); await member.add_roles(r); return True, pt

class CloseConfirmView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_close(self, interaction, button):
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        d = ticket_data.get(str(interaction.channel.id))
        if d and d.get("admin_message_id"):
            ac = interaction.guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
            if ac:
                try: msg = await ac.fetch_message(d["admin_message_id"]); await msg.delete()
                except: pass
        ticket_data.pop(str(interaction.channel.id), None); save_json(TICKETS_FILE, ticket_data)
        await asyncio.sleep(2); await interaction.channel.delete()

class TicketManageView(discord.ui.View):
    def __init__(self, owner_id=None): super().__init__(timeout=None)
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="claim_ticket_button")
    async def claim_ticket(self, interaction, button): await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.")
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket(self, interaction, button):
        d = ticket_data.get(str(interaction.channel.id)); owner = d.get("user_id") if d else None
        if owner and interaction.user.id != owner and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("No permission.", ephemeral=True)
        await interaction.response.send_message("Are you sure you want to close this ticket?", view=CloseConfirmView(), ephemeral=True)

class PromoCodeModal(discord.ui.Modal, title="Gutscheincode einlösen"):
    code_input = discord.ui.TextInput(label="Promo Code", placeholder="z.B. VALE20", required=True)
    async def on_submit(self, interaction):
        d = ticket_data.get(str(interaction.channel.id))
        if not d: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        if interaction.user.id != d.get("user_id") and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        c = str(self.code_input).strip().upper()
        if c not in promos_db or promos_db[c]["uses"] <= 0: return await interaction.response.send_message("❌ Ungültiger Code.", ephemeral=True)
        d["applied_promo"] = c; save_json(TICKETS_FILE, ticket_data); await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message(f"✅ Gutschein `{c}` angewendet!", ephemeral=True)

class GenericCryptoTxidModal(discord.ui.Modal, title="Paste your Crypto TXID here"):
    txid_input = discord.ui.TextInput(label="Transaction Hash (TXID)", required=True)
    async def on_submit(self, interaction):
        d = ticket_data.get(str(interaction.channel.id))
        if not d: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        txid = str(self.txid_input).strip(); d["last_txid"] = txid; d["status"] = "reviewing"; save_json(TICKETS_FILE, ticket_data)
        rc = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if rc: await rc.send(content=f"<@&{STAFF_ROLE_ID}> Review needed.", embed=discord.Embed(title="🪙 Crypto TXID Submitted", description=f"**Buyer:** {interaction.user.mention}\n**Ticket:** <#{interaction.channel.id}>\n**TXID:** `{txid}`", color=COLOR_WARN), view=ReviewView())
        await interaction.channel.send(embed=discord.Embed(title="✅ TXID Submitted", description="Sent to staff.", color=COLOR_SUCCESS)); await update_payment_summary_message(interaction.channel); await interaction.response.send_message("Submitted.", ephemeral=True)

class LitecoinTxidModal(discord.ui.Modal, title="Paste your Litecoin TXID here"):
    txid_input = discord.ui.TextInput(label="Litecoin TXID", required=True, min_length=64, max_length=64)
    async def on_submit(self, interaction):
        d = ticket_data.get(str(interaction.channel.id))
        if not d: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        txid = str(self.txid_input).strip()
        if txid in used_txids_db: return await interaction.response.send_message("Already submitted.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        tx_data, err = await fetch_ltc_tx(txid)
        if err or not tx_data: return await interaction.followup.send(f"API Error. {err}", ephemeral=True)
        conf = int(tx_data.get("confirmations", 0)); f_addr, tot_litoshi = tx_matches_our_address(tx_data, LITECOIN_ADDRESS)
        used_txids_db[txid] = {"user_id": str(interaction.user.id), "used_at": iso_now()}; save_json(USED_TXIDS_FILE, used_txids_db)
        d["last_txid"] = txid; d["status"] = "reviewing"; save_json(TICKETS_FILE, ticket_data)
        await interaction.channel.send(embed=discord.Embed(title="🪙 Litecoin TXID Result", description=f"**Address Match:** {'Yes' if f_addr else 'No'}\n**Confirmations:** {conf}\n**Received:** {litoshi_to_ltc(tot_litoshi):.8f} LTC", color=COLOR_SUCCESS if f_addr and conf >= LTC_MIN_CONFIRMATIONS else COLOR_WARN))
        await update_payment_summary_message(interaction.channel); await interaction.followup.send("TXID Check done.", ephemeral=True)

class PaymentActionView(discord.ui.View):
    def __init__(self, owner_id=None): super().__init__(timeout=None)
    @discord.ui.button(label="Promo Code", style=discord.ButtonStyle.secondary, emoji="🎟️", custom_id="apply_promo_button")
    async def apply_promo(self, interaction, button): await interaction.response.send_modal(PromoCodeModal())
    @discord.ui.button(label="Payment Sent", style=discord.ButtonStyle.success, emoji="✅", custom_id="payment_sent_button")
    async def payment_sent(self, interaction, button):
        d = ticket_data.get(str(interaction.channel.id))
        if not d: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        d["status"] = "reviewing"; save_json(TICKETS_FILE, ticket_data)
        rc = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if rc: await rc.send(content=f"<@&{STAFF_ROLE_ID}> New payment to review.", embed=discord.Embed(title="🧾 Payment Review", description=f"Ticket: <#{interaction.channel.id}>", color=COLOR_WARN), view=ReviewView())
        await update_payment_summary_message(interaction.channel); await interaction.response.send_message("Staff notified.", ephemeral=True)
    @discord.ui.button(label="Submit LTC TXID", style=discord.ButtonStyle.primary, emoji="🪙", custom_id="submit_txid_button")
    async def submit_txid(self, interaction, button): await interaction.response.send_modal(LitecoinTxidModal())
    @discord.ui.button(label="Submit Crypto TXID", style=discord.ButtonStyle.primary, emoji="🔗", custom_id="submit_generic_txid_button")
    async def submit_generic_txid(self, interaction, button): await interaction.response.send_modal(GenericCryptoTxidModal())

class PaymentSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="PayPal", value="paypal", emoji="💸"), discord.SelectOption(label="Litecoin", value="litecoin", emoji="🪙"), discord.SelectOption(label="Ethereum", value="ethereum", emoji="🔷"), discord.SelectOption(label="Solana", value="solana", emoji="🟣"), discord.SelectOption(label="Paysafecard", value="paysafecard", emoji="💳"), discord.SelectOption(label="Amazon Card", value="amazoncard", emoji="🎁")]
        super().__init__(placeholder="💳 Choose payment method", min_values=1, max_values=1, options=options, custom_id="buy_payment_select")
    async def callback(self, interaction):
        d = ticket_data.get(str(interaction.channel.id))
        if not d: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        d["payment_key"] = self.values[0]; save_json(TICKETS_FILE, ticket_data)
        b = interaction.guild.get_member(d["user_id"]); lp = await fetch_ltc_price_eur() if self.values[0] == "litecoin" else None
        await interaction.response.send_message(embed=build_order_summary(d["product_key"], self.values[0], b, lp), view=PaymentActionView()); await update_payment_summary_message(interaction.channel)

class PaymentSelectView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(PaymentSelect())

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="1 Day", description="5€", value="day_1", emoji="📅"), discord.SelectOption(label="1 Week", description="15€", value="week_1", emoji="🗓️"), discord.SelectOption(label="Lifetime", description="30€", value="lifetime", emoji="♾️")]
        super().__init__(placeholder="📦 Choose your product", min_values=1, max_values=1, options=options, custom_id="buy_product_select")
    async def callback(self, interaction):
        d = ticket_data.get(str(interaction.channel.id))
        if not d: return await interaction.response.send_message("Ticket-Daten nicht gefunden.", ephemeral=True)
        d["product_key"] = self.values[0]; save_json(TICKETS_FILE, ticket_data)
        await interaction.response.send_message(embed=discord.Embed(title="📦 Product Selected", description=f"**{PRODUCTS[self.values[0]]['label']}** selected.\nChoose payment method.", color=COLOR_INFO), view=PaymentSelectView()); await update_payment_summary_message(interaction.channel)

class ProductSelectView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(ProductSelect())

class BuySetupView(discord.ui.View):
    def __init__(self, owner_id=None): super().__init__(timeout=None)
    @discord.ui.button(label="Choose Product", style=discord.ButtonStyle.primary, emoji="📦", custom_id="choose_product_button")
    async def choose_product(self, interaction, button): await interaction.response.send_message("Select product:", view=ProductSelectView(), ephemeral=True)
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_buy_ticket_button")
    async def close_buy_ticket(self, interaction, button): await interaction.response.send_message("Are you sure?", view=CloseConfirmView(), ephemeral=True)

class PaymentSummaryView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="refresh_payment_summary")
    async def refresh_summary(self, interaction, button): await interaction.response.edit_message(embed=build_payment_summary_embed(interaction.channel.id), view=PaymentSummaryView())

async def process_approve(interaction, target_channel_id, buyer_id):
    try:
        c = interaction.guild.get_channel(target_channel_id); d = ticket_data.get(str(target_channel_id))
        if not d: return await interaction.response.send_message("❌ Ticket-Daten nicht gefunden.", ephemeral=True)
        if d.get("status") == "approved": return await interaction.response.send_message("✅ Bereits genehmigt.", ephemeral=True)
        b = interaction.guild.get_member(buyer_id); inv_id = build_invoice_id()
        d["invoice_id"] = inv_id; d["status"] = "approved"; save_json(TICKETS_FILE, ticket_data)
        pc = d.get("applied_promo"); pd = promos_db[pc]["discount"] if pc and pc in promos_db else 0
        if pc and pc in promos_db: promos_db[pc]["uses"] -= 1; save_json(PROMOS_FILE, promos_db)
        gk = generate_key(d["product_key"], ticket_id=str(target_channel_id)); keys_db[gk]["bound_user_id"] = str(b.id) if b else "Unknown"; save_json(KEYS_FILE, keys_db)
        fp = get_price(d["product_key"], b, pd)
        create_invoice_record(inv_id, buyer_id, d["product_key"], d["payment_key"], gk, target_channel_id, fp, is_reseller_dc(b))
        if c: await c.send(embed=discord.Embed(title="🧾 Payment Approved", description=f"**Invoice:** `{inv_id}`\n**Price:** {fp}€\n**Key:** `{gk}`", color=COLOR_SUCCESS)); await update_payment_summary_message(c)
        if b: await dm_user_safe(b, embed=discord.Embed(title="🔑 Purchase Approved", description=f"**Key:** `{gk}`\nDu kannst dich mit diesem Key auf der Website einloggen!", color=COLOR_SUCCESS))
        await interaction.response.send_message("✅ Approved. Key wurde generiert.", ephemeral=True)
    except Exception as e: await interaction.response.send_message(f"❌ Fehler: {str(e)}", ephemeral=True)

async def process_deny(interaction, target_channel_id):
    try:
        c = interaction.guild.get_channel(target_channel_id)
        if str(target_channel_id) in ticket_data: ticket_data[str(target_channel_id)]["status"] = "denied"; save_json(TICKETS_FILE, ticket_data)
        if c: await c.send(embed=discord.Embed(title="❌ Denied", description="Payment was denied.", color=COLOR_DENY)); await update_payment_summary_message(c)
        await interaction.response.send_message("✅ Denied.", ephemeral=True)
    except Exception as e: await interaction.response.send_message(f"❌ Fehler: {str(e)}", ephemeral=True)

class AdminPanelView(discord.ui.View):
    def __init__(self, owner_id=None, ticket_channel_id=None): super().__init__(timeout=None)
    async def _get_data(self, interaction):
        emb = interaction.message.embeds[0]; desc = emb.description
        b_match = re.search(r"\*\*Buyer ID:\*\* `?(\d+)`?", desc); t_match = re.search(r"\*\*Ticket ID:\*\* `?(\d+)`?", desc)
        if not b_match or not t_match: return None, None
        return int(t_match.group(1)), int(b_match.group(1))
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="adminpanel_approve")
    async def approve_button(self, interaction, button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Fehler.", ephemeral=True)
        await process_approve(interaction, t_id, b_id)
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="adminpanel_deny")
    async def deny_button(self, interaction, button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Fehler.", ephemeral=True)
        await process_deny(interaction, t_id)

class ReviewView(discord.ui.View):
    def __init__(self, target_channel_id=None, buyer_id=None): super().__init__(timeout=None)
    async def _get_data(self, interaction):
        emb = interaction.message.embeds[0]; desc = emb.description
        b_match = re.search(r"<@!?(\d+)>", desc); t_match = re.search(r"<#(\d+)>", desc)
        if not b_match or not t_match: return None, None
        return int(t_match.group(1)), int(b_match.group(1))
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="review_approve_button")
    async def approve(self, interaction, button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Fehler.", ephemeral=True)
        await process_approve(interaction, t_id, b_id)
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="review_deny_button")
    async def deny(self, interaction, button): 
        t_id, b_id = await self._get_data(interaction)
        if not t_id: return await interaction.response.send_message("Fehler.", ephemeral=True)
        await process_deny(interaction, t_id)

class MainTicketPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="💠", custom_id="main_support_ticket_button")
    async def support_button(self, interaction, button): await self.create_ticket_channel(interaction, "support")
    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, emoji="🛒", custom_id="main_buy_ticket_button")
    async def buy_button(self, interaction, button): await self.create_ticket_channel(interaction, "buy")
    async def create_ticket_channel(self, interaction, ticket_type):
        await interaction.response.defer(ephemeral=True); g, u = interaction.guild, interaction.user
        if is_blacklisted(u.id): return await interaction.followup.send("Blacklisted.", ephemeral=True)
        if u.id in ticket_locks: return await interaction.followup.send("Bitte warten...", ephemeral=True)
        ticket_locks.add(u.id)
        try:
            ex = await find_existing_ticket(g, u)
            if ex: return await interaction.followup.send(f"Ticket offen: {ex.mention}", ephemeral=True)
            cat = g.get_channel(BUY_CATEGORY_ID if ticket_type == "buy" else SUPPORT_CATEGORY_ID)
            ow = {g.default_role: discord.PermissionOverwrite(view_channel=False), u: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
            bm = g.get_member(bot.user.id)
            if bm: ow[bm] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            sr = g.get_role(STAFF_ROLE_ID)
            if sr: ow[sr] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
            c = await g.create_text_channel(name=f"{ticket_type}-{u.name}"[:90], category=cat, overwrites=ow, topic=f"ticket_owner:{u.id}")
            if ticket_type == "support": await c.send(content=f"{u.mention} <@&{STAFF_ROLE_ID}>", embed=discord.Embed(title="💠 Support", description="Issue?", color=COLOR_SUPPORT), view=TicketManageView())
            else:
                ticket_data[str(c.id)] = {"user_id": u.id, "product_key": None, "payment_key": None, "last_txid": None, "invoice_id": None, "status": "waiting", "applied_promo": None}; save_json(TICKETS_FILE, ticket_data)
                await c.send(content=f"{u.mention} <@&{STAFF_ROLE_ID}>", embed=discord.Embed(title="🛒 Buy", description="Choose Product", color=COLOR_BUY), view=BuySetupView())
                await send_summary_and_admin_panels(c, u.id)
            await interaction.followup.send(f"✅ Ticket: {c.mention}", ephemeral=True)
        finally: ticket_locks.discard(u.id)

class RedeemKeyModal(discord.ui.Modal, title="Paste your key here"):
    key_input = discord.ui.TextInput(label="Key", required=True)
    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        ok, res = await redeem_key_for_user(interaction.guild, interaction.user, str(self.key_input).strip().upper())
        if ok: await interaction.followup.send(f"✅ Success! You received the {PRODUCTS.get(res, {}).get('label', 'Unknown')} role.", ephemeral=True)
        else: await interaction.followup.send(f"❌ {res}", ephemeral=True)

class RedeemPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Redeem", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="redeem_key_button")
    async def redeem_button(self, interaction, button): await interaction.response.send_modal(RedeemKeyModal())

@bot.event
async def on_member_join(member):
    c = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if c:
        e = discord.Embed(title="Welcome!", description=f"Welcome {member.mention} to **{SERVER_NAME}**.\n\nRead the rules in <#{RULES_CHANNEL_ID}>", color=COLOR_WELCOME)
        e.set_author(name=SERVER_NAME, icon_url=WELCOME_THUMBNAIL_URL); e.set_thumbnail(url=WELCOME_THUMBNAIL_URL); e.set_image(url=WELCOME_BANNER_URL)
        try: await c.send(embed=e)
        except: pass

@bot.tree.command(name="nuke_database", description="(ADMIN) Löscht alle DBs!")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def nuke_database(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    global users_db, webkeys_db, web_sessions, keys_db, ticket_data, redeemed_db, used_txids_db
    users_db = {}; webkeys_db = {}; web_sessions = {}; keys_db = {}; ticket_data = {}; redeemed_db = {}; used_txids_db = {}
    save_json(USERS_FILE, users_db); save_json(WEBKEYS_FILE, webkeys_db); save_json(SESSIONS_FILE, web_sessions); save_json(KEYS_FILE, keys_db); save_json(TICKETS_FILE, ticket_data); save_json(REDEEMED_FILE, redeemed_db); save_json(USED_TXIDS_FILE, used_txids_db)
    await interaction.response.send_message("💣 **BOOM!** DB gelöscht.", ephemeral=True)

@bot.tree.command(name="gen_admin_key", description="Generiert ADMIN Key")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gen_admin_key(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    nk = f"VALE-ADMIN-{random_block(6)}"
    webkeys_db[nk] = {"role": "admin", "used": False, "created_by": str(interaction.user.name), "created_at": iso_now()}; save_json(WEBKEYS_FILE, webkeys_db)
    c = interaction.guild.get_channel(WEB_KEY_CHANNEL_ID)
    if c: await c.send(embed=discord.Embed(title="🔐 Admin Key", description=f"**Key:** `{nk}`", color=COLOR_MAIN))
    await interaction.response.send_message(f"Admin Key: `{nk}`", ephemeral=True)

@bot.tree.command(name="gen_reseller_key", description="Generiert RESELLER Key")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gen_reseller_key(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    nk = f"VALE-RES-{random_block(6)}"
    webkeys_db[nk] = {"role": "reseller", "used": False, "created_for": str(user.name), "created_at": iso_now()}; save_json(WEBKEYS_FILE, webkeys_db)
    c = interaction.guild.get_channel(WEB_KEY_CHANNEL_ID)
    if c: await c.send(embed=discord.Embed(title="🔐 Reseller Key", description=f"**Key:** `{nk}`", color=COLOR_SUCCESS))
    await interaction.response.send_message(f"Reseller Key: `{nk}`", ephemeral=True)

@bot.tree.command(name="ticket", description="Open ticket panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket(interaction: discord.Interaction):
    e = discord.Embed(title="✦ VALE GEN TICKET CENTER ✦", description=f"{premium_divider()}\n**Open ticket below**\n\n💠 **Support**\n🛒 **Buy**\n{premium_divider()}", color=COLOR_MAIN)
    e.set_image(url=PANEL_IMAGE_URL); await interaction.response.send_message(embed=e, view=MainTicketPanelView())

@bot.tree.command(name="send_redeem_panel", description="Send redeem panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_redeem_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="🎟️ REDEEM", description="Click to redeem.", color=COLOR_MAIN), view=RedeemPanelView())

@bot.tree.command(name="vouch", description="Hinterlasse eine Bewertung")
@app_commands.choices(sterne=[app_commands.Choice(name="⭐⭐⭐⭐⭐", value=5), app_commands.Choice(name="⭐⭐⭐⭐", value=4), app_commands.Choice(name="⭐⭐⭐", value=3)])
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def vouch(interaction: discord.Interaction, sterne: app_commands.Choice[int], produkt: str, bewertung: str):
    c = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if c: 
        e = discord.Embed(title=f"Vouch: {sterne.name}", description=f'"{bewertung}"', color=COLOR_MAIN); e.add_field(name="Käufer", value=interaction.user.mention); e.add_field(name="Produkt", value=produkt); e.set_thumbnail(url=interaction.user.display_avatar.url); await c.send(embed=e)
    await interaction.response.send_message("✅ Danke!", ephemeral=True)

@bot.tree.command(name="send_rules", description="Postet Regelwerk")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_rules(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    e = discord.Embed(title="📜 Rules", description="1. Respect\n2. No Spam\n3. Tickets for Support", color=COLOR_WELCOME); e.set_image(url=WELCOME_BANNER_URL)
    await interaction.channel.send(embed=e); await interaction.response.send_message("Rules posted!", ephemeral=True)

@bot.tree.command(name="test_welcome", description="Testet Welcome")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def test_welcome(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    await interaction.response.send_message("Simuliert...", ephemeral=True); bot.dispatch('member_join', interaction.user)

if __name__ == "__main__":
    bot.run(TOKEN)
