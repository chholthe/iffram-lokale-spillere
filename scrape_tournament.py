"""
Henter en turnerings fulle terminliste (/fotballdata/turnering/terminliste/)
og filtrerer ut kampene til ETT gitt lag. Brukes for HISTORISKE sesonger, der
laget sin egen lagside kun viser inneværende sesong — turneringssiden for det
aktuelle året (funnet manuelt per sesong, se config.HISTORICAL_SEASONS)
inneholder derimot alle kamper for alle lag i den turneringen det året.
"""
from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

from config import BASE_URL, HEADERS


def fetch_tournament_html(tournament_fiks_id: int) -> str:
    url = f"{BASE_URL}/fotballdata/turnering/terminliste/?fiksId={tournament_fiks_id}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_tournament_fixtures(html: str, team_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    fixtures = []
    for row in soup.select("table.customSorterAtomicMatches tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 7:
            continue
        date_link = cells[1].find("a")
        home = cells[4].get_text(strip=True)
        result_link = cells[5].find("a")
        away = cells[6].get_text(strip=True)
        if team_name not in (home, away):
            continue

        fiks_match = re.search(r"fiksId=(\d+)", date_link.get("href", "")) if date_link else None
        result_text = result_link.get_text(strip=True) if result_link else ""

        fixtures.append({
            "fiksId": int(fiks_match.group(1)) if fiks_match else None,
            "date_text": date_link.get_text(strip=True) if date_link else None,
            "home": home,
            "away": away,
            "result": result_text,
            "played": bool(re.match(r"^\d+\s*-\s*\d+$", result_text)),
            "tournament_name": "",
            "counted": True,
        })
    return fixtures


def fetch_team_matches_in_tournament(tournament_fiks_id: int, team_name: str) -> list[dict]:
    html = fetch_tournament_html(tournament_fiks_id)
    return parse_tournament_fixtures(html, team_name)
