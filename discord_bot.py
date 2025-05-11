import os
import discord
import requests
from dotenv import load_dotenv

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

load_dotenv()

RESULTS_BASE_URL = os.getenv("RESULTS_BASE_URL")

@bot.command(description="Bilan cumulatif des x dernières semaines")
async def bilan(ctx, weeks: int, limit: int, skip_weeks: int = 0):
    url = f"{RESULTS_BASE_URL}?weeks={weeks}&skip_weeks={skip_weeks}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            results = data["results"]
            time_range = data.get("time_range", "")

            message = f"**Bilan {time_range}**\n"
            for i in range(min(len(results), limit)):
                message += f"{i+1} - {results[i]}\n"
            await ctx.respond(message)

        else:
            # Handle cases where the request fails
            await ctx.respond(f"Failed to fetch data. HTTP Status: {response.status_code}")
    except Exception as e:
        await ctx.respond(f"An error occurred: {str(e)}")

@bot.command(description="Bilan historique en sautant des semaines")
async def bilan_historique(ctx, weeks: int, skip_weeks: int, limit: int = 10):
    url = f"{RESULTS_BASE_URL}?weeks={weeks}&skip_weeks={skip_weeks}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            results = data["results"]
            time_range = data.get("time_range", "")

            message = f"**Bilan historique {time_range}**\n"
            for i in range(min(len(results), limit)):
                message += f"{i+1} - {results[i]}\n"
            await ctx.respond(message)

        else:
            # Handle cases where the request fails
            await ctx.respond(f"Failed to fetch data. HTTP Status: {response.status_code}")
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