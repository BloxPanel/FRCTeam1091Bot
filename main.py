from aiohttp import web
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN") # MTIzMDMyNDU1MDM5NTIzNjQwMg.GWrX_5.Y8y0CaO5T-LRzVt1cBsvdMcppTy9w5AWF9Mp3A
ALERT_CHANNEL_ID = 1469780138496360555  # Replace with your channel ID

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix=";", intents=intents)

routes = web.RouteTableDef()

@routes.post("/nexus-webhook")
async def nexus_webhook(request):
    try:
        data = await request.json()
        print("Webhook received!", data)
    except Exception as e:
        print("Failed to parse webhook JSON:", e)
        return web.Response(status=400, text="Bad Request")

    # Ensure the bot has fetched the channel
    channel = bot.get_channel(ALERT_CHANNEL_ID)

    matches = data.get("matches", [])
    now_queuing_label = data.get("nowQueuing")

    # Prefer the "nowQueuing" match if present
    match = next((m for m in matches if m.get("label") == now_queuing_label), None)
    if not match and matches:
        match = matches[0]  # fallback

    if match:
        match_name = match.get("label", "Unknown")
        status = match.get("status", "Unknown")
        red = match.get("redTeams", [])
        blue = match.get("blueTeams", [])

        # Ensure all team numbers are strings
        red = [str(t) for t in red]
        blue = [str(t) for t in blue]

        if isinstance(channel, discord.TextChannel):
            await channel.send(
                f"⏭ Match Update: **{match_name}**\n"
                f"Status: {status}\n"
                f"🔴 Red: {', '.join(red)}\n"
                f"🔵 Blue: {', '.join(blue)}"
            )

    return web.Response(text="OK")

app = web.Application()
app.add_routes(routes)

async def start_webhook():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    print("Webhook server started on port 8000")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(start_webhook())

bot.run(TOKEN) # type: ignore