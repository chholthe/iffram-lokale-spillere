"""
Genererer to separate, lesbare rapporter (norsk, markdown) fra state.json
(bygget av scan.py) — én for A-laget, én for Fram 2. Klassifisering
(klubbtrent/larviks-spiller/annet) er den samme for en spiller uansett lag
(den handler om karrierehistorikk), men MINUTTENE i hver rapport gjelder kun
det aktuelle laget, ikke summert på tvers.

Kjør: python3 report.py
"""
from __future__ import annotations

import json
from pathlib import Path

from config import LARVIK_CLUBS, TEAMS

STATE_PATH = Path("state.json")

CLASS_LABELS = {
    "klubbtrent": "🟢 Klubbtrent (hos Fram siden 15 år / aldri spilt for andre)",
    "larviks_spiller": "🔵 Larviks-spiller (spilte for en Larvik-klubb før Fram)",
    "annet": "⚪ Annet (kom fra klubb utenfor Larvik)",
    "ukjent": "❓ Ukjent (ingen historikk funnet)",
}

CLASS_ORDER = ["klubbtrent", "larviks_spiller", "annet", "ukjent"]

OTHER_TEAM = {"a_lag": "fram2", "fram2": "a_lag"}


def build_team_report(state: dict, team_key: str) -> str:
    team_label = TEAMS[team_key]["label"]
    other_key = OTHER_TEAM[team_key]
    other_label = TEAMS[other_key]["label"]

    team_players = [p for p in state["players"] if p["minutes_by_team"].get(team_key, 0) > 0]
    team_players.sort(key=lambda p: -p["minutes_by_team"][team_key])
    grand_total = sum(p["minutes_by_team"][team_key] for p in team_players)

    by_classification: dict = {}
    for p in team_players:
        by_classification.setdefault(p["classification"], {"total_minutes": 0, "players": []})
        by_classification[p["classification"]]["total_minutes"] += p["minutes_by_team"][team_key]
        by_classification[p["classification"]]["players"].append(p)

    lines = [f"# IF Fram {team_label} — klubbtrente og Larviks-spillere", "",
             f"_Sesongen 2026. Basert på fotball.no sin sesonghistorikk per spiller "
             f"(fødselsår er ikke offentlig tilgjengelig — se forbehold nederst)._", ""]

    lines.append("## Sammendrag")
    lines.append(f"**Totalt {grand_total} minutter spilt** for {team_label} denne sesongen, "
                 f"fordelt på {len(team_players)} spillere:")
    for cls in CLASS_ORDER:
        info = by_classification.get(cls)
        if not info:
            continue
        pct = round(100 * info["total_minutes"] / grand_total) if grand_total else 0
        lines.append(f"- {CLASS_LABELS[cls]}: **{info['total_minutes']} min** ({pct}%), "
                      f"{len(info['players'])} spillere")
    lines.append("")

    for cls in CLASS_ORDER:
        info = by_classification.get(cls)
        if not info:
            continue
        lines.append(f"## {CLASS_LABELS[cls]}")
        lines.append("")
        for p in info["players"]:
            minutes_this_team = p["minutes_by_team"][team_key]
            other_minutes = p["minutes_by_team"].get(other_key, 0)
            extra = f" (har også {other_minutes} min for {other_label} denne sesongen)" if other_minutes else ""
            lines.append(f"- **{p['name']}** — {minutes_this_team} min{extra}")
            lines.append(f"  - _{p['detail']}_")
        lines.append("")

    lines.append("## Forbehold og metode")
    lines.append(
        "- **Fødselsår/alder er ikke offentlig tilgjengelig** noe sted på fotball.no. "
        "Der spillerens sesonghistorikk viser en tydelig \"Ungdom 15 år\"-rad, brukes "
        "den til å avgjøre nøyaktig hvilken klubb spilleren var på som 15-åring "
        "(presis metode). For mange lokalt oppfostrede spillere hopper fotball.no sin "
        "egen aldersmerking rett fra 14 til 16 år uten en egen 15-års-rad (typisk i "
        "mindre klubber med sammensatte årsklasser) — da brukes i stedet en "
        "fallback-metode: har spilleren ALDRI stått oppført for noen annen klubb enn "
        "Fram i hele sin registrerte historikk, regnes de som klubbtrent; ellers ser "
        "vi på tidligste klubb utenfor Fram."
    )
    lines.append(
        "- **Samarbeidslag** (f.eks. \"Fram / Hedrum og Sporty\") regnes som Fram, "
        "siden dette er vanlig i yngre årsklasser pga. få spillere og ikke en reell "
        "overgang til en annen klubb."
    )
    lines.append(
        f"- **Minutter** er beregnet fra kamptidslinjen (start/bytt inn/bytt ut/rødt "
        f"kort) for alle spilte serie- og cupkamper {team_label} har spilt denne "
        f"sesongen — treningskamper telles ikke med. Antar 90 minutters kamplengde."
    )
    lines.append(
        f"- **Larvik-klubber** (avtalt med klubben): {', '.join(sorted(set(LARVIK_CLUBS)))}."
    )
    lines.append(
        f"- Denne rapporten viser KUN minutter for {team_label}. Spillere som også har "
        f"spilt for {other_label} denne sesongen er notert med det, men de minuttene "
        f"telles ikke med her — se den andre lagets rapport for de tallene."
    )

    return "\n".join(lines)


def build_reports(state: dict) -> dict:
    return {team_key: build_team_report(state, team_key) for team_key in TEAMS}


if __name__ == "__main__":
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    reports = build_reports(state)
    for team_key, report in reports.items():
        out_path = Path(f"report_{team_key}.md")
        out_path.write_text(report, encoding="utf-8")
        print(f"Skrev {out_path}")
