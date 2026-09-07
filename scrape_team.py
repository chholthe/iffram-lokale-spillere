"""
Henter lagsiden (fiksId=<team_fiksId>) for et IF Fram-lag: kamptermin
(?underside=terminliste) og spillertropp (?underside=spillere).
"""
from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

from config import BASE_URL, COUNTED_TOURNAMENT_HINTS, HEADERS


def fetch_html(fiks_id: int, underside: str) -> str:
    url = f"{BASE_URL}/fotballdata/lag/hjem/?fiksId={fiks_id}&underside={underside}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_fixtures(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    fixtures = []
    for row in soup.select("table.tablesorter tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 8:
            continue
        date_link = cells[0].find("a")
        home_link = cells[3].find("a")
        result_link = cells[4].find("a")
        away_link = cells[5].find("a")
        tourn_link = cells[7].find("a")
        if not (date_link and home_link and away_link and tourn_link):
            continue

        fiks_match = re.search(r"fiksId=(\d+)", date_link.get("href", ""))
        result_text = result_link.get_text(strip=True) if result_link else ""
        tournament_name = tourn_link.get_text(strip=True)

        fixtures.append({
            "fiksId": int(fiks_match.group(1)) if fiks_match else None,
            "date_text": date_link.get_text(strip=True),
            "home": home_link.get_text(strip=True),
            "away": away_link.get_text(strip=True),
            "result": result_text,
            "played": bool(re.match(r"^\d+\s*-\s*\d+$", result_text)),
            "tournament_name": tournament_name,
            "counted": any(hint in tournament_name for hint in COUNTED_TOURNAMENT_HINTS),
        })
    return fixtures


def parse_squad(html: str) -> list[dict]:
    idx = html.rfind('data-tab="spillere"')
    if idx < 0:
        return []
    block_html = html[idx:idx + 80000]
    soup = BeautifulSoup(block_html, "lxml")

    position = None
    players = []
    for el in soup.find_all(["h3", "a"]):
        if el.name == "h3":
            d = el.find("div", class_="sectionHeadingContent")
            if d:
                position = d.get_text(strip=True)
        elif el.name == "a" and el.get("href", "").startswith("/fotballdata/person/profil"):
            name_el = el.find("div", class_="playerName")
            if not name_el:
                continue
            fiks_match = re.search(r"fiksId=(\d+)", el["href"])
            players.append({
                "position": position,
                "name": name_el.get_text(strip=True),
                "profile_fiksId": int(fiks_match.group(1)) if fiks_match else None,
            })
    return players


def fetch_team_fixtures(team_fiks_id: int) -> list[dict]:
    return parse_fixtures(fetch_html(team_fiks_id, "terminliste"))


def fetch_team_squad(team_fiks_id: int) -> list[dict]:
    return parse_squad(fetch_html(team_fiks_id, "spillere"))
