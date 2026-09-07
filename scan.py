"""
Orchestrerer hele skanningen, for flere sesonger:
  - 2026: A-laget + Fram 2 (lagets egen lagside, viser inneværende sesong).
  - 2025 og 2024: KUN A-laget (Fram 2 sin historiske turnering ble ikke
    funnet/er utelatt), hentet fra den historiske turneringens fulle
    terminliste (se scrape_tournament.py + config.HISTORICAL_A_LAG_SEASONS).

For hver (sesong, lag)-kombinasjon:
  1. Hent spilte konkurransekamper (serie + cup — ikke treningskamper).
  2. Hent kamptidslinjen for hver og beregn minutter spilt per spiller (kun
     for DETTE lagets side denne kampen).
  3. Bygg troppen dynamisk fra hvem som FAKTISK har spilt minutter.

Klassifisering (klubbtrent/larviks_spiller/annet) er en egenskap ved
SPILLEREN, ikke sesongen — historikken hentes og klassifiseres én gang per
spiller uansett hvor mange sesonger/lag de dukker opp i.

Lagrer resultatet i state.json, strukturert som state["seasons"][år][lag].
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from config import TEAMS, HISTORICAL_A_LAG_SEASONS
from scrape_team import fetch_team_fixtures
from scrape_tournament import fetch_team_matches_in_tournament
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


def collect_minutes(fixtures: list, team_name: str, match_cache: dict, label: str) -> dict:
    """Returnerer {profile_fiksId: {"name":..., "minutes": int, "matches": int}}."""
    counted_played = [f for f in fixtures if f.get("counted") and f.get("played")]

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
                print(f"[{label}] FEIL fiksId={fixture['fiksId']}: {e}", file=sys.stderr)
                continue
            match_cache[key] = per_player
            fetched += 1

        for fid_str, info in per_player.items():
            fid = int(fid_str)
            if not is_our_side(fixture, info["side"], team_name):
                continue
            totals.setdefault(fid, {"name": info["name"], "minutes": 0, "matches": 0})
            totals[fid]["minutes"] += info["minutes"]
            if info["minutes"] > 0:
                totals[fid]["matches"] += 1

    if fetched:
        print(f"[{label}] Hentet {fetched} nye kamper (resten fra cache).", file=sys.stderr)
    return totals


def build_scopes() -> list:
    """Returnerer [(season_label, team_key, team_label, team_name, fixtures_fn), ...]."""
    scopes = []
    for team_key, team_cfg in TEAMS.items():
        scopes.append((
            "2026", team_key, team_cfg["label"], team_cfg["team_name"],
            lambda cfg=team_cfg: fetch_team_fixtures(cfg["team_fiksId"]),
        ))
    for year, season_cfg in HISTORICAL_A_LAG_SEASONS.items():
        scopes.append((
            str(year), "a_lag", "A-laget", TEAMS["a_lag"]["team_name"],
            lambda cfg=season_cfg: (
                fetch_team_matches_in_tournament(cfg["league_tournament_fiksId"], "Fram Larvik")
                + cfg["cup_matches"]
            ),
        ))
    return scopes


def run() -> dict:
    match_cache = load_cache(MATCH_CACHE_PATH)
    history_cache = load_cache(HISTORY_CACHE_PATH)

    scopes = build_scopes()
    raw_minutes: dict = {}  # (season, team_key) -> {fid: {"name","minutes","matches"}}
    for season, team_key, team_label, team_name, fixtures_fn in scopes:
        fixtures = fixtures_fn()
        label = f"{team_label} {season}"
        raw_minutes[(season, team_key)] = collect_minutes(fixtures, team_name, match_cache, label)
    save_cache(MATCH_CACHE_PATH, match_cache)

    all_fids = {fid for totals in raw_minutes.values() for fid in totals}

    classifications: dict = {}
    for fid in all_fids:
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
        classifications[fid] = classify_player(history)
    save_cache(HISTORY_CACHE_PATH, history_cache)

    seasons_out: dict = {}
    for (season, team_key), totals in raw_minutes.items():
        players_out = []
        for fid, info in totals.items():
            cls = classifications[fid]
            players_out.append({
                "profile_fiksId": fid,
                "name": info["name"],
                "minutes": info["minutes"],
                "matches": info["matches"],
                "classification": cls["classification"],
                "detail": cls["detail"],
            })
        players_out.sort(key=lambda p: -p["minutes"])

        by_classification: dict = {}
        for p in players_out:
            by_classification.setdefault(p["classification"], {"total_minutes": 0, "players": []})
            by_classification[p["classification"]]["total_minutes"] += p["minutes"]
            by_classification[p["classification"]]["players"].append(p)

        seasons_out.setdefault(season, {})[team_key] = {
            "players": players_out,
            "by_classification": by_classification,
            "grand_total_minutes": sum(p["minutes"] for p in players_out),
        }

    state = {"seasons": seasons_out}
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


if __name__ == "__main__":
    state = run()
    for season, teams in state["seasons"].items():
        for team_key, data in teams.items():
            print(f"{season} {team_key}: {len(data['players'])} spillere, "
                  f"{data['grand_total_minutes']} minutter.", file=sys.stderr)
