import os, re, json, uuid, asyncio, aiohttp
from datetime import datetime, timedelta, timezone
from aiohttp import web
import discord
from discord.ext import commands, tasks
from discord import app_commands

# =========================================================
# ENV
# =========================================================
TOKEN = os.getenv("TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

if not TOKEN or not GUILD_ID_RAW: raise ValueError("TOKEN oder GUILD_ID fehlt in Railway.")
try: GUILD_ID = int(GUILD_ID_RAW)
except ValueError: raise ValueError("GUILD_ID muss eine Zahl sein.")

# =========================================================
# CONFIG & LINKS
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
WEBSITE_LOGO_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png"

WELCOME_THUMBNAIL_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png"
WELCOME_BANNER_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371157432467577/analyst.jpg"
PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1477646233563566080/1487826817925513306/ChatGPT_Image_29._Marz_2026_16_52_23.png"

PAYPAL_EMAIL = "hydrasupfivem@gmail.com"
LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"
ETHEREUM_ADDRESS = "0x6Ba2afdA7e61817f9c27f98ffAfe9051F9ad8167"
SOLANA_ADDRESS = "DnzXgySsPnSdEKsMJub21dBjM6bcT2jtic73VeutN3p4"

LTC_MIN_CONFIRMATIONS = 1
EXPIRY_REMINDER_HOURS = 12

COLOR_MAIN = 0x9333EA; COLOR_SUPPORT = 0x3BA7FF; COLOR_BUY = 0x57F287
COLOR_WARN = 0xFEE75C; COLOR_DENY = 0xED4245; COLOR_LOG = 0x2B2D31; COLOR_SUCCESS = 0x57F287
COLOR_INFO = 0x9333EA; COLOR_ADMIN = 0x9B59B6; COLOR_WELCOME = 0xDD0000

# =========================================================
# DATABASES
# =========================================================
KEYS_FILE = "keys.json"; REDEEMED_FILE = "redeemed.json"; USED_TXIDS_FILE = "used_txids.json"
USED_PAYSAFE_FILE = "used_paysafecodes.json"; USED_AMAZON_FILE = "used_amazoncodes.json"
BLACKLIST_FILE = "blacklist.json"; INVOICES_FILE = "invoices.json"; PROMOS_FILE = "promos.json"
ACTIVITY_FILE = "activity.json"; WEBKEYS_FILE = "web_keys.json"; USERS_FILE = "web_users.json"

PRODUCTS = {
    "day_1": {"label": "1 Day", "price_eur": 5, "duration": timedelta(days=1), "key_prefix": "GEN-1D"},
    "week_1": {"label": "1 Week", "price_eur": 15, "duration": timedelta(weeks=1), "key_prefix": "GEN-1W"},
    "lifetime": {"label": "Lifetime", "price_eur": 30, "duration": None, "key_prefix": "GEN-LT"}
}
PAYMENTS = {"paypal": {"label": "PayPal", "emoji": "💸"}, "litecoin": {"label": "Litecoin", "emoji": "🪙"}, "ethereum": {"label": "Ethereum", "emoji": "🔷"}, "solana": {"label": "Solana", "emoji": "🟣"}, "paysafecard": {"label": "Paysafecard", "emoji": "💳"}, "amazoncard": {"label": "Amazon Card", "emoji": "🎁"}}

intents = discord.Intents.default(); intents.guilds = True; intents.members = True; intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

ticket_data = {}; keys_db = {}; redeemed_db = {}; used_txids_db = {}; used_paysafe_db = {}; used_amazon_db = {}
blacklist_db = {}; invoices_db = {}; promos_db = {}; activity_db = []; webkeys_db = {}; users_db = {}
web_sessions = {}

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f: json.dump(default, f)
        return default
    with open(path, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return default
def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

def log_activity(action, user="System"):
    global activity_db
    activity_db.insert(0, {"time": iso_now(), "user": str(user), "action": action})
    activity_db = activity_db[:50]; save_json(ACTIVITY_FILE, activity_db)

def now_utc(): return datetime.now(timezone.utc)
def iso_now(): return now_utc().isoformat()
def random_block(length=4): return uuid.uuid4().hex[:length].upper()
def is_blacklisted(user_id: int): return str(user_id) in blacklist_db

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
        body { font-family: 'Inter', sans-serif; background-color: #050505; color: #e5e7eb; }
        .glass { background: rgba(20, 10, 30, 0.7); backdrop-filter: blur(15px); border: 1px solid rgba(168, 85, 247, 0.2); }
        .glow-text { text-shadow: 0 0 20px rgba(168, 85, 247, 0.8); }
        .glow-box { box-shadow: 0 0 30px rgba(147, 51, 234, 0.3); }
        .hidden-view { display: none !important; }
        .tab-content { display: none; } .tab-content.active { display: block; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: #050505; } ::-webkit-scrollbar-thumb { background: #9333ea; border-radius: 4px; }
    </style>
</head>
<body class="flex h-screen overflow-hidden selection:bg-purple-500 selection:text-white">
    <div id="view-auth" class="flex w-full h-full items-center justify-center relative">
        <div class="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-5"></div>
        <div class="glass p-10 rounded-3xl max-w-md w-full relative z-10 glow-box">
            <div class="text-center mb-8"><img src="LOGO_URL_PLACEHOLDER" class="h-24 mx-auto mb-4 drop-shadow-[0_0_15px_rgba(168,85,247,0.8)]"><h1 class="text-3xl font-black text-white glow-text">VALE GEN</h1></div>
            <div class="flex border-b border-purple-500/30 mb-6"><button onclick="switchAuth('login')" id="auth-tab-login" class="flex-1 pb-3 text-purple-400 font-bold border-b-2 border-purple-500 transition">LOGIN</button><button onclick="switchAuth('register')" id="auth-tab-register" class="flex-1 pb-3 text-gray-500 font-bold hover:text-gray-300 transition border-b-2 border-transparent">REGISTER</button></div>
            <div id="form-login" class="space-y-4"><input type="text" id="l-user" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white outline-none" placeholder="Username"><input type="password" id="l-pass" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white outline-none" placeholder="Password"><button onclick="login()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-3 rounded-xl shadow-lg">LOGIN</button></div>
            <div id="form-register" class="space-y-4 hidden-view"><input type="text" id="r-user" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white outline-none" placeholder="Username"><input type="password" id="r-pass" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-white outline-none" placeholder="Password"><input type="text" id="r-key" class="w-full bg-black/50 border border-purple-500/30 rounded-xl px-4 py-3 text-purple-400 font-mono" placeholder="Invite Key"><button onclick="register()" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-3 rounded-xl shadow-lg">CREATE ACCOUNT</button></div>
            <p id="auth-error" class="text-red-400 mt-4 text-sm text-center font-bold hidden"></p>
        </div>
    </div>
    <div id="view-admin" class="flex w-full h-full hidden-view">
        <aside class="w-64 glass border-r border-purple-500/20 flex flex-col justify-between z-10">
            <div><div class="h-24 flex items-center justify-center border-b border-purple-500/20"><img src="LOGO_URL_PLACEHOLDER" class="h-12 mr-3"><span class="text-xl font-black text-white glow-text">ADMIN</span></div>
                <nav class="p-4 space-y-2 mt-2">
                    <button onclick="nav('dash')" id="btn-dash" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-purple-300 font-bold"><i class="fa-solid fa-chart-pie w-6"></i> Dashboard</button>
                    <button onclick="nav('keys')" id="btn-keys" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400"><i class="fa-solid fa-key w-6"></i> Keys</button>
                    <button onclick="nav('promos')" id="btn-promos" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400"><i class="fa-solid fa-tags w-6"></i> Promos</button>
                    <button onclick="nav('announce')" id="btn-announce" class="nav-btn w-full text-left py-3 px-4 rounded-xl text-gray-400"><i class="fa-solid fa-bullhorn w-6"></i> Broadcast</button>
                </nav>
            </div><button onclick="logout()" class="p-6 text-red-400 font-bold">LOGOUT</button>
        </aside>
        <main class="flex-1 overflow-y-auto p-8 relative">
            <div id="dash" class="tab-content active"><div id="stat-rev" class="text-4xl font-black glow-text mb-4">0.00€</div><canvas id="revenueChart" height="100"></canvas><div id="activity-feed" class="mt-8 space-y-2"></div></div>
            <div id="keys" class="tab-content"><table class="w-full text-left"><tbody id="table-keys"></tbody></table></div>
            <div id="promos" class="tab-content"><button onclick="createPromo()" class="bg-pink-600 p-2 rounded">Create Promo</button><tbody id="table-promos"></tbody></div>
            <div id="announce" class="tab-content"><input id="ann-title" class="w-full bg-black/50 p-2 mb-2"><textarea id="ann-desc" class="w-full bg-black/50 p-2 mb-2"></textarea><button onclick="sendAnnounce()" class="bg-blue-600 p-2 rounded">Send</button></div>
        </main>
    </div>
    <div id="view-reseller" class="flex w-full h-full hidden-view p-8"><div id="r-name" class="text-xl text-purple-400 mb-4"></div><div id="my-keys"></div><button onclick="genKey('day_1')" class="bg-purple-600 p-2 rounded">Gen 1 Day</button></div>
    <div id="key-modal" class="fixed inset-0 bg-black/90 flex items-center justify-center hidden-view"><input id="new-key" class="bg-black border p-4 text-purple-400" readonly><button onclick="closeModal()">Close</button></div>
    <script>
        let myChart=null;
        function switchAuth(t){document.getElementById('form-login').classList.add('hidden-view');document.getElementById('form-register').classList.add('hidden-view');document.getElementById('form-'+t).classList.remove('hidden-view');}
        async function apiCall(ep, d){const t=localStorage.getItem('v_token');const h={'Content-Type':'application/json'};if(t)h['Authorization']=t;const res=await fetch(ep,{method:'POST',headers:h,body:JSON.stringify(d)});if(res.status===401&&ep!=='/api/login'&&ep!=='/api/register'){logout();throw new Error();}return res;}
        async function login(){const u=document.getElementById('l-user').value,p=document.getElementById('l-pass').value;const res=await apiCall('/api/login',{user:u,pass:p});if(res.ok){const d=await res.json();localStorage.setItem('v_token',d.token);initApp(d.role,d.user);}else alert('Fail');}
        async function register(){const u=document.getElementById('r-user').value,p=document.getElementById('r-pass').value,k=document.getElementById('r-key').value;const res=await apiCall('/api/register',{user:u,pass:p,key:k});if(res.ok){const d=await res.json();localStorage.setItem('v_token',d.token);initApp(d.role,d.user);}else alert('Fail');}
        function logout(){localStorage.removeItem('v_token');location.reload();}
        async function checkAuthOnLoad(){const t=localStorage.getItem('v_token');if(t){const res=await apiCall('/api/verify',{});if(res.ok){const d=await res.json();initApp(d.role,d.user);}else logout();}}
        function initApp(r,n){document.getElementById('view-auth').classList.add('hidden-view');if(r==='admin'){document.getElementById('view-admin').classList.remove('hidden-view');nav('dash');}else{document.getElementById('view-reseller').classList.remove('hidden-view');}}
        function nav(t){document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active'));document.getElementById(t).classList.add('active');if(t==='dash')loadDashboard();}
        async function loadDashboard(){const res=await apiCall('/api/stats',{});const d=await res.json();document.getElementById('stat-rev').innerText=d.total_revenue.toFixed(2)+'€';}
        function closeModal(){document.getElementById('key-modal').classList.add('hidden-view');}
        window.onload=checkAuthOnLoad;
    </script>
</body>
</html>
""".replace("LOGO_URL_PLACEHOLDER", WEBSITE_LOGO_URL)

# --- API HANDLERS ---
def get_user_from_token(request):
    token = request.headers.get("Authorization")
    return web_sessions.get(token) if token else None

async def handle_index(request): return web.Response(text=WEB_HTML, content_type='text/html')

async def api_register(request):
    d=await request.json(); u=d.get("user"); p=d.get("pass"); k=d.get("key","").upper()
    if not u or not p or not k: return web.json_response({"error":"Missing fields"},status=400)
    if u in users_db: return web.json_response({"error":"Username exists"},status=400)
    if k not in webkeys_db or webkeys_db[k].get("used"): return web.json_response({"error":"Invalid Key"},status=400)
    role=webkeys_db[k]["role"]; users_db[u]={"pass":p,"role":role}; webkeys_db[k]["used"]=True
    save_json(USERS_FILE, users_db); save_json(WEBKEYS_FILE, webkeys_db)
    t=str(uuid.uuid4()); web_sessions[t]={"user":u,"role":role}
    return web.json_response({"ok":True,"token":t,"role":role,"user":u})

async def api_login(request):
    d=await request.json(); u=d.get("user"); p=d.get("pass")
    if u in users_db and users_db[u]["pass"]==p:
        t=str(uuid.uuid4()); r=users_db[u]["role"]; web_sessions[t]={"user":u,"role":r}
        return web.json_response({"ok":True,"token":t,"role":r,"user":u})
    return web.Response(status=401)

async def api_verify(request):
    u=get_user_from_token(request)
    return web.json_response({"ok":True,"role":u["role"],"user":u["user"]}) if u else web.Response(status=401)

# --- PROTECTED HANDLERS (FIXED SYNTAX) ---
async def api_stats(request):
    u = get_user_from_token(request)
    if not u or u["role"] != "admin": return web.Response(status=401)
    rev = sum(float(v.get("final_price_eur", 0)) for v in invoices_db.values())
    return web.json_response({"total_revenue": rev, "buyers_today": 0, "active_keys": len(keys_db), "chart_labels": [], "chart_data": []})

async def api_activity(request):
    u = get_user_from_token(request)
    if not u or u["role"] != "admin": return web.Response(status=401)
    return web.json_response(activity_db)

async def api_keys(request):
    u = get_user_from_token(request)
    if not u or u["role"] != "admin": return web.Response(status=401)
    return web.json_response(keys_db)

async def api_promos(request):
    u = get_user_from_token(request)
    if not u or u["role"] != "admin": return web.Response(status=401)
    return web.json_response(promos_db)

async def api_announce(request):
    u = get_user_from_token(request)
    if not u or u["role"] != "admin": return web.Response(status=401)
    d = await request.json(); ch = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if ch: await ch.send(embed=discord.Embed(title=d["title"], description=d["desc"], color=COLOR_MAIN))
    return web.json_response({"ok": True})

async def api_blacklist(request):
    u = get_user_from_token(request)
    if not u or u["role"] != "admin": return web.Response(status=401)
    return web.json_response(blacklist_db)

async def api_reseller_gen(request):
    u = get_user_from_token(request)
    if not u or u["role"] != "reseller": return web.Response(status=401)
    pt = (await request.json()).get("t", "day_1"); k = f"GEN-{random_block()}"
    keys_db[k] = {"type": pt, "used": False, "created_by": u["user"]}; save_json(KEYS_FILE, keys_db)
    return web.json_response({"key": k})

async def start_web_server():
    app=web.Application(); app.router.add_get('/', handle_index)
    app.router.add_post('/api/login', api_login); app.router.add_post('/api/register', api_register); app.router.add_post('/api/verify', api_verify)
    app.router.add_post('/api/stats', api_stats); app.router.add_post('/api/activity', api_activity); app.router.add_post('/api/keys', api_keys)
    app.router.add_post('/api/promos', api_promos); app.router.add_post('/api/announce', api_announce)
    app.router.add_post('/api/blacklist', api_blacklist); app.router.add_post('/api/reseller/generate', api_reseller_gen)
    runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,'0.0.0.0',8080); await site.start()

# --- BOT FUNCTIONS ---
async def redeem_key(g, m, k):
    if k not in keys_db or keys_db[k]["used"]: return False, "Fail"
    r = g.get_role(REDEEM_ROLE_ID); await m.add_roles(r); keys_db[k]["used"] = True; save_json(KEYS_FILE, keys_db); return True, "Ok"

@bot.tree.command(name="gen_admin_key")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gak(i):
    nk = f"VALE-ADMIN-{random_block(6)}"; webkeys_db[nk] = {"role": "admin", "used": False}; save_json(WEBKEYS_FILE, webkeys_db)
    await i.response.send_message(f"Key: `{nk}`", ephemeral=True)

@bot.tree.command(name="ticket")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def stp(i):
    emb = discord.Embed(title="✦ VALE GEN TICKET CENTER ✦", color=COLOR_MAIN); emb.set_image(url=PANEL_IMAGE_URL)
    await i.response.send_message(embed=emb, view=MainTicketPanelView())

@bot.tree.command(name="send_rules")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def sr(i):
    emb = discord.Embed(title="📜 Server Rules", description="**1. Respect**\n**2. No Scam**", color=COLOR_MAIN); emb.set_image(url=WELCOME_BANNER_URL)
    await i.channel.send(embed=emb); await i.response.send_message("Posted", ephemeral=True)

@bot.event
async def on_member_join(m):
    ch = m.guild.get_channel(WELCOME_CHANNEL_ID)
    emb = discord.Embed(title="Welcome!", description=f"Hi {m.mention}", color=COLOR_MAIN)
    emb.set_thumbnail(url=WELCOME_THUMBNAIL_URL); emb.set_image(url=WELCOME_BANNER_URL)
    if ch: await ch.send(embed=emb)

@bot.event
async def on_ready():
    global keys_db, redeemed_db, blacklist_db, invoices_db, promos_db, webkeys_db, users_db, activity_db
    keys_db=load_json(KEYS_FILE,{}); invoices_db=load_json(INVOICES_FILE,{})
    promos_db=load_json(PROMOS_FILE,{}); webkeys_db=load_json(WEBKEYS_FILE,{})
    users_db=load_json(USERS_FILE,{}); activity_db=load_json(ACTIVITY_FILE,[])
    bot.loop.create_task(start_web_server())
    try: bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID)); await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    except: pass
    print(f"Bot ready: {bot.user}")

bot.run(TOKEN)
