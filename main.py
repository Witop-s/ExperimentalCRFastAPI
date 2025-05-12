import logging
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
import os
from dotenv import load_dotenv
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Fetch values from .env
API_KEY = os.getenv("API_KEY")
CLAN_TAG = os.getenv("CLAN_TAG")

BASE_URL = "https://proxy.royaleapi.dev/v1"

def get_clan_info(clan_tag: str, start_date: datetime, end_date: datetime):
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
        if race_end_time < start_date or race_end_time > end_date:
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

    # Detect duplicate names
    name_to_tags = defaultdict(list)
    for tag, info in player_info.items():
        name_to_tags[info["name"]].append(tag)

    # Update names of duplicates to include first chars of tag
    for name, tags in name_to_tags.items():
        if len(tags) > 1:
            for tag in tags:
                player_info[tag]["name"] += f" ({tag[0:3]})"

    return player_info

app = FastAPI()

@app.get("/cr/api/results")
def get_results(
    weeks: int = Query(1, description="Number of past war weeks"),
    skip_weeks: int = Query(0, description="Number of past war weeks to skip (starting from today)"),
    ranking: bool = Query(True, description="Whether to display rank changes")
):
    # Main period range
    end_datetime = datetime.now() - timedelta(weeks=skip_weeks)
    start_datetime = end_datetime - timedelta(weeks=weeks)
    start_datetime = datetime.combine(start_datetime.date(), datetime.min.time())
    end_datetime = datetime.combine(end_datetime.date(), datetime.min.time())

    print(f"Main range: {start_datetime.isoformat()} to {end_datetime.isoformat()}")
    clan_info = get_clan_info(CLAN_TAG, start_datetime, end_datetime)

    # Rank comparison setup
    previous_ranks = {}
    current_ranks = {}
    if ranking:
        compare_end = datetime.now() - timedelta(weeks=skip_weeks+1)
        compare_start = compare_end - timedelta(weeks=(weeks if weeks == 1 else weeks - 1))
        compare_start = datetime.combine(compare_start.date(), datetime.min.time())
        compare_end = datetime.combine(compare_end.date(), datetime.min.time())

        print(f"Comparison range: {compare_start.isoformat()} to {compare_end.isoformat()}")
        previous_info = get_clan_info(CLAN_TAG, compare_start, compare_end)

        previous_ranks = compute_ranks(previous_info)

    # Compute current ranks
    current_ranks = compute_ranks(clan_info)

    # Prepare list sorted by total_points descending
    players_list = sorted(clan_info.items(), key=lambda x: x[1]["total_points"], reverse=True)

    grouped = {}
    for tag, info in players_list:
        name = info["name"]
        pts = info["total_points"]

        if pts not in grouped:
            grouped[pts] = []

        arrow = ""
        if ranking:
            new_rank = current_ranks.get(name)
            old_rank = previous_ranks.get(name)

            print(f"Member: {name}, Points: {pts}, Rank: {new_rank}, Old Rank: {old_rank}")

            if old_rank is not None:
                if new_rank < old_rank:
                    arrow = f" 🔺{old_rank - new_rank}"
                elif new_rank > old_rank:
                    arrow = f" 🔻{new_rank - old_rank}"
                else:
                    arrow = " ▬"

        grouped[pts].append(name + arrow)

    # Format result lines
    results = []
    for pts, members in sorted(grouped.items(), key=lambda x: x[0], reverse=True):
        line = ", ".join(members)
        if len(members) > 1:
            to_replace = sum(len(member) for member in members[:-1]) + 2 * (len(members) - 1) - 2
            line = line[:to_replace] + " &" + line[to_replace + 1:]
        line += f" / {pts}"
        results.append(line)

    return {"results": results}

def compute_ranks(clan_data: dict) -> dict[str, int]:
    sorted_players = sorted(clan_data.items(), key=lambda x: x[1]["total_points"], reverse=True)

    ranks = {}
    current_rank = 1
    prev_points = None

    for tag, info in sorted_players:
        pts = info["total_points"]
        name = info["name"]

        if pts != prev_points:
            rank_to_assign = current_rank
            current_rank += 1

        # Else: same rank as before
        ranks[name] = rank_to_assign

        prev_points = pts

    return ranks
