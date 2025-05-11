import os
import discord
import requests
from dotenv import load_dotenv

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

load_dotenv()

RESULTS_BASE_URL = os.getenv("RESULTS_BASE_URL")


async def fetch_and_format_results(weeks, skip_weeks, limit=None, title_prefix="Bilan"):
    url = f"{RESULTS_BASE_URL}?weeks={weeks}&skip_weeks={skip_weeks}"

    response = requests.get(url)
    if response.status_code != 200:
        return f"Failed to fetch data. HTTP Status: {response.status_code}"

    data = response.json()
    results = data["results"]
    time_range = data.get("time_range", "")

    message = f"**{title_prefix} {time_range}**\n"

    # Determine how many results to show
    result_count = len(results) if limit is None else min(len(results), limit)

    for i in range(result_count):
        message += f"{i + 1} - {results[i]}\n"

    return message


@bot.command(description="Bilan complet des x dernières semaines")
async def bilan(ctx, weeks: int, skip_weeks: int = 0):
    try:
        message = await fetch_and_format_results(weeks, skip_weeks)
        await ctx.respond(message)
    except Exception as e:
        await ctx.respond(f"An error occurred: {str(e)}")


@bot.command(description="Top 10 du bilan des x dernières semaines")
async def bilantop(ctx, weeks: int, skip_weeks: int = 0):
    try:
        message = await fetch_and_format_results(weeks, skip_weeks, limit=10, title_prefix="Top 10")
        await ctx.respond(message)
    except Exception as e:
        await ctx.respond(f"An error occurred: {str(e)}")


try:
    token = os.getenv("TOKEN") or ""
    if token == "":
        raise Exception("No discord token found")
    bot.run(token)
except discord.HTTPException as e:
    if e.status == 429:
        print(
            "The Discord servers denied the connection for making too many requests"
        )
        print(
            "Get help from https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for"
            "-toomanyrequests"
        )
    else:
        raise e