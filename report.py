"""
Genererer lesbare rapporter (norsk, markdown) fra state.json (bygget av
scan.py) — én per (sesong, lag)-kombinasjon. 2026 har både A-laget og Fram 2;
2025 og 2024 har kun A-laget (se scan.py/config.py for hvorfor).

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


def build_scope_report(state: dict, season: str, team_key: str) -> str:
    data = state["seasons"][season][team_key]
    team_label = TEAMS[team_key]["label"]
    other_key = OTHER_TEAM[team_key]
    other_data = state["seasons"].get(season, {}).get(other_key)
    other_minutes_by_fid = ({p["profile_fiksId"]: p["minutes"] for p in other_data["players"]}
                             if other_data else {})
    other_label = TEAMS[other_key]["label"]

    grand_total = data["grand_total_minutes"]

    lines = [f"# IF Fram {team_label} {season} — klubbtrente og Larviks-spillere", "",
             f"_Sesongen {season}. \"Egenutviklet spiller\" følger NFFs definisjon: en "
             f"spiller klubben selv har hatt og utviklet fra vedkommende var 15 år. "
             f"Basert på fotball.no sin sesonghistorikk per spiller (fødselsår er ikke "
             f"offentlig tilgjengelig — se forbehold nederst)._", ""]

    lines.append("## Sammendrag")
    lines.append(f"**Totalt {grand_total} minutter spilt** for {team_label} sesongen {season}, "
                 f"fordelt på {len(data['players'])} spillere:")
    for cls in CLASS_ORDER:
        info = data["by_classification"].get(cls)
        if not info:
            continue
        pct = round(100 * info["total_minutes"] / grand_total) if grand_total else 0
        lines.append(f"- {CLASS_LABELS[cls]}: **{info['total_minutes']} min** ({pct}%), "
                      f"{len(info['players'])} spillere")
    lines.append("")

    for cls in CLASS_ORDER:
        info = data["by_classification"].get(cls)
        if not info:
            continue
        lines.append(f"## {CLASS_LABELS[cls]}")
        lines.append("")
        for p in info["players"]:
            other_minutes = other_minutes_by_fid.get(p["profile_fiksId"], 0)
            extra = f" (har også {other_minutes} min for {other_label} denne sesongen)" if other_minutes else ""
            lines.append(f"- **{p['name']}** — {p['minutes']} min{extra}")
            lines.append(f"  - _{p['detail']}_")
        lines.append("")

    u19 = data["u19"]
    lines.append("## 🟡 Spillere under 19 år brukt")
    if u19["players"]:
        pct = round(100 * u19["total_minutes"] / grand_total) if grand_total else 0
        lines.append(f"**{u19['total_minutes']} min** ({pct}% av alle minutter), "
                     f"{len(u19['players'])} spillere:")
        for p in sorted(u19["players"], key=lambda p: -p["minutes"]):
            confidence_note = " (anslått alder)" if p["u19_confidence"] == "estimated" else ""
            lines.append(f"- **{p['name']}** — {p['minutes']} min, "
                         f"{p['age_that_season']} år{confidence_note}")
            lines.append(f"  - _{p['u19_detail']}_")
    else:
        lines.append("Ingen spillere under 19 år brukt denne sesongen.")
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
        f"kort) for alle spilte serie- og cupkamper {team_label} spilte sesongen "
        f"{season} — treningskamper telles ikke med. Antar 90 minutters kamplengde."
    )
    lines.append(
        f"- **Larvik-klubber** (avtalt med klubben): {', '.join(sorted(set(LARVIK_CLUBS)))}."
    )
    lines.append(
        "- **Under 19 år** avgjøres av samme «Alderskategori»-felt: en bekreftet "
        "«Ungdom X år»-rad for nettopp denne sesongen brukes når den finnes og stemmer "
        "med resten av forløpet, ellers anslås alderen ut fra siste kjente "
        "ungdoms-alderskategori pluss antall år som har gått. Stemmer ikke en "
        "«bekreftet» rad med forløpet ellers (avvik >3 år), mistenkes det å være en "
        "feilregistrering hos fotball.no, og forløpet brukes i stedet."
    )
    if other_data:
        lines.append(
            f"- Denne rapporten viser KUN minutter for {team_label}. Spillere som også "
            f"har spilt for {other_label} denne sesongen er notert med det, men de "
            f"minuttene telles ikke med her — se den andre lagets rapport for de tallene."
        )
    if season != "2026":
        lines.append(
            f"- Kamper for sesongen {season} er hentet fra den historiske turneringens "
            f"fulle terminliste (lagets egen side viser kun inneværende sesong). "
            f"Fram 2 er ikke inkludert for dette året."
        )

    return "\n".join(lines)


def build_reports(state: dict) -> dict:
    reports = {}
    for season, teams in state["seasons"].items():
        for team_key in teams:
            reports[(season, team_key)] = build_scope_report(state, season, team_key)
    return reports


if __name__ == "__main__":
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    reports = build_reports(state)
    for (season, team_key), report in reports.items():
        out_path = Path(f"report_{team_key}_{season}.md")
        out_path.write_text(report, encoding="utf-8")
        print(f"Skrev {out_path}")
