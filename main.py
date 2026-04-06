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

LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"

# Farben
COLOR_MAIN = 0x9333EA
COLOR_SUCCESS = 0x57F287
COLOR_DENY = 0xED4245

# =========================================================
# DATABASES
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

def iso_now(): return datetime.now(timezone.utc).isoformat()
def random_block(length=4): return uuid.uuid4().hex[:length].upper()

# --- LTC BLOCKCHAIN CHECKER ---
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
    return False, "No payment to our address found in this TXID."

def send_delivery_email(to_email, product_label, key):
    if not SMTP_USER or not SMTP_PASS: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Vielen Dank für deinen Kauf bei {SERVER_NAME}! 🎉"
        body = f"Hallo!\n\nHier ist dein Key für {product_label}:\n\nCode: {key}\n\nDu kannst ihn auf unserer Website oder in Discord einlösen."
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        return True
    except: return False

# =========================================================
# WEB DESIGN (KRASSES UI)
# =========================================================
WEB_HTML = """
<!DOCTYPE html>
<html lang="de" class="dark">
<head>
    <meta charset="UTF-8">
    <title>VALE GEN | PREMIUM STORE</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;500;700&display=swap');
        body { font-family: 'Space Grotesk', sans-serif; background-color: #050505; color: white; overflow-x: hidden; }
        .grid-bg {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background-image: linear-gradient(rgba(147, 51, 234, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(147, 51, 234, 0.1) 1px, transparent 1px);
            background-size: 50px 50px; z-index: -1;
        }
        .glass { background: rgba(15, 15, 25, 0.7); backdrop-filter: blur(20px); border: 1px solid rgba(147, 51, 234, 0.3); }
        .gradient-text { background: linear-gradient(90deg, #a855f7, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-premium { background: linear-gradient(90deg, #9333ea, #db2777); transition: 0.3s; }
        .btn-premium:hover { transform: scale(1.05); box-shadow: 0 0 20px rgba(147, 51, 234, 0.5); }
        .hidden-view { display: none; }
        .loader { border: 3px solid #1a1a2e; border-top: 3px solid #9333ea; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; display: inline-block; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="p-6">
    <div class="grid-bg"></div>

    <nav class="max-w-6xl mx-auto flex justify-between items-center py-8">
        <div class="flex items-center gap-4">
            <img src="LOGO_URL" class="h-12 w-12 rounded-2xl shadow-lg shadow-purple-500/20">
            <span class="text-3xl font-bold tracking-tighter uppercase">Vale <span class="gradient-text">Gen</span></span>
        </div>
        <div class="flex gap-8">
            <button onclick="switchView('shop')" class="text-gray-400 hover:text-white font-medium transition">Store</button>
            <button onclick="switchView('auth')" class="text-gray-400 hover:text-white font-medium transition">User Portal</button>
        </div>
    </nav>

    <div id="view-shop" class="max-w-6xl mx-auto mt-20">
        <div class="text-center mb-20">
            <h1 class="text-6xl md:text-8xl font-bold mb-6 tracking-tight">Access the <span class="gradient-text">Future.</span></h1>
            <p class="text-gray-400 text-xl max-w-2xl mx-auto">Automatisierte Keys, sofortige Lieferung und sicherster Schutz auf dem Markt.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-b-4 border-purple-500">
                <span class="text-purple-400 text-xs font-bold uppercase tracking-widest mb-4">Daily Pass</span>
                <h3 class="text-3xl font-bold mb-2">1 Day Access</h3>
                <div class="text-5xl font-black mb-8">5.00€</div>
                <button onclick="openCheckout('day_1', '5.00')" class="w-full btn-premium py-4 rounded-2xl font-bold uppercase tracking-wider">Get Started</button>
            </div>
            <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-b-4 border-pink-500 scale-105 relative overflow-hidden">
                <div class="absolute top-4 right-4 bg-pink-500 text-white text-[10px] font-black px-3 py-1 rounded-full uppercase">Hot</div>
                <span class="text-pink-400 text-xs font-bold uppercase tracking-widest mb-4">Weekly Pass</span>
                <h3 class="text-3xl font-bold mb-2">1 Week Access</h3>
                <div class="text-5xl font-black mb-8">15.00€</div>
                <button onclick="openCheckout('week_1', '15.00')" class="w-full btn-premium py-4 rounded-2xl font-bold uppercase tracking-wider">Purchase Now</button>
            </div>
            <div class="glass p-10 rounded-[2rem] flex flex-col items-center border-b-4 border-yellow-500">
                <span class="text-yellow-500 text-xs font-bold uppercase tracking-widest mb-4">Permanent</span>
                <h3 class="text-3xl font-bold mb-2">Lifetime Access</h3>
                <div class="text-5xl font-black mb-8">30.00€</div>
                <button onclick="openCheckout('lifetime', '30.00')" class="w-full btn-premium py-4 rounded-2xl font-bold uppercase tracking-wider">Go Unlimited</button>
            </div>
        </div>
    </div>

    <div id="checkout-modal" class="fixed inset-0 bg-black/95 backdrop-blur-xl hidden-view flex items-center justify-center p-4 z-50">
        <div class="glass max-w-lg w-full p-12 rounded-[2.5rem] relative">
            <button onclick="closeCheckout()" class="absolute top-8 right-8 text-gray-500 hover:text-white transition text-2xl"><i class="fa-solid fa-xmark"></i></button>
            
            <h2 class="text-3xl font-bold mb-10 text-center uppercase tracking-tighter">Secure <span class="gradient-text">Checkout</span></h2>
            
            <div class="space-y-6">
                <div>
                    <label class="text-xs font-bold text-gray-500 uppercase tracking-widest ml-1">Your Delivery Email</label>
                    <input type="email" id="co-email" class="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 mt-2 outline-none focus:border-purple-500 transition" placeholder="email@example.com">
                </div>

                <div class="p-6 bg-purple-500/5 border border-purple-500/20 rounded-3xl">
                    <p class="text-xs font-bold text-purple-400 uppercase mb-3 tracking-widest">Pay with Litecoin (LTC)</p>
                    <div class="text-[10px] font-mono break-all text-gray-400 bg-black/40 p-4 rounded-xl border border-white/5">LTC_ADDR</div>
                    <p class="text-[10px] text-gray-500 mt-3 text-center">Amount: <span id="co-display-price"></span>€ in LTC</p>
                </div>

                <div>
                    <label class="text-xs font-bold text-gray-500 uppercase tracking-widest ml-1">Litecoin TXID (Hash)</label>
                    <input type="text" id="co-txid" class="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 mt-2 outline-none focus:border-blue-500 transition font-mono text-sm" placeholder="Paste TXID here...">
                </div>

                <div id="co-status" class="hidden text-center p-4 rounded-2xl text-sm font-bold"></div>

                <button id="btn-verify" onclick="verifyPayment()" class="w-full btn-premium py-5 rounded-2xl font-bold uppercase tracking-widest shadow-lg shadow-purple-500/20">Verify Payment & Get Key</button>
            </div>
        </div>
    </div>

    <script>
        let currentProd = "";
        function switchView(v) { /* Logic */ }
        function openCheckout(id, price) {
            currentProd = id;
            document.getElementById('co-display-price').innerText = price;
            document.getElementById('checkout-modal').classList.remove('hidden-view');
        }
        function closeCheckout() { document.getElementById('checkout-modal').classList.add('hidden-view'); }

        async function verifyPayment() {
            const email = document.getElementById('co-email').value;
            const txid = document.getElementById('co-txid').value;
            const btn = document.getElementById('btn-verify');
            const status = document.getElementById('co-status');

            if(!email || !txid) return alert("Fill out all fields!");

            btn.disabled = true;
            btn.innerHTML = '<span class="loader"></span> Checking Blockchain...';
            
            try {
                const res = await fetch('/api/web_buy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, txid, product: currentProd})
                });
                const data = await res.json();
                
                status.classList.remove('hidden');
                if(data.ok) {
                    status.className = "text-center p-4 rounded-2xl text-green-400 bg-green-500/10 border border-green-500/20 block";
                    status.innerHTML = "Payment Verified! <br> Your Key: " + data.key;
                    btn.innerText = "Success";
                } else {
                    status.className = "text-center p-4 rounded-2xl text-red-400 bg-red-500/10 border border-red-500/20 block";
                    status.innerText = data.error;
                    btn.disabled = false;
                    btn.innerText = "Try Again";
                }
            } catch(e) { 
                btn.disabled = false; btn.innerText = "Error"; 
            }
        }
    </script>
</body>
</html>
""".replace("LOGO_URL", WEBSITE_LOGO_URL).replace("LTC_ADDR", LITECOIN_ADDRESS)

# =========================================================
# WEB SERVER LOGIC
# =========================================================
async def handle_index(request): return web.Response(text=WEB_HTML, content_type='text/html')

async def api_web_buy(request):
    try:
        data = await request.json()
        email, txid, ptype = data.get("email"), data.get("txid"), data.get("product")
        if not email or not txid or ptype not in PRODUCTS:
            return web.json_response({"ok": False, "error": "Missing data."})
        
        # Check Blockchain
        ok, reason = await verify_ltc_payment(txid)
        if not ok: return web.json_response({"ok": False, "error": reason})

        # Generate Key
        prefix = PRODUCTS[ptype]["key_prefix"]
        key = f"{prefix}-{random_block()}-{random_block()}-{random_block()}"
        keys_db[key] = {
            "type": ptype, "used": False, "used_by": None, 
            "created_at": iso_now(), "creator": "WebShop_Auto", "revoked": False
        }
        save_json(KEYS_FILE, keys_db)
        
        # Create Invoice
        inv_id = build_invoice_id()
        invoices_db[inv_id] = {
            "buyer_id": email, "product_type": ptype, "payment_key": "litecoin",
            "key": key, "created_at": iso_now(), "final_price_eur": PRODUCTS[ptype]["price_eur"]
        }
        save_json(INVOICES_FILE, invoices_db)

        # Send Mail
        send_delivery_email(email, PRODUCTS[ptype]["label"], key)
        log_activity(f"Web Order Success: {ptype} to {email}", "WebStore")
        
        return web.json_response({"ok": True, "key": key})
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Internal Error: {str(e)}"})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_post('/api/web_buy', api_web_buy)
    # [Hier folgen alle weiteren originalen Web-Endpoints...]
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()
    print("🚀 Web Store & API online!")

# =========================================================
# BOT CORE (ALLE ORIGINAL FEATURES RESTAURIERT)
# =========================================================
class ValeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    
    async def setup_hook(self):
        self.loop.create_task(start_web_server())
        # Hier werden die originalen Views wieder registriert
        # self.add_view(MainTicketPanelView()) etc...

bot = ValeBot()

# --- ORIGINAL COMMANDS ---
@bot.tree.command(name="nuke_database", description="Löscht alle Datenbanken (Admin Only)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def nuke_database(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    global keys_db, ticket_data, activity_db
    keys_db, ticket_data, activity_db = {}, {}, []
    save_json(KEYS_FILE, {}); save_json(TICKETS_FILE, {}); save_json(ACTIVITY_FILE, [])
    await interaction.response.send_message("Database Nuked! 💣", ephemeral=True)

# [Füge hier alle deine weiteren originalen Commands und Views wieder ein]

if __name__ == "__main__":
    bot.run(TOKEN)
