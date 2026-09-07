"""
Henter en spillers profilside fra fotball.no og parser
'Sesongstatistikk'-tabellen — den eneste offentlige kilden til klubbhistorikk
(fødselsår/alder er IKKE tilgjengelig noe sted på fotball.no).

Tabellen viser én rad per (sesong, lag) spilleren har vært registrert for,
nyest først. Vi bruker denne til å avgjøre om spilleren noensinne har vært
registrert for en klubb utenfor IF Fram.
"""
from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

from config import BASE_URL, HEADERS


def fetch_player_html(fiks_id: int) -> str:
    url = f"{BASE_URL}/fotballdata/person/profil/?fiksId={fiks_id}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _season_sort_key(season_label: str) -> int:
    """Førsteårstall i sesongteksten ('Futsalsesongen 2024/2025' -> 2024)."""
    match = re.search(r"(\d{4})", season_label)
    return int(match.group(1)) if match else 0


def parse_season_history(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    heading = soup.find(
        lambda tag: tag.name == "div" and tag.get("class") == ["sectionHeadingContent"]
        and tag.get_text(strip=True) == "Sesongstatistikk"
    )
    if heading is None:
        return []

    table = heading.find_parent("div").find_next("table")
    if table is None:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue  # header eller ugyldig rad
        season_label = cells[0].get_text(strip=True)
        team_name = cells[1].get_text(strip=True)
        age_category = cells[2].get_text(strip=True) if len(cells) > 2 else None

        team_id = None
        matches = 0
        any_link = tr.find("a", attrs={"data-team-id": True})
        if any_link:
            team_id = int(any_link["data-team-id"])
        matches_link = cells[3].find("a") if len(cells) > 3 else None
        if matches_link:
            text = matches_link.get_text(strip=True)
            matches = int(text) if text.isdigit() else 0

        rows.append({
            "season_label": season_label,
            "season_year": _season_sort_key(season_label),
            "team_name": team_name,
            "team_fiksId": team_id,
            "age_category": age_category,
            "matches": matches,
        })

    # Nyest først i HTML-en allerede, men sørg eksplisitt for kronologisk
    # rekkefølge (eldst -> nyest) siden klassifiseringslogikken går fremover
    # i tid.
    rows.sort(key=lambda r: r["season_year"])
    return rows


def fetch_player_history(fiks_id: int) -> list[dict]:
    html = fetch_player_html(fiks_id)
    return parse_season_history(html)


if __name__ == "__main__":
    import json
    import sys
    fiks_id = int(sys.argv[1]) if len(sys.argv) > 1 else 3255986
    print(json.dumps(fetch_player_history(fiks_id), ensure_ascii=False, indent=2))
