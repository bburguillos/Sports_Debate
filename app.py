import re
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import requests
import streamlit as st


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Sports Debate of the Day",
    page_icon="🔥",
    layout="wide",
)

st.markdown(
    """
<style>

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 3rem;
}

.hero {
    border-radius: 18px;
    padding: 20px 24px;
    margin-bottom: 18px;
    background: linear-gradient(
        135deg,
        rgba(255,120,0,.16),
        rgba(20,20,20,.04)
    );
    border: 1px solid rgba(120,120,120,.22);
}

.hero-title {
    font-size: 2.4rem;
    font-weight: 900;
}

.hero-sub {
    font-size: 1.05rem;
    opacity: .82;
}

.debate-card {
    padding: 18px;
    border-radius: 16px;
    border: 1px solid rgba(120,120,120,.25);
    margin-bottom: 14px;
}

.side-a {
    border-left: 5px solid #2e7d32;
    border-radius: 8px;
    padding: 12px;
    background: rgba(46,125,50,.08);
}

.side-b {
    border-left: 5px solid #c62828;
    border-radius: 8px;
    padding: 12px;
    background: rgba(198,40,40,.07);
}

.verified {
    border-left: 5px solid #1976d2;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 7px 0;
    background: rgba(25,118,210,.07);
}

.reported {
    border-left: 5px solid #7b1fa2;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 7px 0;
    background: rgba(123,31,162,.07);
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# CONSTANTS
# ============================================================

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

MLB_BASE = "https://statsapi.mlb.com/api/v1"

NHL_BASE = "https://api-web.nhle.com/v1"

F1_BASE = "https://api.jolpi.ca/ergast/f1"


SPORT_CONFIG = {
    "NFL": {
        "query": "NFL football",
        "espn_sport": "football",
        "espn_league": "nfl",
    },

    "NBA": {
        "query": "NBA basketball",
        "espn_sport": "basketball",
        "espn_league": "nba",
    },

    "MLB": {
        "query": "MLB baseball",
    },

    "NHL": {
        "query": "NHL hockey",
    },

    "MLS": {
        "query": "MLS soccer",
        "espn_sport": "soccer",
        "espn_league": "usa.1",
    },

    "F1": {
        "query": "Formula 1 F1",
    },
}


ALLOWED_SOURCE_WORDS = [
    "ESPN",
    "CBS",
    "NBC",
    "FOX",
    "Yahoo",
    "Associated Press",
    "AP News",
    "Sports Illustrated",
    "The Athletic",
    "MLB.com",
    "NBA",
    "NFL",
    "NHL",
    "MLS",
    "Formula 1",
    "Motorsport",
    "Autosport",
    "Reuters",
]


DEBATE_KEYWORDS = [
    "should",
    "trade",
    "bench",
    "start",
    "starter",
    "coach",
    "fire",
    "fired",
    "hot seat",
    "playoff",
    "contender",
    "mvp",
    "award",
    "struggle",
    "slump",
    "streak",
    "injury",
    "return",
    "lineup",
    "rotation",
    "quarterback",
    "deadline",
    "change",
    "future",
    "concern",
]


NHL_TEAMS = [
    ("Anaheim Ducks", "ANA"),
    ("Boston Bruins", "BOS"),
    ("Buffalo Sabres", "BUF"),
    ("Calgary Flames", "CGY"),
    ("Carolina Hurricanes", "CAR"),
    ("Chicago Blackhawks", "CHI"),
    ("Colorado Avalanche", "COL"),
    ("Columbus Blue Jackets", "CBJ"),
    ("Dallas Stars", "DAL"),
    ("Detroit Red Wings", "DET"),
    ("Edmonton Oilers", "EDM"),
    ("Florida Panthers", "FLA"),
    ("Los Angeles Kings", "LAK"),
    ("Minnesota Wild", "MIN"),
    ("Montreal Canadiens", "MTL"),
    ("Nashville Predators", "NSH"),
    ("New Jersey Devils", "NJD"),
    ("New York Islanders", "NYI"),
    ("New York Rangers", "NYR"),
    ("Ottawa Senators", "OTT"),
    ("Philadelphia Flyers", "PHI"),
    ("Pittsburgh Penguins", "PIT"),
    ("San Jose Sharks", "SJS"),
    ("Seattle Kraken", "SEA"),
    ("St. Louis Blues", "STL"),
    ("Tampa Bay Lightning", "TBL"),
    ("Toronto Maple Leafs", "TOR"),
    ("Utah Mammoth", "UTA"),
    ("Vancouver Canucks", "VAN"),
    ("Vegas Golden Knights", "VGK"),
    ("Washington Capitals", "WSH"),
    ("Winnipeg Jets", "WPG"),
]


# ============================================================
# HELPERS
# ============================================================

def safe_get(
    url,
    params=None,
    timeout=20,
):
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={
            "User-Agent":
                "Mozilla/5.0 Sports Debate Classroom App",
            "Accept":
                "application/json,text/plain,*/*",
        },
    )

    response.raise_for_status()

    return response.json()


def clean(text):
    return re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()


def as_number(value):
    if value is None:
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    if isinstance(
        value,
        dict,
    ):
        for key in [
            "value",
            "displayValue",
            "score",
        ]:
            if key in value:
                result = as_number(
                    value[key]
                )

                if result is not None:
                    return result

        return None

    try:
        return float(
            str(value)
            .replace(",", "")
            .replace("%", "")
            .strip()
        )

    except Exception:
        return None


def strip_google_source(title):
    """
    Google News titles frequently look like:
    Headline - ESPN
    """

    if " - " not in title:
        return title

    pieces = title.rsplit(
        " - ",
        1,
    )

    return pieces[0].strip()


def source_allowed(source):
    if not source:
        return True

    source_lower = source.lower()

    return any(
        word.lower() in source_lower
        for word
        in ALLOWED_SOURCE_WORDS
    )


# ============================================================
# CURRENT SEASONS
# ============================================================

def current_year():
    return datetime.now().year


def current_nba_season():
    now = datetime.now()

    if now.month >= 7:
        return now.year + 1

    return now.year


def current_nhl_season_string():
    now = datetime.now()

    if now.month >= 7:
        start = now.year

    else:
        start = now.year - 1

    return (
        f"{start}"
        f"{start + 1}"
    )


# ============================================================
# GOOGLE NEWS
# ============================================================

def news_window_code(
    window,
):
    return {
        "Past 24 Hours": "1d",
        "Past 48 Hours": "2d",
        "Past 7 Days": "7d",
    }[window]


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def scan_google_news(
    sport,
    window,
):
    query = (
        SPORT_CONFIG[
            sport
        ]["query"]
        + " when:"
        + news_window_code(
            window
        )
    )

    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )

    feed = feedparser.parse(
        url
    )

    articles = []

    for item in feed.entries[:60]:

        source = ""

        if hasattr(
            item,
            "source",
        ):
            try:
                source = item.source.get(
                    "title",
                    "",
                )
            except Exception:
                source = ""

        title = clean(
            item.get(
                "title",
                "",
            )
        )

        if not source:
            if " - " in title:
                source = title.rsplit(
                    " - ",
                    1,
                )[-1].strip()

        if not source_allowed(
            source
        ):
            continue

        articles.append({
            "sport":
                sport,

            "title":
                strip_google_source(
                    title
                ),

            "source":
                source or "News source",

            "link":
                item.get(
                    "link",
                    "",
                ),

            "published":
                item.get(
                    "published",
                    "",
                ),
        })

    return articles


# ============================================================
# ESPN TEAM LISTS
# ============================================================

@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def espn_teams(
    sport,
    league,
):
    data = safe_get(
        f"{ESPN_BASE}/{sport}/{league}/teams"
    )

    result = []

    sports = data.get(
        "sports",
        [],
    )

    if not sports:
        return result

    leagues = sports[0].get(
        "leagues",
        [],
    )

    if not leagues:
        return result

    for entry in leagues[0].get(
        "teams",
        [],
    ):
        team = entry.get(
            "team",
            {},
        )

        if not team.get("id"):
            continue

        result.append({
            "id":
                str(team["id"]),

            "name":
                team.get(
                    "displayName",
                    "",
                ),

            "short":
                team.get(
                    "shortDisplayName",
                    "",
                ),

            "abbr":
                team.get(
                    "abbreviation",
                    "",
                ),
        })

    return result


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def get_mlb_teams():
    data = safe_get(
        f"{MLB_BASE}/teams",
        params={
            "sportId": 1,
            "season":
                current_year(),
        },
    )

    return [
        {
            "id":
                str(team["id"]),

            "name":
                team["name"],

            "short":
                team["name"],

            "abbr":
                team.get(
                    "abbreviation",
                    "",
                ),
        }

        for team
        in data.get(
            "teams",
            [],
        )

        if team.get("id")
    ]


def get_nhl_teams():
    return [
        {
            "id": abbr,
            "name": name,
            "short": name,
            "abbr": abbr,
        }

        for name, abbr
        in NHL_TEAMS
    ]


@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def get_f1_entities():
    entities = []

    try:
        data = safe_get(
            f"{F1_BASE}/current/driverstandings.json"
        )

        lists = (
            data
            .get(
                "MRData",
                {},
            )
            .get(
                "StandingsTable",
                {},
            )
            .get(
                "StandingsLists",
                [],
            )
        )

        if lists:
            for standing in lists[0].get(
                "DriverStandings",
                [],
            ):
                driver = standing.get(
                    "Driver",
                    {},
                )

                full_name = (
                    f"{driver.get('givenName','')} "
                    f"{driver.get('familyName','')}"
                ).strip()

                entities.append({
                    "id":
                        driver.get(
                            "driverId",
                            full_name,
                        ),

                    "name":
                        full_name,

                    "short":
                        driver.get(
                            "familyName",
                            full_name,
                        ),

                    "abbr":
                        driver.get(
                            "code",
                            "",
                        ),

                    "entity_type":
                        "driver",
                })

    except Exception:
        pass

    return entities


def entities_for_sport(
    sport,
):
    if sport == "NFL":
        return espn_teams(
            "football",
            "nfl",
        )

    if sport == "NBA":
        return espn_teams(
            "basketball",
            "nba",
        )

    if sport == "MLS":
        return espn_teams(
            "soccer",
            "usa.1",
        )

    if sport == "MLB":
        return get_mlb_teams()

    if sport == "NHL":
        return get_nhl_teams()

    if sport == "F1":
        return get_f1_entities()

    return []


# ============================================================
# ENTITY MATCHING
# ============================================================

def team_match_score(
    headline,
    entity,
):
    title = (
        headline
        .lower()
    )

    name = (
        entity.get(
            "name",
            "",
        )
        .lower()
    )

    short = (
        entity.get(
            "short",
            "",
        )
        .lower()
    )

    abbr = (
        entity.get(
            "abbr",
            "",
        )
        .lower()
    )

    score = 0

    if name and name in title:
        score += 8

    if (
        short
        and len(short) >= 4
        and short in title
    ):
        score += 6

    if (
        abbr
        and len(abbr) >= 3
        and re.search(
            rf"\b{re.escape(abbr)}\b",
            title,
        )
    ):
        score += 3

    # Common final word, e.g. Yankees, Rangers, Lakers
    final_word = (
        name.split()[-1]
        if name
        else ""
    )

    if (
        final_word
        and len(final_word) >= 5
        and final_word in title
    ):
        score += 5

    return score


def find_entity(
    headline,
    entities,
):
    best = None
    best_score = 0

    for entity in entities:
        score = team_match_score(
            headline,
            entity,
        )

        if score > best_score:
            best = entity
            best_score = score

    if best_score < 5:
        return None

    return best


# ============================================================
# ESPN CURRENT TEAM STATS
# ============================================================

def espn_season_for_sport(
    sport,
):
    if sport == "NBA":
        return current_nba_season()

    return current_year()


@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def espn_schedule(
    sport,
    league,
    team_id,
    season,
):
    data = safe_get(
        f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}/schedule",
        params={
            "season":
                season,
        },
    )

    return data.get(
        "events",
        [],
    )


def espn_team_stats(
    display_sport,
    sport,
    league,
    team_id,
):
    events = espn_schedule(
        sport,
        league,
        team_id,
        espn_season_for_sport(
            display_sport
        ),
    )

    completed = []

    for event in events:
        competitions = event.get(
            "competitions",
            [],
        )

        if not competitions:
            continue

        competition = competitions[0]

        status = (
            competition
            .get(
                "status",
                {},
            )
            .get(
                "type",
                {},
            )
        )

        is_complete = (
            status.get(
                "completed"
            ) is True
            or str(
                status.get(
                    "state",
                    "",
                )
            ).lower() == "post"
        )

        if not is_complete:
            continue

        team_comp = None
        opp_comp = None

        for comp in competition.get(
            "competitors",
            [],
        ):
            comp_id = str(
                comp.get(
                    "team",
                    {},
                ).get(
                    "id",
                    "",
                )
            )

            if comp_id == str(
                team_id
            ):
                team_comp = comp

            else:
                opp_comp = comp

        if (
            not team_comp
            or not opp_comp
        ):
            continue

        scored = as_number(
            team_comp.get(
                "score"
            )
        )

        allowed = as_number(
            opp_comp.get(
                "score"
            )
        )

        if (
            scored is None
            or allowed is None
        ):
            continue

        if scored > allowed:
            result = "W"

        elif scored < allowed:
            result = "L"

        else:
            result = "D"

        completed.append({
            "date":
                event.get(
                    "date",
                    "",
                ),

            "result":
                result,

            "scored":
                scored,

            "allowed":
                allowed,
        })

    completed = sorted(
        completed,
        key=lambda x:
            x["date"],
    )

    if not completed:
        return []

    wins = sum(
        game["result"] == "W"
        for game
        in completed
    )

    losses = sum(
        game["result"] == "L"
        for game
        in completed
    )

    draws = sum(
        game["result"] == "D"
        for game
        in completed
    )

    recent = completed[-5:]

    recent_record = "-".join(
        game["result"]
        for game
        in recent
    )

    avg_scored = sum(
        game["scored"]
        for game
        in recent
    ) / len(recent)

    avg_allowed = sum(
        game["allowed"]
        for game
        in recent
    ) / len(recent)

    if display_sport == "MLS":
        record = (
            f"{wins}-{losses}-{draws}"
        )

    else:
        record = (
            f"{wins}-{losses}"
        )

    return [
        (
            "Season record",
            record,
        ),

        (
            "Last 5 results",
            recent_record,
        ),

        (
            "Average scored — last 5",
            f"{avg_scored:.1f}",
        ),

        (
            "Average allowed — last 5",
            f"{avg_allowed:.1f}",
        ),
    ]


# ============================================================
# MLB CURRENT STATS
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def mlb_schedule(
    team_id,
):
    data = safe_get(
        f"{MLB_BASE}/schedule",
        params={
            "sportId":
                1,

            "teamId":
                team_id,

            "season":
                current_year(),

            "gameType":
                "R",
        },
    )

    return [
        game

        for day
        in data.get(
            "dates",
            [],
        )

        for game
        in day.get(
            "games",
            [],
        )
    ]


def mlb_team_stats(
    team_id,
):
    results = []

    for game in mlb_schedule(
        team_id
    ):
        state = str(
            game.get(
                "status",
                {},
            ).get(
                "abstractGameState",
                "",
            )
        ).lower()

        if state != "final":
            continue

        home = (
            game.get(
                "teams",
                {},
            ).get(
                "home",
                {},
            )
        )

        away = (
            game.get(
                "teams",
                {},
            ).get(
                "away",
                {},
            )
        )

        home_id = str(
            home.get(
                "team",
                {},
            ).get(
                "id",
                "",
            )
        )

        if home_id == str(
            team_id
        ):
            team = home
            opp = away

        else:
            team = away
            opp = home

        scored = as_number(
            team.get(
                "score"
            )
        )

        allowed = as_number(
            opp.get(
                "score"
            )
        )

        if (
            scored is None
            or allowed is None
        ):
            continue

        results.append({
            "date":
                game.get(
                    "gameDate",
                    "",
                ),

            "result":
                (
                    "W"
                    if scored > allowed
                    else "L"
                ),

            "scored":
                scored,

            "allowed":
                allowed,
        })

    results = sorted(
        results,
        key=lambda x:
            x["date"],
    )

    if not results:
        return []

    wins = sum(
        result["result"] == "W"
        for result
        in results
    )

    losses = len(
        results
    ) - wins

    recent = results[-5:]

    avg_runs = (
        sum(
            game["scored"]
            for game
            in recent
        )
        / len(recent)
    )

    avg_allowed = (
        sum(
            game["allowed"]
            for game
            in recent
        )
        / len(recent)
    )

    return [
        (
            "Regular-season record",
            f"{wins}-{losses}",
        ),

        (
            "Last 5 results",
            "-".join(
                game["result"]
                for game
                in recent
            ),
        ),

        (
            "Runs per game — last 5",
            f"{avg_runs:.1f}",
        ),

        (
            "Runs allowed — last 5",
            f"{avg_allowed:.1f}",
        ),
    ]


# ============================================================
# NHL CURRENT STATS
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def nhl_schedule(
    abbreviation,
):
    data = safe_get(
        f"{NHL_BASE}/club-schedule-season/"
        f"{abbreviation}/"
        f"{current_nhl_season_string()}"
    )

    return data.get(
        "games",
        [],
    )


def nhl_team_stats(
    abbreviation,
):
    results = []

    for game in nhl_schedule(
        abbreviation
    ):
        if game.get(
            "gameType"
        ) != 2:
            continue

        state = str(
            game.get(
                "gameState",
                "",
            )
        ).upper()

        if state not in [
            "FINAL",
            "OFF",
        ]:
            continue

        home = game.get(
            "homeTeam",
            {},
        )

        away = game.get(
            "awayTeam",
            {},
        )

        if (
            home.get(
                "abbrev"
            )
            == abbreviation
        ):
            team = home
            opp = away

        else:
            team = away
            opp = home

        scored = as_number(
            team.get(
                "score"
            )
        )

        allowed = as_number(
            opp.get(
                "score"
            )
        )

        if (
            scored is None
            or allowed is None
        ):
            continue

        results.append({
            "date":
                game.get(
                    "gameDate",
                    "",
                ),

            "result":
                (
                    "W"
                    if scored > allowed
                    else "L"
                ),

            "scored":
                scored,

            "allowed":
                allowed,
        })

    results = sorted(
        results,
        key=lambda x:
            x["date"],
    )

    if not results:
        return []

    wins = sum(
        game["result"] == "W"
        for game
        in results
    )

    losses = len(
        results
    ) - wins

    recent = results[-5:]

    return [
        (
            "Completed-game record",
            f"{wins}-{losses}",
        ),

        (
            "Last 5 results",
            "-".join(
                game["result"]
                for game
                in recent
            ),
        ),

        (
            "Goals per game — last 5",
            f"{sum(g['scored'] for g in recent) / len(recent):.1f}",
        ),

        (
            "Goals allowed — last 5",
            f"{sum(g['allowed'] for g in recent) / len(recent):.1f}",
        ),
    ]


# ============================================================
# F1 VERIFIED STATS
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def f1_current_standings():
    return safe_get(
        f"{F1_BASE}/current/driverstandings.json"
    )


def f1_driver_stats(
    driver_id,
):
    data = f1_current_standings()

    lists = (
        data
        .get(
            "MRData",
            {},
        )
        .get(
            "StandingsTable",
            {},
        )
        .get(
            "StandingsLists",
            [],
        )
    )

    if not lists:
        return []

    for standing in lists[0].get(
        "DriverStandings",
        [],
    ):
        driver = standing.get(
            "Driver",
            {},
        )

        if (
            driver.get(
                "driverId"
            )
            != driver_id
        ):
            continue

        constructors = (
            standing.get(
                "Constructors",
                [],
            )
        )

        constructor = (
            constructors[0].get(
                "name",
                "Unknown",
            )
            if constructors
            else "Unknown"
        )

        return [
            (
                "Championship position",
                standing.get(
                    "positionText",
                    standing.get(
                        "position",
                        "?",
                    ),
                ),
            ),

            (
                "Championship points",
                standing.get(
                    "points",
                    "?",
                ),
            ),

            (
                "Wins",
                standing.get(
                    "wins",
                    "0",
                ),
            ),

            (
                "Team",
                constructor,
            ),
        ]

    return []


# ============================================================
# VERIFIED STATS DISPATCH
# ============================================================

def verified_stats(
    sport,
    entity,
):
    try:
        if sport == "NFL":
            return espn_team_stats(
                "NFL",
                "football",
                "nfl",
                entity["id"],
            )

        if sport == "NBA":
            return espn_team_stats(
                "NBA",
                "basketball",
                "nba",
                entity["id"],
            )

        if sport == "MLS":
            return espn_team_stats(
                "MLS",
                "soccer",
                "usa.1",
                entity["id"],
            )

        if sport == "MLB":
            return mlb_team_stats(
                entity["id"]
            )

        if sport == "NHL":
            return nhl_team_stats(
                entity["abbr"]
            )

        if sport == "F1":
            return f1_driver_stats(
                entity["id"]
            )

    except Exception:
        return []

    return []


# ============================================================
# DEBATE GENERATION
# ============================================================

def topic_text(
    headlines,
):
    return " ".join(
        article[
            "title"
        ].lower()

        for article
        in headlines
    )


def make_debate(
    entity_name,
    headlines,
):
    text = topic_text(
        headlines
    )

    if any(
        word in text
        for word
        in [
            "fire",
            "fired",
            "hot seat",
            "coach",
            "manager",
        ]
    ):
        return {
            "question":
                f"Should {entity_name} make a coaching or leadership change?",

            "a":
                "YES — recent results and current reporting may show that a change is needed.",

            "b":
                "NO — the team should stay patient and avoid overreacting to a short stretch.",
        }

    if any(
        word in text
        for word
        in [
            "trade",
            "deadline",
            "roster move",
            "acquire",
            "signing",
        ]
    ):
        return {
            "question":
                f"Should {entity_name} make a major roster move right now?",

            "a":
                "YES — the current situation suggests the team should act aggressively.",

            "b":
                "NO — the team should trust its current roster and avoid sacrificing too much for a short-term move.",
        }

    if any(
        word in text
        for word
        in [
            "bench",
            "starter",
            "starting",
            "lineup",
            "rotation",
            "quarterback",
        ]
    ):
        return {
            "question":
                f"Should {entity_name} change its current starting lineup or rotation?",

            "a":
                "YES — a change could improve the team's performance.",

            "b":
                "NO — consistency and patience may be more valuable than making a quick change.",
        }

    if any(
        word in text
        for word
        in [
            "struggle",
            "struggling",
            "slump",
            "concern",
            "collapse",
        ]
    ):
        return {
            "question":
                f"Should fans be seriously concerned about {entity_name} right now?",

            "a":
                "YES — the recent evidence suggests the problems may be meaningful.",

            "b":
                "NO — recent struggles may be temporary and the larger picture may still be positive.",
        }

    if any(
        word in text
        for word
        in [
            "playoff",
            "postseason",
            "contender",
            "championship",
            "title",
        ]
    ):
        return {
            "question":
                f"Is {entity_name} a legitimate championship or postseason contender right now?",

            "a":
                "YES — current performance and results support the contender argument.",

            "b":
                "NO — important weaknesses still make the contender label premature.",
        }

    if any(
        word in text
        for word
        in [
            "streak",
            "surge",
            "hot",
            "winning",
        ]
    ):
        return {
            "question":
                f"Is {entity_name}'s recent success sustainable?",

            "a":
                "YES — the current numbers suggest the success may continue.",

            "b":
                "NO — the recent run may be temporary or influenced by a small sample.",
        }

    return {
        "question":
            f"Is the current positive or negative buzz around {entity_name} justified by the evidence?",

        "a":
            "YES — the latest reporting and current statistics support the way people are talking about them.",

        "b":
            "NO — the headlines may be stronger than what the actual numbers show.",
    }


# ============================================================
# CANDIDATE RANKING
# ============================================================

def keyword_score(
    headlines,
):
    text = topic_text(
        headlines
    )

    return sum(
        1
        for word
        in DEBATE_KEYWORDS
        if word in text
    )


def build_candidates(
    selected_sports,
    window,
):
    groups = defaultdict(
        list
    )

    for sport in selected_sports:

        articles = scan_google_news(
            sport,
            window,
        )

        entities = entities_for_sport(
            sport
        )

        for article in articles:

            entity = find_entity(
                article[
                    "title"
                ],
                entities,
            )

            if entity is None:
                continue

            key = (
                sport,
                entity["id"],
            )

            groups[key].append({
                **article,
                "entity":
                    entity,
            })

    candidates = []

    for (
        sport,
        entity_id,
    ), articles in groups.items():

        unique_sources = set(
            article[
                "source"
            ]

            for article
            in articles
        )

        # We strongly prefer stories being discussed
        # by more than one source.
        if len(
            unique_sources
        ) < 2:
            continue

        entity = articles[0][
            "entity"
        ]

        stats = verified_stats(
            sport,
            entity,
        )

        # Critical classroom rule:
        # No verified sports data = no debate.
        if not stats:
            continue

        articles = articles[:5]

        debate = make_debate(
            entity[
                "name"
            ],
            articles,
        )

        score = (
            len(
                unique_sources
            ) * 5
            + min(
                len(articles),
                5,
            ) * 2
            + keyword_score(
                articles
            ) * 3
        )

        candidates.append({
            "sport":
                sport,

            "entity":
                entity,

            "articles":
                articles,

            "stats":
                stats,

            "question":
                debate["question"],

            "side_a":
                debate["a"],

            "side_b":
                debate["b"],

            "score":
                score,

            "sources":
                len(
                    unique_sources
                ),
        })

    return sorted(
        candidates,
        key=lambda x:
            x["score"],
        reverse=True,
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="hero">

<div class="hero-title">
🔥 Sports Debate of the Day
</div>

<div class="hero-sub">
Scan current sports coverage, find a real debate,
and support both sides with verified information.
</div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TEACHER SETTINGS
# ============================================================

with st.expander(
    "⚙️ Teacher Scan Settings",
    expanded=True,
):
    selected_sports = st.multiselect(
        "Sports to scan",
        [
            "NFL",
            "NBA",
            "MLB",
            "NHL",
            "MLS",
            "F1",
        ],
        default=[
            "NFL",
            "NBA",
            "MLB",
            "NHL",
            "MLS",
            "F1",
        ],
    )

    col1, col2 = st.columns(2)

    with col1:
        news_window = st.selectbox(
            "How current should the news be?",
            [
                "Past 24 Hours",
                "Past 48 Hours",
                "Past 7 Days",
            ],
            index=0,
        )

    with col2:
        number_of_debates = st.selectbox(
            "Debates to show",
            [
                1,
                2,
                3,
                5,
            ],
            index=2,
        )


# ============================================================
# SCAN
# ============================================================

scan = st.button(
    "🔎 SCAN CURRENT SPORTS NEWS",
    type="primary",
    use_container_width=True,
)


if scan:

    if not selected_sports:
        st.warning(
            "Choose at least one sport."
        )
        st.stop()

    progress = st.progress(
        0
    )

    status = st.empty()

    status.write(
        "### Step 1 of 4 — Searching fresh sports coverage..."
    )

    progress.progress(
        20
    )

    status.write(
        "### Step 2 of 4 — Finding stories being discussed by multiple sources..."
    )

    progress.progress(
        45
    )

    with st.spinner(
        "Scanning current news and sports data..."
    ):
        candidates = build_candidates(
            selected_sports,
            news_window,
        )

    status.write(
        "### Step 3 of 4 — Verifying current sports statistics..."
    )

    progress.progress(
        75
    )

    status.write(
        "### Step 4 of 4 — Building today's debates..."
    )

    progress.progress(
        100
    )

    status.empty()
    progress.empty()

    st.session_state[
        "debate_candidates"
    ] = candidates


# ============================================================
# RESULTS
# ============================================================

candidates = st.session_state.get(
    "debate_candidates",
    [],
)


if not candidates:

    st.info(
        "Press **SCAN CURRENT SPORTS NEWS** to find today's debates."
    )

    st.stop()


shown = candidates[
    :number_of_debates
]


if not shown:

    st.warning(
        "The scan found current stories, but none had enough verified statistical evidence and multiple news sources. Try the 48-hour or 7-day window."
    )

    st.stop()


st.success(
    f"Found {len(candidates)} current debate candidate(s) with verified sports data."
)


for index, candidate in enumerate(
    shown,
    start=1,
):

    st.markdown("---")

    if index == 1:
        st.write(
            "## 🔥 Today's Best Debate"
        )

    else:
        st.write(
            f"## Debate #{index}"
        )

    st.caption(
        f"{candidate['sport']} • "
        f"{candidate['sources']} current news sources"
    )

    st.write(
        f"# {candidate['question']}"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
<div class="side-a">

### 🟢 SIDE A — YES

{candidate['side_a']}

</div>
""",
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
<div class="side-b">

### 🔴 SIDE B — NO

{candidate['side_b']}

</div>
""",
            unsafe_allow_html=True,
        )


    # ========================================================
    # VERIFIED DATA
    # ========================================================

    st.write(
        "### 📊 Verified Data Pool"
    )

    st.caption(
        "These values were retrieved from sports data sources when you pressed Scan. They were not invented by the app."
    )

    stats_df = pd.DataFrame(
        candidate[
            "stats"
        ],
        columns=[
            "Verified statistic",
            "Current value",
        ],
    )

    st.dataframe(
        stats_df,
        hide_index=True,
        use_container_width=True,
    )


    # ========================================================
    # NEWS
    # ========================================================

    st.write(
        "### 📰 Current Reporting"
    )

    st.caption(
        "Use these headlines as current context. Open the source if you need more detail."
    )

    for article in candidate[
        "articles"
    ][:4]:

        st.markdown(
            f"""
<div class="reported">

<b>🔵 REPORTED CURRENTLY</b><br>
{article['title']}<br>
<small>{article['source']}</small>

</div>
""",
            unsafe_allow_html=True,
        )

        if article[
            "link"
        ]:
            st.link_button(
                f"Open {article['source']}",
                article[
                    "link"
                ],
            )


    # ========================================================
    # STUDENT TASK
    # ========================================================

    st.write(
        "### 🎤 Your Turn"
    )

    student_side = st.radio(
        "Which side do you defend?",
        [
            "SIDE A — YES",
            "SIDE B — NO",
            "I need more evidence",
        ],
        key=f"side_{index}",
        horizontal=True,
    )

    st.text_area(
        "Choose at least TWO pieces of evidence and explain why they support your argument.",
        placeholder=(
            "I believe ... because the data shows ... "
            "Another piece of evidence is ..."
        ),
        key=f"response_{index}",
    )


# ============================================================
# CLASSROOM NOTE
# ============================================================

st.markdown("---")

st.caption(
    "🟢 Verified Stat = retrieved from structured sports data. "
    "🔵 Current Reporting = a current news headline/source. "
    "A statistic can support an argument, but it does not automatically prove the argument."
)
