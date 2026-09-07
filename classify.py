"""
Klassifiserer en spiller som "klubbtrent", "larviks_spiller" eller "annet"
basert på sesonghistorikken fra scrape_player_history.py.

Primærmetode: finn raden(e) der Alderskategori inneholder "15 år" — dette er
det faktiske alder-15-tidspunktet klubben ba om. Sjekk hvilken klubb det var,
og om spilleren har vært UAVBRUTT hos Fram fra og med det tidspunktet.

Fallback (kun når historikken ikke inneholder noen alder-15-rad, typisk for
spillere som kom til fotball.no-systemet først som voksne — f.eks. utenlandsk
bakgrunn): bruk tidligste kjente klubb i hele historikken i stedet.
"""
from __future__ import annotations

from config import is_fram_team, is_larvik_club


def classify_player(history: list[dict]) -> dict:
    """
    history: kronologisk (eldst -> nyest) liste fra scrape_player_history.
    Returnerer {"classification": "klubbtrent"|"larviks_spiller"|"annet"|"ukjent",
                "detail": str}
    """
    if not history:
        return {"classification": "ukjent", "detail": "Ingen sesonghistorikk funnet."}

    age15_rows = [r for r in history if r["age_category"] and "15 år" in r["age_category"]]

    if age15_rows:
        idx15 = history.index(age15_rows[0])
        after15 = history[idx15:]

        at_fram_age15 = any(is_fram_team(r["team_fiksId"], r["team_name"]) for r in age15_rows)
        at_larvik_age15 = any(is_larvik_club(r["team_name"]) for r in age15_rows)
        ever_elsewhere_since_15 = any(
            not is_fram_team(r["team_fiksId"], r["team_name"]) for r in after15
        )

        if at_fram_age15 and not ever_elsewhere_since_15:
            return {
                "classification": "klubbtrent",
                "detail": f"Hos Fram siden {age15_rows[0]['season_year']} (15 år, "
                          f"{age15_rows[0]['team_name']}), aldri spilt for andre siden.",
            }
        if at_larvik_age15:
            return {
                "classification": "larviks_spiller",
                "detail": f"Spilte for {age15_rows[0]['team_name']} som 15-åring "
                          f"({age15_rows[0]['season_year']}), kom senere til Fram.",
            }
        return {
            "classification": "annet",
            "detail": f"Spilte for {age15_rows[0]['team_name']} som 15-åring "
                      f"({age15_rows[0]['season_year']}) — verken Fram eller Larvik-klubb.",
        }

    # Fallback: ingen alder-15-rad synlig i historikken. Finn den TIDLIGSTE
    # raden som faktisk IKKE er Fram (ikke nødvendigvis historikkens første
    # rad — en spiller kan ha startet hos Fram, vært innom en annen klubb en
    # sesong, og kommet tilbake; da er det den andre klubben som er relevant,
    # ikke nødvendigvis den aller første raden).
    non_fram_rows = [r for r in history if not is_fram_team(r["team_fiksId"], r["team_name"])]
    if not non_fram_rows:
        return {
            "classification": "klubbtrent",
            "detail": "Ingen alder-15-data i historikken; har aldri stått oppført for "
                      "annen klubb enn Fram i registrert historikk (fallback-metode).",
        }
    earliest_other = non_fram_rows[0]
    if is_larvik_club(earliest_other["team_name"]):
        return {
            "classification": "larviks_spiller",
            "detail": f"Ingen alder-15-data; tidligste kjente klubb utenfor Fram er "
                      f"{earliest_other['team_name']} ({earliest_other['season_year']}) — "
                      f"Larvik-klubb (fallback-metode).",
        }
    return {
        "classification": "annet",
        "detail": f"Ingen alder-15-data; tidligste kjente klubb utenfor Fram er "
                  f"{earliest_other['team_name']} ({earliest_other['season_year']}) — "
                  f"ikke Fram eller Larvik-klubb (fallback-metode).",
    }
