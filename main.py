import logging
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Fetch values from .env
API_KEY = os.getenv("API_KEY")
CLAN_TAG = os.getenv("CLAN_TAG")

BASE_URL = "https://proxy.royaleapi.dev/v1"


def get_clan_info(clan_tag: str, start_date: datetime, end_date: datetime = None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }

    # Get clan information
    clan_url = f"{BASE_URL}/clans/%23{clan_tag[1:]}"
    clan_response = requests.get(clan_url, headers=headers)

    if clan_response.status_code != 200:
        logging.error(f"Failed to fetch clan data. Status code: {clan_response.status_code}")
        logging.error(f"Response content: {clan_response.text}")
        raise HTTPException(status_code=500, detail="Failed to fetch clan data")

    clan_data = clan_response.json()

    if 'memberList' not in clan_data:
        logging.error("'memberList' not found in clan data")
        raise HTTPException(status_code=500, detail="'memberList' not found in clan data")

    # Get river race log
    riverrace_url = f"{BASE_URL}/clans/%23{clan_tag[1:]}/riverracelog"
    riverrace_response = requests.get(riverrace_url, headers=headers)

    if riverrace_response.status_code != 200:
        logging.error(f"Failed to fetch river race log. Status code: {riverrace_response.status_code}")
        logging.error(f"Response content: {riverrace_response.text}")
        raise HTTPException(status_code=500, detail="Failed to fetch river race log")

    riverrace_data = riverrace_response.json()

    player_info = {}

    for member in clan_data["memberList"]:
        player_tag = member["tag"]
        donations = member["donations"]
        donations_received = member["donationsReceived"]
        player_info[player_tag] = {
            "name": member["name"],
            "rank": member["role"],
            "last_week_points": 0,
            "last_week_attacks": 0,
            "last_week_boat_attacks": 0,
            "total_wars": 0,
            "total_points": 0,
            "total_attacks": 0,
            "streak_above_3000": 0,
            "streak_below_1600": 0,
            "donations": donations,
            "donations_received": donations_received,
            "donation_ratio": donations / donations_received if donations_received > 0 else float('inf')
        }

    # Process river races
    for race in reversed(riverrace_data["items"]):  # from oldest to newest
        race_end_time = datetime.strptime(race["createdDate"], "%Y%m%dT%H%M%S.%fZ")

        # Skip if before start_date or after end_date (if provided)
        if race_end_time < start_date:
            continue
        if end_date and race_end_time > end_date:
            continue

        for standing in race["standings"]:
            if standing["clan"]["tag"] == clan_tag:
                for participant in standing["clan"]["participants"]:
                    player_tag = participant["tag"]
                    if player_tag in player_info:
                        player_info[player_tag]["total_wars"] += 1
                        player_info[player_tag]["total_points"] += participant["fame"]
                        player_info[player_tag]["total_attacks"] += participant["decksUsed"]

                        # If within the last week, update last_week_* stats
                        if race_end_time > (datetime.now() - timedelta(days=7)):
                            player_info[player_tag]["last_week_points"] = participant["fame"]
                            player_info[player_tag]["last_week_attacks"] = participant["decksUsed"]
                            player_info[player_tag]["last_week_boat_attacks"] = participant["boatAttacks"]

                        # Update streaks
                        if participant["fame"] >= 3000:
                            player_info[player_tag]["streak_above_3000"] += 1
                        else:
                            player_info[player_tag]["streak_above_3000"] = 0

                        if participant["fame"] < 1600:
                            player_info[player_tag]["streak_below_1600"] += 1
                        else:
                            player_info[player_tag]["streak_below_1600"] = 0

    # Calculate averages
    for player in player_info.values():
        if player["total_wars"] > 0:
            player["avg_points_per_week"] = player["total_points"] / player["total_wars"]
            player["avg_attacks_per_week"] = player["total_attacks"] / player["total_wars"]
        else:
            player["avg_points_per_week"] = 0
            player["avg_attacks_per_week"] = 0

    return player_info


app = FastAPI()


@app.get("/cr/api/results")
def get_results(
        weeks: int = Query(1, description="Number of past war weeks"),
        skip_weeks: int = Query(0, description="Number of recent weeks to skip")
):
    now = datetime.now()

    # Calculate the end date (now minus the number of weeks to skip)
    end_date = None
    if skip_weeks > 0:
        end_date = now - timedelta(weeks=skip_weeks)

    # Calculate the start date (end_date minus the number of weeks to include)
    start_date = (now - timedelta(weeks=(weeks + skip_weeks))).date()
    start_datetime = datetime.combine(start_date, datetime.min.time())

    clan_info = get_clan_info(CLAN_TAG, start_datetime, end_date)

    # Sort by total_points descending
    # Convert dict to list for easier sorting
    players_list = list(clan_info.items())
    players_list.sort(key=lambda x: x[1]["total_points"], reverse=True)

    # Group by total_points
    results = []
    grouped = {}
    for tag, info in players_list:
        pts = info["total_points"]
        if pts not in grouped:
            grouped[pts] = []
        grouped[pts].append(info["name"])

    # Create the final structure:
    # Each entry: {"line": "member1 & member2 / total_points"}
    for pts, members in sorted(grouped.items(), key=lambda x: x[0], reverse=True):
        line = ", ".join(members)
        # Replace the last occurrence of ", " by " & "
        if len(members) > 1:
            # Calculate the character to replace
            to_replace = sum(len(member) for member in members[:-1]) + 2 * (len(members) - 1) - 2
            line = line[:to_replace] + " &" + line[to_replace + 1:]
        line += f" / {pts}"
        results.append(line)

    # Add time range information to results
    time_range = f"From {start_date.strftime('%Y-%m-%d')}"
    if end_date:
        time_range += f" to {end_date.date().strftime('%Y-%m-%d')}"

    return {
        "results": results,
        "time_range": time_range
    }