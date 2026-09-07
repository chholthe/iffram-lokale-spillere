"""
Orchestrerer hele skanningen:
  1. For hvert lag (A-lag, Fram 2): hent kamptermin, finn spilte
     konkurransekamper (serie/cup — ikke treningskamper), hent kamptidslinjen
     for hver og beregn minutter spilt per spiller (kun for DETTE lagets side).
  2. Bygg troppen dynamisk fra hvem som FAKTISK har spilt minutter denne
     sesongen (mer komplett enn den offisielt oppgitte spillertroppen, som
     kan mangle enkeltspillere).
  3. For hver unike spiller: hent sesonghistorikk fra profilsiden og
     klassifiser (klubbtrent / larviks_spiller / annet / ukjent).
  4. Slå sammen minutter på tvers av lag (samme spiller kan ha spilt for
     begge) og grupper etter klassifisering.

Lagrer resultatet i state.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from config import TEAMS
from scrape_team import fetch_team_fixtures
from scrape_match_lineup import fetch_match_minutes
from scrape_player_history import fetch_player_history
from classify import classify_player

MATCH_CACHE_PATH = Path("raw/match_minutes_cache.json")
HISTORY_CACHE_PATH = Path("raw/player_history_cache.json")
STATE_PATH = Path("state.json")


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, cache: dict) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def is_our_side(fixture: dict, side: str, team_name: str) -> bool:
    team = fixture["home"] if side == "home" else fixture["away"]
    return team == team_name


def collect_team_minutes(team_key: str, team_cfg: dict, match_cache: dict) -> dict:
    """Returnerer {profile_fiksId: {"name":..., "minutes": int, "matches": int}}."""
    fixtures = fetch_team_fixtures(team_cfg["team_fiksId"])
    counted_played = [f for f in fixtures if f["counted"] and f["played"]]

    totals: dict = {}
    fetched = 0
    for fixture in counted_played:
        key = str(fixture["fiksId"])
        if key in match_cache:
            per_player = match_cache[key]
        else:
            try:
                per_player = fetch_match_minutes(fixture["fiksId"])
                time.sleep(0.3)
            except Exception as e:
                print(f"[{team_cfg['label']}] FEIL fiksId={fixture['fiksId']}: {e}", file=sys.stderr)
                continue
            match_cache[key] = per_player
            fetched += 1

        for fid_str, info in per_player.items():
            fid = int(fid_str)
            if not is_our_side(fixture, info["side"], team_cfg["team_name"]):
                continue
            totals.setdefault(fid, {"name": info["name"], "minutes": 0, "matches": 0})
            totals[fid]["minutes"] += info["minutes"]
            if info["minutes"] > 0:
                totals[fid]["matches"] += 1

    if fetched:
        print(f"[{team_cfg['label']}] Hentet {fetched} nye kamper (resten fra cache).", file=sys.stderr)
    return totals


def run() -> dict:
    match_cache = load_cache(MATCH_CACHE_PATH)
    history_cache = load_cache(HISTORY_CACHE_PATH)

    per_team_minutes = {}
    for team_key, team_cfg in TEAMS.items():
        per_team_minutes[team_key] = collect_team_minutes(team_key, team_cfg, match_cache)
    save_cache(MATCH_CACHE_PATH, match_cache)

    combined: dict = {}
    for team_key, totals in per_team_minutes.items():
        for fid, info in totals.items():
            combined.setdefault(fid, {"name": info["name"], "minutes_by_team": {}, "total_minutes": 0})
            combined[fid]["minutes_by_team"][team_key] = info["minutes"]
            combined[fid]["total_minutes"] += info["minutes"]

    players_out = []
    for fid, info in combined.items():
        cache_key = str(fid)
        if cache_key in history_cache:
            history = history_cache[cache_key]
        else:
            try:
                history = fetch_player_history(fid)
                time.sleep(0.3)
            except Exception as e:
                print(f"FEIL ved henting av spillerhistorikk fiksId={fid}: {e}", file=sys.stderr)
                history = []
            history_cache[cache_key] = history

        classification = classify_player(history)
        players_out.append({
            "profile_fiksId": fid,
            "name": info["name"],
            "total_minutes": info["total_minutes"],
            "minutes_by_team": info["minutes_by_team"],
            "classification": classification["classification"],
            "detail": classification["detail"],
        })

    save_cache(HISTORY_CACHE_PATH, history_cache)

    players_out.sort(key=lambda p: -p["total_minutes"])

    by_classification: dict = {}
    for p in players_out:
        by_classification.setdefault(p["classification"], {"total_minutes": 0, "players": []})
        by_classification[p["classification"]]["total_minutes"] += p["total_minutes"]
        by_classification[p["classification"]]["players"].append(p)

    state = {
        "players": players_out,
        "by_classification": by_classification,
        "grand_total_minutes": sum(p["total_minutes"] for p in players_out),
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


if __name__ == "__main__":
    state = run()
    print(f"Ferdig. {len(state['players'])} spillere, "
          f"{state['grand_total_minutes']} minutter totalt.", file=sys.stderr)
