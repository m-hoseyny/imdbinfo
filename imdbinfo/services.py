from typing import Optional
from functools import lru_cache
from time import time
import logging
import requests
import json
from lxml import html
from random import choice

from .models import SearchResult, MovieDetail, SeasonEpisodesList, PersonDetail
from .parsers import (
    parse_json_movie,
    parse_json_search,
    parse_json_person_detail,
    parse_json_season_episodes,
    parse_json_bulked_episodes, parse_json_akas,
)
from .locale import get_locale

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.86 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.78 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.79 Safari/537.36"
]

@lru_cache(maxsize=128)
def get_movie(imdb_id: str, locale: str = None) -> MovieDetail:
    """Fetch movie details from IMDb using the provided IMDb ID as string,
    preserve the 'tt' prefix or not, it will be stripped in the function.
    """
    lang = get_locale()
    if type(imdb_id) != str:
        imdb_id = str(imdb_id)
    imdb_id = imdb_id.lstrip("tt")
    if len(imdb_id) != 7:
        imdb_id = "0" * (7 - len(imdb_id)) + imdb_id
    url = f"https://www.imdb.com/title/tt{imdb_id}/reference"
    logger.info("Fetching movie %s", imdb_id)
    resp = requests.get(url, headers={"User-Agent": choice(USER_AGENTS)})
    if resp.status_code > 204:
        logger.error("Error fetching %s: %s", url, resp.status_code)
        raise Exception(f"Error fetching {url}")
    tree = html.fromstring(resp.content)
    script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if not script:
        logger.error("No script found with id '__NEXT_DATA__'")
        raise Exception("No script found with id '__NEXT_DATA__'")
    raw_json = json.loads(script[0])
    movie = parse_json_movie(raw_json)
    logger.debug("Fetched url %s", url)
    return movie


@lru_cache(maxsize=128)
def search_title(title: str, locale: str = None) -> Optional[SearchResult]:
    """Search for a movie by title and return a list of titles and names."""
    lang = get_locale()
    url = f"https://www.imdb.com/{lang}/find?q={title}&ref_=nv_sr_sm"
    logger.info("Searching for title '%s'", title)
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code != 200:
        logger.warning("Search request failed: %s", resp.status_code)
        return None
    tree = html.fromstring(resp.content)
    script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if not script:  # throw if no script found
        logger.error("No script found with id '__NEXT_DATA__'")
        raise Exception("No script found with id '__NEXT_DATA__'")
    raw_json = json.loads(script[0])

    result = parse_json_search(raw_json)
    logger.debug("Search for '%s' returned %s titles", title, len(result.titles))
    return result


@lru_cache(maxsize=128)
def get_name(person_id: str, locale: str = None) -> Optional[PersonDetail]:
    """Fetch person details from IMDb using the provided IMDb ID.
    Preserve the 'nm' prefix or not, it will be stripped in the function.
    """
    lang = get_locale()
    person_id = person_id.lstrip("nm")
    url = f"https://www.imdb.com/name/nm{person_id}/"
    logger.info("Fetching person %s", person_id)
    t0 = time()
    resp = requests.get(url, headers={"User-Agent": choice(USER_AGENTS)})
    t1 = time()
    logger.debug("Fetched person %s in %.2f seconds", person_id, t1 - t0)
    if resp.status_code != 200:
        logger.error("Error fetching %s: %s", url, resp.status_code)
        raise Exception(f"Error fetching {url}")
    tree = html.fromstring(resp.content)
    script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if not script:
        logger.error("No script found with id '__NEXT_DATA__'")
        raise Exception("No script found with id '__NEXT_DATA__'")
    t0 = time()
    raw_json = json.loads(script[0])
    person = parse_json_person_detail(raw_json)
    t1 = time()
    logger.debug("Parsed person %s in %.2f seconds", person_id, t1 - t0)
    return person


@lru_cache(maxsize=128)
def get_season_episodes(imdb_id: str, season=1, locale: str = None) -> SeasonEpisodesList:
    """Fetch episodes for a movie or series using the provided IMDb ID."""
    movies_id = imdb_id.lstrip("tt")
    lang = locale or get_locale()
    url = f"https://www.imdb.com/{lang}/title/tt{movies_id}/episodes/?season={season}"
    logger.info("Fetching episodes for movie %s", imdb_id)
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code != 200:
        logger.error("Error fetching %s: %s", url, resp.status_code)
        raise Exception(f"Error fetching {url}")
    tree = html.fromstring(resp.content)
    script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if not script:
        logger.error("No script found with id '__NEXT_DATA__'")
        raise Exception("No script found with id '__NEXT_DATA__'")
    raw_json = json.loads(script[0])
    episodes = parse_json_season_episodes(raw_json)
    logger.debug("Fetched %d episodes for movie %s", len(episodes.episodes), imdb_id)
    return episodes


@lru_cache(maxsize=128)
def get_all_episodes(imdb_id: str, locale: str = None):
    series_id = imdb_id.lstrip("tt")
    lang = locale or get_locale()
    url = f"https://www.imdb.com/{lang}/search/title/?count=250&series=tt{series_id}&sort=release_date,asc"
    logger.info("Fetching bulk episodes for series %s", imdb_id)
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code != 200:
        logger.error("Error fetching %s: %s", url, resp.status_code)
        raise Exception(f"Error fetching {url}")
    tree = html.fromstring(resp.content)
    script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if not script:
        logger.error("No script found with id '__NEXT_DATA__'")
        raise Exception("No script found with id '__NEXT_DATA__'")
    raw_json = json.loads(script[0])
    episodes = parse_json_bulked_episodes(raw_json)
    logger.debug("Fetched %d episodes for series %s", len(episodes), imdb_id)
    return episodes


@lru_cache(maxsize=128)
def get_episodes(imdb_id: str, season=1, locale: str = None) -> SeasonEpisodesList:
    """wrap until deprecation : use get_season_episodes instead for seasons
    or get_all_episodes for all episodes
    """
    logger.warning("get_episodes is deprecating, use get_season_episodes or get_all_episodes instead.")
    return get_season_episodes(imdb_id, season, locale)





@lru_cache(maxsize=128)
def get_akas(imdb_id: str) -> dict:
    imdb_id = "tt%s"%imdb_id.lstrip("tt")
    url = "https://api.graphql.imdb.com/"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": choice(USER_AGENTS),
    }
    query = '''
    query {
      title(id: "%s") {
        id
        titleText {
          text
        }
        originalTitle: originalTitleText {
          text
        }
        akas(first: 200) {
          edges {
            node {
              country { name: text code: id }
              language { name: text code: id }
              title: text
            }
          }
        }
      }
    }
    ''' % imdb_id
    payload = {"query": query}
    logger.info("Fetching title %s from GraphQL API", imdb_id)
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        logger.error("GraphQL request failed: %s", resp.status_code)
        raise Exception(f"GraphQL request failed: {resp.status_code}")
    data = resp.json()
    if "errors" in data:
        logger.error("GraphQL error: %s", data["errors"])
        raise Exception(f"GraphQL error: {data['errors']}")
    raw_json = data.get("data", {}).get("title", {})
    akas = parse_json_akas(raw_json)
    if not raw_json:
        logger.warning("No AKAs found for title %s", imdb_id)
        return []
    logger.debug("Fetched %d AKAs for title %s", len(akas), imdb_id)
    return akas
