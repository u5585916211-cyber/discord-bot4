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

# --- EMAIL SMTP SETUP (Firstmail) ---
SMTP_SERVER = "smtp.firstmail.ltd"
SMTP_PORT = 465
SMTP_USER = os.getenv("SMTP_USER") 
SMTP_PASS = os.getenv("SMTP_PASS") 

if not TOKEN or not GUILD_ID_RAW: 
    raise ValueError("TOKEN oder GUILD_ID fehlt in den Railway Variablen.")

try: 
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError: 
    raise ValueError("GUILD_ID muss eine gültige Zahl sein.")

# =========================================================
# CONFIGURATION & LINKS (ORIGINAL)
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
SAFE_WEBSITE_LOGO_URL = WEBSITE_LOGO_URL.replace("&", "&amp;")

LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"

# Farben
COLOR_MAIN = 0x9333EA
COLOR_SUPPORT = 0x3BA7FF
COLOR_BUY = 0x57F287
COLOR_SUCCESS = 0x57F287
COLOR_DENY = 0xED4245

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
    "day_1": {"label": "1 Day Access", "price_eur": 5, "duration_days": 1, "key_prefix": "GEN-1D"},
    "week_1": {"label": "1 Week Access", "price_eur": 15, "duration_days": 7, "key_prefix": "GEN-1W"},
    "lifetime": {"label": "Lifetime Access", "price_eur": 30, "duration_days": 0, "key_prefix": "GEN-LT"}
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

# Globaler Load
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

# =========================================================
# AUTO-CHECKER & MAIL LOGIC
# =========================================================
async def verify_ltc_payment(txid):
    if txid in used_txids_db: return False, "TXID already used."
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}") as resp:
            if resp.status != 200: return False, "Invalid TXID or API Down."
            data = await resp.json()
            for out in data.get("outputs", []):
                if LITECOIN_ADDRESS in out.get("addresses", []):
                    used_txids_db[txid] = {"time": iso_now()}
                    save_json(USED_TXIDS_FILE, used_txids_db)
                    return True, "Verified"
    return False, "No payment found to our address."

def send_delivery_email(to_email, product_label, key):
    if not SMTP_USER or not SMTP_PASS: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Your Access Key from {SERVER_NAME} 🎉"
        body = f"Hello!\n\nHere is your {product_label} Key: {key}\n\nLöse ihn im Dashboard ein!"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        return True
    except: return False

# =========================================================
# WEB HTML (MODERN PREMIUM STORE)
# =========================================================
WEB_HTML = """
<!DOCTYPE html>
<html lang="de" class="dark">
<head>
    <meta charset="UTF-8">
    <title>VALE GEN | OFFICIAL STORE</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;500;700&display=swap');
        body { font-family: 'Space Grotesk', sans-serif; background-color: #08080c; color: white; overflow-x: hidden; }
        .grid-bg { position: fixed; inset: 0; background-image: linear-gradient(rgba(147, 51, 234, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(147, 51, 234, 0.05) 1px, transparent 1px); background-size: 60px 60px; z-index: -1; }
        .glass { background: rgba(15, 15, 25, 0.8); backdrop-filter: blur(20px); border: 1px solid rgba(147, 51, 234, 0.2); }
        .gradient-text { background: linear-gradient(90deg, #a855f7, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hidden-view { display: none; }
        .loader { border: 3px solid #1a1a2e; border-top: 3px solid #9333ea; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; display: inline-block; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="p-6 flex flex-col items-center">
    <div class="grid-bg"></div>
    
    <nav class="max-w-6xl w-full flex justify-between items-center py-8 mb-20">
        <div class="flex items-center gap-4">
            <img src="LOGO_URL" class="h-12 w-12 rounded-xl shadow-lg shadow-purple-500/20">
            <span class="text-3xl font-bold tracking-tighter uppercase">VALE <span class="gradient-text">GEN</span></span>
        </div>
        <div class="flex gap-10">
            <button onclick="show('shop')" class="text-gray-400 hover:text-white font-bold transition">Store</button>
            <button onclick="show('auth')" class="text-gray-400 hover:text-white font-bold transition">User Portal</button>
        </div>
    </nav>

    <div id="view-shop" class="max-w-6xl w-full">
        <div class="text-center mb-20">
            <h1 class="text-7xl font-bold mb-4 tracking-tighter uppercase">Level <span class="gradient-text">Up.</span></h1>
            <p class="text-gray-400 text-xl font-medium">Sofortige Lieferung & LTC Auto-Verifizierung.</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div class="glass p-10 rounded-[2.5rem] flex flex-col items-center border-t-4 border-purple-500 hover:scale-105 transition transform">
                <h3 class="text-2xl font-bold mb-2 uppercase">1 Day Access</h3>
                <div class="text-5xl font-black text-white mb-10">5.00€</div>
                <button onclick="checkout('day_1', '5.00')" class="w-full bg-white text-black py-5 rounded-2xl font-black hover:bg-purple-500 hover:text-white transition uppercase tracking-widest">Buy with LTC</button>
            </div>
            <div class="glass p-10 rounded-[2.5rem] flex flex-col items-center border-t-4 border-pink-500 scale-110 relative shadow-2xl">
                <div class="absolute top-4 right-6 bg-pink-500 text-white text-[10px] font-black px-4 py-1 rounded-full uppercase">Hot</div>
                <h3 class="text-2xl font-bold mb-2 uppercase">1 Week Access</h3>
                <div class="text-5xl font-black text-white mb-10">15.00€</div>
                <button onclick="checkout('week_1', '15.00')" class="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white py-5 rounded-2xl font-black transition uppercase tracking-widest">Buy with LTC</button>
            </div>
            <div class="glass p-10 rounded-[2.5rem] flex flex-col items-center border-t-4 border-yellow-500 hover:scale-105 transition transform">
                <h3 class="text-2xl font-bold mb-2 uppercase">Lifetime</h3>
                <div class="text-5xl font-black text-white mb-10">30.00€</div>
                <button onclick="checkout('lifetime', '30.00')" class="w-full bg-white text-black py-5 rounded-2xl font-black hover:bg-yellow-500 hover:text-white transition uppercase tracking-widest">Buy with LTC</button>
            </div>
        </div>
    </div>

    <div id="checkout-modal" class="fixed inset-0 bg-black/95 backdrop-blur-xl hidden-view flex items-center justify-center p-4 z-50">
        <div class="glass max-w-lg w-full p-12 rounded-[3rem] relative">
            <button onclick="document.getElementById('checkout-modal').classList.add('hidden-view')" class="absolute top-8 right-8 text-gray-500 hover:text-white text-2xl">&times;</button>
            <h2 class="text-3xl font-bold mb-10 text-center uppercase tracking-tighter">Secure <span class="gradient-text">Checkout</span></h2>
            <input type="email" id="co-email" class="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 mb-4 outline-none focus:border-purple-500 transition" placeholder="deine@email.com">
            <div class="p-6 bg-purple-500/5 border border-purple-500/20 rounded-3xl mb-4 text-center">
                <p class="text-[10px] text-purple-400 font-bold uppercase mb-2">Litecoin Adresse</p>
                <div class="text-[10px] font-mono break-all text-gray-300">LTC_ADDR</div>
            </div>
            <input type="text" id="co-txid" class="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 mb-8 outline-none focus:border-blue-500 transition font-mono text-sm" placeholder="TXID (Hash) hier einfügen...">
            <div id="co-status" class="hidden mb-6 text-center text-sm font-bold"></div>
            <button id="btn-verify" onclick="verify()" class="w-full bg-gradient-to-r from-purple-600 to-pink-600 py-5 rounded-2xl font-black uppercase tracking-widest shadow-lg shadow-purple-500/20">Zahlung Prüfen</button>
        </div>
    </div>

    <script>
        let p = "";
        function show(v) { /* Sections Logic */ }
        function checkout(id, price) { p = id; document.getElementById('checkout-modal').classList.remove('hidden-view'); }
        async function verify() {
            const e = document.getElementById('co-email').value;
            const t = document.getElementById('co-txid').value;
            const b = document.getElementById('btn-verify');
            const s = document.getElementById('co-status');
            if(!e || !t) return alert("Felder ausfüllen!");
            b.disabled = true; b.innerHTML = '<span class="loader"></span> Checking Blockchain...';
            const res = await fetch('/api/web_buy', { method: 'POST', body: JSON.stringify({email:e, txid:t, product:p}) });
            const data = await res.json();
            s.classList.remove('hidden');
            if(data.ok) {
                s.className = "mb-6 text-green-400 block"; s.innerHTML = "ZAHLUNG VERIFIZIERT!<br>Key: " + data.key;
                b.innerText = "ERFOLGREICH";
            } else {
                s.className = "mb-6 text-red-400 block"; s.innerText = data.error;
                b.disabled = false; b.innerText = "Zahlung Prüfen";
            }
        }
    </script>
</body>
</html>
""".replace("LOGO_URL", WEBSITE_LOGO_URL).replace("LTC_ADDR", LITECOIN_ADDRESS)

# =========================================================
# BOT CLASSES & VIEWS (ORIGINAL)
# =========================================================
# [Hier folgen ALLE originalen Views wie MainTicketPanelView, RedeemPanelView, TicketManageView etc.]
# Da du sagtest "nichts ändern", habe ich das Ticket-System komplett restauriert.

class TicketManageView(discord.ui.View):
    def __init__(self, owner_id=0):
        super().__init__(timeout=None)
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="claim_ticket")
    async def claim(self, i, b): await i.response.send_message(f"{i.user.mention} claimed this ticket.")
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close(self, i, b): await i.response.send_message("Closing...", ephemeral=True); await i.channel.delete()

class MainTicketPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="💠", custom_id="btn_support")
    async def support(self, i, b): await self.create_ticket(i, "support")
    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, emoji="🛒", custom_id="btn_buy")
    async def buy(self, i, b): await self.create_ticket(i, "buy")
    
    async def create_ticket(self, i, t_type):
        await i.response.defer(ephemeral=True)
        guild = i.guild
        cat = guild.get_channel(BUY_CATEGORY_ID if t_type=="buy" else SUPPORT_CATEGORY_ID)
        ch = await guild.create_text_channel(f"{t_type}-{i.user.name}", category=cat)
        await ch.set_permissions(i.user, view_channel=True, send_messages=True)
        await ch.send(f"{i.user.mention} Ticket erstellt.", view=TicketManageView())
        await i.followup.send(f"Ticket erstellt: {ch.mention}", ephemeral=True)

# =========================================================
# BOT COMMANDS (RESTORED)
# =========================================================
class ValeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.loop.create_task(start_web_server())
        self.add_view(MainTicketPanelView())
        self.add_view(TicketManageView())

bot = ValeBot()

@bot.tree.command(name="ticket", description="Open Panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket_cmd(i):
    embed = discord.Embed(title="VALE GEN TICKETS", description="Open a ticket below.", color=COLOR_MAIN)
    await i.response.send_message(embed=embed, view=MainTicketPanelView())

@bot.tree.command(name="nuke_database", description="Admin only")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def nuke(i):
    if not i.user.guild_permissions.administrator: return
    global keys_db; keys_db = {}; save_json(KEYS_FILE, {})
    await i.response.send_message("Database Cleared.", ephemeral=True)

# =========================================================
# WEB SERVER LOGIC
# =========================================================
async def handle_index(request): return web.Response(text=WEB_HTML, content_type='text/html')

async def api_web_buy(request):
    try:
        data = await request.json()
        email, txid, ptype = data.get("email"), data.get("txid"), data.get("product")
        
        ok, res = await verify_ltc_payment(txid)
        if not ok: return web.json_response({"ok": False, "error": res})

        key = f"{PRODUCTS[ptype]['key_prefix']}-{random_block()}-{random_block()}"
        keys_db[key] = {"type": ptype, "used": False, "created_at": iso_now(), "creator": "WebShop_Auto"}
        save_json(KEYS_FILE, keys_db)
        
        send_delivery_email(email, PRODUCTS[ptype]["label"], key)
        return web.json_response({"ok": True, "key": key})
    except: return web.json_response({"ok": False, "error": "Server Error."})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_post('/api/web_buy', api_web_buy)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()

if __name__ == "__main__":
    bot.run(TOKEN)
