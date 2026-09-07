"""
Konfigurasjon for rapport om klubbtrente/Larviks-spillere i IF Fram.

Definisjoner (avtalt med klubben):
  - "Klubbtrent": spilleren har ALDRI stått oppført for noen annen klubb enn
    IF Fram i hele sin sesonghistorikk på fotball.no (siden fødselsår ikke er
    offentlig tilgjengelig, brukes "har aldri spilt for andre" som proxy for
    "har spilt i Fram fra 15 år").
  - "Larviks-spiller": spilleren har spilt for IF Fram nå, men hadde en eller
    flere sesonger for en av LARVIK_CLUBS FØR de kom til Fram.
  - "Annet": kom til Fram fra en klubb som verken er Fram selv eller en av
    LARVIK_CLUBS.

FRAM_TEAM_FIKS_IDS må oppdateres om klubben oppretter nye lag/årsklasser
(sjekk https://www.fotball.no/fotballdata/klubb/hjem/?fiksId=503).
"""
from __future__ import annotations

import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
BASE_URL = "https://www.fotball.no"

SEASON = 2026

CLUB_FIKS_ID = 503  # Idrettsforeningen Fram (klubbprofil)

# Lagene som inngår i denne rapporten (senior A-lag + Fram 2).
TEAMS = {
    "a_lag": {"label": "A-laget", "team_fiksId": 821, "team_name": "Fram Larvik"},
    "fram2": {"label": "Fram 2", "team_fiksId": 191, "team_name": "Fram Larvik 2"},
}

# Turneringsnavn som skal TELLES MED i minuttberegningen (konkurransekamper).
# Treningskamper ("Treningskamper 2026" e.l.) telles bevisst ikke med.
COUNTED_TOURNAMENT_HINTS = ["Norsk Tipping-ligaen", "NM menn", "5.div", "5. div"]

# Alle IF Frams egne lag sine fiksId-er (senior + alle årsklasser), hentet
# fra klubbprofilsiden. Brukes til å avgjøre om en sesong-rad i en spillers
# historikk faktisk er et EGET Fram-lag (ikke f.eks. et samarbeidslag som
# "Stag / Fram 2", som har en helt annen fiksId og ikke skal telle som Fram).
FRAM_TEAM_FIKS_IDS = {
    821: "Fram Larvik MEN 1 (A-laget)",
    191: "Fram Larvik MEN 2 (Fram 2)",
    13833: "Fram G10 blå",
    203305: "Fram G10 rød",
    142281: "Fram G11 rød",
    13206: "Fram G12 blå",
    184507: "Fram G12 rød",
    204905: "Fram G6 blå",
    193554: "Fram G6 hvit",
    13422: "Fram G6 rød",
    152263: "Fram G7 blå",
    58874: "Fram G7 rød",
    182737: "Fram G8 rød",
    175588: "Fram G9 blå",
    88329: "Fram G9 rød",
    58875: "Fram J7 rød",
    31149: "Fram J8 rød",
    187884: "Fram G14-1",
    170754: "Fram G14-2",
    146084: "Fram G17-1",
    180044: "Fram G19-1",
    118882: "Fram G19-2",
}

# Klubber som regnes som "i Larvik" for Larviks-spiller-definisjonen (oppgitt
# av klubben selv — geografisk plassering er ikke noe fotball.no eksponerer
# maskinlesbart, så dette må vedlikeholdes manuelt).
LARVIK_CLUBS = ["Nanset", "Stag", "Halsen", "Kvelde", "Nesjar", "Larvik Turn"]


def is_fram_team(team_fiks_id: int | None, team_name: str) -> bool:
    if team_fiks_id in FRAM_TEAM_FIKS_IDS:
        return True
    # Fallback for rader uten kjent team-id (typisk yngre årsklasser, som får
    # NY fiksId hvert år etter hvert som spillerne flyttes opp — FRAM_TEAM_
    # FIKS_IDS er kun et øyeblikksbilde og blir raskt ufullstendig for disse).
    # "fram" som eget ord fanger også opp samarbeidslag som "Fram / Hedrum og
    # Sporty" — vanlig i yngre årsklasser pga. få spillere i egen klubb, og
    # regnes her som "innenfor Fram-systemet", ikke som en annen klubb.
    tokens = re.split(r"[\s/]+", team_name.strip().lower())
    return "fram" in tokens


def is_larvik_club(team_name: str) -> bool:
    name = team_name.strip().lower()
    return any(name.startswith(c.lower()) for c in LARVIK_CLUBS)
