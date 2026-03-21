import os
import discord
import aiohttp
from discord.ext import commands
from dotenv import load_dotenv
from discord.ext import tasks


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("NEXUS_API_KEY")        
NEXUS_API_URL = os.getenv("NEXUS_API_URL")

EVENT_KEY = "2026wiapp"
DEFAULT_TEAM = 1091

alert_channel = None
last_alert_match = None
ALLOWED_USERS = {1227388850574200974}

bot = commands.Bot(command_prefix=";", intents=discord.Intents.all())


async def fetch_events():
    headers = {"Nexus-Api-Key": API_KEY}
    url = f"{NEXUS_API_URL}/events"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp: # type: ignore
            data = await resp.json()

            # return the actual list of events
            if isinstance(data, dict):
                return data.get("events", [])

            return data


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
        
def clean_teams(team_list):
    return [str(t) for t in team_list if t is not None]

def format_teams(team_list):
    return ', '.join(clean_teams(team_list))

@tasks.loop(seconds=30)
async def match_alerts():
    global last_alert_match

    if not alert_channel:
        return

    data = await fetch_event_data()
    matches = data.get("matches", [])

    if not matches:
        return

    match = matches[0]

    if not isinstance(match, dict):
        return

    label = match.get("label")

    if label == last_alert_match:
        return

    red = clean_teams(match.get("redTeams", []))
    blue = clean_teams(match.get("blueTeams", []))

    if str(DEFAULT_TEAM) in red + blue:
        last_alert_match = label

        await alert_channel.send(
            f"🚨 **MATCH ALERT**\n"
            f"Team {DEFAULT_TEAM} is up soon!\n"
            f"Match: **{label}**"
        )

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    match_alerts.start()


@bot.command()
async def setevent(ctx, *, event_name: str):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("❌ You don't have permission to use this command.")
        return
    global EVENT_KEY

    events = await fetch_events()

    if not events:
        await ctx.send("❌ Could not fetch events from API.")
        return

    for event in events:
        name = event.get("name", "")
        key = event.get("key", "")

        if event_name.lower() in name.lower():
            EVENT_KEY = key

            await ctx.send(
                f"✅ Event set to **{name}**\n"
                f"Event Key: `{EVENT_KEY}`"
            )
            return

    await ctx.send("❌ Event not found.")


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
            f"🔴 Red: {', '.join(str(t) for t in red_teams if t is not None)}\n"
            f"🔵 Blue: {', '.join(str(t) for t in blue_teams if t is not None)}"
        )
    else:
        # if it's a string (unlikely now)
        await ctx.send(f"⏭ Next Match: **{str(match)}**")


@bot.command()
async def teamnext(ctx, team: int = DEFAULT_TEAM):
    data = await fetch_event_data()
    matches = data.get("matches", [])

    for match in matches:
        if not isinstance(match, dict):
            continue

        red = clean_teams(match.get("redTeams", []))
        blue = clean_teams(match.get("blueTeams", []))

        if str(team) in red + blue:
            alliance = "🔴 Red" if str(team) in red else "🔵 Blue"
            partners = red if alliance == "🔴 Red" else blue

            await ctx.send(
                f"🤖 Team **{team}** next match: **{match.get('label')}**\n"
                f"{alliance} Alliance\n"
                f"Partners: {', '.join(partners)}\n"
                f"Status: {match.get('status')}"
            )
            return

    await ctx.send("No upcoming match found.")

@bot.command()
async def matchesleft(ctx, team: int = DEFAULT_TEAM):
    data = await fetch_event_data()
    matches = data.get("matches", [])

    count = 0

    for match in matches:
        if not isinstance(match, dict):
            continue

        red = clean_teams(match.get("redTeams", []))
        blue = clean_teams(match.get("blueTeams", []))

        if str(team) in red + blue:
            await ctx.send(f"⏳ Team **{team}** plays in **{count} matches**")
            return

        count += 1

    await ctx.send("Couldn't find upcoming match.")

@bot.command()
async def teammatches(ctx, team: int = DEFAULT_TEAM):
    data = await fetch_event_data()
    matches = data.get("matches", [])

    found = []

    for match in matches:
        if not isinstance(match, dict):
            continue

        red = clean_teams(match.get("redTeams", []))
        blue = clean_teams(match.get("blueTeams", []))

        if str(team) in red + blue:
            found.append(match.get("label"))

    if not found:
        await ctx.send("No matches found.")
        return

    await ctx.send(
        f"📅 Matches for **{team}**:\n" +
        "\n".join(found[:10])  # limit to avoid spam
    )

@bot.command()
async def alerts(ctx, channel: discord.TextChannel):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("❌ You don't have permission to use this command.")
        return
    global alert_channel
    alert_channel = channel
    await ctx.send(f"✅ Alerts set to {channel.mention}")

@bot.command()
async def testalert(ctx):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("❌ You don't have permission to use this command.")
        return
    global alert_channel

    if not alert_channel:
        await ctx.send("❌ No alert channel set. Use `;alerts #channel` first.")
        return

    await alert_channel.send(
        "🚨 **TEST ALERT**\n"
        "Team 1091 is up soon!\n"
        "Match: **Finals 85**\n"
        "🔴 Red Alliance: 1091, 254, 1678"
    )

    await ctx.send("✅ Test alert sent!")

bot.run(TOKEN) # type: ignore