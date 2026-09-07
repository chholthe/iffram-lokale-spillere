"""
Anslår om en spiller var under 19 år en gitt sesong, ut fra samme
'Alderskategori'-felt i sesonghistorikken som classify.py bruker for
alder-15-vurderingen (fødselsår er ikke offentlig tilgjengelig noe sted).

Primærmetode: fotball.no viser ofte en egen rad med "Ungdom 19 år" (eller
yngre) for NETTOPP den sesongen vi ser på — da er svaret sikkert.

Fallback: har spilleren en ELDRE ungdoms-alderskategori-rad (f.eks. "Ungdom
17 år" i 2024), anslås alderen i rapportsesongen ved å legge til antall år
som har gått siden. Mindre sikkert (spilleren kan ha blitt registrert i en
annen kategori enn "korrekt" alder det året), men bedre enn ingenting.

Har spilleren INGEN ungdoms-alderskategori i hele historikken, regnes de som
allerede voksen da fotball.no-historikken starter — status "ukjent", telles
IKKE som under 19.
"""
from __future__ import annotations

import re

YOUTH_AGE_RE = re.compile(r"Ungdom (\d+) år")


# Hvor mange års avvik mellom en "sikker" alder-i-år-X-rad og forløpet ellers
# i historikken som tolereres før raden mistenkes å være en feilregistrering
# hos fotball.no (sett i praksis: en spiller med sammenhengende "Ungdom 19
# år"-rader 2023-2025 fikk en enkeltstående, åpenbart uriktig "Ungdom 14 år"
# for 2026 på et helt annet lag — trolig feilkobling i fotball.no sin egen
# database, ikke en reell alder).
MAX_PLAUSIBLE_DEVIATION_YEARS = 3


def _trajectory_estimate(history: list[dict], report_year: int, exclude_row=None) -> dict | None:
    youth_rows = [r for r in history
                  if r is not exclude_row and r["age_category"] and YOUTH_AGE_RE.search(r["age_category"])]
    if not youth_rows:
        return None
    last = max(youth_rows, key=lambda r: r["season_year"])
    base_age = int(YOUTH_AGE_RE.search(last["age_category"]).group(1))
    return {"age": base_age + (report_year - last["season_year"]), "source": last}


def estimate_u19_status(history: list[dict], report_year: int) -> dict:
    confirmed_row = None
    confirmed_age = None
    for r in history:
        if r["season_year"] != report_year or not r["age_category"]:
            continue
        m = YOUTH_AGE_RE.search(r["age_category"])
        if m:
            confirmed_row = r
            confirmed_age = int(m.group(1))
            break

    if confirmed_row is not None:
        trajectory = _trajectory_estimate(history, report_year, exclude_row=confirmed_row)
        if trajectory is not None and abs(trajectory["age"] - confirmed_age) > MAX_PLAUSIBLE_DEVIATION_YEARS:
            # Den "sikre" raden strider mot resten av forløpet — mistenkelig
            # feilregistrering hos fotball.no. Stol på forløpet i stedet.
            est_age = trajectory["age"]
            src = trajectory["source"]
            return {
                "is_u19": est_age <= 19,
                "confidence": "estimated",
                "age_that_season": est_age,
                "detail": f"fotball.no viser «{confirmed_row['age_category']}» for {report_year} "
                          f"({confirmed_row['team_name']}), men det stemmer ikke med resten av "
                          f"forløpet — trolig feilregistrering. Anslått {est_age} år basert på "
                          f"«{src['age_category']}» i {src['season_year']} i stedet.",
            }
        return {
            "is_u19": confirmed_age <= 19,
            "confidence": "confirmed",
            "age_that_season": confirmed_age,
            "detail": f"Registrert som «Ungdom {confirmed_age} år» i {report_year}.",
        }

    trajectory = _trajectory_estimate(history, report_year)
    if trajectory is not None:
        est_age = trajectory["age"]
        src = trajectory["source"]
        return {
            "is_u19": est_age <= 19,
            "confidence": "estimated",
            "age_that_season": est_age,
            "detail": f"Ingen alderskategori for {report_year} — anslått {est_age} år basert "
                      f"på «{src['age_category']}» i {src['season_year']}.",
        }

    return {
        "is_u19": False,
        "confidence": "unknown",
        "age_that_season": None,
        "detail": "Ingen ungdoms-alderskategori funnet i historikken — sannsynligvis "
                  "allerede voksen da fotball.no sin historikk for spilleren starter.",
    }
