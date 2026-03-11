import os
import discord
import aiohttp
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("NEXUS_API_KEY")        
NEXUS_API_URL = os.getenv("NEXUS_API_URL")

EVENT_KEY = None
DEFAULT_TEAM = 1091

bot = commands.Bot(command_prefix=";", intents=discord.Intents.all())


async def fetch_events():
    """Fetch events list"""

    if not API_KEY:
        # Mock data for testing
        return [
            {"name": "Milwaukee Regional", "key": "2024mke"},
            {"name": "Wisconsin Regional", "key": "2024wi"}
        ]

    headers = {"Nexus-Api-Key": API_KEY}
    url = f"{NEXUS_API_URL}/events"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json()


async def fetch_event_data():
    """Fetch match data"""

    if EVENT_KEY is None:
        return {
            "nowQueuing": "Qualification 12",
            "matches": [
                {
                    "matchName": "Qualification 13",
                    "teams": [1091, 1678, 254, 971, 4414, 1323]
                },
                {
                    "matchName": "Qualification 14",
                    "teams": [118, 148, 2056, 33, 16, 1923]
                }
            ]
        }

    headers = {"Nexus-Api-Key": API_KEY}
    url = f"{NEXUS_API_URL}/event/{EVENT_KEY}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp: # type: ignore
            return await resp.json()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.command()
async def setevent(ctx, *, event_name: str):
    """Set event by name"""
    global EVENT_KEY

    events = await fetch_events()

    for event in events:
        # Determine if event is a dict or string
        if isinstance(event, dict):
            name = event.get("name") or event.get("label") or str(event)
            key = event.get("key") or event.get("keyName") or str(event)
        else:
            # it's a string
            name = str(event)
            key = str(event)  # sometimes API returns key same as name

        if event_name.lower() in name.lower():
            EVENT_KEY = key
            await ctx.send(f"✅ Event set to **{name}**\nKey: `{EVENT_KEY}`")
            return

    await ctx.send("❌ Could not find that event.")


@bot.command()
async def queuing(ctx):
    """Show current queuing match"""
    data = await fetch_event_data()

    match = data.get("nowQueuing")

    if match:
        await ctx.send(f"🚦 Currently Queuing: **{match}**")
    else:
        await ctx.send("Nothing is queuing.")


@bot.command()
async def nextmatch(ctx):
    """Next match at event"""
    data = await fetch_event_data()
    matches = data.get("matches", [])

    if not matches:
        await ctx.send("No upcoming matches.")
        return

    match = matches[0]

    if isinstance(match, dict):
        match_name = match.get("label", "Unknown Match")
        red_teams = match.get("redTeams", [])
        blue_teams = match.get("blueTeams", [])
        status = match.get("status", "Unknown status")

        await ctx.send(
            f"⏭ Next Match: **{match_name}**\n"
            f"Status: {status}\n"
            f"🔴 Red: {', '.join(red_teams)}\n"
            f"🔵 Blue: {', '.join(blue_teams)}"
        )
    else:
        # if it's a string (unlikely now)
        await ctx.send(f"⏭ Next Match: **{str(match)}**")


@bot.command()
async def teamnext(ctx, team: int = DEFAULT_TEAM):
    """Next match for team (default 1091)"""

    data = await fetch_event_data()
    matches = data.get("matches", [])

    for match in matches:
        if team in match.get("teams", []):
            await ctx.send(
                f"🤖 Team **{team}** next match: **{match['matchName']}**"
            )
            return

    await ctx.send("Couldn't find a match for that team.")


bot.run(TOKEN) # type: ignore