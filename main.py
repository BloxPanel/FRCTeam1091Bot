import os
import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
NEXUS_API_URL = os.getenv("NEXUS_API_URL")
NEXUS_API_KEY = os.getenv("NEXUS_API_KEY")
ALERT_CHANNEL_ID = 1469780138496360555
TRACKED_TEAM = "100"

last_team_status = None
last_team_match = None

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=";",
    intents=intents,
)

DEMO_EVENT = False  # Set to True to use the demo event, False to require manual event setting

if DEMO_EVENT:
    current_event = "demo0923"
else:
    current_event = None

async def get_event_data(event_key: str):
    url = f"{NEXUS_API_URL}/event/{event_key}"

    headers = {
        "Nexus-Api-Key": NEXUS_API_KEY,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers=headers,
        ) as response:
            if response.status == 401:
                raise RuntimeError(
                    "Nexus API key is missing."
                )

            if response.status == 403:
                raise RuntimeError(
                    "Nexus API key is invalid."
                )

            if response.status == 404:
                raise RuntimeError(
                    f"Event `{event_key}` was not found."
                )

            if response.status != 200:
                raise RuntimeError(
                    f"Nexus returned HTTP {response.status}."
                )

            return await response.json()

def get_match_relative_to_queue(
    data: dict,
    offset: int,
):
    matches = data.get("matches", [])
    now_queuing = data.get("nowQueuing")

    if not matches or not now_queuing:
        return None

    queue_index = next(
        (
            i
            for i, match in enumerate(matches)
            if match.get("label") == now_queuing
        ),
        None,
    )

    if queue_index is None:
        return None

    target_index = queue_index + offset

    if target_index < 0 or target_index >= len(matches):
        return None

    return matches[target_index]

def get_team_queue_status(
    data: dict,
    team_number: str,
):
    matches = data.get("matches", [])
    now_queuing = data.get("nowQueuing")

    if not matches or not now_queuing:
        return None, None

    queue_index = next(
        (
            i
            for i, match in enumerate(matches)
            if match.get("label") == now_queuing
        ),
        None,
    )

    if queue_index is None:
        return None, None

    status_offsets = {
        -2: "On Field",
        -1: "On Deck",
        0: "Now Queuing",
        1: "Queuing Soon",
    }

    for offset, status in status_offsets.items():
        index = queue_index + offset

        if index < 0 or index >= len(matches):
            continue

        match = matches[index]

        red = [
            str(team)
            for team in match.get("redTeams", [])
        ]

        blue = [
            str(team)
            for team in match.get("blueTeams", [])
        ]

        if team_number in red or team_number in blue:
            return status, match

    return None, None

@tasks.loop(seconds=15)
async def queue_alerts():
    global last_team_status
    global last_team_match

    if current_event is None:
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        print(f"Nexus alert polling failed: {e}")
        return

    status, match = get_team_queue_status(
        data,
        TRACKED_TEAM,
    )

    if status is None or match is None:
        return

    match_label = match.get(
        "label",
        "Unknown Match",
    )

    if (
        status == last_team_status
        and match_label == last_team_match
    ):
        return

    last_team_status = status
    last_team_match = match_label

    channel = bot.get_channel(
        ALERT_CHANNEL_ID,
    )

    if not isinstance(
        channel,
        discord.TextChannel,
    ):
        return

    red = [
        str(team)
        for team in match.get("redTeams", [])
    ]

    blue = [
        str(team)
        for team in match.get("blueTeams", [])
    ]

    emoji = {
        "Queuing Soon": "⏳",
        "Now Queuing": "📣",
        "On Deck": "⏭️",
        "On Field": "🏟️",
    }.get(status, "🤖")

    embed = discord.Embed(
        title=f"{emoji} Team {TRACKED_TEAM} — {status}",
        description=f"**{match_label}**",
    )

    embed.add_field(
        name="🔴 Red Alliance",
        value=" • ".join(red) if red else "Unknown",
        inline=False,
    )

    embed.add_field(
        name="🔵 Blue Alliance",
        value=" • ".join(blue) if blue else "Unknown",
        inline=False,
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not queue_alerts.is_running():
        queue_alerts.start()

@bot.command(name="nextmatch")
async def nextmatch(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set.\n"
            "Use `;setevent <event>` first."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    matches = data.get("matches", [])
    now_queuing = data.get("nowQueuing")

    if not matches:
        await ctx.send(
            f"❌ Nexus has no matches for `{current_event}`."
        )
        return

    match = None

    if now_queuing:
        match = next(
            (
                m
                for m in matches
                if m.get("label") == now_queuing
            ),
            None,
        )

    if match is None:
        match = matches[0]

    label = match.get("label", "Unknown Match")
    status = match.get("status", "Unknown")

    red = [
        str(team)
        for team in match.get("redTeams", [])
    ]

    blue = [
        str(team)
        for team in match.get("blueTeams", [])
    ]

    embed = discord.Embed(
        title=f"📣 {label}",
        description=f"**Status:** {status}",
    )

    embed.add_field(
        name="🔴 Red Alliance",
        value=" • ".join(red) if red else "Unknown",
        inline=False,
    )

    embed.add_field(
        name="🔵 Blue Alliance",
        value=" • ".join(blue) if blue else "Unknown",
        inline=False,
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await ctx.send(embed=embed)

@bot.command(name="ondeck")
async def ondeck(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set.\n"
            "Use `;setevent <event>` first."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    match = get_match_relative_to_queue(
        data,
        -1,
    )

    if match is None:
        await ctx.send(
            "❌ No on-deck match could be determined."
        )
        return

    label = match.get("label", "Unknown Match")

    red = [
        str(team)
        for team in match.get("redTeams", [])
    ]

    blue = [
        str(team)
        for team in match.get("blueTeams", [])
    ]

    embed = discord.Embed(
        title=f"⏭️ On Deck — {label}",
    )

    embed.add_field(
        name="🔴 Red Alliance",
        value=" • ".join(red) if red else "Unknown",
        inline=False,
    )

    embed.add_field(
        name="🔵 Blue Alliance",
        value=" • ".join(blue) if blue else "Unknown",
        inline=False,
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await ctx.send(embed=embed)

@bot.command(name="onfield")
async def onfield(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set.\n"
            "Use `;setevent <event>` first."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    match = get_match_relative_to_queue(
        data,
        -2,
    )

    if match is None:
        await ctx.send(
            "❌ No on-field match could be determined."
        )
        return

    label = match.get("label", "Unknown Match")

    red = [
        str(team)
        for team in match.get("redTeams", [])
    ]

    blue = [
        str(team)
        for team in match.get("blueTeams", [])
    ]

    embed = discord.Embed(
        title=f"🏟️ On Field — {label}",
    )

    embed.add_field(
        name="🔴 Red Alliance",
        value=" • ".join(red) if red else "Unknown",
        inline=False,
    )

    embed.add_field(
        name="🔵 Blue Alliance",
        value=" • ".join(blue) if blue else "Unknown",
        inline=False,
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await ctx.send(embed=embed)

@bot.command(name="queuingsoon")
async def queuingsoon(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set.\n"
            "Use `;setevent <event>` first."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    match = get_match_relative_to_queue(
        data,
        1,
    )

    if match is None:
        await ctx.send(
            "❌ No queuing-soon match could be determined."
        )
        return

    label = match.get("label", "Unknown Match")

    red = [
        str(team)
        for team in match.get("redTeams", [])
    ]

    blue = [
        str(team)
        for team in match.get("blueTeams", [])
    ]

    embed = discord.Embed(
        title=f"⏳ Queuing Soon — {label}",
    )

    embed.add_field(
        name="🔴 Red Alliance",
        value=" • ".join(red) if red else "Unknown",
        inline=False,
    )

    embed.add_field(
        name="🔵 Blue Alliance",
        value=" • ".join(blue) if blue else "Unknown",
        inline=False,
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await ctx.send(embed=embed)

@bot.command(name="queue")
async def queue(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set.\n"
            "Use `;setevent <event>` first."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    on_field = get_match_relative_to_queue(
        data,
        -2,
    )

    on_deck = get_match_relative_to_queue(
        data,
        -1,
    )

    now_queuing = get_match_relative_to_queue(
        data,
        0,
    )

    queuing_soon = get_match_relative_to_queue(
        data,
        1,
    )

    embed = discord.Embed(
        title="📡 FRC Queue Status"
    )

    embed.add_field(
        name="🏟️ On Field",
        value=(
            on_field.get("label", "Unknown")
            if on_field
            else "None"
        ),
        inline=False,
    )

    embed.add_field(
        name="⏭️ On Deck",
        value=(
            on_deck.get("label", "Unknown")
            if on_deck
            else "None"
        ),
        inline=False,
    )

    embed.add_field(
        name="📣 Now Queuing",
        value=(
            now_queuing.get("label", "Unknown")
            if now_queuing
            else "None"
        ),
        inline=False,
    )

    embed.add_field(
        name="⏳ Queuing Soon",
        value=(
            queuing_soon.get("label", "Unknown")
            if queuing_soon
            else "None"
        ),
        inline=False,
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await ctx.send(embed=embed)

@bot.command(name="teamnext")
async def teamnext(
    ctx: commands.Context,
    team_number: int,
):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set.\n"
            "Use `;setevent <event>` first."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    matches = data.get("matches", [])

    if not matches:
        await ctx.send(
            f"❌ Nexus has no matches for `{current_event}`."
        )
        return

    now_queuing = data.get("nowQueuing")

    start_index = 0

    if now_queuing:
        queue_index = next(
            (
                i
                for i, match in enumerate(matches)
                if match.get("label") == now_queuing
            ),
            None,
        )

        if queue_index is not None:
            start_index = queue_index

    target_team = str(team_number)

    next_match = None

    for match in matches[start_index:]:
        red = [
            str(team)
            for team in match.get("redTeams", [])
        ]

        blue = [
            str(team)
            for team in match.get("blueTeams", [])
        ]

        if target_team in red or target_team in blue:
            next_match = match
            break

    if next_match is None:
        await ctx.send(
            f"❌ No upcoming match found for team `{team_number}`."
        )
        return

    label = next_match.get(
        "label",
        "Unknown Match",
    )

    red = [
        str(team)
        for team in next_match.get("redTeams", [])
    ]

    blue = [
        str(team)
        for team in next_match.get("blueTeams", [])
    ]

    alliance = (
        "Red"
        if target_team in red
        else "Blue"
    )

    embed = discord.Embed(
        title=f"🤖 Team {team_number}",
        description=f"Next match: **{label}**",
    )

    embed.add_field(
        name="Alliance",
        value=alliance,
        inline=False,
    )

    embed.add_field(
        name="🔴 Red Alliance",
        value=" • ".join(red) if red else "Unknown",
        inline=False,
    )

    embed.add_field(
        name="🔵 Blue Alliance",
        value=" • ".join(blue) if blue else "Unknown",
        inline=False,
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await ctx.send(embed=embed)

@bot.command(name="matches")
async def matches(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    all_matches = data.get("matches", [])
    now_queuing = data.get("nowQueuing")

    if not all_matches:
        await ctx.send(
            "❌ No matches found."
        )
        return

    start_index = 0

    if now_queuing:
        queue_index = next(
            (
                i
                for i, match in enumerate(all_matches)
                if match.get("label") == now_queuing
            ),
            None,
        )

        if queue_index is not None:
            start_index = queue_index

    upcoming = all_matches[
        start_index:start_index + 5
    ]

    lines = []

    for match in upcoming:
        label = match.get(
            "label",
            "Unknown",
        )

        status = match.get(
            "status",
            "Unknown",
        )

        lines.append(
            f"**{label}** — {status}"
        )

    embed = discord.Embed(
        title="📋 Upcoming Matches",
        description="\n".join(lines),
    )

    embed.set_footer(
        text=f"Nexus • Event {current_event}"
    )

    await ctx.send(embed=embed)

@bot.command(name="eventinfo")
async def eventinfo(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set."
        )
        return

    try:
        data = await get_event_data(current_event)
    except Exception as e:
        await ctx.send(
            f"❌ Failed to contact Nexus:\n`{e}`"
        )
        return

    matches = data.get("matches", [])
    now_queuing = data.get("nowQueuing")

    embed = discord.Embed(
        title="🏟️ Event Information"
    )

    embed.add_field(
        name="Event Key",
        value=current_event,
        inline=False,
    )

    embed.add_field(
        name="Matches Loaded",
        value=str(len(matches)),
        inline=False,
    )

    embed.add_field(
        name="Now Queuing",
        value=now_queuing or "None",
        inline=False,
    )

    embed.set_footer(
        text="Data provided by Nexus"
    )

    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.send("Pong!")


@bot.command(name="setevent")
async def setevent(
    ctx: commands.Context,
    event_code: str,
):
    global current_event

    current_event = event_code.strip()

    await ctx.send(
        f"✅ Event set to `{current_event}`"
    )


@bot.command(name="event")
async def event(ctx: commands.Context):
    if current_event is None:
        await ctx.send(
            "❌ No event is currently set."
        )
        return

    await ctx.send(
        f"📍 Current event: `{current_event}`"
    )


@bot.command(name="debug")
async def debug(ctx: commands.Context):
    api_url_loaded = bool(NEXUS_API_URL)
    api_key_loaded = bool(NEXUS_API_KEY)

    await ctx.send(
        "```text\n"
        f"Bot: ONLINE\n"
        f"Event: {current_event or 'Not set'}\n"
        f"API URL loaded: {api_url_loaded}\n"
        f"API key loaded: {api_key_loaded}\n"
        "```"
    )


bot.run(TOKEN)