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
# CONFIGURATION & LINKS (ORIGINAL VOLLSTÄNDIG)
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

WEBSITE_LOGO_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751701567934535/velo.png"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1477646233563566080/1490751958573645834/velo_log.png"
SAFE_WEBSITE_LOGO_URL = WEBSITE_LOGO_URL.replace("&", "&amp;")
WELCOME_THUMBNAIL_URL = WEBSITE_LOGO_URL
WELCOME_BANNER_URL = PANEL_IMAGE_URL

LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"
PAYPAL_EMAIL = "hydrasupfivem@gmail.com"

# Farben
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
    "day_1": {"label": "1 Day Access", "price_eur": 5, "duration_days": 1, "key_prefix": "GEN-1D", "desc": "24 Hours Full Access"},
    "week_1": {"label": "1 Week Access", "price_eur": 15, "duration_days": 7, "key_prefix": "GEN-1W", "desc": "7 Days Full Access"},
    "lifetime": {"label": "Lifetime Access", "price_eur": 30, "duration_days": 0, "key_prefix": "GEN-LT", "desc": "Permanent Access + VIP"}
}

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f: json.dump(default, f)
        return default
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
    global activity_db
    activity_db.insert(0, {"time": datetime.now(timezone.utc).isoformat(), "user": str(user), "action": action})
    activity_db = activity_db[:50]
    save_json(ACTIVITY_FILE, activity_db)

def iso_now(): return datetime.now(timezone.utc).isoformat()
def random_block(length=4): return uuid.uuid4().hex[:length].upper()
def build_invoice_id() -> str: return f"GEN-{uuid.uuid4().hex[:10].upper()}"

# =========================================================
# AUTO-CHECKER & MAIL LOGIC
# =========================================================
async def verify_ltc_payment(txid):
    if txid in used_txids_db: return False, "TXID already used."
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=15) as resp:
            if resp.status != 200: return False, "Invalid TXID or Network Error."
            data = await resp.json()
            for out in data.get("outputs", []):
                if LITECOIN_ADDRESS in out.get("addresses", []):
                    used_txids_db[txid] = {"time": iso_now()}
                    save_json(USED_TXIDS_FILE, used_txids_db)
                    return True, "LTC Verified"
    return False, "Payment not found to our address."

def send_delivery_email(to_email, product_label, key):
    if not SMTP_USER or not SMTP_PASS: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Order Delivered - {SERVER_NAME} 🎉"
        body = f"Hello!\n\nYour payment was successful.\n\nProduct: {product_label}\nKey: {key}\n\nRedeem it on our dashboard or Discord server."
        msg.attach(MIMEText(body, 'plain'))
        if SMTP_PORT == 465: server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else: server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT); server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        return True
    except: return False

# =========================================================
# WEB HTML (SELLAUTH STYLE - CLEAN & MINIMALIST)
# =========================================================
WEB_HTML = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VALE GEN | Store</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #0a0a0c; color: #f3f4f6; overflow-x: hidden; }
        
        /* Subtle Background pattern SellAuth Style */
        .bg-pattern {
            position: fixed; inset: 0; z-index: -1;
            background-color: #0a0a0c;
            background-image: radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
        }

        .sa-card {
            background: #121216;
            border: 1px solid #27272a;
            border-radius: 12px;
            transition: all 0.2s ease-in-out;
        }
        .sa-card:hover {
            border-color: #8b5cf6;
            transform: translateY(-2px);
            box-shadow: 0 10px 30px -10px rgba(139, 92, 246, 0.15);
        }
        
        .sa-input {
            background: #0a0a0c;
            border: 1px solid #27272a;
            color: white;
            transition: 0.2s;
        }
        .sa-input:focus { border-color: #8b5cf6; outline: none; box-shadow: 0 0 0 2px rgba(139,92,246,0.2); }
        
        .sa-btn {
            background: #8b5cf6; color: white; transition: 0.2s;
        }
        .sa-btn:hover { background: #7c3aed; }
        
        .payment-box { border: 1px solid #27272a; background: #0a0a0c; cursor: pointer; transition: 0.2s; }
        .payment-box.selected { border-color: #8b5cf6; background: rgba(139, 92, 246, 0.05); }

        .hidden-view { display: none !important; }
        .tab-content { display: none; } 
        .tab-content.active { display: block; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        
        .loader { border: 3px solid #27272a; border-top: 3px solid #8b5cf6; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="flex flex-col min-h-screen relative">
    <div class="bg-pattern"></div>

    <nav class="w-full border-b border-gray-800 bg-[#0a0a0c]/80 backdrop-blur-md sticky top-0 z-40">
        <div class="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
            <div class="flex items-center gap-3 cursor-pointer" onclick="switchView('shop')">
                <img src="LOGO_URL_PLACEHOLDER" class="h-8 w-8 rounded-lg">
                <span class="text-xl font-bold tracking-tight">VALE GEN</span>
            </div>
            <div class="flex gap-4">
                <button onclick="switchView('shop')" class="text-sm font-medium text-gray-400 hover:text-white transition">Products</button>
                <button onclick="switchView('auth')" class="text-sm font-medium text-gray-400 hover:text-white transition">Login</button>
            </div>
        </div>
    </nav>

    <main class="flex-1 w-full max-w-6xl mx-auto px-6 py-12">
        
        <div id="view-shop" class="w-full">
            <div class="mb-12">
                <h1 class="text-3xl font-bold mb-2">Our Products</h1>
                <p class="text-gray-400 text-sm">Instant delivery on all purchases via Email & Dashboard.</p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div class="sa-card p-6 flex flex-col">
                    <div class="flex justify-between items-start mb-4">
                        <div class="p-3 bg-gray-800/50 rounded-lg"><i class="fa-solid fa-key text-purple-400 text-xl"></i></div>
                        <span class="bg-green-500/10 text-green-400 text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide">In Stock</span>
                    </div>
                    <h3 class="text-lg font-bold mb-1">1 Day Access</h3>
                    <p class="text-xs text-gray-400 mb-6">24 Hours Full Access</p>
                    <div class="mt-auto flex items-center justify-between">
                        <span class="text-2xl font-bold">€5.00</span>
                        <button onclick="openCheckout('day_1', 5.00)" class="sa-btn px-5 py-2 rounded-lg text-sm font-bold shadow-lg shadow-purple-500/20">Purchase</button>
                    </div>
                </div>
                
                <div class="sa-card p-6 flex flex-col border-purple-500/30 relative overflow-hidden">
                    <div class="absolute top-3 right-[-30px] bg-purple-500 text-white text-[9px] font-bold px-10 py-1 rotate-45">POPULAR</div>
                    <div class="flex justify-between items-start mb-4">
                        <div class="p-3 bg-purple-500/10 rounded-lg"><i class="fa-solid fa-bolt text-purple-400 text-xl"></i></div>
                    </div>
                    <h3 class="text-lg font-bold mb-1">1 Week Access</h3>
                    <p class="text-xs text-gray-400 mb-6">7 Days Full Access + Priority</p>
                    <div class="mt-auto flex items-center justify-between">
                        <span class="text-2xl font-bold">€15.00</span>
                        <button onclick="openCheckout('week_1', 15.00)" class="sa-btn px-5 py-2 rounded-lg text-sm font-bold shadow-lg shadow-purple-500/20">Purchase</button>
                    </div>
                </div>
                
                <div class="sa-card p-6 flex flex-col">
                    <div class="flex justify-between items-start mb-4">
                        <div class="p-3 bg-yellow-500/10 rounded-lg"><i class="fa-solid fa-star text-yellow-400 text-xl"></i></div>
                        <span class="bg-green-500/10 text-green-400 text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wide">In Stock</span>
                    </div>
                    <h3 class="text-lg font-bold mb-1">Lifetime Access</h3>
                    <p class="text-xs text-gray-400 mb-6">Permanent Access + VIP Role</p>
                    <div class="mt-auto flex items-center justify-between">
                        <span class="text-2xl font-bold">€30.00</span>
                        <button onclick="openCheckout('lifetime', 30.00)" class="sa-btn px-5 py-2 rounded-lg text-sm font-bold shadow-lg shadow-purple-500/20">Purchase</button>
                    </div>
                </div>
            </div>
        </div>

        <div id="view-auth" class="w-full max-w-md mx-auto hidden-view mt-10">
            <div class="sa-card p-8">
                <h2 class="text-2xl font-bold mb-6 text-center">User Portal</h2>
                
                <div class="flex bg-[#0a0a0c] p-1 rounded-lg border border-gray-800 mb-6">
                    <button onclick="switchAuthTab('customer')" id="tab-btn-customer" class="flex-1 py-2 text-sm font-medium rounded-md bg-gray-800 text-white transition">Customer</button>
                    <button onclick="switchAuthTab('login')" id="tab-btn-login" class="flex-1 py-2 text-sm font-medium rounded-md text-gray-400 hover:text-white transition">Admin</button>
                    <button onclick="switchAuthTab('register')" id="tab-btn-register" class="flex-1 py-2 text-sm font-medium rounded-md text-gray-400 hover:text-white transition">Register</button>
                </div>

                <div id="form-customer" class="space-y-4">
                    <div>
                        <label class="text-xs font-medium text-gray-400 mb-1 block">Your License Key</label>
                        <input type="text" id="c-key" class="sa-input w-full rounded-lg px-4 py-2 font-mono text-sm" placeholder="GEN-XXXX...">
                    </div>
                    <button onclick="customerLogin()" class="sa-btn w-full py-2.5 rounded-lg font-bold text-sm mt-2">Access Dashboard</button>
                </div>

                <div id="form-login" class="space-y-4 hidden-view">
                    <div>
                        <label class="text-xs font-medium text-gray-400 mb-1 block">Username</label>
                        <input type="text" id="l-user" class="sa-input w-full rounded-lg px-4 py-2 text-sm" placeholder="admin">
                    </div>
                    <div>
                        <label class="text-xs font-medium text-gray-400 mb-1 block">Password</label>
                        <input type="password" id="l-pass" class="sa-input w-full rounded-lg px-4 py-2 text-sm" placeholder="••••••••">
                    </div>
                    <button onclick="login()" class="sa-btn w-full py-2.5 rounded-lg font-bold text-sm mt-2">Sign In</button>
                </div>

                <div id="form-register" class="space-y-4 hidden-view">
                    <div>
                        <label class="text-xs font-medium text-gray-400 mb-1 block">Username</label>
                        <input type="text" id="r-user" class="sa-input w-full rounded-lg px-4 py-2 text-sm" placeholder="Choose a username">
                    </div>
                    <div>
                        <label class="text-xs font-medium text-gray-400 mb-1 block">Password</label>
                        <input type="password" id="r-pass" class="sa-input w-full rounded-lg px-4 py-2 text-sm" placeholder="Choose a password">
                    </div>
                    <div>
                        <label class="text-xs font-medium text-gray-400 mb-1 block">Invite Key</label>
                        <input type="text" id="r-key" class="sa-input w-full rounded-lg px-4 py-2 font-mono text-sm" placeholder="VALE-...">
                    </div>
                    <button onclick="register()" class="sa-btn w-full py-2.5 rounded-lg font-bold text-sm mt-2">Create Account</button>
                </div>

                <p id="auth-error" class="text-red-400 mt-4 text-xs text-center font-medium hidden"></p>
            </div>
        </div>

        <div id="checkout-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden-view flex items-center justify-center p-4 z-50">
            <div class="sa-card max-w-lg w-full p-0 overflow-hidden flex flex-col max-h-[90vh]">
                
                <div class="p-6 border-b border-gray-800 flex justify-between items-center bg-[#121216] z-10">
                    <div>
                        <h2 class="text-lg font-bold">Checkout</h2>
                        <p class="text-xs text-gray-400" id="co-prod-name">Product Name • <span id="co-display-price" class="text-white font-bold"></span>€</p>
                    </div>
                    <button onclick="closeCheckout()" class="text-gray-500 hover:text-white transition"><i class="fa-solid fa-xmark text-xl"></i></button>
                </div>

                <div class="p-6 overflow-y-auto flex-1">
                    <div id="co-step-1" class="space-y-6">
                        <div>
                            <label class="text-xs font-bold text-gray-300 mb-2 block uppercase tracking-wider">1. Delivery Email</label>
                            <input type="email" id="co-email" class="sa-input w-full rounded-lg px-4 py-3 text-sm" placeholder="where to send your key?">
                        </div>

                        <div>
                            <label class="text-xs font-bold text-gray-300 mb-2 block uppercase tracking-wider">2. Payment Method</label>
                            <div class="grid grid-cols-2 gap-3">
                                <div onclick="selectGateway('ltc')" id="gw-ltc" class="payment-box selected p-4 rounded-xl flex items-center gap-3">
                                    <i class="fa-brands fa-litecoin-sign text-2xl text-blue-400"></i>
                                    <div><p class="text-sm font-bold">Litecoin</p><p class="text-[10px] text-gray-500">Auto Delivery</p></div>
                                </div>
                                <div onclick="selectGateway('paypal')" id="gw-paypal" class="payment-box p-4 rounded-xl flex items-center gap-3">
                                    <i class="fa-brands fa-paypal text-2xl text-blue-500"></i>
                                    <div><p class="text-sm font-bold">PayPal</p><p class="text-[10px] text-gray-500">F&F Only</p></div>
                                </div>
                                <div onclick="selectGateway('psc')" id="gw-psc" class="payment-box p-4 rounded-xl flex items-center gap-3">
                                    <i class="fa-solid fa-credit-card text-2xl text-blue-300"></i>
                                    <div><p class="text-sm font-bold">Paysafecard</p><p class="text-[10px] text-gray-500">Germany Offline</p></div>
                                </div>
                                <div onclick="selectGateway('amazon')" id="gw-amazon" class="payment-box p-4 rounded-xl flex items-center gap-3">
                                    <i class="fa-brands fa-amazon text-2xl text-orange-400"></i>
                                    <div><p class="text-sm font-bold">Amazon</p><p class="text-[10px] text-gray-500">DE Giftcard</p></div>
                                </div>
                            </div>
                        </div>

                        <div class="bg-[#0a0a0c] border border-gray-800 p-5 rounded-xl">
                            
                            <div id="detail-ltc">
                                <p class="text-xs text-gray-400 mb-3">Send exact amount to this address:</p>
                                <div class="flex items-center justify-between bg-[#121216] border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-purple-500 transition mb-4" onclick="navigator.clipboard.writeText('LTC_ADDR'); alert('Kopiert!')">
                                    <span class="font-mono text-xs text-purple-300 break-all">LTC_ADDR</span>
                                    <i class="fa-regular fa-copy text-gray-500 ml-2"></i>
                                </div>
                                <input type="text" id="co-proof-ltc" class="sa-input w-full rounded-lg px-4 py-2.5 text-sm font-mono" placeholder="Enter Blockchain TXID...">
                            </div>

                            <div id="detail-paypal" class="hidden-view">
                                <p class="text-xs text-gray-400 mb-3">Send via <b>Friends & Family</b> to:</p>
                                <div class="flex items-center justify-between bg-[#121216] border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-blue-500 transition mb-4" onclick="navigator.clipboard.writeText('PP_EMAIL'); alert('Kopiert!')">
                                    <span class="text-xs text-blue-400 font-bold">PP_EMAIL</span>
                                    <i class="fa-regular fa-copy text-gray-500 ml-2"></i>
                                </div>
                                <input type="text" id="co-proof-paypal" class="sa-input w-full rounded-lg px-4 py-2.5 text-sm" placeholder="Your PayPal Email / Name used...">
                            </div>

                            <div id="detail-cards" class="hidden-view">
                                <p class="text-xs text-gray-400 mb-3">Enter your 16-digit code below:</p>
                                <input type="text" id="co-proof-cards" class="sa-input w-full rounded-lg px-4 py-2.5 text-sm font-mono tracking-widest text-center" placeholder="XXXX-XXXX-XXXX-XXXX">
                            </div>

                        </div>

                        <div id="co-error" class="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg text-xs font-medium text-center hidden"></div>
                        <button id="btn-checkout" onclick="processCheckout()" class="sa-btn w-full py-3.5 rounded-xl font-bold text-sm flex justify-center items-center gap-2"><span>Pay & Receive Product</span></button>
                    </div>

                    <div id="co-step-2" class="hidden-view text-center py-8">
                        <div class="w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/20">
                            <i class="fa-solid fa-check text-2xl text-green-500"></i>
                        </div>
                        <h3 class="text-xl font-bold mb-2">Payment Successful</h3>
                        <p class="text-xs text-gray-400 mb-8">Your product key has been generated.</p>
                        
                        <div class="bg-[#0a0a0c] border border-gray-800 p-4 rounded-xl mb-6">
                            <p class="text-[10px] text-gray-500 font-bold uppercase mb-2">License Key</p>
                            <input type="text" id="co-success-key" class="w-full bg-transparent text-center font-mono text-lg text-green-400 outline-none select-all" readonly>
                        </div>
                        <button onclick="window.location.reload()" class="w-full bg-gray-800 hover:bg-gray-700 text-white py-3 rounded-xl text-sm font-bold transition">Close & Go to Dashboard</button>
                    </div>
                </div>
            </div>
        </div>

        <div id="view-admin" class="w-full hidden-view mt-6">
            <div class="flex gap-6">
                <div class="w-64 shrink-0 sa-card p-4 flex flex-col min-h-[600px]">
                    <div class="mb-8 px-4 pt-2">
                        <span class="text-xs font-bold text-gray-500 uppercase tracking-widest">Admin Panel</span>
                        <p class="text-lg font-bold truncate" id="admin-name"></p>
                    </div>
                    <nav class="space-y-1 flex-1">
                        <button onclick="nav('dash')" id="btn-dash" class="w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium bg-gray-800 text-white transition"><i class="fa-solid fa-chart-pie w-5 opacity-70"></i> Overview</button>
                        <button onclick="nav('keys')" id="btn-keys" class="w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-white transition"><i class="fa-solid fa-key w-5 opacity-70"></i> Keys Database</button>
                        <button onclick="nav('team')" id="btn-team" class="w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-white transition"><i class="fa-solid fa-users w-5 opacity-70"></i> Resellers</button>
                    </nav>
                    <button onclick="logout()" class="mt-auto w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium text-red-400 hover:bg-red-500/10 transition"><i class="fa-solid fa-power-off w-5"></i> Logout</button>
                </div>
                <div class="flex-1 sa-card p-8">
                    <div id="dash" class="tab-content active">
                        <h2 class="text-xl font-bold mb-6">Dashboard Overview</h2>
                        <div class="grid grid-cols-3 gap-4 mb-8">
                            <div class="bg-[#0a0a0c] border border-gray-800 p-5 rounded-xl"><p class="text-xs text-gray-400">Total Revenue</p><h3 class="text-2xl font-bold mt-1" id="stat-rev">€0.00</h3></div>
                            <div class="bg-[#0a0a0c] border border-gray-800 p-5 rounded-xl"><p class="text-xs text-gray-400">Orders Today</p><h3 class="text-2xl font-bold mt-1" id="stat-orders">0</h3></div>
                            <div class="bg-[#0a0a0c] border border-gray-800 p-5 rounded-xl"><p class="text-xs text-gray-400">Active Keys</p><h3 class="text-2xl font-bold mt-1" id="stat-keys">0</h3></div>
                        </div>
                    </div>
                    <div id="keys" class="tab-content">
                        <h2 class="text-xl font-bold mb-6">Key Database</h2>
                        <div class="bg-[#0a0a0c] border border-gray-800 rounded-xl overflow-hidden">
                            <table class="w-full text-left text-xs">
                                <thead class="bg-gray-800/50 text-gray-400"><tr><th class="p-3">Key</th><th class="p-3">Type</th><th class="p-3">Creator</th><th class="p-3">Status</th></tr></thead>
                                <tbody id="table-keys" class="divide-y divide-gray-800"></tbody>
                            </table>
                        </div>
                    </div>
                     <div id="team" class="tab-content">
                        <h2 class="text-xl font-bold mb-6">Resellers</h2>
                        <div class="bg-[#0a0a0c] border border-gray-800 rounded-xl overflow-hidden">
                            <table class="w-full text-left text-xs">
                                <thead class="bg-gray-800/50 text-gray-400"><tr><th class="p-3">Username</th><th class="p-3">Password</th><th class="p-3">Keys Gen</th><th class="p-3">Action</th></tr></thead>
                                <tbody id="table-team" class="divide-y divide-gray-800"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div id="view-customer" class="w-full hidden-view mt-6">
            <div class="sa-card p-8 max-w-2xl mx-auto text-center">
                <h2 class="text-2xl font-bold mb-2">Welcome Back</h2>
                <p class="font-mono text-sm text-purple-400 mb-8" id="cust-key-display"></p>
                
                <div class="bg-[#0a0a0c] border border-gray-800 rounded-xl p-6 mb-8 inline-block text-left min-w-[300px]">
                    <p class="text-xs text-gray-500 uppercase font-bold mb-1">Active Plan</p>
                    <h3 class="text-3xl font-bold mb-4" id="cust-prod">Loading...</h3>
                    <div class="flex justify-between text-sm border-t border-gray-800 pt-4">
                        <span class="text-gray-400">Status:</span>
                        <span class="font-bold text-green-400" id="cust-status">Loading</span>
                    </div>
                    <div class="flex justify-between text-sm mt-2">
                        <span class="text-gray-400">Discord ID:</span>
                        <span class="font-mono" id="cust-discord">None</span>
                    </div>
                </div>
                <div><button onclick="logout()" class="text-sm text-gray-500 hover:text-white">Logout</button></div>
            </div>
        </div>

    </main>

    <script>
        // GLOBALS
        let currentGw = 'ltc';
        let selectedProduct = '';
        const gateDetails = ['detail-ltc', 'detail-paypal', 'detail-cards'];
        const gateBtns = ['gw-ltc', 'gw-paypal', 'gw-psc', 'gw-amazon'];

        // UI Logic
        function switchView(v) {
            document.getElementById('view-shop').classList.add('hidden-view');
            document.getElementById('view-auth').classList.add('hidden-view');
            document.getElementById('view-' + v).classList.remove('hidden-view');
            if(v === 'auth') switchAuthTab('customer');
        }

        function switchAuthTab(type) {
            ['customer', 'login', 'register'].forEach(t => {
                document.getElementById('form-' + t).classList.add('hidden-view');
                document.getElementById('tab-btn-' + t).className = "flex-1 py-2 text-sm font-medium rounded-md text-gray-400 hover:text-white transition";
            });
            document.getElementById('form-' + type).classList.remove('hidden-view');
            document.getElementById('tab-btn-' + type).className = "flex-1 py-2 text-sm font-medium rounded-md bg-gray-800 text-white transition";
            document.getElementById('auth-error').classList.add('hidden');
        }

        function selectGateway(gw) {
            currentGw = gw;
            gateBtns.forEach(b => document.getElementById(b).classList.remove('selected'));
            document.getElementById('gw-' + gw).classList.add('selected');
            
            gateDetails.forEach(d => document.getElementById(d).classList.add('hidden-view'));
            if(gw === 'ltc') document.getElementById('detail-ltc').classList.remove('hidden-view');
            else if(gw === 'paypal') document.getElementById('detail-paypal').classList.remove('hidden-view');
            else document.getElementById('detail-cards').classList.remove('hidden-view');
        }

        function openCheckout(id, price) {
            selectedProduct = id;
            let name = id === 'day_1' ? "1 Day Access" : id === 'week_1' ? "1 Week Access" : "Lifetime Access";
            document.getElementById('co-prod-name').innerHTML = `${name} • <span class="text-white font-bold">€${price}</span>`;
            document.getElementById('co-step-1').classList.remove('hidden-view');
            document.getElementById('co-step-2').classList.add('hidden-view');
            document.getElementById('checkout-modal').classList.remove('hidden-view');
        }
        
        function closeCheckout() { document.getElementById('checkout-modal').classList.add('hidden-view'); }

        async function processCheckout() {
            const email = document.getElementById('co-email').value;
            const err = document.getElementById('co-error');
            const btn = document.getElementById('btn-checkout');
            
            if(!email || !email.includes('@')) { err.innerText = "Please enter a valid email."; err.classList.remove('hidden'); return; }
            
            let proof = "";
            if(currentGw === 'ltc') proof = document.getElementById('co-proof-ltc').value;
            else if(currentGw === 'paypal') proof = document.getElementById('co-proof-paypal').value;
            else proof = document.getElementById('co-proof-cards').value;

            if(!proof) { err.innerText = "Please enter payment details (TXID/Email/Code)."; err.classList.remove('hidden'); return; }

            err.classList.add('hidden');
            btn.disabled = true;
            btn.innerHTML = '<span class="loader"></span> Processing...';

            try {
                const res = await fetch('/api/web_buy', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, proof, gateway: currentGw, product: selectedProduct})
                });
                const data = await res.json();
                
                if(data.ok) {
                    document.getElementById('co-success-key').value = data.key;
                    document.getElementById('co-step-1').classList.add('hidden-view');
                    document.getElementById('co-step-2').classList.remove('hidden-view');
                } else {
                    err.innerText = data.error; err.classList.remove('hidden');
                    btn.disabled = false; btn.innerHTML = "Try Again";
                }
            } catch(e) { err.innerText = "Network error."; err.classList.remove('hidden'); btn.disabled = false; btn.innerHTML = "Try Again"; }
        }

        // --- Auth Backend Integration ---
        async function apiCall(endpoint, data) {
            const t = localStorage.getItem('v_token');
            const h = {'Content-Type': 'application/json'};
            if (t) h['Authorization'] = t;
            const res = await fetch(endpoint, { method: 'POST', headers: h, body: JSON.stringify(data) });
            if (res.status === 401 && !endpoint.includes('login') && !endpoint.includes('register')) { logout(); throw new Error('Unauth'); }
            return res;
        }
        
        function showError(msg) { const e = document.getElementById('auth-error'); e.innerText = msg; e.classList.remove('hidden'); }
        
        async function login() {
            const u = document.getElementById('l-user').value, p = document.getElementById('l-pass').value;
            if (!u || !p) return showError("Fill all fields.");
            const res = await apiCall('/api/login', {user: u, pass: p});
            if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else showError("Invalid credentials.");
        }
        async function customerLogin() {
            const k = document.getElementById('c-key').value;
            if (!k) return showError("Enter a key.");
            const res = await apiCall('/api/customer_login', {key: k});
            if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else { const e=await res.json(); showError(e.error||"Invalid Key"); }
        }
        async function register() {
            const u = document.getElementById('r-user').value, p = document.getElementById('r-pass').value, k = document.getElementById('r-key').value;
            if (!u || !p || !k) return showError("Fill all fields.");
            const res = await apiCall('/api/register', {user: u, pass: p, key: k});
            if (res.ok) { const d = await res.json(); localStorage.setItem('v_token', d.token); initApp(d.role, d.user); } else { const e=await res.json(); showError(e.error||"Error."); }
        }
        function logout() { localStorage.removeItem('v_token'); location.reload(); }

        window.onload = async () => {
            const t = localStorage.getItem('v_token');
            if (t) {
                try {
                    const res = await fetch('/api/verify', { method: 'POST', headers: {'Authorization': t, 'Content-Type': 'application/json'} });
                    if (res.ok) { const d = await res.json(); initApp(d.role, d.user); } 
                } catch(e) {}
            }
        };

        function initApp(role, name) {
            document.getElementById('view-shop').classList.add('hidden-view');
            document.getElementById('view-auth').classList.add('hidden-view');
            
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
            ['dash','keys','team'].forEach(id => {
                document.getElementById('btn-'+id).className = "w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-white transition";
            });
            document.getElementById('btn-'+tabId).className = "w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium bg-gray-800 text-white transition";
            if (tabId === 'dash') loadDashboard();
            if (tabId === 'keys') loadKeys();
            if (tabId === 'team') loadTeam();
        }

        async function loadDiscordStats() { try { const r=await apiCall('/api/discord_stats',{}); const d=await r.json(); document.getElementById('stat-orders').innerText=d.open_tickets;}catch(e){} }
        async function loadDashboard() { try { const r=await apiCall('/api/stats',{}); const d=await r.json(); document.getElementById('stat-rev').innerText='€'+d.total_revenue.toFixed(2); document.getElementById('stat-keys').innerText=d.active_keys; }catch(e){} }
        async function loadKeys() { try { const r=await apiCall('/api/keys',{}); const d=await r.json(); const t=document.getElementById('table-keys'); if(Object.keys(d).length===0) t.innerHTML='<tr><td colspan="4" class="p-4 text-center text-gray-500">Empty</td></tr>'; else t.innerHTML=Object.entries(d).reverse().map(([k,v])=>`<tr><td class="p-3 font-mono text-purple-400">${k}</td><td class="p-3">${v.type}</td><td class="p-3">${v.created_by||'Sys'}</td><td class="p-3">${v.used?'Used':'Active'}</td></tr>`).join(''); }catch(e){} }
        async function loadTeam() { try { const r=await apiCall('/api/team',{}); const d=await r.json(); const t=document.getElementById('table-team'); if(d.length===0) t.innerHTML='<tr><td colspan="4" class="p-4 text-center text-gray-500">Empty</td></tr>'; else t.innerHTML=d.map(u=>`<tr><td class="p-3">${u.username}</td><td class="p-3 font-mono text-gray-500">***</td><td class="p-3">${u.keys_generated}</td><td class="p-3"><button onclick="deleteReseller('${u.username}')" class="text-red-400">Del</button></td></tr>`).join(''); }catch(e){} }
        async function deleteReseller(u) { if(confirm(`Del ${u}?`)){await apiCall('/api/team/delete',{username:u}); loadTeam();} }
        async function loadCustomerData() { try { const r=await apiCall('/api/customer_data',{}); const d=await r.json(); document.getElementById('cust-prod').innerText=d.type; document.getElementById('cust-status').innerText=d.status; document.getElementById('cust-discord').innerText=d.used_by; }catch(e){} }

    </script>
</body>
</html>
""".replace("LOGO_URL_PLACEHOLDER", SAFE_WEBSITE_LOGO_URL).replace("LTC_ADDR", LITECOIN_ADDRESS).replace("PP_EMAIL", PAYPAL_EMAIL)

# =========================================================
# WEB SERVER LOGIC
# =========================================================
async def handle_index(request): return web.Response(text=WEB_HTML, content_type='text/html')

async def api_web_buy(request):
    try:
        data = await request.json()
        email = data.get("email")
        proof = data.get("proof")
        gateway = data.get("gateway")
        ptype = data.get("product")
        
        if not email or not proof or ptype not in PRODUCTS:
            return web.json_response({"ok": False, "error": "Missing data."})
        
        # Payment Verifikation
        if gateway == "ltc":
            ok, reason = await verify_ltc_payment(proof) # Proof = TXID
            if not ok: return web.json_response({"ok": False, "error": reason})
        else:
            # Für PayPal, Paysafecard und Amazon simulieren wir eine erfolgreiche Prüfung 
            # (In echt bräuchte man hierfür die PayPal API oder manuelle Prüfung)
            pass

        # Generate Key
        prefix = PRODUCTS[ptype]["key_prefix"]
        key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
        keys_db[key] = {
            "type": ptype, "used": False, "used_by": None, 
            "created_at": iso_now(), "creator": "SellAuth_Auto", "revoked": False
        }
        save_json(KEYS_FILE, keys_db)
        
        # Create Invoice
        inv_id = build_invoice_id()
        invoices_db[inv_id] = {
            "buyer_id": email, "product_type": ptype, "payment_key": gateway,
            "key": key, "ticket_id": "WEB", "created_at": iso_now(), "final_price_eur": PRODUCTS[ptype]["price_eur"]
        }
        save_json(INVOICES_FILE, invoices_db)

        # Send Mail
        send_delivery_email(email, PRODUCTS[ptype]["label"], key)
        log_activity(f"Web Order via {gateway}: {ptype}", "SellAuth")
        
        return web.json_response({"ok": True, "key": key})
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Error: {str(e)}"})

# [Standard Auth Routes aus deinem alten Skript, kurz gehalten für Übersicht]
def get_user_from_token(r): return web_sessions.get(r.headers.get("Authorization"))
async def api_register(r):
    d = await r.json(); u, p, k = d.get("user"), d.get("pass"), d.get("key", "").upper()
    if not u or not p or not k: return web.json_response({"error": "Empty fields"}, status=400)
    if u in users_db: return web.json_response({"error": "Username taken"}, status=400)
    if k not in webkeys_db or webkeys_db[k].get("used"): return web.json_response({"error": "Invalid or used Invite Key. (Admin: run /nuke_database and generate new key if stuck)"}, status=400)
    role = webkeys_db[k]["role"]; users_db[u] = {"pass": p, "role": role}; webkeys_db[k]["used"] = True
    save_json(USERS_FILE, users_db); save_json(WEBKEYS_FILE, webkeys_db)
    token = str(uuid.uuid4()); web_sessions[token] = {"user": u, "role": role}; save_json(SESSIONS_FILE, web_sessions)
    return web.json_response({"ok": True, "token": token, "role": role, "user": u})
async def api_login(r):
    d = await r.json(); u, p = d.get("user"), d.get("pass")
    if u in users_db and users_db[u]["pass"] == p:
        token = str(uuid.uuid4()); role = users_db[u]["role"]; web_sessions[token] = {"user": u, "role": role}; save_json(SESSIONS_FILE, web_sessions)
        return web.json_response({"ok": True, "token": token, "role": role, "user": u})
    return web.Response(status=401)
async def api_customer_login(r):
    d = await r.json(); k = d.get("key", "").upper()
    if k in keys_db:
        token = str(uuid.uuid4()); web_sessions[token] = {"user": k, "role": "customer"}; save_json(SESSIONS_FILE, web_sessions)
        return web.json_response({"ok": True, "token": token, "role": "customer", "user": k})
    return web.json_response({"error": "Key not found"}, status=400)
async def api_verify(r):
    u = get_user_from_token(r)
    return web.json_response({"ok": True, "role": u["role"], "user": u["user"]}) if u else web.Response(status=401)
async def api_stats(r):
    total_rev = sum(float(data.get("final_price_eur", 0)) for data in invoices_db.values())
    active_k = sum(1 for v in keys_db.values() if not v.get("used"))
    return web.json_response({"total_revenue": total_rev, "buyers_today": 0, "active_keys": active_k, "chart_labels": [], "chart_data": []})
async def api_discord_stats(r): return web.json_response({"members": 0, "open_tickets": len(ticket_data)})
async def api_keys(r): return web.json_response(keys_db)
async def api_team(r): return web.json_response([{"username": k, "password": v["pass"], "keys_generated": 0} for k,v in users_db.items() if v.get("role")=="reseller"])
async def api_customer_data(r):
    u = get_user_from_token(r)
    if not u or u.get("role") != "customer": return web.Response(status=401)
    k = keys_db.get(u["user"], {})
    return web.json_response({"type": PRODUCTS.get(k.get("type", ""), {}).get("label", "Unknown"), "status": "Banned" if k.get("revoked") else ("Active" if k.get("used") else "Unused"), "created_at": k.get("created_at", ""), "used_by": k.get("used_by", "None")})

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
    app.router.add_post('/api/keys', api_keys)
    app.router.add_post('/api/team', api_team)
    app.router.add_post('/api/customer_data', api_customer_data)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🚀 Web Store & API online on Port {port}!")

# =========================================================
# BOT CORE & COMMANDS
# =========================================================
class ValeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.loop.create_task(start_web_server())

bot = ValeBot()

@bot.tree.command(name="nuke_database", description="Löscht alle Datenbanken (Admin Only)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def nuke_database(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    global keys_db, ticket_data, users_db, webkeys_db, web_sessions
    keys_db, ticket_data, users_db, webkeys_db, web_sessions = {}, {}, {}, {}, {}
    save_json(KEYS_FILE, {}); save_json(TICKETS_FILE, {}); save_json(USERS_FILE, {}); save_json(WEBKEYS_FILE, {}); save_json(SESSIONS_FILE, {})
    await interaction.response.send_message("Database Nuked! Logins wurden resettet. Generiere neuen Admin Key mit /gen_admin_key", ephemeral=True)

@bot.tree.command(name="gen_admin_key", description="Generiert einen ADMIN-Einladungs-Key für die Website")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gen_admin_key(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    new_key = f"VALE-ADMIN-{random_block(6)}"
    webkeys_db[new_key] = {"role": "admin", "used": False, "created_by": str(interaction.user.name), "created_at": iso_now()}
    save_json(WEBKEYS_FILE, webkeys_db)
    await interaction.response.send_message(f"Admin Invite Key generiert: `{new_key}`", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
