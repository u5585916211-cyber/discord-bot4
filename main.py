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
if not TOKEN or not GUILD_ID_RAW: raise ValueError("TOKEN/GUILD_ID missing")
try: GUILD_ID = int(GUILD_ID_RAW)
except: raise ValueError("GUILD_ID must be int")

# =========================================================
# CONFIG
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
# Dein Logo-Link
LOGO_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371158242099351/analyst_klein.png"
PANEL_IMAGE = "https://media.discordapp.net/attachments/1477646233563566080/1487826817925513306/ChatGPT_Image_29._Marz_2026_16_52_23.png"
BANNER_URL = "https://media.discordapp.net/attachments/1490333042328211648/1490371157432467577/analyst.jpg"

LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"

# =========================================================
# DATABASES
# =========================================================
def load_db(file):
    if not os.path.exists(file):
        with open(file, "w") as f: json.dump({}, f)
        return {}
    with open(file, "r") as f:
        try: return json.load(f)
        except: return {}

def save_db(file, data):
    with open(file, "w") as f: json.dump(data, f, indent=4)

KEYS_FILE = "keys.json"; USERS_FILE = "web_users.json"; WEBKEYS_FILE = "web_keys.json"
INVOICES_FILE = "invoices.json"; PROMOS_FILE = "promos.json"; BLACKLIST_FILE = "blacklist.json"

PRODUCTS = {
    "day_1": {"label": "1 Day", "price": 5, "duration": timedelta(days=1), "prefix": "GEN-1D"},
    "week_1": {"label": "1 Week", "price": 15, "duration": timedelta(weeks=1), "prefix": "GEN-1W"},
    "lifetime": {"label": "Lifetime", "price": 30, "duration": None, "prefix": "GEN-LT"}
}

PAYMENTS = {"paypal": "💸 PayPal", "litecoin": "🪙 Litecoin", "paysafecard": "💳 Paysafecard", "amazoncard": "🎁 Amazon"}

intents = discord.Intents.default(); intents.guilds = True; intents.members = True; intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

ticket_data = {}; web_sessions = {}

# =========================================================
# 🌍 WEB DASHBOARD HTML (FULL UI FIX)
# =========================================================
WEB_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vale Gen | Command Center</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #08080c; color: #e2e8f0; }
        .neon-border { border: 1px solid rgba(147, 51, 234, 0.3); box-shadow: 0 0 15px rgba(147, 51, 234, 0.1); }
        .neon-text { color: #a855f7; text-shadow: 0 0 10px rgba(168, 85, 247, 0.5); }
        .sidebar-btn { display: flex; align-items: center; width: 100%; padding: 0.75rem 1rem; border-radius: 0.75rem; transition: 0.2s; color: #94a3b8; }
        .sidebar-btn:hover { background: rgba(168, 85, 247, 0.1); color: white; }
        .sidebar-btn.active { background: #9333ea; color: white; box-shadow: 0 0 15px rgba(147, 51, 234, 0.4); }
        .glass-card { background: rgba(15, 15, 25, 0.8); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.05); }
        .tab-content { display: none; } .tab-content.active { display: block; animation: fadeIn 0.3s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="flex h-screen overflow-hidden">

    <div id="view-auth" class="fixed inset-0 z-50 flex items-center justify-center bg-[#08080c]">
        <div class="glass-card p-10 rounded-3xl w-full max-w-md neon-border text-center">
            <img src="LOGO_URL_PLACEHOLDER" class="h-20 mx-auto mb-6 drop-shadow-[0_0_15px_rgba(168,85,247,0.6)]">
            <h1 class="text-3xl font-black mb-8 tracking-tighter">VALE <span class="neon-text">GEN</span></h1>
            
            <div class="flex gap-2 mb-8 bg-black/40 p-1 rounded-xl">
                <button onclick="setAuthMode('login')" id="tab-l" class="flex-1 py-2 rounded-lg font-bold bg-purple-600 text-white">LOGIN</button>
                <button onclick="setAuthMode('register')" id="tab-r" class="flex-1 py-2 rounded-lg font-bold text-gray-400">REGISTER</button>
            </div>

            <div id="auth-form" class="space-y-4">
                <input type="text" id="user" placeholder="Username" class="w-full bg-black/60 border border-white/10 rounded-xl px-4 py-3 outline-none focus:border-purple-500 transition">
                <input type="password" id="pass" placeholder="Password" class="w-full bg-black/60 border border-white/10 rounded-xl px-4 py-3 outline-none focus:border-purple-500 transition">
                <input type="text" id="invite" placeholder="Invite Key (VALE-...)" class="w-full hidden bg-black/60 border border-white/10 rounded-xl px-4 py-3 outline-none focus:border-purple-500 transition">
                <button onclick="submitAuth()" class="w-full bg-purple-600 hover:bg-purple-500 py-4 rounded-xl font-black transition shadow-lg shadow-purple-900/20 uppercase tracking-widest">Access System</button>
            </div>
            <p id="auth-msg" class="mt-4 text-red-400 text-sm font-bold hidden"></p>
        </div>
    </div>

    <div id="view-main" class="flex w-full h-full hidden">
        <aside class="w-64 glass-card border-r border-white/5 flex flex-col p-4">
            <div class="flex items-center gap-3 px-2 mb-10">
                <img src="LOGO_URL_PLACEHOLDER" class="h-10">
                <span class="font-black text-xl tracking-tighter">VALE <span class="neon-text">SYSTEM</span></span>
            </div>
            <nav class="space-y-2 flex-1">
                <button onclick="showTab('dash')" id="btn-dash" class="sidebar-btn active"><i class="fa-solid fa-house w-6"></i> Dashboard</button>
                <button onclick="showTab('keys')" id="btn-keys" class="sidebar-btn"><i class="fa-solid fa-key w-6"></i> Keys</button>
                <button onclick="showTab('promos')" id="btn-promos" class="sidebar-btn"><i class="fa-solid fa-ticket w-6"></i> Promos</button>
                <button onclick="showTab('broadcast')" id="btn-broadcast" class="sidebar-btn"><i class="fa-solid fa-bullhorn w-6"></i> Broadcast</button>
            </nav>
            <button onclick="logout()" class="sidebar-btn text-red-400 hover:bg-red-500/10 mb-4"><i class="fa-solid fa-power-off w-6"></i> Logout</button>
        </aside>

        <main class="flex-1 overflow-y-auto p-8">
            <div id="tab-dash" class="tab-content active">
                <div class="grid grid-cols-3 gap-6 mb-8">
                    <div class="glass-card p-6 rounded-2xl border-l-4 border-purple-500">
                        <p class="text-gray-400 text-xs font-bold uppercase tracking-wider">Total Revenue</p>
                        <h2 id="val-rev" class="text-3xl font-black mt-1">0.00€</h2>
                    </div>
                    <div class="glass-card p-6 rounded-2xl border-l-4 border-pink-500">
                        <p class="text-gray-400 text-xs font-bold uppercase tracking-wider">Stock Active</p>
                        <h2 id="val-keys" class="text-3xl font-black mt-1">0</h2>
                    </div>
                    <div class="glass-card p-6 rounded-2xl border-l-4 border-blue-500">
                        <p class="text-gray-400 text-xs font-bold uppercase tracking-wider">Status</p>
                        <h2 class="text-3xl font-black mt-1 text-green-400">Online</h2>
                    </div>
                </div>
                <div class="glass-card p-6 rounded-2xl">
                    <h3 class="font-bold mb-4 text-purple-400">Sales Overview</h3>
                    <canvas id="salesChart" height="100"></canvas>
                </div>
            </div>

            <div id="tab-keys" class="tab-content">
                <div class="glass-card rounded-2xl overflow-hidden">
                    <table class="w-full text-left">
                        <thead class="bg-white/5 text-gray-400 text-xs uppercase">
                            <tr><th class="p-4">Key ID</th><th class="p-4">Type</th><th class="p-4">Creator</th><th class="p-4">Status</th></tr>
                        </thead>
                        <tbody id="key-list" class="divide-y divide-white/5"></tbody>
                    </table>
                </div>
            </div>
            
            <div id="tab-broadcast" class="tab-content">
                <div class="max-w-xl glass-card p-8 rounded-2xl neon-border">
                    <h2 class="text-xl font-bold mb-6">Send Global Broadcast</h2>
                    <input type="text" id="bc-title" placeholder="Broadcast Title" class="w-full bg-black/40 border border-white/10 p-3 rounded-xl mb-4 outline-none focus:border-purple-500">
                    <textarea id="bc-desc" rows="5" placeholder="Message content..." class="w-full bg-black/40 border border-white/10 p-3 rounded-xl mb-6 outline-none focus:border-purple-500"></textarea>
                    <button onclick="sendBC()" class="w-full bg-purple-600 py-3 rounded-xl font-bold hover:bg-purple-500 transition">Post to Discord</button>
                </div>
            </div>
        </main>
    </div>

    <script>
        let mode = 'login';
        let chart = null;

        function setAuthMode(m) {
            mode = m;
            document.getElementById('tab-l').className = m === 'login' ? 'flex-1 py-2 rounded-lg font-bold bg-purple-600 text-white' : 'flex-1 py-2 rounded-lg font-bold text-gray-400';
            document.getElementById('tab-r').className = m === 'register' ? 'flex-1 py-2 rounded-lg font-bold bg-purple-600 text-white' : 'flex-1 py-2 rounded-lg font-bold text-gray-400';
            document.getElementById('invite').classList.toggle('hidden', m === 'login');
        }

        async function api(path, data) {
            const token = localStorage.getItem('v_token');
            const res = await fetch(path, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Authorization': token},
                body: JSON.stringify(data)
            });
            if (res.status === 401 && path !== '/api/login' && path !== '/api/register') { logout(); }
            return res.json();
        }

        async function submitAuth() {
            const u = document.getElementById('user').value;
            const p = document.getElementById('pass').value;
            const i = document.getElementById('invite').value;
            const path = mode === 'login' ? '/api/login' : '/api/register';
            const res = await api(path, {user: u, pass: p, key: i});
            
            if (res.ok) {
                localStorage.setItem('v_token', res.token);
                document.getElementById('view-auth').classList.add('hidden');
                document.getElementById('view-main').classList.remove('hidden');
                loadStats();
            } else {
                const err = document.getElementById('auth-msg');
                err.innerText = res.error || 'Access Denied';
                err.classList.remove('hidden');
            }
        }

        function showTab(id) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-'+id).classList.add('active');
            document.getElementById('btn-'+id).classList.add('active');
            if(id === 'keys') loadKeys();
        }

        async function loadStats() {
            const d = await api('/api/stats', {});
            document.getElementById('val-rev').innerText = d.rev.toFixed(2) + '€';
            document.getElementById('val-keys').innerText = d.keys_count;
            
            const ctx = document.getElementById('salesChart').getContext('2d');
            if(chart) chart.destroy();
            chart = new Chart(ctx, {
                type: 'line',
                data: { labels: d.labels, datasets: [{label: 'Sales', data: d.data, borderColor: '#a855f7', tension: 0.4, fill: true, backgroundColor: 'rgba(168, 85, 247, 0.1)'}] },
                options: { plugins: {legend: {display: false}}, scales: { y: { grid: {color: '#1e293b'} }, x: { grid: {color: '#1e293b'} } } }
            });
        }

        async function loadKeys() {
            const d = await api('/api/keys', {});
            document.getElementById('key-list').innerHTML = Object.entries(d).reverse().map(([k,v]) => `
                <tr class="hover:bg-white/5 transition">
                    <td class="p-4 font-mono text-purple-400 text-xs">${k}</td>
                    <td class="p-4 text-sm">${v.type}</td>
                    <td class="p-4 text-sm text-gray-400">${v.created_by || 'System'}</td>
                    <td class="p-4"><span class="px-2 py-1 rounded text-[10px] font-bold ${v.used ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}">${v.used ? 'USED' : 'ACTIVE'}</span></td>
                </tr>
            `).join('');
        }

        async function sendBC() {
            const t = document.getElementById('bc-title').value;
            const d = document.getElementById('bc-desc').value;
            await api('/api/announce', {title: t, desc: d});
            alert('Broadcast sent!');
        }

        function logout() { localStorage.removeItem('v_token'); location.reload(); }

        window.onload = async () => {
            const t = localStorage.getItem('v_token');
            if (t) {
                const res = await fetch('/api/verify', {method: 'POST', headers: {'Authorization': t}});
                if (res.ok) {
                    document.getElementById('view-auth').classList.add('hidden');
                    document.getElementById('view-main').classList.remove('hidden');
                    loadStats();
                }
            }
        };
    </script>
</body>
</html>
""".replace("LOGO_URL_PLACEHOLDER", LOGO_URL)

# =========================================================
# 🌍 WEB SERVER LOGIC
# =========================================================
def get_user(request):
    token = request.headers.get("Authorization")
    return web_sessions.get(token)

async def handle_index(request): return web.Response(text=WEB_HTML, content_type='text/html')

async def api_register(request):
    d = await request.json(); u = d.get("user"); p = d.get("pass"); k = d.get("key", "").upper()
    wk = load_db(WEBKEYS_FILE); users = load_db(USERS_FILE)
    if not u or not p or k not in wk or wk[k].get("used"): return web.json_response({"ok": False, "error": "Invalid Key"})
    users[u] = {"pass": p, "role": wk[k]["role"]}; wk[k]["used"] = True
    save_db(USERS_FILE, users); save_db(WEBKEYS_FILE, wk)
    token = str(uuid.uuid4()); web_sessions[token] = {"user": u, "role": users[u]["role"]}
    return web.json_response({"ok": True, "token": token})

async def api_login(request):
    d = await request.json(); u = d.get("user"); p = d.get("pass")
    users = load_db(USERS_FILE)
    if u in users and users[u]["pass"] == p:
        token = str(uuid.uuid4()); web_sessions[token] = {"user": u, "role": users[u]["role"]}
        return web.json_response({"ok": True, "token": token})
    return web.json_response({"ok": False}, status=401)

async def api_verify(request):
    return web.Response(status=200) if get_user(request) else web.Response(status=401)

async def api_stats(request):
    if not get_user(request): return web.Response(status=401)
    inv = load_db(INVOICES_FILE); keys = load_db(KEYS_FILE)
    rev = sum(float(v.get("final_price_eur", 0)) for v in inv.values())
    return web.json_response({"rev": rev, "keys_count": len(keys), "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "data": [0,0,0,0,0,0,rev]})

async def api_keys(request):
    if not get_user(request): return web.Response(status=401)
    return web.json_response(load_db(KEYS_FILE))

async def api_announce(request):
    u = get_user(request)
    if not u or u["role"] != "admin": return web.Response(status=401)
    d = await request.json(); ch = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if ch: await ch.send(embed=discord.Embed(title=d["title"], description=d["desc"], color=COLOR_MAIN))
    return web.json_response({"ok": True})

async def start_web():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_post('/api/login', api_login); app.router.add_post('/api/register', api_register)
    app.router.add_post('/api/verify', api_verify); app.router.add_post('/api/stats', api_stats)
    app.router.add_post('/api/keys', api_keys); app.router.add_post('/api/announce', api_announce)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()

# =========================================================
# 🤖 BOT LOGIC (TICKETS, COMMANDS)
# =========================================================
@bot.tree.command(name="gen_admin_key")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def gak(i: discord.Interaction):
    if not i.user.guild_permissions.administrator: return
    nk = f"VALE-ADMIN-{uuid.uuid4().hex[:6].upper()}"
    db = load_db(WEBKEYS_FILE); db[nk] = {"role": "admin", "used": False}; save_db(WEBKEYS_FILE, db)
    await i.response.send_message(f"Admin Key: `{nk}`", ephemeral=True)

@bot.tree.command(name="ticket")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def stp(i: discord.Interaction):
    emb = discord.Embed(title="✦ VALE GEN TICKET CENTER ✦", description="Support & Buy", color=COLOR_MAIN)
    emb.set_image(url=PANEL_IMAGE)
    await i.response.send_message(embed=emb, view=MainTicketPanelView())

class MainTicketPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="💠")
    async def s(self, i, b): await self.c(i, "support")
    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, emoji="🛒")
    async def buy(self, i, b): await self.c(i, "buy")
    async def c(self, i, t):
        cat = i.guild.get_channel(BUY_CATEGORY_ID if t=="buy" else SUPPORT_CATEGORY_ID)
        ch = await i.guild.create_text_channel(name=f"{t}-{i.user.name}", category=cat)
        await ch.send(f"{i.user.mention}", embed=discord.Embed(title=f"{t.title()} Ticket", description="Welcome!", color=COLOR_MAIN))
        await i.response.send_message(f"Ticket: {ch.mention}", ephemeral=True)

@bot.tree.command(name="send_rules")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def sr(i: discord.Interaction):
    emb = discord.Embed(title="📜 Server Rules", description="**1. Be Respectful**\n**2. No Scam**\n**3. Tickets only**", color=COLOR_MAIN)
    emb.set_image(url=BANNER_URL)
    await i.channel.send(embed=emb); await i.response.send_message("Posted", ephemeral=True)

@bot.event
async def on_member_join(m):
    ch = m.guild.get_channel(WELCOME_CHANNEL_ID)
    emb = discord.Embed(title="Welcome!", description=f"Welcome {m.mention} to **{SERVER_NAME}**.", color=COLOR_MAIN)
    emb.set_author(name=SERVER_NAME, icon_url=WELCOME_THUMBNAIL_URL)
    emb.set_thumbnail(url=WELCOME_THUMBNAIL_URL); emb.set_image(url=BANNER_URL)
    if ch: await ch.send(embed=emb)

@bot.event
async def on_ready():
    bot.loop.create_task(start_web())
    try:
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    except: pass
    print(f"Bot ready: {bot.user}")

bot.run(TOKEN)
