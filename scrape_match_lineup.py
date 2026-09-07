"""
Henter en kampside og beregner minutter spilt per spiller, ved å kombinere:
  - Startoppstilling/Innbyttere (hvem startet, hvem satt på benken)
  - Kamphendelser-tidslinjen: innbytter-hendelser ("Inn:"/"Ut:" med minutt)
    og røde kort (avslutter en spillers kamp tidlig)

Antar 90 minutters kamplengde (standard senior 11-er-fotball; ekstraomganger/
straffesparkkonkurranser i seriespill forekommer ikke og er ikke håndtert).
"""
from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

from config import BASE_URL, HEADERS

MATCH_LENGTH_MINUTES = 90
CARD_LABELS = {"Advarsel": "yellow", "Utvisning": "red"}


def fetch_match_html(fiks_id: int) -> str:
    url = f"{BASE_URL}/fotballdata/kamp/?fiksId={fiks_id}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse_player_list(ul_div) -> list[dict]:
    players = []
    for item in ul_div.select(".matchPlayerListItem"):
        num_el = item.select_one(".playerNumber")
        name_el = item.select_one(".playerName")
        if not name_el:
            continue
        fiks_match = re.search(r"fiksId=(\d+)", name_el.get("href", ""))
        players.append({
            "number": num_el.get_text(strip=True) if num_el else None,
            "name": name_el.get_text(strip=True),
            "profile_fiksId": int(fiks_match.group(1)) if fiks_match else None,
        })
    return players


def _parse_side_lineup(wrapper) -> dict:
    sections = {}
    current_label = None
    for el in wrapper.find_all(["h4", "div"], recursive=True):
        if el.name == "h4":
            current_label = el.get_text(strip=True).rstrip(":")
        elif el.name == "div" and "a_matchPlayerList" in el.get("class", []) and current_label:
            sections[current_label] = _parse_player_list(el)
            current_label = None
    return {
        "starting_xi": sections.get("Startoppstilling", []),
        "substitutes": sections.get("Innbyttere", []),
    }


def parse_lineups(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    home_wrapper = soup.select_one(".homeTeamWrapper")
    away_wrapper = soup.select_one(".awayTeamWrapper")
    return {
        "home": _parse_side_lineup(home_wrapper) if home_wrapper else {"starting_xi": [], "substitutes": []},
        "away": _parse_side_lineup(away_wrapper) if away_wrapper else {"starting_xi": [], "substitutes": []},
    }


def parse_timeline_events(html: str) -> list[dict]:
    """
    Returnerer ALLE hendelser (kort + bytter) fra Kamphendelser-tidslinjen,
    ikke bare kort (se scrape_match.py i iffram-karantene-prosjektet for en
    variant som kun henter kort).
    """
    soup = BeautifulSoup(html, "lxml")
    wrapper = soup.select_one('.tabulatedContentWrapper[data-tab="kamphendelser"]')
    if not wrapper:
        return []

    events = []
    for line in wrapper.select(".timelineEventLine"):
        classes = line.get("class", [])
        side = "home" if "homeTeam" in classes else ("away" if "awayTeam" in classes else None)
        minute_el = line.select_one(".timelineMinute")
        minute_text = minute_el.get_text(strip=True).rstrip("'") if minute_el else None
        minute = int(minute_text) if minute_text and minute_text.isdigit() else None

        for content in line.select(".timelineEventContent"):
            # Kort: <a class="eventHeading">Navn</a> + <div>Advarsel|Utvisning</div>
            label_div = content.find("div")
            heading = content.find("a", class_="eventHeading")
            if label_div and heading and label_div.get_text(strip=True) in CARD_LABELS:
                fiks_match = re.search(r"fiksId=(\d+)", heading.get("href", ""))
                events.append({
                    "type": "card",
                    "card_type": CARD_LABELS[label_div.get_text(strip=True)],
                    "side": side, "minute": minute,
                    "profile_fiksId": int(fiks_match.group(1)) if fiks_match else None,
                    "player_name": heading.get_text(strip=True),
                })
                continue

            # Bytte: <div class="eventHeading"><span>Inn: </span><a>Navn</a></div>
            #        <div><span>Ut: </span><a>Navn</a></div>
            heading_div = content.find("div", class_="eventHeading")
            if heading_div and "Inn" in heading_div.get_text():
                in_link = heading_div.find("a")
                in_fiks = re.search(r"fiksId=(\d+)", in_link.get("href", "")) if in_link else None
                out_link = None
                for sub_div in content.find_all("div"):
                    if sub_div is heading_div:
                        continue
                    if "Ut" in sub_div.get_text():
                        out_link = sub_div.find("a")
                        break
                out_fiks = re.search(r"fiksId=(\d+)", out_link.get("href", "")) if out_link else None
                events.append({
                    "type": "sub",
                    "side": side, "minute": minute,
                    "in_profile_fiksId": int(in_fiks.group(1)) if in_fiks else None,
                    "in_player_name": in_link.get_text(strip=True) if in_link else None,
                    "out_profile_fiksId": int(out_fiks.group(1)) if out_fiks else None,
                    "out_player_name": out_link.get_text(strip=True) if out_link else None,
                })
    return events


def compute_minutes(lineups: dict, events: list[dict]) -> dict:
    """Returnerer {profile_fiksId: {"name":..., "side":..., "minutes": int}}."""
    result: dict = {}

    for side in ("home", "away"):
        subbed_out_minute: dict = {}
        subbed_in_minute: dict = {}
        red_card_minute: dict = {}

        for ev in events:
            if ev.get("side") != side:
                continue
            if ev["type"] == "sub":
                if ev["out_profile_fiksId"]:
                    subbed_out_minute[ev["out_profile_fiksId"]] = ev["minute"]
                if ev["in_profile_fiksId"]:
                    subbed_in_minute[ev["in_profile_fiksId"]] = ev["minute"]
            elif ev["type"] == "card" and ev["card_type"] == "red" and ev["profile_fiksId"]:
                red_card_minute[ev["profile_fiksId"]] = ev["minute"]

        for p in lineups[side]["starting_xi"]:
            fid = p["profile_fiksId"]
            if not fid:
                continue
            end = subbed_out_minute.get(fid, MATCH_LENGTH_MINUTES)
            if fid in red_card_minute:
                end = min(end, red_card_minute[fid])
            result[fid] = {"name": p["name"], "side": side, "minutes": max(0, end)}

        for fid, start in subbed_in_minute.items():
            end = subbed_out_minute.get(fid, MATCH_LENGTH_MINUTES)
            if fid in red_card_minute:
                end = min(end, red_card_minute[fid])
            name = next((p["name"] for p in lineups[side]["substitutes"] if p["profile_fiksId"] == fid), None)
            result[fid] = {"name": name, "side": side, "minutes": max(0, end - start)}

    return result


def fetch_match_minutes(fiks_id: int) -> dict:
    html = fetch_match_html(fiks_id)
    lineups = parse_lineups(html)
    events = parse_timeline_events(html)
    return compute_minutes(lineups, events)


if __name__ == "__main__":
    import json
    import sys
    fiks_id = int(sys.argv[1]) if len(sys.argv) > 1 else 8996099
    print(json.dumps(fetch_match_minutes(fiks_id), ensure_ascii=False, indent=2))
