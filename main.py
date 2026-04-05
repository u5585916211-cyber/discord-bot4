import os
import re
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp
import discord
from discord.ext import commands, tasks
from discord import app_commands

# =========================================================
# ENV
# =========================================================
TOKEN = os.getenv("TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

if not TOKEN:
    raise ValueError("TOKEN is missing. Add it in Railway Variables.")

if not GUILD_ID_RAW:
    raise ValueError("GUILD_ID is missing. Add it in Railway Variables.")

try:
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError:
    raise ValueError("GUILD_ID must be a valid integer.")

# =========================================================
# CONFIG
# =========================================================
BUY_CATEGORY_ID = 1490336321913356459
SUPPORT_CATEGORY_ID = 1490336154044727407

STAFF_ROLE_ID = 1490327988800065597
REVIEW_CHANNEL_ID = 1490330053836542082
PAYSAFE_CODES_CHANNEL_ID = 1490335565256851466
AMAZON_CODES_CHANNEL_ID = 1490335639357362298
INVOICE_CHANNEL_ID = 1490336085568524550
ADMIN_PANEL_CHANNEL_ID = 1490335327619911873
VOUCH_CHANNEL_ID = 123456789012345678  # ⚠️ ERSETZE DIES durch deine Vouch-Kanal ID

REDEEM_ROLE_ID = 1490321899266506913
RESELLER_ROLE_ID = 1490335130890534923

PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1490329787976253510/1490371088494887053/asdawdwaw.jpg?ex=69d3cfbd&is=69d27e3d&hm=2002f406c99904440eff8662415e9ce8e46d5a64b9cb5da5fe7d43660c0f449f&=&format=webp&width=652&height=652"

PAYPAL_EMAIL = "hydrasupfivem@gmail.com"
LITECOIN_ADDRESS = "ltc1qn39l4h59x4s0hr90pn3p4qflhhm5ahe6x9u6jg"
ETHEREUM_ADDRESS = "0x6Ba2afdA7e61817f9c27f98ffAfe9051F9ad8167"
SOLANA_ADDRESS = "DnzXgySsPnSdEKsMJub21dBjM6bcT2jtic73VeutN3p4"

LTC_MIN_CONFIRMATIONS = 1
EXPIRY_REMINDER_HOURS = 12

# =========================================================
# COLORS
# =========================================================
COLOR_MAIN = 0x6D5DF6
COLOR_SUPPORT = 0x3BA7FF
COLOR_BUY = 0x57F287
COLOR_WARN = 0xFEE75C
COLOR_DENY = 0xED4245
COLOR_LOG = 0x2B2D31
COLOR_SUCCESS = 0x57F287
COLOR_INFO = 0x5865F2
COLOR_PENDING = 0xFAA61A
COLOR_ADMIN = 0x9B59B6

# =========================================================
# FILES
# =========================================================
KEYS_FILE = "keys.json"
REDEEMED_FILE = "redeemed.json"
USED_TXIDS_FILE = "used_txids.json"
USED_PAYSAFE_FILE = "used_paysafecodes.json"
USED_AMAZON_FILE = "used_amazoncodes.json"
BLACKLIST_FILE = "blacklist.json"
INVOICES_FILE = "invoices.json"

# =========================================================
# PRODUCTS & PAYMENTS
# =========================================================
PRODUCTS = {
    "day_1": {
        "label": "1 Day",
        "price_eur": 5,
        "duration": timedelta(days=1),
        "key_prefix": "GEN-1D",
    },
    "week_1": {
        "label": "1 Week",
        "price_eur": 15,
        "duration": timedelta(weeks=1),
        "key_prefix": "GEN-1W",
    },
    "lifetime": {
        "label": "Lifetime",
        "price_eur": 30,
        "duration": None,
        "key_prefix": "GEN-LT",
    }
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
# BOT
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ticket_data = {}
forwarded_paysafe_codes = {}
forwarded_amazon_codes = {}

keys_db = {}
redeemed_db = {}
used_txids_db = {}
used_paysafe_db = {}
used_amazon_db = {}
blacklist_db = {}
invoices_db = {}

# =========================================================
# JSON HELPERS
# =========================================================
def load_json(path: str, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default

    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# =========================================================
# HELPERS
# =========================================================
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso_now() -> str:
    return now_utc().isoformat()

def premium_divider() -> str:
    return "━━━━━━━━━━━━━━━━━━━━━━━━"

def short_txid(txid: str) -> str:
    if len(txid) < 20:
        return txid
    return f"{txid[:14]}...{txid[-14:]}"

def random_block(length=4) -> str:
    return uuid.uuid4().hex[:length].upper()

def is_blacklisted(user_id: int) -> bool:
    return str(user_id) in blacklist_db

def format_expiry(expires_at: str | None) -> str:
    if not expires_at:
        return "Never"
    try:
        dt = datetime.fromisoformat(expires_at)
        return f"<t:{int(dt.timestamp())}:F>"
    except Exception:
        return str(expires_at)

def parse_duration_string(duration_text: str) -> timedelta | None:
    txt = duration_text.strip().lower()
    match = re.fullmatch(r"(\d+)([dhw])", txt)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "d":
        return timedelta(days=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "w":
        return timedelta(weeks=value)
    return None

def build_invoice_id() -> str:
    return f"GEN-{uuid.uuid4().hex[:10].upper()}"

def is_reseller(member: discord.Member | None) -> bool:
    if member is None:
        return False
    return any(role.id == RESELLER_ROLE_ID for role in member.roles)

def get_price(product_key: str, member: discord.Member | None = None) -> float:
    base_price = PRODUCTS[product_key]["price_eur"]
    if is_reseller(member):
        return round(base_price * 0.5, 2)
    return float(base_price)

def format_price(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"

async def dm_user_safe(user: discord.abc.User, content: str = None, embed: discord.Embed = None):
    try:
        await user.send(content=content, embed=embed)
    except Exception:
        pass

def generate_key(product_type: str, ticket_id: int | None = None) -> str:
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
                "approved_in_ticket": ticket_id
            }
            save_json(KEYS_FILE, keys_db)
            return key

def create_invoice_record(
    invoice_id: str,
    buyer_id: int,
    product_type: str,
    payment_key: str,
    key: str,
    ticket_id: int,
    final_price_eur: float,
    reseller_discount: bool
):
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
        addresses = output.get("addresses", [])
        if expected_address in addresses:
            found = True
            total_received += int(output.get("value", 0))
    return found, total_received

async def fetch_ltc_tx(txid: str):
    url = f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as resp:
            if resp.status != 200:
                return None, f"API returned status {resp.status}"
            return await resp.json(), None

async def fetch_ltc_price_eur():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=eur"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("litecoin", {}).get("eur")

async def find_existing_ticket(guild: discord.Guild, user: discord.Member):
    for channel in guild.text_channels:
        if channel.topic == f"ticket_owner:{user.id}":
            return channel
    return None

def find_user_latest_key(user_id: int):
    user_id = str(user_id)
    latest_key = None
    latest_created = None
    for key, data in keys_db.items():
        if str(data.get("bound_user_id")) == user_id or str(data.get("used_by")) == user_id:
            created = data.get("created_at")
            if latest_created is None or (created and created > latest_created):
                latest_created = created
                latest_key = (key, data)
    return latest_key

# =========================================================
# LOGGING
# =========================================================
def make_log_embed(title: str, description: str, color: int = COLOR_LOG) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)

async def send_log(guild: discord.Guild, title: str, description: str, color: int = COLOR_LOG):
    ch = guild.get_channel(REVIEW_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        await ch.send(embed=make_log_embed(title, description, color))

# =========================================================
# EMBEDS
# =========================================================
def panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="✦ GEN TICKET CENTER ✦",
        description=(
            f"{premium_divider()}\n"
            f"**Open a private ticket below**\n\n"
            f"💠 **Support**\n> Help, questions, issues\n\n"
            f"🛒 **Buy**\n> Orders, payments, purchase setup\n\n"
            f"{premium_divider()}\n"
            f"**Fast • Private • Premium**"
        ),
        color=COLOR_MAIN
    )
    embed.set_image(url=PANEL_IMAGE_URL)
    embed.set_footer(text="Only one open ticket per user.")
    return embed

def build_redeem_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎟️ GEN REDEEM CENTER",
        description=(
            f"{premium_divider()}\n"
            f"Click the button below to redeem your key.\n\n"
            f"✅ Supported:\n• 1 Day\n• 1 Week\n• Lifetime\n\n"
            f"After redeeming, you receive your access role automatically.\n"
            f"{premium_divider()}"
        ),
        color=COLOR_MAIN
    )
    return embed

def support_ticket_embed(user: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="💠 Support Ticket Opened",
        description=(
            f"{premium_divider()}\n"
            f"Welcome {user.mention}\n\n"
            f"Please send:\n"
            f"• what the issue is\n"
            f"• what product/service is affected\n"
            f"• screenshots if needed\n"
            f"{premium_divider()}"
        ),
        color=COLOR_SUPPORT
    )
    embed.set_footer(text=f"Ticket owner: {user}")
    return embed

def buy_ticket_embed(user: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="🛒 Buy Ticket Opened",
        description=(
            f"{premium_divider()}\n"
            f"Welcome {user.mention}\n\n"
            f"**Step 1** → Choose product\n"
            f"**Step 2** → Choose payment method\n"
            f"**Step 3** → Follow payment instructions\n"
            f"{premium_divider()}"
        ),
        color=COLOR_BUY
    )
    embed.set_footer(text=f"Ticket owner: {user}")
    return embed

def build_order_summary(product_key: str, payment_key: str, user: discord.Member, ltc_price_eur: float | None = None) -> discord.Embed:
    product = PRODUCTS[product_key]
    payment = PAYMENTS[payment_key]
    price = get_price(product_key, user)

    price_header = f"💶 **Price:** {format_price(price)}€"
    if is_reseller(user):
        price_header += " (**Reseller 50% OFF**)"

    if payment_key == "paypal":
        extra = (
            f"## 💸 PayPal Payment\n"
            f"**Send payment to:**\n`{PAYPAL_EMAIL}`\n\n"
            f"**After payment:**\n"
            f"• Send screenshot / proof in this ticket\n"
            f"• Click **Payment Sent**"
        )
    elif payment_key == "litecoin":
        extra = (
            f"## 🪙 Litecoin Payment\n"
            f"**Main price:** `{format_price(price)}€`\n"
            f"**Send to address:**\n`{LITECOIN_ADDRESS}`\n\n"
        )
        if ltc_price_eur and ltc_price_eur > 0:
            ltc_amount = price / ltc_price_eur
            extra += f"**Approx LTC amount:** `{ltc_amount:.6f} LTC`\n"
            extra += f"**Market rate:** `{ltc_price_eur:.2f} EUR/LTC`\n\n"
        extra += (
            f"**After payment:**\n"
            f"• Click **Submit TXID**\n"
            f"• Paste your TXID in the popup\n"
            f"• Bot checks it automatically"
        )
    elif payment_key == "ethereum":
        extra = (
            f"## 🔷 Ethereum (ERC20) Payment\n"
            f"**Main price:** `{format_price(price)}€`\n"
            f"**Send to address:**\n`{ETHEREUM_ADDRESS}`\n\n"
            f"**After payment:**\n"
            f"• Click **Submit Crypto TXID**\n"
            f"• Paste your TXID in the popup\n"
            f"• Staff will verify it shortly"
        )
    elif payment_key == "solana":
        extra = (
            f"## 🟣 Solana Payment\n"
            f"**Main price:** `{format_price(price)}€`\n"
            f"**Send to address:**\n`{SOLANA_ADDRESS}`\n\n"
            f"**After payment:**\n"
            f"• Click **Submit Crypto TXID**\n"
            f"• Paste your TXID in the popup\n"
            f"• Staff will verify it shortly"
        )
    elif payment_key == "paysafecard":
        extra = (
            f"## 💳 Paysafecard Payment\n"
            f"**Main price:** `{format_price(price)}€`\n\n"
            f"**After buying your code:**\n"
            f"• Click **Submit Paysafecard Code**\n"
            f"• Paste the code in the popup\n"
            f"• It gets sent to staff automatically"
        )
    else:
        extra = (
            f"## 🎁 Amazon Card Payment\n"
            f"**Main price:** `{format_price(price)}€`\n\n"
            f"**After buying your Amazon card:**\n"
            f"• Click **Submit Amazon Code**\n"
            f"• Paste the code in the popup\n"
            f"• Amazon code can only be used once"
        )

    embed = discord.Embed(
        title="✦ ORDER SETUP COMPLETE ✦",
        description=(
            f"{premium_divider()}\n"
            f"{user.mention}\n\n"
            f"📦 **Product:** {product['label']}\n"
            f"{price_header}\n"
            f"{payment['emoji']} **Method:** {payment['label']}\n\n"
            f"{extra}\n"
            f"{premium_divider()}"
        ),
        color=COLOR_MAIN
    )
    return embed

def build_ltc_result_embed(txid: str, found_addr: bool, confirmations: int, total_received_ltc: float) -> discord.Embed:
    if found_addr and confirmations >= LTC_MIN_CONFIRMATIONS:
        status = "✅ VERIFIED"
        color = COLOR_SUCCESS
    elif found_addr and confirmations < LTC_MIN_CONFIRMATIONS:
        status = "🟠 PENDING CONFIRMATIONS"
        color = COLOR_PENDING
    else:
        status = "❌ ADDRESS NOT MATCHED"
        color = COLOR_DENY

    embed = discord.Embed(
        title="🪙 Litecoin TXID Result",
        description=f"{premium_divider()}\n**Status:** {status}\n{premium_divider()}",
        color=color
    )
    embed.add_field(name="TXID", value=f"`{short_txid(txid)}`", inline=False)
    embed.add_field(name="Address Match", value="Yes" if found_addr else "No", inline=True)
    embed.add_field(name="Confirmations", value=str(confirmations), inline=True)
    embed.add_field(name="Received", value=f"{total_received_ltc:.8f} LTC", inline=True)
    return embed

def build_invoice_embed(
    invoice_id: str,
    buyer: discord.Member,
    product_type: str,
    payment_key: str,
    final_price_eur: float | None = None,
    reseller_discount: bool = False
) -> discord.Embed:
    product = PRODUCTS[product_type]
    payment = PAYMENTS[payment_key]
    price = final_price_eur if final_price_eur is not None else get_price(product_type, buyer)

    embed = discord.Embed(
        title="🧾 Payment Invoice",
        description=f"{premium_divider()}\n**Status:** Paid / Approved\n{premium_divider()}",
        color=COLOR_INFO
    )
    embed.add_field(name="Invoice ID", value=f"`{invoice_id}`", inline=False)
    embed.add_field(name="Buyer", value=buyer.mention, inline=True)
    embed.add_field(name="Product", value=product["label"], inline=True)
    embed.add_field(name="Price", value=f"{format_price(price)}€", inline=True)
    embed.add_field(name="Method", value=payment["label"], inline=True)
    embed.add_field(name="Date", value=f"<t:{int(now_utc().timestamp())}:F>", inline=True)
    embed.add_field(name="Server", value="Gen", inline=True)
    if reseller_discount:
        embed.add_field(name="Discount", value="Reseller 50%", inline=True)
    return embed

def build_key_delivery_embed(product_type: str, key: str) -> discord.Embed:
    product = PRODUCTS[product_type]
    embed = discord.Embed(
        title="🔑 Your Key Has Been Generated",
        description=(
            f"{premium_divider()}\n"
            f"**Product:** {product['label']}\n"
            f"**Your Key:**\n`{key}`\n\n"
            f"Go to the redeem panel and click **Redeem**.\n"
            f"{premium_divider()}"
        ),
        color=COLOR_SUCCESS
    )
    return embed

def build_payment_summary_embed(channel_id: int) -> discord.Embed:
    data = ticket_data.get(channel_id, {})
    product_key = data.get("product_key")
    payment_key = data.get("payment_key")
    status = data.get("status", "waiting")
    invoice_id = data.get("invoice_id")
    txid = data.get("last_txid")
    paysafe_submitted = data.get("paysafe_submitted", False)
    amazon_submitted = data.get("amazon_submitted", False)

    product_text = PRODUCTS[product_key]["label"] if product_key in PRODUCTS else "Not selected"

    user = None
    guild = bot.get_guild(GUILD_ID)
    uid = data.get("user_id")
    if guild and uid:
        user = guild.get_member(uid)

    if product_key in PRODUCTS:
        price_value = get_price(product_key, user)
        price_text = f"{format_price(price_value)}€"
        if is_reseller(user):
            price_text += " (Reseller)"
    else:
        price_text = "—"

    payment_text = PAYMENTS[payment_key]["label"] if payment_key in PAYMENTS else "Not selected"

    status_map = {
        "waiting": "🟡 Waiting",
        "reviewing": "🟠 Reviewing",
        "approved": "✅ Approved",
        "denied": "❌ Denied",
    }

    embed = discord.Embed(
        title="📋 Payment Summary",
        description=f"{premium_divider()}\n**Live order status**\n{premium_divider()}",
        color=COLOR_INFO
    )
    embed.add_field(name="Product", value=product_text, inline=True)
    embed.add_field(name="Price", value=price_text, inline=True)
    embed.add_field(name="Method", value=payment_text, inline=True)
    embed.add_field(name="Status", value=status_map.get(status, status), inline=True)
    embed.add_field(name="TXID", value=f"`{short_txid(txid)}`" if txid else "Not submitted", inline=True)
    embed.add_field(name="Paysafe", value="Submitted" if paysafe_submitted else "Not submitted", inline=True)
    embed.add_field(name="Amazon", value="Submitted" if amazon_submitted else "Not submitted", inline=True)
    embed.add_field(name="Invoice", value=f"`{invoice_id}`" if invoice_id else "Not created", inline=False)
    return embed

def build_admin_panel_embed(owner_id: int, ticket_channel_id: int) -> discord.Embed:
    embed = discord.Embed(
        title="🛠️ GEN ADMIN PANEL",
        description=(
            f"{premium_divider()}\n"
            f"**Buyer ID:** `{owner_id}`\n"
            f"**Ticket ID:** `{ticket_channel_id}`\n"
            f"{premium_divider()}"
        ),
        color=COLOR_ADMIN
    )
    return embed

# =========================================================
# PANEL CLEANUP
# =========================================================
async def delete_admin_panel_message(guild: discord.Guild, ticket_channel_id: int):
    data = ticket_data.get(ticket_channel_id)
    if not data:
        return

    admin_message_id = data.get("admin_message_id")
    if not admin_message_id:
        return

    admin_channel = guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
    if not isinstance(admin_channel, discord.TextChannel):
        return

    try:
        msg = await admin_channel.fetch_message(admin_message_id)
        await msg.delete()
    except Exception:
        pass

# =========================================================
# STATE / MESSAGE HELPERS
# =========================================================
async def update_payment_summary_message(channel: discord.TextChannel):
    data = ticket_data.get(channel.id)
    if not data:
        return
    message_id = data.get("summary_message_id")
    if not message_id:
        return
    try:
        msg = await channel.fetch_message(message_id)
        await msg.edit(embed=build_payment_summary_embed(channel.id), view=PaymentSummaryView())
    except Exception:
        pass

async def send_admin_panel_to_channel(guild: discord.Guild, owner_id: int, ticket_channel_id: int):
    admin_channel = guild.get_channel(ADMIN_PANEL_CHANNEL_ID)
    if not isinstance(admin_channel, discord.TextChannel):
        return

    msg = await admin_channel.send(
        embed=build_admin_panel_embed(owner_id, ticket_channel_id),
        view=AdminPanelView(owner_id=owner_id, ticket_channel_id=ticket_channel_id)
    )

    if ticket_channel_id in ticket_data:
        ticket_data[ticket_channel_id]["admin_message_id"] = msg.id

async def send_summary_and_admin_panels(channel: discord.TextChannel, owner_id: int):
    summary_msg = await channel.send(
        embed=build_payment_summary_embed(channel.id),
        view=PaymentSummaryView()
    )
    ticket_data[channel.id]["summary_message_id"] = summary_msg.id
    await send_admin_panel_to_channel(channel.guild, owner_id, channel.id)

# =========================================================
# REDEEM
# =========================================================
async def redeem_key_for_user(guild: discord.Guild, member: discord.Member, key: str):
    global keys_db, redeemed_db

    if is_blacklisted(member.id):
        return False, "You are blacklisted from using this system."

    if key not in keys_db:
        return False, "Key not found."

    key_data = keys_db[key]
    if key_data["used"]:
        return False, "This key has already been used."

    bound_user_id = key_data.get("bound_user_id")
    if bound_user_id is not None and str(bound_user_id) != str(member.id):
        return False, "This key is bound to a different user."

    product_type = key_data["type"]
    product = PRODUCTS[product_type]

    role = guild.get_role(REDEEM_ROLE_ID)
    if not role:
        return False, "Redeem role not found."

    expires_at = None
    if product["duration"] is not None:
        expires_at = (now_utc() + product["duration"]).isoformat()

    keys_db[key]["used"] = True
    keys_db[key]["used_by"] = str(member.id)
    keys_db[key]["bound_user_id"] = str(member.id)
    keys_db[key]["redeemed_at"] = iso_now()
    save_json(KEYS_FILE, keys_db)

    redeemed_db[str(member.id)] = {
        "key": key,
        "type": product_type,
        "role_id": REDEEM_ROLE_ID,
        "redeemed_at": iso_now(),
        "expires_at": expires_at,
        "expiry_reminder_sent": False
    }
    save_json(REDEEMED_FILE, redeemed_db)

    try:
        await member.add_roles(role, reason=f"Redeemed key: {key}")
    except Exception as e:
        return False, f"Failed to add role: {e}"

    return True, product_type

# =========================================================
# TICKETS
# =========================================================
async def create_ticket_channel(interaction: discord.Interaction, ticket_type: str):
    guild = interaction.guild
    user = interaction.user

    if not guild or not isinstance(user, discord.Member):
        await interaction.response.send_message("This command only works in a server.", ephemeral=True)
        return

    if is_blacklisted(user.id):
        reason = blacklist_db[str(user.id)]["reason"]
        await interaction.response.send_message(
            f"You are blacklisted from using this system.\nReason: {reason}",
            ephemeral=True
        )
        return

    existing = await find_existing_ticket(guild, user)
    if existing:
        await interaction.response.send_message(
            f"You already have an open ticket: {existing.mention}",
            ephemeral=True
        )
        return

    category_id = BUY_CATEGORY_ID if ticket_type == "buy" else SUPPORT_CATEGORY_ID
    category = guild.get_channel(category_id)
    if not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message("Category not found. Check your IDs.", ephemeral=True)
        return

    bot_member = guild.get_member(bot.user.id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True
        )
    }

    if bot_member:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True
        )

    staff_role = guild.get_role(STAFF_ROLE_ID)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True
        )

    safe_name = "".join(c for c in user.name.lower().replace(" ", "-") if c.isalnum() or c == "-")
    channel_name = f"{ticket_type}-{safe_name}"[:90]

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"ticket_owner:{user.id}"
    )

    if ticket_type == "support":
        await channel.send(
            content=f"{user.mention} <@&{STAFF_ROLE_ID}>",
            embed=support_ticket_embed(user),
            view=TicketManageView(owner_id=user.id)
        )
    else:
        ticket_data[channel.id] = {
            "user_id": user.id,
            "product_key": None,
            "payment_key": None,
            "last_txid": None,
            "last_txid_check": None,
            "invoice_id": None,
            "status": "waiting",
            "paysafe_submitted": False,
            "amazon_submitted": False,
            "summary_message_id": None,
            "admin_message_id": None
        }
        forwarded_paysafe_codes[channel.id] = []
        forwarded_amazon_codes[channel.id] = []

        await channel.send(
            content=f"{user.mention} <@&{STAFF_ROLE_ID}>",
            embed=buy_ticket_embed(user),
            view=BuySetupView(owner_id=user.id)
        )
        await send_summary_and_admin_panels(channel, user.id)

    await send_log(
        guild,
        "🎫 Ticket Created",
        f"**User:** {user.mention}\n**Type:** {ticket_type.title()}\n**Channel:** {channel.mention}\n**User ID:** `{user.id}`"
    )

    await interaction.response.send_message(
        f"Your ticket has been created: {channel.mention}",
        ephemeral=True
    )

# =========================================================
# MODALS
# =========================================================
class PaysafeCodeModal(discord.ui.Modal, title="Paste your Paysafecard code here"):
    paysafe_code = discord.ui.TextInput(
        label="Paysafecard Code",
        placeholder="Enter your code here...",
        required=True,
        max_length=200,
        style=discord.TextStyle.paragraph
    )

    def __init__(self, owner_id: int):
        super().__init__()
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can submit the code.", ephemeral=True)
            return

        data = ticket_data.get(interaction.channel.id)
        if not data or data.get("payment_key") != "paysafecard":
            await interaction.response.send_message("This modal is only for Paysafecard tickets.", ephemeral=True)
            return

        codes_channel = interaction.guild.get_channel(PAYSAFE_CODES_CHANNEL_ID)
        if not isinstance(codes_channel, discord.TextChannel):
            await interaction.response.send_message("Paysafe code channel not found.", ephemeral=True)
            return

        raw_text = str(self.paysafe_code).strip()
        found_codes = extract_possible_paysafe_codes(raw_text)
        if not found_codes:
            found_codes = [raw_text.upper()]

        found_codes = list(dict.fromkeys(found_codes))
        new_codes = []

        for code in found_codes:
            if code in used_paysafe_db:
                continue
            already = forwarded_paysafe_codes.setdefault(interaction.channel.id, [])
            if code in already:
                continue

            used_paysafe_db[code] = {
                "user_id": str(interaction.user.id),
                "ticket_id": str(interaction.channel.id),
                "used_at": iso_now()
            }
            new_codes.append(code)
            already.append(code)

        save_json(USED_PAYSAFE_FILE, used_paysafe_db)

        if not new_codes:
            await interaction.response.send_message(
                "No new valid Paysafecard code found. It may already have been submitted before.",
                ephemeral=True
            )
            return

        data["paysafe_submitted"] = True
        data["status"] = "reviewing"

        embed = discord.Embed(
            title="💳 New Paysafecard Code",
            description=(
                f"**Buyer:** {interaction.user.mention}\n"
                f"**Ticket:** {interaction.channel.mention}\n\n"
                f"**Codes:**\n" + "\n".join(f"`{code}`" for code in new_codes)
            ),
            color=COLOR_WARN
        )

        await codes_channel.send(
            content=f"<@&{STAFF_ROLE_ID}> New paysafecard code received.",
            embed=embed
        )

        await interaction.channel.send(
            embed=discord.Embed(
                title="💳 Paysafecard Code Submitted",
                description=(
                    f"{premium_divider()}\n"
                    f"Your code was sent to staff successfully.\n"
                    f"Staff will review it soon.\n"
                    f"{premium_divider()}"
                ),
                color=COLOR_SUCCESS
            )
        )

        await update_payment_summary_message(interaction.channel)

        await send_log(
            interaction.guild,
            "💳 Paysafecard Code Forwarded",
            f"**Buyer:** {interaction.user.mention}\n**Ticket:** {interaction.channel.mention}\n**Codes sent:** `{len(new_codes)}`",
            color=COLOR_INFO
        )

        await interaction.response.send_message("Paysafecard code sent to staff.", ephemeral=True)

class AmazonCodeModal(discord.ui.Modal, title="Paste your Amazon code here"):
    amazon_code = discord.ui.TextInput(
        label="Amazon Code",
        placeholder="Enter your Amazon code here...",
        required=True,
        max_length=200,
        style=discord.TextStyle.paragraph
    )

    def __init__(self, owner_id: int):
        super().__init__()
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can submit the code.", ephemeral=True)
            return

        data = ticket_data.get(interaction.channel.id)
        if not data or data.get("payment_key") != "amazoncard":
            await interaction.response.send_message("This modal is only for Amazon Card tickets.", ephemeral=True)
            return

        amazon_channel = interaction.guild.get_channel(AMAZON_CODES_CHANNEL_ID)
        if not isinstance(amazon_channel, discord.TextChannel):
            await interaction.response.send_message("Amazon code channel not found.", ephemeral=True)
            return

        raw_text = str(self.amazon_code).strip()
        found_codes = extract_possible_amazon_codes(raw_text)
        if not found_codes:
            found_codes = [raw_text.upper()]

        found_codes = list(dict.fromkeys(found_codes))
        new_codes = []

        for code in found_codes:
            if code in used_amazon_db:
                continue
            already = forwarded_amazon_codes.setdefault(interaction.channel.id, [])
            if code in already:
                continue

            used_amazon_db[code] = {
                "user_id": str(interaction.user.id),
                "ticket_id": str(interaction.channel.id),
                "used_at": iso_now()
            }
            new_codes.append(code)
            already.append(code)

        save_json(USED_AMAZON_FILE, used_amazon_db)

        if not new_codes:
            await interaction.response.send_message(
                "No new valid Amazon code found. It may already have been submitted before.",
                ephemeral=True
            )
            return

        data["amazon_submitted"] = True
        data["status"] = "reviewing"

        embed = discord.Embed(
            title="🎁 New Amazon Code",
            description=(
                f"**Buyer:** {interaction.user.mention}\n"
                f"**Ticket:** {interaction.channel.mention}\n\n"
                f"**Codes:**\n" + "\n".join(f"`{code}`" for code in new_codes)
            ),
            color=COLOR_WARN
        )

        await amazon_channel.send(
            content=f"<@&{STAFF_ROLE_ID}> New Amazon code received.",
            embed=embed
        )

        await interaction.channel.send(
            embed=discord.Embed(
                title="🎁 Amazon Code Submitted",
                description=(
                    f"{premium_divider()}\n"
                    f"Your Amazon code was sent to staff successfully.\n"
                    f"Amazon codes can only be used once.\n"
                    f"{premium_divider()}"
                ),
                color=COLOR_SUCCESS
            )
        )

        await update_payment_summary_message(interaction.channel)

        await send_log(
            interaction.guild,
            "🎁 Amazon Code Forwarded",
            f"**Buyer:** {interaction.user.mention}\n**Ticket:** {interaction.channel.mention}\n**Codes sent:** `{len(new_codes)}`",
            color=COLOR_INFO
        )

        await interaction.response.send_message("Amazon code sent to staff.", ephemeral=True)

class GenericCryptoTxidModal(discord.ui.Modal, title="Paste your Crypto TXID here"):
    txid_input = discord.ui.TextInput(
        label="Transaction Hash (TXID)",
        placeholder="Paste your Ethereum or Solana TXID...",
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, owner_id: int):
        super().__init__()
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can submit a TXID.", ephemeral=True)
            return

        txid = str(self.txid_input).strip()
        data = ticket_data.get(interaction.channel.id)
        
        data["last_txid"] = txid
        data["status"] = "reviewing"
        
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        embed = discord.Embed(
            title="🪙 Crypto TXID Submitted (Manual Review)",
            description=f"**Buyer:** {interaction.user.mention}\n**Ticket:** {interaction.channel.mention}\n**TXID:** `{txid}`\n**Coin:** {data['payment_key'].title()}",
            color=COLOR_PENDING
        )
        
        if isinstance(review_channel, discord.TextChannel):
            await review_channel.send(content=f"<@&{STAFF_ROLE_ID}> Review needed.", embed=embed, view=ReviewView(target_channel_id=interaction.channel.id, buyer_id=interaction.user.id))

        await interaction.channel.send(
            embed=discord.Embed(title="✅ TXID Submitted", description="Your TXID has been sent to staff for manual verification.", color=COLOR_SUCCESS)
        )
        await update_payment_summary_message(interaction.channel)
        await interaction.response.send_message("TXID submitted successfully.", ephemeral=True)

class LitecoinTxidModal(discord.ui.Modal, title="Paste your Litecoin TXID here"):
    txid_input = discord.ui.TextInput(
        label="Litecoin TXID",
        placeholder="Paste the full TXID here...",
        required=True,
        min_length=64,
        max_length=64
    )

    def __init__(self, owner_id: int):
        super().__init__()
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can submit a TXID.", ephemeral=True)
            return

        data = ticket_data.get(interaction.channel.id)
        if not data or data.get("payment_key") != "litecoin":
            await interaction.response.send_message("This modal is only for Litecoin tickets.", ephemeral=True)
            return

        txid = str(self.txid_input).strip()
        if not re.fullmatch(r"[a-fA-F0-9]{64}", txid):
            await interaction.response.send_message("That is not a valid 64-character TXID.", ephemeral=True)
            return

        if txid in used_txids_db:
            await interaction.response.send_message("This TXID was already submitted before.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        tx_data, err = await fetch_ltc_tx(txid)
        if err or not tx_data:
            await interaction.followup.send(f"Could not verify TXID right now. {err or 'Unknown error'}", ephemeral=True)
            return

        confirmations = int(tx_data.get("confirmations", 0))
        found_addr, total_received_litoshi = tx_matches_our_address(tx_data, LITECOIN_ADDRESS)
        total_received_ltc = litoshi_to_ltc(total_received_litoshi)

        used_txids_db[txid] = {
            "user_id": str(interaction.user.id),
            "ticket_id": str(interaction.channel.id),
            "used_at": iso_now()
        }
        save_json(USED_TXIDS_FILE, used_txids_db)

        data["last_txid"] = txid
        data["last_txid_check"] = {
            "confirmations": confirmations,
            "matched_address": found_addr,
            "amount_ltc": total_received_ltc,
        }
        data["status"] = "reviewing"

        await interaction.channel.send(
            embed=build_ltc_result_embed(txid, found_addr, confirmations, total_received_ltc)
        )
        await update_payment_summary_message(interaction.channel)

        await send_log(
            interaction.guild,
            "🪙 LTC TXID Checked",
            f"**Buyer:** {interaction.user.mention}\n"
            f"**Ticket:** {interaction.channel.mention}\n"
            f"**TXID:** `{txid}`\n"
            f"**Address match:** {'Yes' if found_addr else 'No'}\n"
            f"**Amount:** `{total_received_ltc:.8f} LTC`\n"
            f"**Confirmations:** `{confirmations}`",
            color=COLOR_INFO
        )

        if found_addr and confirmations >= LTC_MIN_CONFIRMATIONS:
            await interaction.followup.send("TXID verified successfully.", ephemeral=True)
        elif found_addr:
            await interaction.followup.send("TXID found, but still waiting for more confirmations.", ephemeral=True)
        else:
            await interaction.followup.send("TXID found, but no output to the configured LTC address was detected.", ephemeral=True)

class RedeemKeyModal(discord.ui.Modal, title="Paste your key here"):
    key_input = discord.ui.TextInput(
        label="Key",
        placeholder="Enter your key here...",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message("This only works in a server.", ephemeral=True)
            return

        key = str(self.key_input).strip().upper()

        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, result = await redeem_key_for_user(guild, member, key)

        if not ok:
            await interaction.followup.send(result, ephemeral=True)
            return

        product_type = result
        success_embed = discord.Embed(
            title="✅ Key Redeemed Successfully",
            description=(
                f"{premium_divider()}\n"
                f"Your key has been redeemed.\n"
                f"Role granted successfully.\n\n"
                f"**Type:** {PRODUCTS[product_type]['label']}\n"
                f"{premium_divider()}"
            ),
            color=COLOR_SUCCESS
        )
        success_embed.add_field(name="Access Duration", value=PRODUCTS[product_type]["label"], inline=False)

        await send_log(
            interaction.guild,
            "🎟️ Key Redeemed",
            f"**User:** {member.mention}\n**Type:** {PRODUCTS[product_type]['label']}\n**Key:** `{key}`",
            color=COLOR_SUCCESS
        )

        await interaction.followup.send(embed=success_embed, ephemeral=True)

class ExtendModal(discord.ui.Modal, title="Extend Access"):
    extend_input = discord.ui.TextInput(
        label="Duration",
        placeholder="Example: 1d or 7d or 12h",
        required=True,
        max_length=10
    )

    def __init__(self, target_user_id: int):
        super().__init__()
        self.target_user_id = target_user_id

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return

        duration = parse_duration_string(str(self.extend_input))
        if duration is None:
            await interaction.response.send_message("Invalid format. Use for example: 1d, 7d, 12h", ephemeral=True)
            return

        uid = str(self.target_user_id)
        if uid not in redeemed_db:
            await interaction.response.send_message("This user has no active redeem entry.", ephemeral=True)
            return

        old_exp = redeemed_db[uid].get("expires_at")
        now = now_utc()

        if old_exp:
            try:
                base = datetime.fromisoformat(old_exp)
                if base < now:
                    base = now
            except Exception:
                base = now
        else:
            base = now

        new_exp = (base + duration).isoformat()
        redeemed_db[uid]["expires_at"] = new_exp
        redeemed_db[uid]["expiry_reminder_sent"] = False
        save_json(REDEEMED_FILE, redeemed_db)

        member = interaction.guild.get_member(self.target_user_id)
        if member:
            await dm_user_safe(
                member,
                embed=discord.Embed(
                    title="⏳ Access Extended",
                    description=f"Your access has been extended.\nNew expiry: {format_expiry(new_exp)}",
                    color=COLOR_SUCCESS
                )
            )

        await send_log(
            interaction.guild,
            "⏳ Access Extended",
            f"**By:** {interaction.user.mention}\n**User ID:** `{self.target_user_id}`\n**New Expiry:** {format_expiry(new_exp)}",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message("Access extended successfully.", ephemeral=True)

# =========================================================
# VIEWS
# =========================================================
class MainTicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="💠", custom_id="main_support_ticket_button")
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket_channel(interaction, "support")

    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, emoji="🛒", custom_id="main_buy_ticket_button")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket_channel(interaction, "buy")

class RedeemPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Redeem", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="redeem_key_button")
    async def redeem_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_blacklisted(interaction.user.id):
            reason = blacklist_db[str(interaction.user.id)]["reason"]
            await interaction.response.send_message(
                f"You are blacklisted from using this system.\nReason: {reason}",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(RedeemKeyModal())

class CloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        user = interaction.user

        await interaction.response.send_message("Closing ticket...", ephemeral=True)

        if guild and isinstance(channel, discord.TextChannel):
            await send_log(
                guild,
                "🔒 Ticket Closed",
                f"**Channel:** {channel.name}\n**Closed by:** {user.mention}\n**Channel ID:** `{channel.id}`"
            )

            await delete_admin_panel_message(guild, channel.id)

            ticket_data.pop(channel.id, None)
            forwarded_paysafe_codes.pop(channel.id, None)
            forwarded_amazon_codes.pop(channel.id, None)

        await asyncio.sleep(2)
        await channel.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Close cancelled.", view=None)

class TicketManageView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="claim_ticket_button")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.")
        if interaction.guild and isinstance(interaction.channel, discord.TextChannel):
            await send_log(
                interaction.guild,
                "🛠️ Ticket Claimed",
                f"**Staff:** {interaction.user.mention}\n**Channel:** {interaction.channel.mention}\n**Channel ID:** `{interaction.channel.id}`"
            )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_owner = interaction.user.id == self.owner_id
        is_staff = interaction.user.guild_permissions.manage_channels

        if not is_owner and not is_staff:
            await interaction.response.send_message("Only the ticket owner or staff can close this ticket.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Are you sure you want to close this ticket?",
            view=CloseConfirmView(),
            ephemeral=True
        )

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1 Day", description="5€", value="day_1", emoji="📅"),
            discord.SelectOption(label="1 Week", description="15€", value="week_1", emoji="🗓️"),
            discord.SelectOption(label="Lifetime", description="30€", value="lifetime", emoji="♾️"),
        ]
        super().__init__(
            placeholder="📦 Choose your product",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="buy_product_select"
        )

    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(interaction.channel.id)
        if not data:
            await interaction.response.send_message("Ticket data not found.", ephemeral=True)
            return

        if interaction.user.id != data["user_id"] and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the ticket owner can use this.", ephemeral=True)
            return

        data["product_key"] = self.values[0]
        product = PRODUCTS[self.values[0]]
        price = get_price(self.values[0], interaction.user)

        description = (
            f"**{product['label']}** selected\n"
            f"Price: **{format_price(price)}€**"
        )
        if is_reseller(interaction.user):
            description += " (**Reseller 50% OFF**)"
        description += "\n\nNow choose your payment method below."

        embed = discord.Embed(
            title="📦 Product Selected",
            description=description,
            color=COLOR_INFO
        )

        await interaction.response.send_message(embed=embed, view=PaymentSelectView())
        await update_payment_summary_message(interaction.channel)

        if interaction.guild and isinstance(interaction.channel, discord.TextChannel):
            log_text = (
                f"**User:** {interaction.user.mention}\n"
                f"**Product:** {product['label']}\n"
                f"**Price:** {format_price(price)}€\n"
            )
            if is_reseller(interaction.user):
                log_text += "**Discount:** Reseller 50%\n"
            log_text += f"**Channel:** {interaction.channel.mention}"

            await send_log(
                interaction.guild,
                "📦 Product Selected",
                log_text
            )

class ProductSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ProductSelect())

class PaymentSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="PayPal", value="paypal", emoji="💸", description="Pay with PayPal"),
            discord.SelectOption(label="Litecoin", value="litecoin", emoji="🪙", description="Pay with LTC"),
            discord.SelectOption(label="Ethereum", value="ethereum", emoji="🔷", description="Pay with ETH"),
            discord.SelectOption(label="Solana", value="solana", emoji="🟣", description="Pay with SOL"),
            discord.SelectOption(label="Paysafecard", value="paysafecard", emoji="💳", description="Pay with PSC"),
            discord.SelectOption(label="Amazon Card", value="amazoncard", emoji="🎁", description="Pay with Amazon Card"),
        ]
        super().__init__(
            placeholder="💳 Choose your payment method",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="buy_payment_select"
        )

    async def callback(self, interaction: discord.Interaction):
        data = ticket_data.get(interaction.channel.id)
        if not data or not data.get("product_key"):
            await interaction.response.send_message("Choose a product first.", ephemeral=True)
            return

        if interaction.user.id != data["user_id"] and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the ticket owner can use this.", ephemeral=True)
            return

        data["payment_key"] = self.values[0]
        buyer = interaction.guild.get_member(data["user_id"])
        if buyer is None:
            await interaction.response.send_message("Buyer not found.", ephemeral=True)
            return

        ltc_price = None
        if data["payment_key"] == "litecoin":
            ltc_price = await fetch_ltc_price_eur()

        embed = build_order_summary(data["product_key"], data["payment_key"], buyer, ltc_price_eur=ltc_price)
        await interaction.response.send_message(embed=embed, view=PaymentActionView(owner_id=data["user_id"]))
        await update_payment_summary_message(interaction.channel)

        if interaction.guild and isinstance(interaction.channel, discord.TextChannel):
            await send_log(
                interaction.guild,
                "💳 Payment Method Selected",
                f"**User:** {interaction.user.mention}\n**Method:** {PAYMENTS[data['payment_key']]['label']}\n**Channel:** {interaction.channel.mention}"
            )

class PaymentSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PaymentSelect())

class BuySetupView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    @discord.ui.button(label="Choose Product", style=discord.ButtonStyle.primary, emoji="📦", custom_id="choose_product_button")
    async def choose_product(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the ticket owner can do this.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Select the product you want to buy:",
            view=ProductSelectView(),
            ephemeral=True
        )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_buy_ticket_button")
    async def close_buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_owner = interaction.user.id == self.owner_id
        is_staff = interaction.user.guild_permissions.manage_channels

        if not is_owner and not is_staff:
            await interaction.response.send_message("Only the ticket owner or staff can close this ticket.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Are you sure you want to close this ticket?",
            view=CloseConfirmView(),
            ephemeral=True
        )

class PaymentActionView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    @discord.ui.button(label="Payment Sent", style=discord.ButtonStyle.success, emoji="✅", custom_id="payment_sent_button")
    async def payment_sent(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can use this.", ephemeral=True)
            return

        data = ticket_data.get(interaction.channel.id)
        if not data or not data.get("product_key") or not data.get("payment_key"):
            await interaction.response.send_message("Order data is incomplete.", ephemeral=True)
            return

        product = PRODUCTS[data["product_key"]]
        payment = PAYMENTS[data["payment_key"]]
        buyer = interaction.guild.get_member(data["user_id"])
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)

        if buyer is None:
            await interaction.response.send_message("Buyer not found.", ephemeral=True)
            return

        data["status"] = "reviewing"
        price = get_price(data["product_key"], buyer)

        embed = discord.Embed(
            title="🧾 New Payment Review",
            description="A buyer says they sent payment.",
            color=COLOR_WARN
        )
        embed.add_field(name="Buyer", value=buyer.mention, inline=False)
        embed.add_field(name="Product", value=product["label"], inline=True)
        embed.add_field(name="Price", value=f"{format_price(price)}€", inline=True)
        embed.add_field(name="Method", value=payment["label"], inline=True)
        embed.add_field(name="Ticket", value=interaction.channel.mention, inline=False)

        if is_reseller(buyer):
            embed.add_field(name="Discount", value="Reseller 50%", inline=True)

        if data.get("last_txid"):
            embed.add_field(name="Submitted TXID", value=f"`{short_txid(data['last_txid'])}`", inline=False)

        if isinstance(review_channel, discord.TextChannel):
            await review_channel.send(
                content=f"<@&{STAFF_ROLE_ID}> New payment to review.",
                embed=embed,
                view=ReviewView(target_channel_id=interaction.channel.id, buyer_id=buyer.id)
            )

        await update_payment_summary_message(interaction.channel)

        log_text = (
            f"**Buyer:** {buyer.mention}\n"
            f"**Product:** {product['label']}\n"
            f"**Price:** {format_price(price)}€\n"
            f"**Method:** {payment['label']}\n"
        )
        if is_reseller(buyer):
            log_text += "**Discount:** Reseller 50%\n"
        log_text += f"**Ticket:** {interaction.channel.mention}"

        await send_log(
            interaction.guild,
            "📨 Payment Marked As Sent",
            log_text
        )

        await interaction.response.send_message("Payment marked as sent. Staff has been notified.", ephemeral=True)

    @discord.ui.button(label="Submit LTC TXID", style=discord.ButtonStyle.primary, emoji="🪙", custom_id="submit_txid_button")
    async def submit_txid(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(interaction.channel.id)
        if not data or data.get("payment_key") != "litecoin":
            await interaction.response.send_message("This button is only for Litecoin tickets.", ephemeral=True)
            return

        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can use this.", ephemeral=True)
            return

        await interaction.response.send_modal(LitecoinTxidModal(owner_id=self.owner_id))

    @discord.ui.button(label="Submit Crypto TXID (ETH/SOL)", style=discord.ButtonStyle.primary, emoji="🔗", custom_id="submit_generic_txid_button")
    async def submit_generic_txid(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(interaction.channel.id)
        if not data or data.get("payment_key") not in ["ethereum", "solana"]:
            await interaction.response.send_message("This button is only for Ethereum/Solana tickets.", ephemeral=True)
            return

        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can use this.", ephemeral=True)
            return

        await interaction.response.send_modal(GenericCryptoTxidModal(owner_id=self.owner_id))

    @discord.ui.button(label="Submit Paysafecard Code", style=discord.ButtonStyle.secondary, emoji="💳", custom_id="submit_paysafe_button")
    async def submit_paysafe(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(interaction.channel.id)
        if not data or data.get("payment_key") != "paysafecard":
            await interaction.response.send_message("This button is only for Paysafecard tickets.", ephemeral=True)
            return

        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can use this.", ephemeral=True)
            return

        await interaction.response.send_modal(PaysafeCodeModal(owner_id=self.owner_id))

    @discord.ui.button(label="Submit Amazon Code", style=discord.ButtonStyle.secondary, emoji="🎁", custom_id="submit_amazon_button")
    async def submit_amazon(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = ticket_data.get(interaction.channel.id)
        if not data or data.get("payment_key") != "amazoncard":
            await interaction.response.send_message("This button is only for Amazon Card tickets.", ephemeral=True)
            return

        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only the buyer can use this.", ephemeral=True)
            return

        await interaction.response.send_modal(AmazonCodeModal(owner_id=self.owner_id))

class PaymentSummaryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="refresh_payment_summary")
    async def refresh_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=build_payment_summary_embed(interaction.channel.id),
            view=PaymentSummaryView()
        )

class AdminPanelView(discord.ui.View):
    def __init__(self, owner_id: int, ticket_channel_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.ticket_channel_id = ticket_channel_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="adminpanel_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return
        view = ReviewView(target_channel_id=self.ticket_channel_id, buyer_id=self.owner_id)
        await view._approve_logic(interaction)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="adminpanel_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return
        view = ReviewView(target_channel_id=self.ticket_channel_id, buyer_id=self.owner_id)
        await view._deny_logic(interaction)

    @discord.ui.button(label="Resend Key", style=discord.ButtonStyle.primary, emoji="🔁", custom_id="adminpanel_resend")
    async def resend_key_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return

        latest = find_user_latest_key(self.owner_id)
        if not latest:
            await interaction.response.send_message("No key found for this user.", ephemeral=True)
            return

        key, data = latest
        product_type = data["type"]
        buyer = interaction.guild.get_member(self.owner_id)

        if buyer:
            await dm_user_safe(
                buyer,
                embed=discord.Embed(
                    title="🔁 Your Key Was Resent",
                    description=f"**Product:** {PRODUCTS[product_type]['label']}\n**Key:** `{key}`",
                    color=COLOR_INFO
                )
            )

        ticket_channel = interaction.guild.get_channel(self.ticket_channel_id)
        if isinstance(ticket_channel, discord.TextChannel):
            await ticket_channel.send(embed=build_key_delivery_embed(product_type, key))

        await interaction.response.send_message("Key resent.", ephemeral=True)

    @discord.ui.button(label="Extend", style=discord.ButtonStyle.secondary, emoji="⏳", custom_id="adminpanel_extend")
    async def extend_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return
        await interaction.response.send_modal(ExtendModal(target_user_id=self.owner_id))

    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id="adminpanel_blacklist")
    async def blacklist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return

        blacklist_db[str(self.owner_id)] = {
            "reason": "Added from admin panel",
            "added_by": str(interaction.user.id),
            "added_at": iso_now()
        }
        save_json(BLACKLIST_FILE, blacklist_db)
        await interaction.response.send_message("User blacklisted.", ephemeral=True)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="adminpanel_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return

        ticket_channel = interaction.guild.get_channel(self.ticket_channel_id)
        if not isinstance(ticket_channel, discord.TextChannel):
            await interaction.response.send_message("Ticket channel not found.", ephemeral=True)
            return

        await interaction.response.send_message("Closing ticket...", ephemeral=True)

        await send_log(
            interaction.guild,
            "🔒 Ticket Closed",
            f"**Channel:** {ticket_channel.name}\n**Closed by:** {interaction.user.mention}\n**Channel ID:** `{ticket_channel.id}`"
        )

        await delete_admin_panel_message(interaction.guild, ticket_channel.id)

        ticket_data.pop(ticket_channel.id, None)
        forwarded_paysafe_codes.pop(ticket_channel.id, None)
        forwarded_amazon_codes.pop(ticket_channel.id, None)

        await asyncio.sleep(2)
        await ticket_channel.delete()

class ReviewView(discord.ui.View):
    def __init__(self, target_channel_id: int, buyer_id: int):
        super().__init__(timeout=None)
        self.target_channel_id = target_channel_id
        self.buyer_id = buyer_id

    async def _approve_logic(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.target_channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Ticket channel not found.", ephemeral=True)
            return

        data = ticket_data.get(self.target_channel_id)
        if not data or not data.get("product_key") or not data.get("payment_key"):
            await interaction.response.send_message("No order data found for this ticket.", ephemeral=True)
            return

        product_type = data["product_key"]
        payment_key = data["payment_key"]
        buyer = interaction.guild.get_member(self.buyer_id)

        if buyer is None:
            await interaction.response.send_message("Buyer not found.", ephemeral=True)
            return

        invoice_id = build_invoice_id()
        data["invoice_id"] = invoice_id
        data["status"] = "approved"

        generated_key = generate_key(product_type, ticket_id=self.target_channel_id)
        keys_db[generated_key]["bound_user_id"] = str(buyer.id)
        save_json(KEYS_FILE, keys_db)

        final_price = get_price(product_type, buyer)
        reseller_discount = is_reseller(buyer)

        create_invoice_record(
            invoice_id,
            buyer.id,
            product_type,
            payment_key,
            generated_key,
            self.target_channel_id,
            final_price_eur=final_price,
            reseller_discount=reseller_discount
        )

        invoice_embed = build_invoice_embed(
            invoice_id,
            buyer,
            product_type,
            payment_key,
            final_price_eur=final_price,
            reseller_discount=reseller_discount
        )

        await channel.send(embed=invoice_embed)
        await channel.send(embed=build_key_delivery_embed(product_type, generated_key))
        await channel.send(
            embed=discord.Embed(
                title="✅ Payment Approved",
                description=f"{interaction.user.mention} approved this payment.\nInvoice created and key generated successfully.",
                color=COLOR_BUY
            )
        )

        invoice_channel = interaction.guild.get_channel(INVOICE_CHANNEL_ID)
        if isinstance(invoice_channel, discord.TextChannel):
            await invoice_channel.send(embed=invoice_embed)

        await update_payment_summary_message(channel)

        await dm_user_safe(
            buyer,
            embed=discord.Embed(
                title="🔑 Your Purchase Was Approved",
                description=(
                    f"**Product:** {PRODUCTS[product_type]['label']}\n"
                    f"**Price:** {format_price(final_price)}€\n"
                    f"**Invoice:** `{invoice_id}`\n"
                    f"**Key:** `{generated_key}`\n\n"
                    f"Use the redeem panel to redeem your key."
                ),
                color=COLOR_SUCCESS
            )
        )

        log_text = (
            f"**Approved by:** {interaction.user.mention}\n"
            f"**Buyer:** {buyer.mention}\n"
            f"**Ticket:** {channel.mention}\n"
            f"**Product:** {PRODUCTS[product_type]['label']}\n"
            f"**Price:** {format_price(final_price)}€\n"
            f"**Invoice:** `{invoice_id}`\n"
            f"**Key:** `{generated_key}`"
        )
        if reseller_discount:
            log_text += "\n**Discount:** Reseller 50%"

        await send_log(
            interaction.guild,
            "✅ Payment Approved + Key Generated",
            log_text,
            color=COLOR_SUCCESS
        )

        await interaction.response.send_message("Payment approved, invoice created, key generated.", ephemeral=True)

    async def _deny_logic(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.target_channel_id)
        if isinstance(channel, discord.TextChannel):
            embed = discord.Embed(
                title="❌ Payment Denied",
                description=f"{interaction.user.mention} denied this payment.\nPlease check the payment details and try again.",
                color=COLOR_DENY
            )
            await channel.send(embed=embed)
            if self.target_channel_id in ticket_data:
                ticket_data[self.target_channel_id]["status"] = "denied"
                await update_payment_summary_message(channel)

        await send_log(
            interaction.guild,
            "❌ Payment Denied",
            f"**Denied by:** {interaction.user.mention}\n**Ticket Channel ID:** `{self.target_channel_id}`\n**Buyer ID:** `{self.buyer_id}`",
            color=COLOR_DENY
        )

        await interaction.response.send_message("Payment denied.", ephemeral=True)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✔️", custom_id="review_approve_button")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only staff can do this.", ephemeral=True)
            return
        await self._approve_logic(interaction)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="review_deny_button")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Only staff can do this.", ephemeral=True)
            return
        await self._deny_logic(interaction)

# =========================================================
# TASKS
# =========================================================
@tasks.loop(minutes=5)
async def check_expired_roles():
    global redeemed_db

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        return

    current_time = now_utc()
    changed = False

    for user_id, data in list(redeemed_db.items()):
        expires_at = data.get("expires_at")
        if not expires_at:
            continue

        try:
            expire_time = datetime.fromisoformat(expires_at)
        except Exception:
            continue

        member = guild.get_member(int(user_id))
        if member is None:
            continue

        remaining = expire_time - current_time

        if remaining.total_seconds() <= 0:
            role = guild.get_role(data.get("role_id", REDEEM_ROLE_ID))
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Access expired")
                except Exception:
                    pass

            await dm_user_safe(
                member,
                embed=discord.Embed(
                    title="⚠️ Access Expired",
                    description="Your access has expired. Open a new ticket if you want to buy again.",
                    color=COLOR_DENY
                )
            )

            redeemed_db.pop(user_id, None)
            changed = True
            continue

        reminder_sent = data.get("expiry_reminder_sent", False)
        if not reminder_sent and remaining <= timedelta(hours=EXPIRY_REMINDER_HOURS):
            await dm_user_safe(
                member,
                embed=discord.Embed(
                    title="⏳ Access Expiring Soon",
                    description=f"Your access will expire in less than {EXPIRY_REMINDER_HOURS} hours.",
                    color=COLOR_WARN
                )
            )
            redeemed_db[user_id]["expiry_reminder_sent"] = True
            changed = True

    if changed:
        save_json(REDEEMED_FILE, redeemed_db)

# =========================================================
# COMMANDS
# =========================================================

# ----------------- HIER IST DER NEUE SYNC COMMAND -----------------
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_commands(ctx):
    await ctx.send("Synchronisiere Slash-Commands... ⏳")
    try:
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await ctx.send(f"✅ Erfolgreich {len(synced)} Slash-Commands für diesen Server synchronisiert! Drücke jetzt STRG+R in Discord.")
    except Exception as e:
        await ctx.send(f"❌ Fehler beim Synchronisieren:\n```py\n{e}\n```")
# ------------------------------------------------------------------

@bot.tree.command(name="ticket", description="Open the Gen ticket panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket(interaction: discord.Interaction):
    await interaction.response.send_message(embed=panel_embed(), view=MainTicketPanelView())

@bot.tree.command(name="send_redeem_panel", description="Send the redeem panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def send_redeem_panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admins only.", ephemeral=True)
        return
    await interaction.response.send_message(embed=build_redeem_panel_embed(), view=RedeemPanelView())

@bot.tree.command(name="invoice_lookup", description="Lookup an invoice by ID")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def invoice_lookup(interaction: discord.Interaction, invoice_id: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return

    invoice_id = invoice_id.strip().upper()
    data = invoices_db.get(invoice_id)
    if not data:
        await interaction.response.send_message("Invoice not found.", ephemeral=True)
        return

    buyer = interaction.guild.get_member(int(data["buyer_id"]))
    stored_price = data.get("final_price_eur")
    reseller_discount = data.get("reseller_discount", False)

    embed = discord.Embed(title="🧾 Invoice Lookup", color=COLOR_INFO)
    embed.add_field(name="Invoice ID", value=f"`{invoice_id}`", inline=False)
    embed.add_field(name="Buyer", value=buyer.mention if buyer else data["buyer_id"], inline=True)
    embed.add_field(name="Product", value=PRODUCTS[data["product_type"]]["label"], inline=True)
    embed.add_field(name="Method", value=PAYMENTS[data["payment_key"]]["label"], inline=True)
    if stored_price is not None:
        embed.add_field(name="Price", value=f"{format_price(float(stored_price))}€", inline=True)
    else:
        embed.add_field(name="Price", value=f"{PRODUCTS[data['product_type']]['price_eur']}€", inline=True)
    if reseller_discount:
        embed.add_field(name="Discount", value="Reseller 50%", inline=True)
    embed.add_field(name="Key", value=f"`{data['key']}`", inline=False)
    embed.add_field(name="Ticket ID", value=f"`{data['ticket_id']}`", inline=True)
    embed.add_field(name="Created", value=data["created_at"], inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="resend_key", description="Resend a user's latest key")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def resend_key(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return

    latest = find_user_latest_key(user.id)
    if not latest:
        await interaction.response.send_message("No key found for this user.", ephemeral=True)
        return

    key, data = latest
    product_type = data["type"]

    await dm_user_safe(
        user,
        embed=discord.Embed(
            title="🔁 Your Key Was Resent",
            description=f"**Product:** {PRODUCTS[product_type]['label']}\n**Key:** `{key}`",
            color=COLOR_INFO
        )
    )

    await interaction.response.send_message(f"Key resent to {user.mention}.", ephemeral=True)

@bot.tree.command(name="extend", description="Extend a user's access")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def extend(interaction: discord.Interaction, user: discord.Member, duration: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return

    td = parse_duration_string(duration)
    if td is None:
        await interaction.response.send_message("Invalid duration. Use for example: 1d, 7d, 12h", ephemeral=True)
        return

    uid = str(user.id)
    if uid not in redeemed_db:
        await interaction.response.send_message("This user has no active redeem entry.", ephemeral=True)
        return

    old_exp = redeemed_db[uid].get("expires_at")
    now = now_utc()

    if old_exp:
        try:
            base = datetime.fromisoformat(old_exp)
            if base < now:
                base = now
        except Exception:
            base = now
    else:
        base = now

    new_exp = (base + td).isoformat()
    redeemed_db[uid]["expires_at"] = new_exp
    redeemed_db[uid]["expiry_reminder_sent"] = False
    save_json(REDEEMED_FILE, redeemed_db)

    await dm_user_safe(
        user,
        embed=discord.Embed(
            title="⏳ Access Extended",
            description=f"Your access has been extended.\nNew expiry: {format_expiry(new_exp)}",
            color=COLOR_SUCCESS
        )
    )

    await interaction.response.send_message(f"Extended {user.mention} until {format_expiry(new_exp)}", ephemeral=True)

@bot.tree.command(name="blacklist_add", description="Blacklist a user")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def blacklist_add(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admins only.", ephemeral=True)
        return

    blacklist_db[str(user.id)] = {
        "reason": reason,
        "added_by": str(interaction.user.id),
        "added_at": iso_now()
    }
    save_json(BLACKLIST_FILE, blacklist_db)
    await interaction.response.send_message(f"{user.mention} was blacklisted.\nReason: {reason}", ephemeral=True)

@bot.tree.command(name="blacklist_remove", description="Remove a user from blacklist")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def blacklist_remove(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admins only.", ephemeral=True)
        return

    if str(user.id) in blacklist_db:
        del blacklist_db[str(user.id)]
        save_json(BLACKLIST_FILE, blacklist_db)
        await interaction.response.send_message(f"{user.mention} was removed from blacklist.", ephemeral=True)
    else:
        await interaction.response.send_message("User is not blacklisted.", ephemeral=True)

@bot.tree.command(name="vouch", description="Hinterlasse eine Bewertung für deinen Kauf!")
@app_commands.describe(
    sterne="Wie viele Sterne gibst du? (1-5)",
    produkt="Was hast du gekauft? (z.B. 1 Week Gen)",
    bewertung="Deine Erfahrung mit dem Produkt und Support"
)
@app_commands.choices(sterne=[
    app_commands.Choice(name="⭐⭐⭐⭐⭐ (5/5)", value=5),
    app_commands.Choice(name="⭐⭐⭐⭐ (4/5)", value=4),
    app_commands.Choice(name="⭐⭐⭐ (3/5)", value=3),
    app_commands.Choice(name="⭐⭐ (2/5)", value=2),
    app_commands.Choice(name="⭐ (1/5)", value=1)
])
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def vouch(interaction: discord.Interaction, sterne: app_commands.Choice[int], produkt: str, bewertung: str):
    vouch_channel = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if not isinstance(vouch_channel, discord.TextChannel):
        await interaction.response.send_message("Vouch-Kanal ist nicht konfiguriert. Bitte Admin kontaktieren.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Neue Bewertung: {sterne.name}",
        description=f'"{bewertung}"',
        color=0xFFD700 
    )
    embed.add_field(name="👤 Käufer", value=interaction.user.mention, inline=True)
    embed.add_field(name="📦 Produkt", value=f"`{produkt}`", inline=True)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text="✦ Gen Ticket System ✦")

    await vouch_channel.send(embed=embed)
    await interaction.response.send_message("✅ Danke für deine Bewertung! Sie wurde im Vouch-Kanal veröffentlicht.", ephemeral=True)


# =========================================================
# READY
# =========================================================
@bot.event
async def on_ready():
    global keys_db, redeemed_db, used_txids_db, used_paysafe_db, used_amazon_db, blacklist_db, invoices_db

    keys_db = load_json(KEYS_FILE, {})
    redeemed_db = load_json(REDEEMED_FILE, {})
    used_txids_db = load_json(USED_TXIDS_FILE, {})
    used_paysafe_db = load_json(USED_PAYSAFE_FILE, {})
    used_amazon_db = load_json(USED_AMAZON_FILE, {})
    blacklist_db = load_json(BLACKLIST_FILE, {})
    invoices_db = load_json(INVOICES_FILE, {})

    print("Bot is starting...")
    print(f"Logged in as: {bot.user} ({bot.user.id})")
    print(f"Guild ID loaded: {GUILD_ID}")

    bot.add_view(MainTicketPanelView())
    bot.add_view(RedeemPanelView())
    bot.add_view(TicketManageView(owner_id=0))
    bot.add_view(BuySetupView(owner_id=0))
    bot.add_view(PaymentActionView(owner_id=0))
    bot.add_view(PaymentSummaryView())
    bot.add_view(AdminPanelView(owner_id=0, ticket_channel_id=0))
    bot.add_view(ReviewView(target_channel_id=0, buyer_id=0))

    if not check_expired_roles.is_running():
        check_expired_roles.start()

    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}.")
    except Exception as e:
        print(f"Slash command sync error: {e}")

    print("Bot is ready.")

bot.run(TOKEN)
