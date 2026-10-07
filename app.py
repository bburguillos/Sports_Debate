import calendar
import re
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import requests
import streamlit as st


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Sports Debate of the Day",
    page_icon="🔥",
    layout="wide",
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
MLB_BASE = "https://statsapi.mlb.com/api/v1"
NHL_BASE = "https://api-web.nhle.com/v1"
F1_BASE = "https://api.jolpi.ca/ergast/f1"


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
<style>

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 3rem;
}

.hero {
    border-radius: 20px;
    padding: 22px 26px;
    margin-bottom: 18px;
    background: linear-gradient(
        135deg,
        rgba(255,125,0,.18),
        rgba(15,15,15,.04)
    );
    border: 1px solid rgba(120,120,120,.22);
}

.hero-title {
    font-size: 2.45rem;
    font-weight: 900;
}

.hero-sub {
    font-size: 1.06rem;
    opacity: .82;
}

.side-a {
    border-left: 5px solid #2e7d32;
    border-radius: 10px;
    padding: 14px;
    background: rgba(46,125,50,.08);
}

.side-b {
    border-left: 5px solid #c62828;
    border-radius: 10px;
    padding: 14px;
    background: rgba(198,40,40,.07);
}

.news-card {
    border-left: 5px solid #1565c0;
    border-radius: 8px;
    padding: 11px 13px;
    margin-bottom: 9px;
    background: rgba(21,101,192,.07);
}

.phase-card {
    border: 1px solid rgba(120,120,120,.25);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 12px;
}

.data-note {
    border-left: 5px solid #00897b;
    border-radius: 8px;
    padding: 10px 12px;
    background: rgba(0,137,123,.07);
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# CONFIG
# ============================================================

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


TRUSTED_SOURCES = [
    "ESPN",
    "CBS Sports",
    "NBC Sports",
    "Yahoo Sports",
    "FOX Sports",
    "Associated Press",
    "AP News",
    "Reuters",
    "Sports Illustrated",
    "The Athletic",
    "MLB.com",
    "NFL.com",
    "NBA.com",
    "NHL.com",
    "MLSsoccer.com",
    "Formula 1",
    "Autosport",
    "Motorsport.com",
]


HISTORICAL_WORDS = [
    "on this day",
    "from the archive",
    "archive",
    "classic game",
    "classic games",
    "throwback",
    "retrospective",
    "history of",
    "historical",
    "box score from",
    "remembering",
    "rewind",
]


TOPIC_WORDS = {
    "postseason": [
        "postseason",
        "playoffs",
        "playoff",
        "world series",
        "stanley cup",
        "nba finals",
        "super bowl",
        "elimination",
        "eliminated",
        "advance",
        "series",
        "game 7",
        "game 6",
        "game 5",
        "game 4",
        "game 3",
    ],

    "contender": [
        "contender",
        "championship",
        "title contender",
        "super bowl contender",
        "world series contender",
        "stanley cup contender",
        "finals contender",
        "playoff contender",
    ],

    "concern": [
        "struggle",
        "struggling",
        "slump",
        "skid",
        "losing streak",
        "collapse",
        "concern",
        "worried",
        "problem",
        "falling apart",
    ],

    "momentum": [
        "winning streak",
        "win streak",
        "surge",
        "rolling",
        "hot streak",
        "red hot",
        "on fire",
        "turned it around",
        "turnaround",
    ],

    "offense": [
        "offense",
        "offensive",
        "scoring",
        "can't score",
        "cannot score",
        "runs",
        "bats",
        "shooting",
        "goals",
    ],

    "defense": [
        "defense",
        "defensive",
        "pitching",
        "bullpen",
        "goaltending",
        "goaltender",
        "run prevention",
        "allowing",
        "conceding",
    ],

    "player_award": [
        "mvp",
        "cy young",
        "rookie of the year",
        "hart trophy",
        "award race",
        "ballon",
    ],

    "roster": [
        "trade",
        "traded",
        "deadline",
        "bench",
        "benched",
        "lineup",
        "rotation",
        "starter",
        "starting quarterback",
        "fire coach",
        "fired coach",
        "hot seat",
        "injury",
        "injured",
    ],
}


SUPPORTED_TOPICS = {
    "postseason",
    "contender",
    "concern",
    "momentum",
    "offense",
    "defense",
}


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
# BASIC HELPERS
# ============================================================

def now_utc():
    return datetime.now(
        timezone.utc
    )


def safe_get(
    url,
    params=None,
    timeout=25,
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
    if " - " not in title:
        return title.strip()

    return title.rsplit(
        " - ",
        1,
    )[0].strip()


def source_is_trusted(source):
    if not source:
        return False

    source_lower = (
        source.lower()
    )

    return any(
        trusted.lower()
        in source_lower

        for trusted
        in TRUSTED_SOURCES
    )


# ============================================================
# STRICT NEWS DATE FILTERING
# ============================================================

def feed_date_to_datetime(entry):
    parsed = entry.get(
        "published_parsed"
    )

    if parsed is None:
        parsed = entry.get(
            "updated_parsed"
        )

    if parsed is None:
        return None

    try:
        timestamp = calendar.timegm(
            parsed
        )

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )

    except Exception:
        return None


def window_hours(window):
    return {
        "Past 24 Hours": 24,
        "Past 48 Hours": 48,
        "Past 7 Days": 168,
    }[window]


def article_is_fresh(
    published_dt,
    window,
):
    if published_dt is None:
        return False

    age = (
        now_utc()
        - published_dt
    ).total_seconds() / 3600

    # Reject future timestamps and
    # anything older than the selected window.
    return (
        age >= -3
        and age <= window_hours(
            window
        )
    )


# ============================================================
# HISTORICAL / ARCHIVE FILTER
# ============================================================

def looks_historical(title):
    text = title.lower()

    if any(
        phrase in text
        for phrase
        in HISTORICAL_WORDS
    ):
        return True

    years = re.findall(
        r"\b(18\d{2}|19\d{2}|20\d{2})\b",
        title,
    )

    current = now_utc().year

    for year_text in years:
        year = int(year_text)

        if year < current - 2:
            # Historical dates alone are not always bad,
            # but old year + archive/box-score language is.
            if (
                "box score" in text
                or "season" in text
                or "game" in text
                or "team" in text
                or "roster" in text
            ):
                return True

    return False


# ============================================================
# GOOGLE NEWS
# ============================================================

def news_window_code(window):
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
    seen = set()

    for entry in feed.entries[:100]:
        title = clean(
            entry.get(
                "title",
                "",
            )
        )

        if not title:
            continue

        source = ""

        try:
            source = (
                entry.get(
                    "source",
                    {}
                )
                .get(
                    "title",
                    ""
                )
            )

        except Exception:
            source = ""

        if not source and " - " in title:
            source = title.rsplit(
                " - ",
                1,
            )[-1].strip()

        if not source_is_trusted(
            source
        ):
            continue

        published_dt = (
            feed_date_to_datetime(
                entry
            )
        )

        if not article_is_fresh(
            published_dt,
            window,
        ):
            continue

        clean_title = (
            strip_google_source(
                title
            )
        )

        if looks_historical(
            clean_title
        ):
            continue

        dedupe_key = (
            clean_title.lower(),
            source.lower(),
        )

        if dedupe_key in seen:
            continue

        seen.add(
            dedupe_key
        )

        articles.append({
            "sport":
                sport,

            "title":
                clean_title,

            "source":
                source,

            "link":
                entry.get(
                    "link",
                    "",
                ),

            "published_dt":
                published_dt,

            "published":
                published_dt.strftime(
                    "%b %d, %Y %I:%M %p UTC"
                ),
        })

    return articles


# ============================================================
# SEASON PHASE DETECTOR
# ============================================================

def sport_phase(sport):
    now = now_utc()
    month = now.month

    if sport == "MLB":
        if month in [3]:
            return "Preseason"

        if month in [
            4, 5, 6, 7, 8, 9
        ]:
            return "Regular Season"

        if month == 10:
            return "Postseason"

        return "Offseason"

    if sport == "NFL":
        if month in [
            9, 10, 11, 12
        ]:
            return "Regular Season"

        if month in [1, 2]:
            return "Postseason"

        return "Offseason"

    if sport == "NBA":
        if month in [
            10, 11, 12, 1, 2, 3, 4
        ]:
            return "Regular Season"

        if month in [5, 6]:
            return "Postseason"

        return "Offseason"

    if sport == "NHL":
        if month in [
            10, 11, 12, 1, 2, 3, 4
        ]:
            return "Regular Season"

        if month in [5, 6]:
            return "Postseason"

        return "Offseason"

    if sport == "MLS":
        if month in [
            2, 3, 4, 5, 6, 7, 8, 9
        ]:
            return "Regular Season"

        if month in [
            10, 11, 12
        ]:
            return "Postseason"

        return "Offseason"

    if sport == "F1":
        if month in [
            3, 4, 5, 6, 7, 8, 9, 10, 11
        ]:
            return "Championship Season"

        return "Offseason"

    return "Unknown"


# ============================================================
# TOPIC CLASSIFICATION
# ============================================================

def classify_topic(title):
    text = title.lower()

    scores = {}

    for topic, words in (
        TOPIC_WORDS.items()
    ):
        scores[topic] = sum(
            1
            for phrase in words
            if phrase in text
        )

    if not scores:
        return None

    topic = max(
        scores,
        key=scores.get,
    )

    if scores[topic] == 0:
        return None

    return topic


def phase_topic_allowed(
    sport,
    phase,
    topic,
):
    if topic not in SUPPORTED_TOPICS:
        return False

    if phase == "Offseason":
        return False

    # In the postseason, don't create
    # "playoff contender" questions.
    if (
        phase == "Postseason"
        and topic == "contender"
    ):
        return False

    # Postseason stories are especially useful.
    if (
        phase == "Postseason"
        and topic == "postseason"
    ):
        return True

    return True


# ============================================================
# TEAM / ENTITY LISTS
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
            "sportId":
                1,

            "season":
                now_utc().year,
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
            "id":
                abbr,

            "name":
                name,

            "short":
                name,

            "abbr":
                abbr,
        }

        for name, abbr
        in NHL_TEAMS
    ]


@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def get_f1_drivers():
    try:
        data = safe_get(
            f"{F1_BASE}/current/driverstandings.json"
        )

    except Exception:
        return []

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

    result = []

    for standing in lists[0].get(
        "DriverStandings",
        [],
    ):
        driver = standing.get(
            "Driver",
            {},
        )

        name = (
            f"{driver.get('givenName','')} "
            f"{driver.get('familyName','')}"
        ).strip()

        result.append({
            "id":
                driver.get(
                    "driverId",
                    name,
                ),

            "name":
                name,

            "short":
                driver.get(
                    "familyName",
                    name,
                ),

            "abbr":
                driver.get(
                    "code",
                    "",
                ),

            "entity_type":
                "driver",
        })

    return result


def entities_for_sport(sport):
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
        return get_f1_drivers()

    return []


# ============================================================
# ENTITY MATCHING
# ============================================================

def entity_match_score(
    headline,
    entity,
):
    text = headline.lower()

    name = entity.get(
        "name",
        "",
    ).lower()

    short = entity.get(
        "short",
        "",
    ).lower()

    abbr = entity.get(
        "abbr",
        "",
    ).lower()

    score = 0

    if name and name in text:
        score += 10

    if (
        short
        and len(short) >= 4
        and short in text
    ):
        score += 7

    if (
        abbr
        and len(abbr) >= 3
        and re.search(
            rf"\b{re.escape(abbr)}\b",
            text,
        )
    ):
        score += 3

    if name:
        final_word = (
            name.split()[-1]
        )

        if (
            len(final_word) >= 5
            and final_word in text
        ):
            score += 6

    return score


def find_entity(
    headline,
    entities,
):
    best = None
    best_score = 0

    for entity in entities:
        score = entity_match_score(
            headline,
            entity,
        )

        if score > best_score:
            best_score = score
            best = entity

    if best_score < 6:
        return None

    return best


# ============================================================
# GENERIC GAME SNAPSHOT HELPERS
# ============================================================

def result_record(games):
    wins = sum(
        game["result"] == "W"
        for game in games
    )

    losses = sum(
        game["result"] == "L"
        for game in games
    )

    ties = sum(
        game["result"] == "T"
        for game in games
    )

    if ties:
        return f"{wins}-{losses}-{ties}"

    return f"{wins}-{losses}"


def recent_results(
    games,
    n=5,
):
    subset = games[-n:]

    return "-".join(
        game["result"]
        for game in subset
    )


def average_scored(
    games,
    n=None,
):
    subset = (
        games[-n:]
        if n
        else games
    )

    if not subset:
        return None

    return (
        sum(
            game["scored"]
            for game in subset
        )
        / len(subset)
    )


def average_allowed(
    games,
    n=None,
):
    subset = (
        games[-n:]
        if n
        else games
    )

    if not subset:
        return None

    return (
        sum(
            game["allowed"]
            for game in subset
        )
        / len(subset)
    )


def win_percentage(games):
    if not games:
        return None

    wins = sum(
        game["result"] == "W"
        for game in games
    )

    return wins / len(games)


# ============================================================
# ESPN GAME DATA
# ============================================================

def espn_current_season(sport):
    now = now_utc()

    if sport == "NBA":
        if now.month >= 7:
            return now.year + 1

        return now.year

    if sport == "NFL":
        if now.month <= 2:
            return now.year - 1

        return now.year

    return now.year


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


def espn_event_phase(event):
    text_parts = []

    season_type = event.get(
        "seasonType",
        {},
    )

    if isinstance(
        season_type,
        dict,
    ):
        text_parts.extend([
            str(
                season_type.get(
                    "name",
                    ""
                )
            ),
            str(
                season_type.get(
                    "type",
                    ""
                )
            ),
        ])

    competitions = event.get(
        "competitions",
        [],
    )

    if competitions:
        competition = (
            competitions[0]
        )

        text_parts.append(
            str(
                competition.get(
                    "type",
                    ""
                )
            )
        )

    text = " ".join(
        text_parts
    ).lower()

    if (
        "post" in text
        or "playoff" in text
    ):
        return "Postseason"

    if "pre" in text:
        return "Preseason"

    return "Regular Season"


def espn_games_for_team(
    display_sport,
    espn_sport,
    league,
    team_id,
):
    events = espn_schedule(
        espn_sport,
        league,
        team_id,
        espn_current_season(
            display_sport
        ),
    )

    results = []

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

        completed = (
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

        if not completed:
            continue

        team_comp = None
        opp_comp = None

        for competitor in competition.get(
            "competitors",
            [],
        ):
            competitor_id = str(
                competitor.get(
                    "team",
                    {},
                ).get(
                    "id",
                    "",
                )
            )

            if competitor_id == str(
                team_id
            ):
                team_comp = competitor

            else:
                opp_comp = competitor

        if not team_comp or not opp_comp:
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
            result = "T"

        results.append({
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

            "opponent":
                opp_comp.get(
                    "team",
                    {},
                ).get(
                    "displayName",
                    "Opponent",
                ),

            "phase":
                espn_event_phase(
                    event
                ),
        })

    return sorted(
        results,
        key=lambda game:
            game["date"],
    )


# ============================================================
# MLB GAME DATA
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def mlb_schedule(team_id):
    data = safe_get(
        f"{MLB_BASE}/schedule",
        params={
            "sportId":
                1,

            "teamId":
                team_id,

            "season":
                now_utc().year,
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


def mlb_game_phase(game):
    game_type = str(
        game.get(
            "gameType",
            ""
        )
    ).upper()

    if game_type == "R":
        return "Regular Season"

    if game_type in [
        "F",
        "D",
        "L",
        "W",
    ]:
        return "Postseason"

    return "Other"


def mlb_games_for_team(
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

        phase = mlb_game_phase(
            game
        )

        if phase == "Other":
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

        if home_id == str(team_id):
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

            "opponent":
                opp.get(
                    "team",
                    {},
                ).get(
                    "name",
                    "Opponent",
                ),

            "phase":
                phase,
        })

    return sorted(
        results,
        key=lambda game:
            game["date"],
    )


# ============================================================
# NHL GAME DATA
# ============================================================

def current_nhl_season():
    now = now_utc()

    if now.month >= 7:
        start = now.year

    else:
        start = now.year - 1

    return (
        f"{start}"
        f"{start + 1}"
    )


@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def nhl_schedule(abbreviation):
    data = safe_get(
        f"{NHL_BASE}/club-schedule-season/"
        f"{abbreviation}/"
        f"{current_nhl_season()}"
    )

    return data.get(
        "games",
        [],
    )


def nhl_games_for_team(
    abbreviation,
):
    results = []

    for game in nhl_schedule(
        abbreviation
    ):
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

        game_type = game.get(
            "gameType"
        )

        if game_type == 2:
            phase = "Regular Season"

        elif game_type == 3:
            phase = "Postseason"

        else:
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

            "opponent":
                opp.get(
                    "abbrev",
                    "Opponent",
                ),

            "phase":
                phase,
        })

    return sorted(
        results,
        key=lambda game:
            game["date"],
    )


# ============================================================
# F1 CURRENT DATA
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def f1_driver_standings():
    return safe_get(
        f"{F1_BASE}/current/driverstandings.json"
    )


def f1_snapshot(entity):
    try:
        data = (
            f1_driver_standings()
        )

    except Exception:
        return None

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
        return None

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
            != entity["id"]
        ):
            continue

        constructors = standing.get(
            "Constructors",
            [],
        )

        constructor = (
            constructors[0].get(
                "name",
                "Unknown",
            )
            if constructors
            else "Unknown"
        )

        return {
            "phase":
                sport_phase(
                    "F1"
                ),

            "evidence": [
                (
                    "Championship position",
                    standing.get(
                        "positionText",
                        "?",
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
                    "Race wins",
                    standing.get(
                        "wins",
                        "0",
                    ),
                ),

                (
                    "Team",
                    constructor,
                ),
            ],
        }

    return None


# ============================================================
# SERIES RECORD
# ============================================================

def current_series_record(
    postseason_games,
):
    if not postseason_games:
        return None

    latest_opponent = (
        postseason_games[-1][
            "opponent"
        ]
    )

    same_opponent = [
        game
        for game
        in postseason_games

        if game[
            "opponent"
        ] == latest_opponent
    ]

    if not same_opponent:
        return None

    wins = sum(
        game["result"] == "W"
        for game in same_opponent
    )

    losses = sum(
        game["result"] == "L"
        for game in same_opponent
    )

    return (
        latest_opponent,
        wins,
        losses,
    )


# ============================================================
# BUILD TEAM SNAPSHOT
# ============================================================

def team_games(
    sport,
    entity,
):
    if sport == "NFL":
        return espn_games_for_team(
            "NFL",
            "football",
            "nfl",
            entity["id"],
        )

    if sport == "NBA":
        return espn_games_for_team(
            "NBA",
            "basketball",
            "nba",
            entity["id"],
        )

    if sport == "MLS":
        return espn_games_for_team(
            "MLS",
            "soccer",
            "usa.1",
            entity["id"],
        )

    if sport == "MLB":
        return mlb_games_for_team(
            entity["id"]
        )

    if sport == "NHL":
        return nhl_games_for_team(
            entity["abbr"]
        )

    return []


def build_snapshot(
    sport,
    entity,
):
    if sport == "F1":
        return f1_snapshot(
            entity
        )

    games = team_games(
        sport,
        entity,
    )

    if not games:
        return None

    phase = sport_phase(
        sport
    )

    regular = [
        game
        for game in games
        if game["phase"]
        == "Regular Season"
    ]

    postseason = [
        game
        for game in games
        if game["phase"]
        == "Postseason"
    ]

    if phase == "Postseason":
        # Key fix:
        # postseason debates require postseason data.
        if not postseason:
            return None

        active_games = postseason

    else:
        active_games = regular

    if not active_games:
        return None

    snapshot = {
        "phase":
            phase,

        "regular":
            regular,

        "postseason":
            postseason,

        "active":
            active_games,
    }

    return snapshot


# ============================================================
# TOPIC-SPECIFIC EVIDENCE
# ============================================================

def evidence_for_topic(
    sport,
    topic,
    snapshot,
):
    if sport == "F1":
        return snapshot.get(
            "evidence",
            [],
        )

    active = snapshot[
        "active"
    ]

    phase = snapshot[
        "phase"
    ]

    regular = snapshot.get(
        "regular",
        [],
    )

    postseason = snapshot.get(
        "postseason",
        [],
    )

    evidence = []

    if topic == "postseason":
        if phase != "Postseason":
            return []

        evidence.append(
            (
                "Postseason record",
                result_record(
                    postseason
                ),
            )
        )

        series = current_series_record(
            postseason
        )

        if series:
            opponent, wins, losses = (
                series
            )

            evidence.append(
                (
                    f"Current series vs. {opponent}",
                    f"{wins}-{losses}",
                )
            )

        last_games = (
            postseason[-5:]
        )

        evidence.append(
            (
                "Postseason scoring average",
                f"{average_scored(last_games):.1f}",
            )
        )

        evidence.append(
            (
                "Postseason scoring allowed",
                f"{average_allowed(last_games):.1f}",
            )
        )

        evidence.append(
            (
                "Latest postseason results",
                recent_results(
                    postseason,
                    5,
                ),
            )
        )

        return evidence

    if topic == "contender":
        if phase == "Postseason":
            return []

        if not regular:
            return []

        evidence.append(
            (
                "Season record",
                result_record(
                    regular
                ),
            )
        )

        win_pct = win_percentage(
            regular
        )

        if win_pct is not None:
            evidence.append(
                (
                    "Season win percentage",
                    f"{win_pct * 100:.1f}%",
                )
            )

        evidence.append(
            (
                "Last 10 results",
                recent_results(
                    regular,
                    10,
                ),
            )
        )

        last10 = regular[-10:]

        evidence.append(
            (
                "Scoring average — last 10",
                f"{average_scored(last10):.1f}",
            )
        )

        evidence.append(
            (
                "Scoring allowed — last 10",
                f"{average_allowed(last10):.1f}",
            )
        )

        return evidence

    if topic in [
        "concern",
        "momentum",
    ]:
        recent = active[-10:]

        evidence.append(
            (
                "Last 10 results",
                recent_results(
                    recent,
                    10,
                ),
            )
        )

        evidence.append(
            (
                "Record over those games",
                result_record(
                    recent
                ),
            )
        )

        evidence.append(
            (
                "Average scored — recent games",
                f"{average_scored(recent):.1f}",
            )
        )

        evidence.append(
            (
                "Average allowed — recent games",
                f"{average_allowed(recent):.1f}",
            )
        )

        differential = (
            average_scored(recent)
            - average_allowed(recent)
        )

        evidence.append(
            (
                "Recent scoring differential per game",
                f"{differential:+.1f}",
            )
        )

        return evidence

    if topic == "offense":
        recent = active[-10:]

        evidence.append(
            (
                "Average scored — last 10",
                f"{average_scored(recent):.1f}",
            )
        )

        evidence.append(
            (
                "Last 10 results",
                recent_results(
                    recent,
                    10,
                ),
            )
        )

        if regular:
            evidence.append(
                (
                    "Season scoring average",
                    f"{average_scored(regular):.1f}",
                )
            )

        return evidence

    if topic == "defense":
        recent = active[-10:]

        evidence.append(
            (
                "Average allowed — last 10",
                f"{average_allowed(recent):.1f}",
            )
        )

        evidence.append(
            (
                "Last 10 results",
                recent_results(
                    recent,
                    10,
                ),
            )
        )

        if regular:
            evidence.append(
                (
                    "Season scoring allowed average",
                    f"{average_allowed(regular):.1f}",
                )
            )

        return evidence

    return []


# ============================================================
# DEBATE WORDING
# ============================================================

def make_debate(
    sport,
    entity_name,
    topic,
    phase,
):
    if topic == "postseason":
        return {
            "question":
                f"Does {entity_name} have what it takes to make a deep postseason run?",

            "side_a":
                "YES — the team's current postseason results support the idea that it can keep advancing.",

            "side_b":
                "NO — weaknesses in the current postseason performance suggest the run may not last.",
        }

    if topic == "contender":
        return {
            "question":
                f"Is {entity_name} a legitimate championship contender right now?",

            "side_a":
                "YES — the team's season performance and recent results support the contender label.",

            "side_b":
                "NO — the numbers still show reasons to doubt whether the team belongs among the very best.",
        }

    if topic == "concern":
        return {
            "question":
                f"Should fans be seriously concerned about {entity_name}'s recent performance?",

            "side_a":
                "YES — the recent results suggest the problems may be more than a short slump.",

            "side_b":
                "NO — a short stretch of games should not outweigh the larger body of evidence.",
        }

    if topic == "momentum":
        return {
            "question":
                f"Is {entity_name}'s recent success likely to continue?",

            "side_a":
                "YES — recent results and scoring trends show signs of sustainable improvement.",

            "side_b":
                "NO — the hot stretch may be temporary and based on a small sample.",
        }

    if topic == "offense":
        return {
            "question":
                f"Is {entity_name}'s offense good enough to drive the team to success right now?",

            "side_a":
                "YES — recent scoring data suggests the offense is producing enough.",

            "side_b":
                "NO — the current scoring numbers reveal important offensive concerns.",
        }

    if topic == "defense":
        return {
            "question":
                f"Is {entity_name}'s defense strong enough for the team to succeed right now?",

            "side_a":
                "YES — recent prevention numbers suggest the defense is doing its job.",

            "side_b":
                "NO — the amount being allowed remains a major concern.",
        }

    return None


# ============================================================
# ARTICLE / TOPIC RELEVANCE
# ============================================================

def article_matches_topic(
    article,
    topic,
):
    return (
        classify_topic(
            article["title"]
        )
        == topic
    )


def relevant_articles(
    articles,
    topic,
):
    return [
        article
        for article in articles
        if article_matches_topic(
            article,
            topic,
        )
    ]


# ============================================================
# CANDIDATE BUILDING
# ============================================================

def build_candidates(
    selected_sports,
    window,
):
    grouped = defaultdict(
        list
    )

    scan_stats = {
        "articles_seen": 0,
        "fresh_articles": 0,
        "matched_entities": 0,
        "rejected_topics": 0,
        "rejected_data": 0,
    }

    for sport in selected_sports:
        articles = scan_google_news(
            sport,
            window,
        )

        scan_stats[
            "fresh_articles"
        ] += len(articles)

        entities = entities_for_sport(
            sport
        )

        phase = sport_phase(
            sport
        )

        for article in articles:
            scan_stats[
                "articles_seen"
            ] += 1

            entity = find_entity(
                article[
                    "title"
                ],
                entities,
            )

            if entity is None:
                continue

            scan_stats[
                "matched_entities"
            ] += 1

            topic = classify_topic(
                article[
                    "title"
                ]
            )

            if topic is None:
                continue

            if not phase_topic_allowed(
                sport,
                phase,
                topic,
            ):
                scan_stats[
                    "rejected_topics"
                ] += 1

                continue

            key = (
                sport,
                entity["id"],
                topic,
            )

            grouped[key].append({
                **article,

                "entity":
                    entity,

                "topic":
                    topic,

                "phase":
                    phase,
            })

    candidates = []

    for (
        sport,
        entity_id,
        topic,
    ), articles in grouped.items():

        # Topic clustering:
        # all articles in this group are about
        # the same entity AND same debate category.
        articles = relevant_articles(
            articles,
            topic,
        )

        unique_sources = set(
            article["source"]
            for article in articles
        )

        if len(unique_sources) < 2:
            continue

        entity = articles[0][
            "entity"
        ]

        snapshot = build_snapshot(
            sport,
            entity,
        )

        if snapshot is None:
            scan_stats[
                "rejected_data"
            ] += 1

            continue

        evidence = evidence_for_topic(
            sport,
            topic,
            snapshot,
        )

        # Require multiple pieces of relevant data.
        if len(evidence) < 3:
            scan_stats[
                "rejected_data"
            ] += 1

            continue

        debate = make_debate(
            sport,
            entity["name"],
            topic,
            snapshot["phase"],
        )

        if debate is None:
            continue

        # Freshness bonus.
        newest = max(
            article[
                "published_dt"
            ]
            for article
            in articles
        )

        age_hours = (
            now_utc()
            - newest
        ).total_seconds() / 3600

        freshness_score = max(
            0,
            24 - min(
                age_hours,
                24,
            )
        )

        score = (
            len(
                unique_sources
            ) * 10
            + len(
                articles
            ) * 3
            + freshness_score
        )

        candidates.append({
            "sport":
                sport,

            "entity":
                entity,

            "topic":
                topic,

            "phase":
                snapshot[
                    "phase"
                ],

            "articles":
                sorted(
                    articles,
                    key=lambda a:
                        a[
                            "published_dt"
                        ],
                    reverse=True,
                )[:5],

            "evidence":
                evidence,

            "question":
                debate[
                    "question"
                ],

            "side_a":
                debate[
                    "side_a"
                ],

            "side_b":
                debate[
                    "side_b"
                ],

            "source_count":
                len(
                    unique_sources
                ),

            "score":
                score,
        })

    candidates = sorted(
        candidates,
        key=lambda candidate:
            candidate[
                "score"
            ],
        reverse=True,
    )

    return (
        candidates,
        scan_stats,
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
Scan what is happening in sports right now,
verify the evidence, and build a debate students can actually defend.
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
            "News window",
            [
                "Past 24 Hours",
                "Past 48 Hours",
                "Past 7 Days",
            ],
            index=0,
        )

    with col2:
        number_of_debates = st.selectbox(
            "Maximum debates to show",
            [
                1,
                2,
                3,
                5,
            ],
            index=2,
        )

    st.caption(
        "The app rejects old articles, unsupported debate types, "
        "offseason questions without meaningful current data, and debates "
        "whose statistics do not match the topic."
    )


# ============================================================
# CURRENT PHASES
# ============================================================

with st.expander(
    "🗓️ Current Sports Calendar",
):
    phase_rows = []

    for sport in selected_sports:
        phase_rows.append({
            "Sport":
                sport,

            "Current phase":
                sport_phase(
                    sport
                ),
        })

    if phase_rows:
        st.dataframe(
            pd.DataFrame(
                phase_rows
            ),
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# SCAN BUTTON
# ============================================================

if st.button(
    "🔎 SCAN CURRENT SPORTS NEWS",
    type="primary",
    use_container_width=True,
):
    if not selected_sports:
        st.warning(
            "Select at least one sport."
        )

        st.stop()

    progress = st.progress(
        0
    )

    message = st.empty()

    message.write(
        "### Step 1 of 5 — Checking article dates..."
    )
    progress.progress(15)

    message.write(
        "### Step 2 of 5 — Matching current stories to teams..."
    )
    progress.progress(35)

    message.write(
        "### Step 3 of 5 — Identifying the actual debate topic..."
    )
    progress.progress(55)

    message.write(
        "### Step 4 of 5 — Retrieving topic-specific sports data..."
    )
    progress.progress(75)

    with st.spinner(
        "Scanning fresh sports news and verifying evidence..."
    ):
        (
            candidates,
            scan_stats,
        ) = build_candidates(
            selected_sports,
            news_window,
        )

    message.write(
        "### Step 5 of 5 — Rejecting weak or irrelevant debates..."
    )
    progress.progress(100)

    message.empty()
    progress.empty()

    st.session_state[
        "debate_candidates_v2"
    ] = candidates

    st.session_state[
        "scan_stats_v2"
    ] = scan_stats


# ============================================================
# RESULTS
# ============================================================

candidates = st.session_state.get(
    "debate_candidates_v2"
)


if candidates is None:
    st.info(
        "Press **SCAN CURRENT SPORTS NEWS** to search for today's debates."
    )

    st.stop()


scan_stats = st.session_state.get(
    "scan_stats_v2",
    {},
)


with st.expander(
    "🔍 What the scan checked",
):
    cols = st.columns(4)

    cols[0].metric(
        "Fresh articles",
        scan_stats.get(
            "fresh_articles",
            0,
        ),
    )

    cols[1].metric(
        "Team/entity matches",
        scan_stats.get(
            "matched_entities",
            0,
        ),
    )

    cols[2].metric(
        "Topics rejected",
        scan_stats.get(
            "rejected_topics",
            0,
        ),
    )

    cols[3].metric(
        "Data mismatches rejected",
        scan_stats.get(
            "rejected_data",
            0,
        ),
    )


if not candidates:
    st.warning(
        "The scan did not find a debate that passed all of the freshness, "
        "source, topic, and evidence checks. Try expanding the news window to "
        "48 hours or 7 days. This is intentional—the app will not force a weak debate."
    )

    st.stop()


shown = candidates[
    :number_of_debates
]


st.success(
    f"{len(candidates)} debate candidate(s) passed all verification checks."
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

    st.markdown(
        f"""
<div class="phase-card">

<b>Sport:</b> {candidate['sport']}<br>
<b>Current phase:</b> {candidate['phase']}<br>
<b>Detected topic:</b> {candidate['topic'].replace('_',' ').title()}<br>
<b>Independent current sources:</b> {candidate['source_count']}

</div>
""",
        unsafe_allow_html=True,
    )

    st.write(
        f"# {candidate['question']}"
    )


    # ========================================================
    # SIDES
    # ========================================================

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
    # VERIFIED EVIDENCE
    # ========================================================

    st.write(
        "### 📊 Relevant Verified Data"
    )

    st.markdown(
        """
<div class="data-note">

These statistics were selected <b>because they match this debate topic</b>.
A postseason debate uses postseason information. A slump debate uses recent
performance. An offensive debate uses scoring information.

</div>
""",
        unsafe_allow_html=True,
    )

    evidence_df = pd.DataFrame(
        candidate[
            "evidence"
        ],
        columns=[
            "Evidence",
            "Current value",
        ],
    )

    st.dataframe(
        evidence_df,
        hide_index=True,
        use_container_width=True,
    )


    # ========================================================
    # CURRENT NEWS
    # ========================================================

    st.write(
        "### 📰 Current Reporting"
    )

    for article in candidate[
        "articles"
    ]:
        st.markdown(
            f"""
<div class="news-card">

<b>{article['title']}</b><br>
{article['source']}<br>
<small>{article['published']}</small>

</div>
""",
            unsafe_allow_html=True,
        )

        if article["link"]:
            st.link_button(
                f"Open article — {article['source']}",
                article[
                    "link"
                ],
            )


    # ========================================================
    # STUDENT RESPONSE
    # ========================================================

    st.write(
        "### 🎤 Your Turn"
    )

    st.radio(
        "Which side will you defend?",
        [
            "SIDE A — YES",
            "SIDE B — NO",
            "I need more evidence",
        ],
        horizontal=True,
        key=f"side_{index}",
    )

    st.text_area(
        "Use at least TWO pieces of evidence to defend your position.",
        placeholder=(
            "I believe ... because the data shows ... "
            "Another piece of evidence that supports my argument is ..."
        ),
        key=f"response_{index}",
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "This app separates current reporting from verified sports data. "
    "It also rejects debates when the available evidence does not match the question."
)
