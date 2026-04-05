import os
import re
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import web
import discord
from discord.ext import commands, tasks
from discord import app_commands

# =========================================================
# ENV
# =========================================================
TOKEN = os.getenv("TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

if not TOKEN: raise ValueError("TOKEN is missing. Add it in Railway Variables.")
if not GUILD_ID_RAW: raise ValueError("GUILD_ID is missing. Add it in Railway Variables.")

try: GUILD_ID = int(GUILD_ID_RAW)
except ValueError: raise ValueError("GUILD_ID must be a valid integer.")

# =========================================================
# CONFIG
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

REDEEM_ROLE_ID = 1490321899266506913
RESELLER_ROLE_ID = 1490335130890534923

SERVER_NAME = "Vale Generator"
WELCOME_THUMBNAIL_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png?ex=69d3cfcd&is=69d27e4d&hm=a1683879f331ba73307cf9ad0e27cac43f02b2de553abd4e8f9e86dcadec0a48&=&format=webp&quality=lossless&width=548&height=548"
WELCOME_BANNER_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371157432467577/analyst.jpg?ex=69d3cfcd&is=69d27e4d&hm=168f0fdba0376421e2a18ad6f421112517035adb2f0711d5c658521f9320c8b6&=&format=webp&width=548&height=548"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371157432467577/analyst.jpg?ex=69d3cfcd&is=69d27e4d&hm=168f0fdba0376421e2a18ad6f421112517035adb2f0711d5c658521f9320c8b6&=&format=webp&width=548&height=548"

PAYPAL_EMAIL = "hydrasupfivem@gmail.com"
LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"
ETHEREUM_ADDRESS = "0x6Ba2afdA7e61817f9c27f98ffAfe9051F9ad8167"
SOLANA_ADDRESS = "DnzXgySsPnSdEKsMJub21dBjM6bcT2jtic73VeutN3p4"

LTC_MIN_CONFIRMATIONS = 1
EXPIRY_REMINDER_HOURS = 12

# =========================================================
# COLORS & FILES
# =========================================================
COLOR_MAIN = 0x6D5DF6; COLOR_SUPPORT = 0x3BA7FF; COLOR_BUY = 0x57F287
COLOR_WARN = 0xFEE75C; COLOR_DENY = 0xED4245; COLOR_LOG = 0x2B2D31
COLOR_SUCCESS = 0x57F287; COLOR_INFO = 0x5865F2; COLOR_PENDING = 0xFAA61A
COLOR_ADMIN = 0x9B59B6; COLOR_WELCOME = 0xDD0000

KEYS_FILE = "keys.json"
REDEEMED_FILE = "redeemed.json"
USED_TXIDS_FILE = "used_txids.json"
USED_PAYSAFE_FILE = "used_paysafecodes.json"
USED_AMAZON_FILE = "used_amazoncodes.json"
BLACKLIST_FILE = "blacklist.json"
INVOICES_FILE = "invoices.json"
PROMOS_FILE = "promos.json"

# =========================================================
# PRODUCTS & PAYMENTS
# =========================================================
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
    "amazoncard": {"label": "Amazon Card", "emoji": "🎁"},
}

# =========================================================
# BOT SETUP & DATABASES
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

ticket_data = {}; forwarded_paysafe_codes = {}; forwarded_amazon_codes = {}
keys_db = {}; redeemed_db = {}; used_txids_db = {}; used_paysafe_db = {}
used_amazon_db = {}; blacklist_db = {}; invoices_db = {}; promos_db = {}

def load_json(path: str, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f: json.dump(default, f, indent=4)
        return default
    with open(path, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except json.JSONDecodeError: return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

# =========================================================
# 🌍 HIGH-END WEB DASHBOARD & API
# =========================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="de" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vale Gen | Pro Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #0f111a; }
        .glass-panel { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.05); }
        .glow-text { text-shadow: 0 0 10px rgba(168, 85, 247, 0.5); }
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="text-gray-200 flex h-screen overflow-hidden">

    <aside class="w-64 glass-panel border-r flex flex-col justify-between hidden md:flex z-10">
        <div>
            <div class="h-20 flex items-center justify-center border-b border-gray-700/50">
                <h1 class="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-indigo-500 glow-text">
                    <i class="fa-solid fa-bolt mr-2 text-purple-400"></i>VALE GEN
                </h1>
            </div>
            <nav class="p-4 space-y-2 mt-4">
                <button onclick="switchTab('dashboard')" id="btn-dashboard" class="w-full flex items-center text-left py-3 px-4 rounded-xl text-purple-400 bg-purple-500/10 font-semibold transition">
                    <i class="fa-solid fa-chart-pie w-6"></i> Overview
                </button>
                <button onclick="switchTab('keys')" id="btn-keys" class="w-full flex items-center text-left py-3 px-4 rounded-xl text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition">
                    <i class="fa-solid fa-key w-6"></i> Key Manager
                </button>
                <button onclick="switchTab('blacklist')" id="btn-blacklist" class="w-full flex items-center text-left py-3 px-4 rounded-xl text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition">
                    <i class="fa-solid fa-ban w-6"></i> Blacklist
                </button>
            </nav>
        </div>
        <div class="p-6 border-t border-gray-700/50 text-center text-xs text-gray-500">
            <span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span> System Online</span>
        </div>
    </aside>

    <main class="flex-1 flex flex-col h-screen overflow-y-auto relative">
        <div class="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-purple-900/20 to-transparent pointer-events-none"></div>
        
        <header class="h-20 flex items-center justify-between px-8 z-10">
            <h2 id="page-title" class="text-2xl font-bold text-white">Overview</h2>
            <div class="flex items-center gap-4">
                <div class="bg-gray-800 rounded-full py-1 px-4 text-sm border border-gray-700"><i class="fa-solid fa-user-shield text-indigo-400 mr-2"></i>Admin Mode</div>
            </div>
        </header>

        <div class="p-8 z-10">
            
            <div id="tab-dashboard" class="tab-content active">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <div class="glass-panel p-6 rounded-2xl relative overflow-hidden group hover:border-purple-500/50 transition">
                        <div class="absolute -right-4 -top-4 text-purple-500/10 text-7xl"><i class="fa-solid fa-euro-sign"></i></div>
                        <p class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">Total Revenue</p>
                        <h3 class="text-4xl font-extrabold text-white" id="stat-revenue">0.00€</h3>
                    </div>
                    <div class="glass-panel p-6 rounded-2xl relative overflow-hidden group hover:border-blue-500/50 transition">
                        <div class="absolute -right-4 -top-4 text-blue-500/10 text-7xl"><i class="fa-solid fa-users"></i></div>
                        <p class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">Buyers Today</p>
                        <h3 class="text-4xl font-extrabold text-white" id="stat-buyers">0</h3>
                    </div>
                    <div class="glass-panel p-6 rounded-2xl relative overflow-hidden group hover:border-emerald-500/50 transition">
                        <div class="absolute -right-4 -top-4 text-emerald-500/10 text-7xl"><i class="fa-solid fa-key"></i></div>
                        <p class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">Generated Keys</p>
                        <h3 class="text-4xl font-extrabold text-white" id="stat-keys">0</h3>
                    </div>
                </div>
                
                <h3 class="text-xl font-bold text-white mb-4"><i class="fa-solid fa-receipt mr-2 text-indigo-400"></i>Recent Orders</h3>
                <div class="glass-panel rounded-2xl overflow-hidden">
                    <table class="w-full text-left text-sm whitespace-nowrap">
                        <thead class="bg-gray-800/50 border-b border-gray-700/50">
                            <tr><th class="px-6 py-4 font-semibold text-gray-300">Invoice ID</th><th class="px-6 py-4 font-semibold text-gray-300">Buyer ID</th><th class="px-6 py-4 font-semibold text-gray-300">Product</th><th class="px-6 py-4 font-semibold text-gray-300">Price</th><th class="px-6 py-4 font-semibold text-gray-300">Method</th></tr>
                        </thead>
                        <tbody id="table-invoices" class="divide-y divide-gray-800/50">
                            <tr><td colspan="5" class="px-6 py-8 text-center text-gray-500">Loading data...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="tab-keys" class="tab-content">
                <div class="glass-panel rounded-2xl overflow-hidden shadow-2xl">
                    <div class="p-6 border-b border-gray-700/50 flex justify-between items-center bg-gray-800/30">
                        <h3 class="text-lg font-bold text-white"><i class="fa-solid fa-database mr-2 text-emerald-400"></i>Key Database</h3>
                        <span class="text-xs font-semibold px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">All Time</span>
                    </div>
                    <div class="overflow-x-auto max-h-[600px]">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-gray-800/50 border-b border-gray-700/50 sticky top-0 backdrop-blur-md">
                                <tr><th class="px-6 py-4 text-gray-300">Key</th><th class="px-6 py-4 text-gray-300">Type</th><th class="px-6 py-4 text-gray-300">Status</th><th class="px-6 py-4 text-gray-300">Bound To</th></tr>
                            </thead>
                            <tbody id="table-keys" class="divide-y divide-gray-800/50"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div id="tab-blacklist" class="tab-content">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div class="lg:col-span-1">
                        <div class="glass-panel p-6 rounded-2xl relative overflow-hidden border-t-4 border-t-red-500">
                            <h3 class="text-lg font-bold text-white mb-4"><i class="fa-solid fa-user-plus mr-2 text-red-400"></i>Add to Blacklist</h3>
                            <div class="space-y-4">
                                <div><label class="block text-xs font-bold text-gray-400 mb-1 uppercase">Discord User ID</label><input type="text" id="bl-id" class="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-red-500 transition" placeholder="z.B. 123456789"></div>
                                <div><label class="block text-xs font-bold text-gray-400 mb-1 uppercase">Reason</label><input type="text" id="bl-reason" class="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-red-500 transition" placeholder="z.B. Scam attempt"></div>
                                <button onclick="addBlacklist()" class="w-full bg-red-600 hover:bg-red-500 text-white font-bold py-2 rounded-lg transition shadow-[0_0_15px_rgba(220,38,38,0.4)] mt-2">Ban User</button>
                            </div>
                        </div>
                    </div>
                    <div class="lg:col-span-2">
                        <div class="glass-panel rounded-2xl overflow-hidden h-full flex flex-col">
                            <div class="p-6 border-b border-gray-700/50 bg-gray-800/30">
                                <h3 class="text-lg font-bold text-white"><i class="fa-solid fa-list mr-2 text-red-400"></i>Banned Users</h3>
                            </div>
                            <div class="flex-1 overflow-x-auto p-4">
                                <table class="w-full text-left text-sm">
                                    <thead class="text-gray-400 border-b border-gray-700/50"><tr><th class="pb-3 px-4">User ID</th><th class="pb-3 px-4">Reason</th><th class="pb-3 px-4 text-right">Action</th></tr></thead>
                                    <tbody id="table-blacklist" class="divide-y divide-gray-800/50"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </div>
    </main>

    <script>
        const API = {
            async getStats() { const r = await fetch('/api/stats'); return await r.json(); },
            async getKeys() { const r = await fetch('/api/keys'); return await r.json(); },
            async getBlacklist() { const r = await fetch('/api/blacklist'); return await r.json(); },
            async removeBlacklist(uid) { await fetch('/api/blacklist/remove', {method:'POST', body:JSON.stringify({user_id:uid})}); },
            async addBlacklist(uid, reason) { await fetch('/api/blacklist/add', {method:'POST', body:JSON.stringify({user_id:uid, reason:reason})}); }
        };

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            
            document.querySelectorAll('aside button').forEach(el => { el.classList.remove('text-purple-400', 'bg-purple-500/10'); el.classList.add('text-gray-400'); });
            const btn = document.getElementById('btn-' + tabId);
            btn.classList.add('text-purple-400', 'bg-purple-500/10'); btn.classList.remove('text-gray-400');
            
            const titles = {'dashboard': 'Overview', 'keys': 'Key Manager', 'blacklist': 'Blacklist Management'};
            document.getElementById('page-title').innerText = titles[tabId];
            
            if(tabId === 'dashboard') loadStats();
            else if(tabId === 'keys') loadKeys();
            else if(tabId === 'blacklist') loadBlacklist();
        }

        async function loadStats() {
            const data = await API.getStats();
            document.getElementById('stat-revenue').innerText = data.total_revenue.toFixed(2) + '€';
            document.getElementById('stat-buyers').innerText = data.buyers_today;
            document.getElementById('stat-keys').innerText = data.total_keys;
            
            const tb = document.getElementById('table-invoices');
            if(data.recent_invoices.length === 0) tb.innerHTML = '<tr><td colspan="5" class="px-6 py-4 text-center text-gray-500">No orders yet</td></tr>';
            else {
                tb.innerHTML = data.recent_invoices.map(inv => `
                    <tr class="hover:bg-gray-800/30 transition">
                        <td class="px-6 py-4 font-mono text-indigo-400">${inv.id}</td>
                        <td class="px-6 py-4 text-gray-300">${inv.buyer}</td>
                        <td class="px-6 py-4"><span class="bg-gray-800 border border-gray-700 px-2 py-1 rounded text-xs">${inv.product}</span></td>
                        <td class="px-6 py-4 text-emerald-400 font-bold">${inv.price}€</td>
                        <td class="px-6 py-4 text-gray-400">${inv.method}</td>
                    </tr>
                `).join('');
            }
        }

        async function loadKeys() {
            const data = await API.getKeys();
            const tb = document.getElementById('table-keys');
            if(Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500">No keys generated</td></tr>';
            tb.innerHTML = Object.entries(data).reverse().map(([key, info]) => {
                const badge = info.used 
                    ? '<span class="px-2 py-1 rounded bg-red-500/10 text-red-400 text-xs border border-red-500/20">Used</span>'
                    : '<span class="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">Active</span>';
                return `<tr class="hover:bg-gray-800/30 transition"><td class="px-6 py-4 font-mono text-purple-400">${key}</td><td class="px-6 py-4">${info.type}</td><td class="px-6 py-4">${badge}</td><td class="px-6 py-4 text-gray-400">${info.bound_user_id || '-'}</td></tr>`;
            }).join('');
        }

        async function loadBlacklist() {
            const data = await API.getBlacklist();
            const tb = document.getElementById('table-blacklist');
            if(Object.keys(data).length === 0) return tb.innerHTML = '<tr><td colspan="3" class="px-4 py-8 text-center text-gray-500">Blacklist ist leer ✨</td></tr>';
            tb.innerHTML = Object.entries(data).map(([uid, info]) => `
                <tr class="hover:bg-gray-800/30 transition border-b border-gray-800/50">
                    <td class="px-4 py-4 font-mono text-gray-300">${uid}</td>
                    <td class="px-4 py-4 text-gray-400">${info.reason}</td>
                    <td class="px-4 py-4 text-right"><button onclick="rmBlacklist('${uid}')" class="text-xs bg-gray-800 hover:bg-red-600 border border-gray-700 hover:border-red-500 text-gray-300 hover:text-white py-1 px-3 rounded transition shadow-lg"><i class="fa-solid fa-trash mr-1"></i>Remove</button></td>
                </tr>
            `).join('');
        }

        async function addBlacklist() {
            const uid = document.getElementById('bl-id').value;
            const rsn = document.getElementById('bl-reason').value || "Banned via Web Panel";
            if(!uid) return alert('Bitte Discord ID eingeben!');
            document.getElementById('bl-id').value = ''; document.getElementById('bl-reason').value = '';
            await API.addBlacklist(uid, rsn); loadBlacklist();
        }

        async function rmBlacklist(uid) {
            if(!confirm('Nutzer entbannen?')) return;
            await API.removeBlacklist(uid); loadBlacklist();
        }

        // Init
        switchTab('dashboard');
    </script>
</body>
</html>
"""

async def handle_dashboard(request): return web.Response(text=DASHBOARD_HTML, content_type='text/html')
async def api_get_blacklist(request): return web.json_response(blacklist_db)
async def api_get_keys(request): return web.json_response(keys_db)
async def api_get_stats(request):
    now = now_utc(); today_buyers = 0; total_rev = 0.0; recent = []
    for inv_id, data in list(invoices_db.items())[-10:]:
        recent.append({"id": inv_id, "buyer": data["buyer_id"], "product": data["product_type"], "price": data.get("final_price_eur", 0), "method": data["payment_key"]})
        total_rev += float(data.get("final_price_eur", 0))
        try:
            if datetime.fromisoformat(data["created_at"]).date() == now.date(): today_buyers += 1
        except: pass
    return web.json_response({"total_revenue": total_rev, "buyers_today": today_buyers, "total_keys": len(keys_db), "recent_invoices": recent[::-1]})

async def api_remove_blacklist(request):
    uid = (await request.json()).get("user_id")
    if uid in blacklist_db: del blacklist_db[uid]; save_json(BLACKLIST_FILE, blacklist_db)
    return web.json_response({"status": "success"})

async def api_add_blacklist(request):
    data = await request.json()
    uid = data.get("user_id"); reason = data.get("reason", "Web Panel Ban")
    if uid:
        blacklist_db[uid] = {"reason": reason, "added_by": "Web Admin", "added_at": iso_now()}
        save_json(BLACKLIST_FILE, blacklist_db)
    return web.json_response({"status": "success"})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_dashboard)
    app.router.add_get('/api/stats', api_get_stats); app.router.add_get('/api/keys', api_get_keys); app.router.add_get('/api/blacklist', api_get_blacklist)
    app.router.add_post('/api/blacklist/remove', api_remove_blacklist); app.router.add_post('/api/blacklist/add', api_add_blacklist)
    runner = web.AppRunner(app); await runner.setup()
    port = int(os.environ.get("PORT", 8080)); site = web.TCPSite(runner, '0.0.0.0', port); await site.start()

# =========================================================
# HELPERS
# =========================================================
def now_utc() -> datetime: return datetime.now(timezone.utc)
def iso_now() -> str: return now_utc().isoformat()
def premium_divider() -> str: return "━━━━━━━━━━━━━━━━━━━━━━━━"
def short_txid(txid: str) -> str: return txid if len(txid) < 20 else f"{txid[:14]}...{txid[-14:]}"
def random_block(length=4) -> str: return uuid.uuid4().hex[:length].upper()
def is_blacklisted(user_id: int) -> bool: return str(user_id) in blacklist_db

def format_expiry(expires_at: str | None) -> str:
    if not expires_at: return "Never"
    try: return f"<t:{int(datetime.fromisoformat(expires_at).timestamp())}:F>"
    except: return str(expires_at)

def parse_duration_string(duration_text: str) -> timedelta | None:
    txt = duration_text.strip().lower()
    match = re.fullmatch(r"(\d+)([dhw])", txt)
    if not match: return None
    v, u = int(match.group(1)), match.group(2)
    return timedelta(days=v) if u == "d" else timedelta(hours=v) if u == "h" else timedelta(weeks=v)

def build_invoice_id() -> str: return f"GEN-{uuid.uuid4().hex[:10].upper()}"

def is_reseller(member: discord.Member | None) -> bool:
    return member and any(role.id == RESELLER_ROLE_ID for role in member.roles)

def get_price(product_key: str, member: discord.Member | None = None, promo_discount: int = 0) -> float:
    base_price = PRODUCTS[product_key]["price_eur"]
    if is_reseller(member): base_price = round(base_price * 0.5, 2)
    if promo_discount > 0: base_price = round(base_price * (1 - (promo_discount / 100.0)), 2)
    return float(base_price)

def format_price(value: float) -> str: return str(int(value)) if float(value).is_integer() else f"{value:.2f}"

async def dm_user_safe(user: discord.abc.User, content: str = None, embed: discord.Embed = None):
    try: await user.send(content=content, embed=embed)
    except: pass

def generate_key(product_type: str, ticket_id: int | None = None) -> str:
    prefix = PRODUCTS[product_type]["key_prefix"]
    while True:
        key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
        if key not in keys_db:
            keys_db[key] = {"type": product_type, "used": False, "used_by": None, "bound_user_id": None, "created_at": iso_now(), "redeemed_at": None, "approved_in_ticket": ticket_id}
            save_json(KEYS_FILE, keys_db)
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
        if expected_address in output.get("addresses", []):
            found = True; total_received += int(output.get("value", 0))
    return found, total_received

async def fetch_ltc_tx(txid: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}", timeout=20) as resp:
            if resp.status != 200: return None, f"API returned {resp.status}"
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

def find_user_latest_key(user_id: int):
    user_id = str(user_id); latest_key = None; latest_created = None
    for key, data in keys_db.items():
        if str(data.get("bound_user_id")) == user_id or str(data.get("used_by")) == user_id:
            if latest_created is None or (data.get("created_at") and data["created_at"] > latest_created):
                latest_created = data["created_at"]; latest_key = (key, data)
    return latest_key

# =========================================================
# LOGGING & EMBEDS
# =========================================================
async def send_log(guild: discord.Guild, title: str, description: str, color: int = COLOR_LOG):
    ch = guild.get_channel(REVIEW_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel): await ch.send(embed=discord.Embed(title=title, description=description, color=color))

def panel_embed() -> discord.Embed:
    embed = discord.Embed(title="✦ VALE GEN TICKET CENTER ✦", description=f"{premium_divider()}\n**Open a private ticket below**\n\n💠 **Support**\n> Help, questions, issues\n\n🛒 **Buy**\n> Orders, payments, purchase setup\n\n{premium_divider()}\n**Fast • Private • Premium**", color=COLOR_MAIN)
    embed.set_image(url=PANEL_IMAGE_URL); embed.set_footer(text="Only one open ticket per user.")
    return embed

def build_redeem_panel_embed() -> discord.Embed: return discord.Embed(title="🎟️ VALE GEN REDEEM CENTER", description=f"{premium_divider()}\nClick the button below to redeem your key.\n\n✅ Supported:\n• 1 Day\n• 1 Week\n• Lifetime\n\nAfter redeeming, you receive your access role automatically.\n{premium_divider()}", color=COLOR_MAIN)
def support_ticket_embed(user: discord.Member) -> discord.Embed: return discord.Embed(title="💠 Support Ticket Opened", description=f"{premium_divider()}\nWelcome {user.mention}\n\nPlease send:\n• what the issue is\n• what product/service is affected\n• screenshots if needed\n{premium_divider()}", color=COLOR_SUPPORT).set_footer(text=f"Ticket owner: {user}")
def buy_ticket_embed(user: discord.Member) -> discord.Embed: return discord.Embed(title="🛒 Buy Ticket Opened", description=f"{premium_divider()}\nWelcome {user.mention}\n\n**Step 1** → Choose product\n**Step 2** → Choose payment method\n**Step 3** → Follow payment instructions\n{premium_divider()}", color=COLOR_BUY).set_footer(text=f"Ticket owner: {user}")

def build_order_summary(product_key: str, payment_key: str, user: discord.Member, ltc_price_eur: float | None = None) -> discord.Embed:
    product = PRODUCTS[product_key]; payment = PAYMENTS[payment_key]; price = get_price(product_key, user)
    price_header = f"💶 **Price:** {format_price(price)}€"
    if is_reseller(user): price_header += " (**Reseller 50% OFF**)"

    if payment_key == "paypal": extra = f"## 💸 PayPal Payment\n**Send payment to:**\n`{PAYPAL_EMAIL}`\n\n**After payment:**\n• Send screenshot / proof in this ticket\n• Click **Payment Sent**"
    elif payment_key == "litecoin":
        extra = f"## 🪙 Litecoin Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{LITECOIN_ADDRESS}`\n\n"
        if ltc_price_eur and ltc_price_eur > 0: extra += f"**Approx LTC amount:** `{price / ltc_price_eur:.6f} LTC`\n**Market rate:** `{ltc_price_eur:.2f} EUR/LTC`\n\n"
        extra += "**After payment:**\n• Click **Submit TXID**\n• Paste your TXID in the popup\n• Bot checks it automatically"
    elif payment_key == "ethereum": extra = f"## 🔷 Ethereum (ERC20) Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{ETHEREUM_ADDRESS}`\n\n**After payment:**\n• Click **Submit Crypto TXID**"
    elif payment_key == "solana": extra = f"## 🟣 Solana Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{SOLANA_ADDRESS}`\n\n**After payment:**\n• Click **Submit Crypto TXID**"
    elif payment_key == "paysafecard": extra = f"## 💳 Paysafecard Payment\n**Main price:** `{format_price(price)}€`\n\n**After buying your code:**\n• Click **Submit Paysafecard Code**"
    else: extra = f"## 🎁 Amazon Card Payment\n**Main price:** `{format_price(price)}€`\n**Send to address:**\n`{LITECOIN_ADDRESS}` (LTC Wallet for Amazon Card Trading)\n\n**After buying your Amazon card:**\n• Click **Submit Amazon Code**"

    return discord.Embed(title="✦ ORDER SETUP COMPLETE ✦", description=f"{premium_divider()}\n{user.mention}\n\n📦 **Product:** {product['label']}\n{price_header}\n{payment['emoji']} **Method:** {payment['label']}\n\n{extra}\n{premium_divider()}", color=COLOR_MAIN)

def build_ltc_result_embed(txid: str, found_addr: bool, confirmations: int, total_received_ltc: float) -> discord.Embed:
    status = "✅ VERIFIED" if found_addr and confirmations >= LTC_MIN_CONFIRMATIONS else "🟠 PENDING CONFIRMATIONS" if found_addr else "❌ ADDRESS NOT MATCHED"
    color = COLOR_SUCCESS if status.startswith("✅") else COLOR_PENDING if status.startswith("🟠") else COLOR_DENY
    embed = discord.Embed(title="🪙 Litecoin TXID Result", description=f"{premium_divider()}\n**Status:** {status}\n{premium_divider()}", color=color)
    embed.add_field(name="TXID", value=f"`{short_txid(txid)}`", inline=False); embed.add_field(name="Address Match", value="Yes" if found_addr else "No", inline=True); embed.add_field(name="Confirmations", value=str(confirmations), inline=True); embed.add_field(name="Received", value=f"{total_received_ltc:.8f} LTC", inline=True)
    return embed

def build_invoice_embed(invoice_id: str, buyer: discord.Member, product_type: str, payment_key: str, final_price_eur: float | None = None, reseller_discount: bool = False) -> discord.Embed:
    price = final_price_eur if final_price_eur is not None else get_price(product_type, buyer)
    embed = discord.Embed(title="🧾 Payment Invoice", description=f"{premium_divider()}\n**Status:** Paid / Approved\n{premium_divider()}", color=COLOR_INFO)
    embed.add_field(name="Invoice ID", value=f"`{invoice_id}`", inline=False); embed.add_field(name="Buyer", value=buyer.mention, inline=True); embed.add_field(name="Product", value=PRODUCTS[product_type]["label"], inline=True)
    embed.add_field(name="Price", value=f"{format_price(price)}€", inline=True); embed.add_field(name="Method", value=PAYMENTS[payment_key]["label"], inline=True); embed.add_field(name="Date", value=f"<t:{int(now_utc().timestamp())}:F>", inline=True)
    embed.add_field(name="Server", value=SERVER_NAME, inline=True)
    if reseller_discount: embed.add_field(name="Discount", value="Reseller 50%", inline=True)
    return embed

def build_key_delivery_embed(product_type: str, key: str) -> discord.Embed: return discord.Embed(title="🔑 Your Key Has Been Generated", description=f"{premium_divider()}\n**Product:** {PRODUCTS[product_type]['label']}\n**Your Key:**\n`{key}`\n\nGo to the redeem panel and click **Redeem**.\n{premium_divider()}", color=COLOR_SUCCESS)

def build_payment_summary_embed(channel_id: int) -> discord.Embed:
    data = ticket_data.get(channel_id, {})
    user = bot.get_guild(GUILD_ID).get_member(data.get("user_id")) if bot.get_guild(GUILD_ID) and data.get("user_id") else None
    
    product_key = data.get("product_key")
    promo_code = data.get("applied_promo")
    promo_discount = promos_db[promo_code]["discount"] if promo_code and promo_code in promos_db else 0
    
    if product_key in PRODUCTS:
        price_text = f"{format_price(get_price(product_key, user, promo_discount))}€"
        if is_reseller(user): price_text += " (Reseller)"
        if promo_discount > 0: price_text += f" (Promo -{promo_discount}%)"
    else: price_text = "—"

    status_map = {"waiting": "🟡 Waiting", "reviewing": "🟠 Reviewing", "approved": "✅ Approved", "denied": "❌ Denied"}
    embed = discord.Embed(title="📋 Payment Summary", description=f"{premium_divider()}\n**Live order status**\n{premium_divider()}", color=COLOR_INFO)
    embed.add_field(name="Product", value=PRODUCTS[product_key]["label"] if product_key in PRODUCTS else "Not selected", inline=True); embed.add_field(name="Price", value=price_text, inline=True); embed.add_field(name="Method", value=PAYMENTS[data.get("payment_key")]["label"] if data.get("payment_key") in PAYMENTS else "Not selected", inline=True)
    embed.add_field(name="Status", value=status_map.get(data.get("status", "waiting"), data.get("status", "waiting")), inline=True); embed.add_field(name="TXID", value=f"`{short_txid(data.get('last_txid'))}`" if data.get('last_txid') else "Not submitted", inline=True); embed.add_field(name="Paysafe", value="Submitted" if data.get("paysafe_submitted") else "Not submitted", inline=True)
    embed.add_field(name="Amazon", value="Submitted" if data.get("amazon_submitted") else "Not submitted", inline=True); embed.add_field(name="Invoice", value=f"`{data.get('invoice_id')}`" if data.get('invoice_id') else "Not created", inline=False)
    if promo_code: embed.add_field(name="Gutschein", value=f"`{promo_code}`", inline=True)
    return embed

def build_admin_panel_embed(owner_id: int, ticket_channel_id: int) -> discord.Embed: return discord.Embed(title="🛠️ GEN ADMIN PANEL", description=f"{premium_divider()}\n**Buyer ID:** `{owner_id}`\n**Ticket ID:** `{ticket_channel_id}`\n{premium_divider()}", color=COLOR_ADMIN)

# =========================================================
# STATE / MESSAGE HELPERS
# =========================================================
async def delete_admin_panel_message(guild: discord.Guild, ticket_channel_id: int):
    data = ticket_data.get(ticket_channel_id)
    if data and data.get("admin_message_id"):
        admin_channel = guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
        if isinstance(admin_channel, discord.TextChannel):
            try: msg = await admin_channel.fetch_message(data["admin_message_id"]); await msg.delete()
            except: pass

async def update_payment_summary_message(channel: discord.TextChannel):
    data = ticket_data.get(channel.id)
    if data and data.get("summary_message_id"):
        try: msg = await channel.fetch_message(data["summary_message_id"]); await msg.edit(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
        except: pass

async def send_admin_panel_to_channel(guild: discord.Guild, owner_id: int, ticket_channel_id: int):
    admin_channel = guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
    if isinstance(admin_channel, discord.TextChannel):
        msg = await admin_channel.send(embed=build_admin_panel_embed(owner_id, ticket_channel_id), view=AdminPanelView(owner_id=owner_id, ticket_channel_id=ticket_channel_id))
        if ticket_channel_id in ticket_data: ticket_data[ticket_channel_id]["admin_message_id"] = msg.id

async def send_summary_and_admin_panels(channel: discord.TextChannel, owner_id: int):
    summary_msg = await channel.send(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
    ticket_data[channel.id]["summary_message_id"] = summary_msg.id
    await send_admin_panel_to_channel(channel.guild, owner_id, channel.id)

# =========================================================
# REDEEM
# =========================================================
async def redeem_key_for_user(guild: discord.Guild, member: discord.Member, key: str):
    global keys_db, redeemed_db
    if is_blacklisted(member.id): return False, "You are blacklisted from using this system."
    if key not in keys_db: return False, "Key not found."
    key_data = keys_db[key]
    if key_data["used"]: return False, "This key has already been used."
    if key_data.get("bound_user_id") is not None and str(key_data.get("bound_user_id")) != str(member.id): return False, "This key is bound to a different user."

    product_type = key_data["type"]
    product = PRODUCTS[product_type]
    role = guild.get_role(REDEEM_ROLE_ID)
    if not role: return False, "Redeem role not found."

    expires_at = (now_utc() + product["duration"]).isoformat() if product["duration"] else None
    keys_db[key].update({"used": True, "used_by": str(member.id), "bound_user_id": str(member.id), "redeemed_at": iso_now()})
    save_json(KEYS_FILE, keys_db)
    redeemed_db[str(member.id)] = {"key": key, "type": product_type, "role_id": REDEEM_ROLE_ID, "redeemed_at": iso_now(), "expires_at": expires_at, "expiry_reminder_sent": False}
    save_json(REDEEMED_FILE, redeemed_db)

    try: await member.add_roles(role, reason=f"Redeemed key: {key}")
    except Exception as e: return False, f"Failed to add role: {e}"
    return True, product_type

# =========================================================
# TICKETS
# =========================================================
async def create_ticket_channel(interaction: discord.Interaction, ticket_type: str):
    guild, user = interaction.guild, interaction.user
    if not guild or not isinstance(user, discord.Member): return await interaction.response.send_message("Server only.", ephemeral=True)
    if is_blacklisted(user.id): return await interaction.response.send_message(f"Blacklisted.\nReason: {blacklist_db[str(user.id)]['reason']}", ephemeral=True)
    
    existing = await find_existing_ticket(guild, user)
    if existing: return await interaction.response.send_message(f"Ticket open: {existing.mention}", ephemeral=True)

    category = guild.get_channel(BUY_CATEGORY_ID if ticket_type == "buy" else SUPPORT_CATEGORY_ID)
    if not isinstance(category, discord.CategoryChannel): return await interaction.response.send_message("Category not found.", ephemeral=True)

    bot_member = guild.get_member(bot.user.id)
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False), user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)}
    if bot_member: overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True)
    staff_role = guild.get_role(STAFF_ROLE_ID)
    if staff_role: overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

    channel_name = f"{ticket_type}-{''.join(c for c in user.name.lower().replace(' ', '-') if c.isalnum() or c == '-')}[:90]"
    channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=f"ticket_owner:{user.id}")

    if ticket_type == "support":
        await channel.send(content=f"{user.mention} <@&{STAFF_ROLE_ID}>", embed=support_ticket_embed(user), view=TicketManageView(owner_id=user.id))
    else:
        ticket_data[channel.id] = {"user_id": user.id, "product_key": None, "payment_key": None, "last_txid": None, "last_txid_check": None, "invoice_id": None, "status": "waiting", "paysafe_submitted": False, "amazon_submitted": False, "applied_promo": None, "summary_message_id": None, "admin_message_id": None}
        forwarded_paysafe_codes[channel.id] = []
        forwarded_amazon_codes[channel.id] = []
        await channel.send(content=f"{user.mention} <@&{STAFF_ROLE_ID}>", embed=buy_ticket_embed(user), view=BuySetupView(owner_id=user.id))
        await send_summary_and_admin_panels(channel, user.id)

    await send_log(guild, "🎫 Ticket Created", f"**User:** {user.mention}\n**Type:** {ticket_type.title()}\n**Channel:** {channel.mention}\n**User ID:** `{user.id}`")
    await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

# =========================================================
# MODALS & VIEWS
# =========================================================

class PromoCodeModal(discord.ui.Modal, title="Gutscheincode einlösen"):
    code_input = discord.ui.TextInput(label="Promo Code", placeholder="z.B. VALE20", required=True)
    def __init__(self, owner_id: int): super().__init__(); self.owner_id = owner_id
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        data = ticket_data.get(interaction.channel.id)
        if not data: return await interaction.response.send_message("No ticket data.", ephemeral=True)
        
        code = str(self.code_input).strip().upper()
        if code not in promos_db or promos_db[code]["uses"] <= 0: return await interaction.response.send_message("❌ Ungültiger oder abgelaufener Code.", ephemeral=True)
            
        data["applied_promo"] = code
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message(f"✅ Gutschein `{code}` erfolgreich angewendet! (Rabatt: {promos_db[code]['discount']}%)", ephemeral=True)

class GenericCryptoTxidModal(discord.ui.Modal, title="Paste your Crypto TXID here"):
    txid_input = discord.ui.TextInput(label="Transaction Hash (TXID)", placeholder="Paste your Ethereum or Solana TXID...", required=True, style=discord.TextStyle.short)
    def __init__(self, owner_id: int): super().__init__(); self.owner_id = owner_id
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        txid = str(self.txid_input).strip()
        data = ticket_data.get(interaction.channel.id)
        data["last_txid"] = txid; data["status"] = "reviewing"
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        embed = discord.Embed(title="🪙 Crypto TXID Submitted (Manual Review)", description=f"**Buyer:** {interaction.user.mention}\n**Ticket:** {interaction.channel.mention}\n**TXID:** `{txid}`\n**Coin:** {data['payment_key'].title()}", color=COLOR_PENDING)
        if isinstance(review_channel, discord.TextChannel): await review_channel.send(content=f"<@&{STAFF_ROLE_ID}> Review needed.", embed=embed, view=ReviewView(target_channel_id=interaction.channel.id, buyer_id=interaction.user.id))
        await interaction.channel.send(embed=discord.Embed(title="✅ TXID Submitted", description="Sent to staff for manual verification.", color=COLOR_SUCCESS))
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("TXID submitted.", ephemeral=True)

class LitecoinTxidModal(discord.ui.Modal, title="Paste your Litecoin TXID here"):
    txid_input = discord.ui.TextInput(label="Litecoin TXID", placeholder="Paste the full TXID here...", required=True, min_length=64, max_length=64)
    def __init__(self, owner_id: int): super().__init__(); self.owner_id = owner_id
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        data = ticket_data.get(interaction.channel.id)
        txid = str(self.txid_input).strip()
        if txid in used_txids_db: return await interaction.response.send_message("TXID already submitted before.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        tx_data, err = await fetch_ltc_tx(txid)
        if err or not tx_data: return await interaction.followup.send(f"Could not verify TXID right now. {err}", ephemeral=True)
        
        conf = int(tx_data.get("confirmations", 0))
        f_addr, tot_litoshi = tx_matches_our_address(tx_data, LITECOIN_ADDRESS)
        tot_ltc = litoshi_to_ltc(tot_litoshi)
        used_txids_db[txid] = {"user_id": str(interaction.user.id), "ticket_id": str(interaction.channel.id), "used_at": iso_now()}
        save_json(USED_TXIDS_FILE, used_txids_db)

        data["last_txid"] = txid; data["last_txid_check"] = {"confirmations": conf, "matched_address": f_addr, "amount_ltc": tot_ltc}; data["status"] = "reviewing"
        await interaction.channel.send(embed=build_ltc_result_embed(txid, f_addr, conf, tot_ltc))
        await update_payment_summary_message(interaction.channel)
        await send_log(interaction.guild, "🪙 LTC TXID Checked", f"**Buyer:** {interaction.user.mention}\n**TXID:** `{txid}`\n**Amount:** `{tot_ltc:.8f} LTC`", color=COLOR_INFO)
        msg = "TXID verified successfully." if f_addr and conf >= LTC_MIN_CONFIRMATIONS else "TXID found, waiting for confirmations." if f_addr else "TXID found, but no output to your LTC address."
        await interaction.followup.send(msg, ephemeral=True)

class PaysafeCodeModal(discord.ui.Modal, title="Paste your Paysafecard code here"):
    paysafe_code = discord.ui.TextInput(label="Paysafecard Code", required=True, max_length=200, style=discord.TextStyle.paragraph)
    def __init__(self, owner_id: int): super().__init__(); self.owner_id = owner_id
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        data = ticket_data.get(interaction.channel.id)
        codes_channel = interaction.guild.get_channel(PAYSAFE_CODES_CHANNEL_ID)
        found_codes = extract_possible_paysafe_codes(str(self.paysafe_code).strip()) or [str(self.paysafe_code).strip().upper()]
        new_codes = []
        for code in list(dict.fromkeys(found_codes)):
            if code not in used_paysafe_db and code not in forwarded_paysafe_codes.setdefault(interaction.channel.id, []):
                used_paysafe_db[code] = {"user_id": str(interaction.user.id), "ticket_id": str(interaction.channel.id), "used_at": iso_now()}
                new_codes.append(code); forwarded_paysafe_codes[interaction.channel.id].append(code)
        save_json(USED_PAYSAFE_FILE, used_paysafe_db)
        if not new_codes: return await interaction.response.send_message("No new valid code found.", ephemeral=True)
        data["paysafe_submitted"] = True; data["status"] = "reviewing"
        await codes_channel.send(content=f"<@&{STAFF_ROLE_ID}> New paysafecard code.", embed=discord.Embed(title="💳 Code", description=f"**Buyer:** {interaction.user.mention}\n**Codes:**\n" + "\n".join(f"`{c}`" for c in new_codes), color=COLOR_WARN))
        await interaction.channel.send(embed=discord.Embed(title="💳 Paysafecard Submitted", description=f"{premium_divider()}\nSent to staff successfully.\n{premium_divider()}", color=COLOR_SUCCESS))
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("Sent to staff.", ephemeral=True)

class AmazonCodeModal(discord.ui.Modal, title="Paste your Amazon code here"):
    amazon_code = discord.ui.TextInput(label="Amazon Code", required=True, max_length=200, style=discord.TextStyle.paragraph)
    def __init__(self, owner_id: int): super().__init__(); self.owner_id = owner_id
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        data = ticket_data.get(interaction.channel.id)
        codes_channel = interaction.guild.get_channel(AMAZON_CODES_CHANNEL_ID)
        found_codes = extract_possible_amazon_codes(str(self.amazon_code).strip()) or [str(self.amazon_code).strip().upper()]
        new_codes = []
        for code in list(dict.fromkeys(found_codes)):
            if code not in used_amazon_db and code not in forwarded_amazon_codes.setdefault(interaction.channel.id, []):
                used_amazon_db[code] = {"user_id": str(interaction.user.id), "ticket_id": str(interaction.channel.id), "used_at": iso_now()}
                new_codes.append(code); forwarded_amazon_codes[interaction.channel.id].append(code)
        save_json(USED_AMAZON_FILE, used_amazon_db)
        if not new_codes: return await interaction.response.send_message("No new valid code found.", ephemeral=True)
        data["amazon_submitted"] = True; data["status"] = "reviewing"
        await codes_channel.send(content=f"<@&{STAFF_ROLE_ID}> New Amazon code.", embed=discord.Embed(title="🎁 Code", description=f"**Buyer:** {interaction.user.mention}\n**Codes:**\n" + "\n".join(f"`{c}`" for c in new_codes), color=COLOR_WARN))
        await interaction.channel.send(embed=discord.Embed(title="🎁 Amazon Submitted", description=f"{premium_divider()}\nSent to staff successfully.\n{premium_divider()}", color=COLOR_SUCCESS))
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("Sent to staff.", ephemeral=True)

class RedeemKeyModal(discord.ui.Modal, title="Paste your key here"):
    key_input = discord.ui.TextInput(label="Key", required=True, max_length=100)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, result = await redeem_key_for_user(interaction.guild, interaction.user, str(self.key_input).strip().upper())
        if not ok: return await interaction.followup.send(result, ephemeral=True)
        await interaction.followup.send(embed=discord.Embed(title="✅ Key Redeemed", description=f"{premium_divider()}\nRole granted successfully.\n**Type:** {PRODUCTS[result]['label']}\n{premium_divider()}", color=COLOR_SUCCESS), ephemeral=True)

class ExtendModal(discord.ui.Modal, title="Extend Access"):
    extend_input = discord.ui.TextInput(label="Duration", placeholder="Example: 1d or 7d", required=True, max_length=10)
    def __init__(self, target_user_id: int): super().__init__(); self.target_user_id = target_user_id
    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
        duration = parse_duration_string(str(self.extend_input))
        if duration is None: return await interaction.response.send_message("Invalid format.", ephemeral=True)
        uid = str(self.target_user_id)
        if uid not in redeemed_db: return await interaction.response.send_message("No active redeem entry.", ephemeral=True)
        old_exp = redeemed_db[uid].get("expires_at")
        now = now_utc()
        base = datetime.fromisoformat(old_exp) if old_exp and datetime.fromisoformat(old_exp) >= now else now
        new_exp = (base + duration).isoformat()
        redeemed_db[uid].update({"expires_at": new_exp, "expiry_reminder_sent": False})
        save_json(REDEEMED_FILE, redeemed_db)
        member = interaction.guild.get_member(self.target_user_id)
        if member: await dm_user_safe(member, embed=discord.Embed(title="⏳ Access Extended", description=f"New expiry: {format_expiry(new_exp)}", color=COLOR_SUCCESS))
        await interaction.response.send_message("Access extended.", ephemeral=True)

class MainTicketPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="💠", custom_id="main_support_ticket_button")
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button): await create_ticket_channel(interaction, "support")
    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, emoji="🛒", custom_id="main_buy_ticket_button")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button): await create_ticket_channel(interaction, "buy")

class RedeemPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Redeem", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="redeem_key_button")
    async def redeem_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_blacklisted(interaction.user.id): return await interaction.response.send_message("Blacklisted.", ephemeral=True)
        await interaction.response.send_modal(RedeemKeyModal())

class CloseConfirmView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await delete_admin_panel_message(interaction.guild, interaction.channel.id)
        ticket_data.pop(interaction.channel.id, None)
        await asyncio.sleep(2); await interaction.channel.delete()
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.edit_message(content="Close cancelled.", view=None)

class TicketManageView(discord.ui.View):
    def __init__(self, owner_id: int): super().__init__(timeout=None); self.owner_id = owner_id
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="claim_ticket_button")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.")
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("No permission.", ephemeral=True)
        await interaction.response.send_message("Are you sure you want to close this ticket?", view=CloseConfirmView(), ephemeral=True)

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1 Day", description="5€", value="day_1", emoji="📅"),
            discord.SelectOption(label="1 Week", description="15€", value="week_1", emoji="🗓️"),
            discord.SelectOption(label="Lifetime", description="30€", value="lifetime", emoji="♾️"),
        ]
        super().__init__(placeholder="📦 Choose your product", min_values=1, max_values=1, options=options, custom_id="buy_product_select")
    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(interaction.channel.id)
        if interaction.user.id != data["user_id"] and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("No permission.", ephemeral=True)
        data["product_key"] = self.values[0]
        embed = discord.Embed(title="📦 Product Selected", description=f"**{PRODUCTS[self.values[0]]['label']}** selected\nPrice: **{format_price(get_price(self.values[0], interaction.user))}€**\n\nNow choose your payment method below.", color=COLOR_INFO)
        await interaction.response.send_message(embed=embed, view=PaymentSelectView())
        await update_payment_summary_message(interaction.channel)

class ProductSelectView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(ProductSelect())

class PaymentSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="PayPal", value="paypal", emoji="💸"),
            discord.SelectOption(label="Litecoin", value="litecoin", emoji="🪙"),
            discord.SelectOption(label="Ethereum", value="ethereum", emoji="🔷"),
            discord.SelectOption(label="Solana", value="solana", emoji="🟣"),
            discord.SelectOption(label="Paysafecard", value="paysafecard", emoji="💳"),
            discord.SelectOption(label="Amazon Card", value="amazoncard", emoji="🎁"),
        ]
        super().__init__(placeholder="💳 Choose payment method", min_values=1, max_values=1, options=options, custom_id="buy_payment_select")
    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(interaction.channel.id)
        if interaction.user.id != data["user_id"] and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("No permission.", ephemeral=True)
        data["payment_key"] = self.values[0]
        buyer = interaction.guild.get_member(data["user_id"])
        ltc_price = await fetch_ltc_price_eur() if self.values[0] == "litecoin" else None
        await interaction.response.send_message(embed=build_order_summary(data["product_key"], self.values[0], buyer, ltc_price), view=PaymentActionView(owner_id=data["user_id"]))
        await update_payment_summary_message(interaction.channel)

class PaymentSelectView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(PaymentSelect())

class BuySetupView(discord.ui.View):
    def __init__(self, owner_id: int): super().__init__(timeout=None); self.owner_id = owner_id
    @discord.ui.button(label="Choose Product", style=discord.ButtonStyle.primary, emoji="📦", custom_id="choose_product_button")
    async def choose_product(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        await interaction.response.send_message("Select product:", view=ProductSelectView(), ephemeral=True)
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_buy_ticket_button")
    async def close_buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("No permission.", ephemeral=True)
        await interaction.response.send_message("Are you sure you want to close this ticket?", view=CloseConfirmView(), ephemeral=True)

class PaymentActionView(discord.ui.View):
    def __init__(self, owner_id: int): super().__init__(timeout=None); self.owner_id = owner_id
    
    @discord.ui.button(label="Promo Code einlösen", style=discord.ButtonStyle.secondary, emoji="🎟️", custom_id="apply_promo_button")
    async def apply_promo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        await interaction.response.send_modal(PromoCodeModal(owner_id=self.owner_id))

    @discord.ui.button(label="Payment Sent", style=discord.ButtonStyle.success, emoji="✅", custom_id="payment_sent_button")
    async def payment_sent(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Only buyer.", ephemeral=True)
        data = ticket_data.get(interaction.channel.id)
        data["status"] = "reviewing"
        buyer = interaction.guild.get_member(data["user_id"])
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        embed = discord.Embed(title="🧾 New Payment Review", description=f"Buyer: {buyer.mention}\nTicket: {interaction.channel.mention}", color=COLOR_WARN)
        if isinstance(review_channel, discord.TextChannel): await review_channel.send(content=f"<@&{STAFF_ROLE_ID}> New payment to review.", embed=embed, view=ReviewView(target_channel_id=interaction.channel.id, buyer_id=buyer.id))
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("Payment marked as sent. Staff notified.", ephemeral=True)
    
    @discord.ui.button(label="Submit LTC TXID", style=discord.ButtonStyle.primary, emoji="🪙", custom_id="submit_txid_button")
    async def submit_txid(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(LitecoinTxidModal(owner_id=self.owner_id))
    @discord.ui.button(label="Submit Crypto TXID (ETH/SOL)", style=discord.ButtonStyle.primary, emoji="🔗", custom_id="submit_generic_txid_button")
    async def submit_generic_txid(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(GenericCryptoTxidModal(owner_id=self.owner_id))
    @discord.ui.button(label="Submit Paysafecard", style=discord.ButtonStyle.secondary, emoji="💳", custom_id="submit_paysafe_button")
    async def submit_paysafe(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(PaysafeCodeModal(owner_id=self.owner_id))
    @discord.ui.button(label="Submit Amazon", style=discord.ButtonStyle.secondary, emoji="🎁", custom_id="submit_amazon_button")
    async def submit_amazon(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(AmazonCodeModal(owner_id=self.owner_id))

class PaymentSummaryView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="refresh_payment_summary")
    async def refresh_summary(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.edit_message(embed=build_payment_summary_embed(interaction.channel.id), view=PaymentSummaryView())

class AdminPanelView(discord.ui.View):
    def __init__(self, owner_id: int, ticket_channel_id: int): super().__init__(timeout=None); self.owner_id = owner_id; self.ticket_channel_id = ticket_channel_id
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="adminpanel_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
        await ReviewView(self.ticket_channel_id, self.owner_id)._approve_logic(interaction)
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="adminpanel_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
        await ReviewView(self.ticket_channel_id, self.owner_id)._deny_logic(interaction)
    @discord.ui.button(label="Resend Key", style=discord.ButtonStyle.primary, emoji="🔁", custom_id="adminpanel_resend")
    async def resend_key_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
        latest = find_user_latest_key(self.owner_id)
        if not latest: return await interaction.response.send_message("No key found.", ephemeral=True)
        key, data = latest
        buyer = interaction.guild.get_member(self.owner_id)
        if buyer: await dm_user_safe(buyer, embed=discord.Embed(title="🔁 Your Key Was Resent", description=f"**Key:** `{key}`", color=COLOR_INFO))
        await interaction.response.send_message("Key resent.", ephemeral=True)
    @discord.ui.button(label="Extend", style=discord.ButtonStyle.secondary, emoji="⏳", custom_id="adminpanel_extend")
    async def extend_button(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(ExtendModal(target_user_id=self.owner_id))
    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id="adminpanel_blacklist")
    async def blacklist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
        blacklist_db[str(self.owner_id)] = {"reason": "Added from admin panel", "added_by": str(interaction.user.id), "added_at": iso_now()}
        save_json(BLACKLIST_FILE, blacklist_db)
        await interaction.response.send_message("User blacklisted.", ephemeral=True)
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="adminpanel_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
        await interaction.response.send_message("Are you sure?", view=CloseConfirmView(), ephemeral=True)

class ReviewView(discord.ui.View):
    def __init__(self, target_channel_id: int, buyer_id: int): super().__init__(timeout=None); self.target_channel_id = target_channel_id; self.buyer_id = buyer_id
    async def _approve_logic(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.target_channel_id)
        data = ticket_data.get(self.target_channel_id)
        buyer = interaction.guild.get_member(self.buyer_id)
        invoice_id = build_invoice_id()
        data["invoice_id"] = invoice_id
        data["status"] = "approved"
        
        promo_code = data.get("applied_promo")
        promo_discount = promos_db[promo_code]["discount"] if promo_code and promo_code in promos_db else 0
        if promo_code and promo_code in promos_db:
            promos_db[promo_code]["uses"] -= 1
            save_json(PROMOS_FILE, promos_db)

        generated_key = generate_key(data["product_key"], ticket_id=self.target_channel_id)
        keys_db[generated_key]["bound_user_id"] = str(buyer.id)
        save_json(KEYS_FILE, keys_db)
        
        final_price = get_price(data["product_key"], buyer, promo_discount)
        create_invoice_record(invoice_id, buyer.id, data["product_key"], data["payment_key"], generated_key, self.target_channel_id, final_price, is_reseller(buyer))
        
        invoice_embed = build_invoice_embed(invoice_id, buyer, data["product_key"], data["payment_key"], final_price, is_reseller(buyer))
        await channel.send(embed=invoice_embed)
        await channel.send(embed=build_key_delivery_embed(data["product_key"], generated_key))
        await update_payment_summary_message(channel)
        
        if buyer: await dm_user_safe(buyer, embed=discord.Embed(title="🔑 Purchase Approved", description=f"**Key:** `{generated_key}`", color=COLOR_SUCCESS))
        await interaction.response.send_message("Approved and Key generated.", ephemeral=True)

    async def _deny_logic(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.target_channel_id)
        await channel.send(embed=discord.Embed(title="❌ Denied", description="Payment was denied.", color=COLOR_DENY))
        if self.target_channel_id in ticket_data: ticket_data[self.target_channel_id]["status"] = "denied"
        await update_payment_summary_message(channel)
        await interaction.response.send_message("Payment denied.", ephemeral=True)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="review_approve_button")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button): await self._approve_logic(interaction)
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="review_deny_button")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button): await self._deny_logic(interaction)

# =========================================================
# EVENTS
# =========================================================
@bot.event
async def on_member_join(member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel): return
    embed = discord.Embed(title="Welcome!", description=f"Welcome {member.mention} to **{SERVER_NAME}**.\n\nRead the rules in <#{RULES_CHANNEL_ID}> to get started!", color=COLOR_WELCOME)
    embed.set_author(name=SERVER_NAME, icon_url=WELCOME_THUMBNAIL_URL); embed.set_thumbnail(url=WELCOME_THUMBNAIL_URL); embed.set_image(url=WELCOME_BANNER_URL)
    try: await channel.send(embed=embed)
    except: pass

# =========================================================
# TASKS
# =========================================================
@tasks.loop(minutes=5)
async def check_expired_roles():
    global redeemed_db
    guild = bot.get_guild(GUILD_ID)
    if not guild: return
    current_time = now_utc(); changed = False

    for user_id, data in list(redeemed_db.items()):
        if not data.get("expires_at"): continue
        try: expire_time = datetime.fromisoformat(data["expires_at"])
        except: continue
        member = guild.get_member(int(user_id))
        if not member: continue
        remaining = expire_time - current_time

        if remaining.total_seconds() <= 0:
            role = guild.get_role(data.get("role_id", REDEEM_ROLE_ID))
            if role and role in member.roles:
                try: await member.remove_roles(role, reason="Access expired")
                except: pass
            await dm_user_safe(member, embed=discord.Embed(title="⚠️ Access Expired", description="Your access has expired.", color=COLOR_DENY))
            redeemed_db.pop(user_id, None); changed = True
        elif not data.get("expiry_reminder_sent", False) and remaining <= timedelta(hours=EXPIRY_REMINDER_HOURS):
            await dm_user_safe(member, embed=discord.Embed(title="⏳ Access Expiring Soon", description=f"Expires in < {EXPIRY_REMINDER_HOURS}h", color=COLOR_WARN))
            redeemed_db[user_id]["expiry_reminder_sent"] = True; changed = True
    if changed: save_json(REDEEMED_FILE, redeemed_db)

# =========================================================
# COMMANDS
# =========================================================
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_commands(ctx):
    await ctx.send("Synchronisiere Slash-Commands... ⏳")
    try:
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await ctx.send(f"✅ Erfolgreich {len(synced)} Slash-Commands synchronisiert! Drücke STRG+R.")
    except Exception as e: await ctx.send(f"❌ Fehler:\n```py\n{e}\n```")

@bot.tree.command(name="create_promo", description="Erstelle einen Rabattcode")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def create_promo(interaction: discord.Interaction, code: str, discount_prozent: int, max_uses: int):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    code = code.upper()
    promos_db[code] = {"discount": discount_prozent, "uses": max_uses, "created_by": str(interaction.user.id)}
    save_json(PROMOS_FILE, promos_db)
    await interaction.response.send_message(f"✅ Promo `{code}` erstellt! Rabatt: {discount_prozent}%, Nutzungen: {max_uses}", ephemeral=True)

@bot.tree.command(name="ticket", description="Open the Gen ticket panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket(interaction: discord.Interaction): await interaction.response.send_message(embed=panel_embed(), view=MainTicketPanelView())

@bot.tree.command(name="send_redeem_panel", description="Send the redeem panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_redeem_panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    await interaction.response.send_message(embed=build_redeem_panel_embed(), view=RedeemPanelView())

@bot.tree.command(name="invoice_lookup", description="Lookup an invoice by ID")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def invoice_lookup(interaction: discord.Interaction, invoice_id: str):
    if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
    data = invoices_db.get(invoice_id.strip().upper())
    if not data: return await interaction.response.send_message("Invoice not found.", ephemeral=True)
    buyer = interaction.guild.get_member(int(data["buyer_id"]))
    embed = discord.Embed(title="🧾 Invoice Lookup", color=COLOR_INFO)
    embed.add_field(name="Invoice ID", value=f"`{invoice_id.strip().upper()}`", inline=False); embed.add_field(name="Buyer", value=buyer.mention if buyer else data["buyer_id"], inline=True); embed.add_field(name="Product", value=PRODUCTS[data["product_type"]]["label"], inline=True)
    embed.add_field(name="Price", value=f"{format_price(float(data.get('final_price_eur', PRODUCTS[data['product_type']]['price_eur'])))}€", inline=True)
    embed.add_field(name="Method", value=PAYMENTS[data["payment_key"]]["label"], inline=True); embed.add_field(name="Key", value=f"`{data['key']}`", inline=False); embed.add_field(name="Created", value=data["created_at"], inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="resend_key", description="Resend a user's latest key")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def resend_key(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
    latest = find_user_latest_key(user.id)
    if not latest: return await interaction.response.send_message("No key found.", ephemeral=True)
    key, data = latest
    await dm_user_safe(user, embed=discord.Embed(title="🔁 Your Key Was Resent", description=f"**Product:** {PRODUCTS[data['type']]['label']}\n**Key:** `{key}`", color=COLOR_INFO))
    await interaction.response.send_message(f"Key resent to {user.mention}.", ephemeral=True)

@bot.tree.command(name="extend", description="Extend a user's access")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def extend(interaction: discord.Interaction, user: discord.Member, duration: str):
    if not interaction.user.guild_permissions.manage_channels: return await interaction.response.send_message("Staff only.", ephemeral=True)
    td = parse_duration_string(duration)
    if td is None: return await interaction.response.send_message("Invalid duration. Use: 1d, 7d, 12h", ephemeral=True)
    uid = str(user.id)
    if uid not in redeemed_db: return await interaction.response.send_message("No active redeem entry.", ephemeral=True)
    base = datetime.fromisoformat(redeemed_db[uid]["expires_at"]) if redeemed_db[uid].get("expires_at") and datetime.fromisoformat(redeemed_db[uid]["expires_at"]) >= now_utc() else now_utc()
    new_exp = (base + td).isoformat()
    redeemed_db[uid].update({"expires_at": new_exp, "expiry_reminder_sent": False}); save_json(REDEEMED_FILE, redeemed_db)
    await dm_user_safe(user, embed=discord.Embed(title="⏳ Access Extended", description=f"New expiry: {format_expiry(new_exp)}", color=COLOR_SUCCESS))
    await interaction.response.send_message(f"Extended {user.mention} until {format_expiry(new_exp)}", ephemeral=True)

@bot.tree.command(name="blacklist_add", description="Blacklist a user")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def blacklist_add(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    blacklist_db[str(user.id)] = {"reason": reason, "added_by": str(interaction.user.id), "added_at": iso_now()}
    save_json(BLACKLIST_FILE, blacklist_db)
    await interaction.response.send_message(f"{user.mention} blacklisted. Reason: {reason}", ephemeral=True)

@bot.tree.command(name="blacklist_remove", description="Remove a user from blacklist")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def blacklist_remove(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    if str(user.id) in blacklist_db:
        del blacklist_db[str(user.id)]; save_json(BLACKLIST_FILE, blacklist_db)
        await interaction.response.send_message(f"{user.mention} removed from blacklist.", ephemeral=True)
    else: await interaction.response.send_message("User is not blacklisted.", ephemeral=True)

@bot.tree.command(name="vouch", description="Hinterlasse eine Bewertung für deinen Kauf!")
@app_commands.describe(sterne="Wie viele Sterne gibst du? (1-5)", produkt="Was hast du gekauft?", bewertung="Deine Erfahrung")
@app_commands.choices(sterne=[
    app_commands.Choice(name="⭐⭐⭐⭐⭐ (5/5)", value=5), app_commands.Choice(name="⭐⭐⭐⭐ (4/5)", value=4),
    app_commands.Choice(name="⭐⭐⭐ (3/5)", value=3), app_commands.Choice(name="⭐⭐ (2/5)", value=2), app_commands.Choice(name="⭐ (1/5)", value=1)
])
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def vouch(interaction: discord.Interaction, sterne: app_commands.Choice[int], produkt: str, bewertung: str):
    ch = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel): return await interaction.response.send_message("Vouch-Kanal nicht konfiguriert.", ephemeral=True)
    embed = discord.Embed(title=f"Neue Bewertung: {sterne.name}", description=f'"{bewertung}"', color=0xFFD700)
    embed.add_field(name="👤 Käufer", value=interaction.user.mention, inline=True); embed.add_field(name="📦 Produkt", value=f"`{produkt}`", inline=True)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await ch.send(embed=embed); await interaction.response.send_message("✅ Danke für deine Bewertung!", ephemeral=True)

@bot.tree.command(name="send_rules", description="Postet das Regelwerk in den aktuellen Kanal")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_rules(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    embed = discord.Embed(title="📜 Server Rules", description="**1. Be Respectful**\nBehandel alle Mitglieder mit Respekt. Keine Beleidigungen, kein Rassismus, kein Spam.\n\n**2. No DM Advertising**\nKeine Werbung für andere Server oder Dienste in den DMs unserer Nutzer.\n\n**3. Support & Tickets**\nBitte eröffne für alle Anfragen oder Käufe ein Ticket im <#1490336321913356459> Bereich. Kein Support in normalen Chats.\n\n**4. Scam & Fraud**\nBetrugsversuche beim Kauf führen zu einem permanenten Ban und Blacklist.", color=COLOR_WELCOME)
    embed.set_image(url=WELCOME_BANNER_URL)
    await interaction.channel.send(embed=embed); await interaction.response.send_message("Regelwerk erfolgreich gepostet!", ephemeral=True)

@bot.tree.command(name="test_welcome", description="Testet die Welcome-Nachricht (Simuliert einen Join)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def test_welcome(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admins only.", ephemeral=True)
    await interaction.response.send_message("Simuliere Server-Beitritt...", ephemeral=True); bot.dispatch('member_join', interaction.user)

# =========================================================
# READY
# =========================================================
@bot.event
async def on_ready():
    global keys_db, redeemed_db, used_txids_db, used_paysafe_db, used_amazon_db, blacklist_db, invoices_db, promos_db

    keys_db = load_json(KEYS_FILE, {})
    redeemed_db = load_json(REDEEMED_FILE, {})
    used_txids_db = load_json(USED_TXIDS_FILE, {})
    used_paysafe_db = load_json(USED_PAYSAFE_FILE, {})
    used_amazon_db = load_json(USED_AMAZON_FILE, {})
    blacklist_db = load_json(BLACKLIST_FILE, {})
    invoices_db = load_json(INVOICES_FILE, {})
    promos_db = load_json(PROMOS_FILE, {})

    print("Bot is starting...")
    bot.loop.create_task(start_web_server())

    print(f"Logged in as: {bot.user} ({bot.user.id})")
    
    bot.add_view(MainTicketPanelView())
    bot.add_view(RedeemPanelView())
    bot.add_view(TicketManageView(owner_id=0))
    bot.add_view(BuySetupView(owner_id=0))
    bot.add_view(PaymentActionView(owner_id=0))
    bot.add_view(PaymentSummaryView())
    bot.add_view(AdminPanelView(owner_id=0, ticket_channel_id=0))
    bot.add_view(ReviewView(target_channel_id=0, buyer_id=0))

    if not check_expired_roles.is_running(): check_expired_roles.start()

    try:
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ FORCED SYNC ERFOLGREICH: {len(synced)} Command(s) an Guild {GUILD_ID} gesendet!")
    except Exception as e:
        print(f"❌ Slash command sync error: {e}")

    print("Bot is ready.")

bot.run(TOKEN)
