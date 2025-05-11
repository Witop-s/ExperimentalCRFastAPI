import os
import discord
import requests
from dotenv import load_dotenv

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

load_dotenv()

RESULTS_BASE_URL = os.getenv("RESULTS_BASE_URL")

@bot.command(description="Bilan cumulatif des x dernières semaines")
async def bilan(ctx, weeks: int, skip_weeks: int = 0, limit: int = 10):
    characters_limit = 70 # Clash Royale limit
    url = f"{RESULTS_BASE_URL}?weeks={weeks}&skip_weeks={skip_weeks}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()["results"][:limit]  # Apply the limit

            messages = []
            current_message = ""

            for i, line in enumerate(data, start=1):
                next_line = f"{i} - {line}\n"
                if len(current_message) + len(next_line) > characters_limit:
                    messages.append(current_message)
                    current_message = next_line
                else:
                    current_message += next_line

            if current_message:
                messages.append(current_message)

            for msg in messages:
                await ctx.respond(msg)

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