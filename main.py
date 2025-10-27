# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import time
import random
import os
from typing import List, Dict, Any

app = FastAPI(title="SmartBros IMDb Hybrid API", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Headers + polite delay
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def delay(min_s=0.5, max_s=1.1):
    time.sleep(random.uniform(min_s, max_s))

# ---------- Helper utilities ----------

def safe_get(url: str, params: dict = None, timeout: int = 10) -> requests.Response:
    """GET wrapper with headers and basic error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        raise

def parse_html(url: str) -> BeautifulSoup:
    """Fetch page and return BeautifulSoup object (static HTML parsing)."""
    resp = safe_get(url)
    return BeautifulSoup(resp.text, "html.parser")

def imdb_suggestion(query: str) -> Dict[str, Any]:
    """
    Use IMDb suggestion endpoint (v3/v2). Returns JSON dict or {}.
    Example endpoint: https://v3.sg.media-imdb.com/suggestion/x/inception.json
    We'll try v3 then v2 then fallback to imdbot.
    """
    q = query.strip()
    if not q:
        return {}
    first = q[0].lower()
    urls = [
        f"https://v3.sg.media-imdb.com/suggestion/{first}/{q}.json",
        f"https://v2.sg.media-imdb.com/suggestion/{first}/{q}.json",
        f"https://search.imdbot.workers.dev/?q={q}"
    ]
    for url in urls:
        try:
            delay(0.2, 0.6)
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            data = r.json()
            # imdbot returns different structure -> normalize later in callers
            return data
        except Exception:
            continue
    return {}

def imdbot_details(imdb_id: str) -> Dict[str, Any]:
    """
    Use an IMDb mirror / public worker (imdbot) to fetch title details by imdb_id.
    Endpoint example: https://search.imdbot.workers.dev/?tt=tt1375666
    Returns dict or {}.
    """
    try:
        delay(0.2, 0.6)
        url = f"https://search.imdbot.workers.dev/?tt={imdb_id}"
        r = requests.get(url, headers=HEADERS, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def extract_top_cast_from_details(details_json: dict, max_cast: int = 5) -> List[str]:
    """
    Try common keys in details JSON to extract top cast names.
    Accepts different mirror shapes.
    """
    cast = []
    if not details_json:
        return cast

    # Common possibilities:
    # - 'cast' list of dicts with 'name'
    # - 'stars' list/str
    # - 'actors' key
    if isinstance(details_json.get("cast"), list):
        for item in details_json.get("cast")[:max_cast]:
            if isinstance(item, dict):
                name = item.get("name") or item.get("actor") or item.get("title")
                if name:
                    cast.append(name)
            elif isinstance(item, str):
                cast.append(item)
    elif isinstance(details_json.get("stars"), list):
        for s in details_json.get("stars")[:max_cast]:
            if isinstance(s, str):
                cast.append(s)
    elif isinstance(details_json.get("actors"), list):
        for s in details_json.get("actors")[:max_cast]:
            if isinstance(s, str):
                cast.append(s)
    elif isinstance(details_json.get("actor"), list):
        for a in details_json.get("actor")[:max_cast]:
            if isinstance(a, dict):
                if a.get("name"):
                    cast.append(a.get("name"))
    # fallback: 'castSummary' or 'principals' or 'credits'
    if not cast:
        for key in ("principals", "credits", "castSummary"):
            val = details_json.get(key)
            if isinstance(val, list):
                for item in val[:max_cast]:
                    if isinstance(item, dict) and item.get("name"):
                        cast.append(item.get("name"))
            if cast:
                break

    return cast[:max_cast]

def normalize_suggestion_item(item: dict) -> dict:
    """
    Normalize suggestion result item (v3/v2 or imdbot shape) into common shape.
    Returns dict: {title, year, imdb_id, type, image, actors[]}
    """
    out = {"title": None, "year": None, "imdb_id": None, "type": None, "image": None, "actors": []}
    if not item:
        return out
    # v3/v2 keys: 'l' (title), 'y' (year), 'id' (imdb id), 'q' (type), 'i' (image)
    if "l" in item:
        out["title"] = item.get("l")
    if "y" in item:
        out["year"] = item.get("y")
    if "id" in item:
        out["imdb_id"] = item.get("id")
    if "q" in item:
        out["type"] = item.get("q")
    # image may be under 'i' as dict {imageUrl:...} or as list
    img = item.get("i")
    if isinstance(img, dict):
        # sometimes 'imageUrl' or 'image' keys
        out["image"] = img.get("imageUrl") or img.get("image")
    elif isinstance(img, list) and len(img) > 0:
        out["image"] = img[0]
    elif "image" in item:
        out["image"] = item.get("image")
    # actors in suggestion appear in 's' as string "Actor1, Actor2"
    if "s" in item and isinstance(item.get("s"), str):
        out["actors"] = [x.strip() for x in item.get("s").split(",") if x.strip()]
    return out

# ---------- Endpoints ----------

@app.get("/")
def root():
    return {
        "message": "Smart Bros IMDb Hybrid API (no-browser hybrid)",
        "endpoints": [
            "/health",
            "/search/{query}",
            "/details/{imdb_id}",
            "/scrape/imdb_top_picks",
            "/scrape/imdb_popular",
            "/scrape/imdb_fan_favorites",
            "/scrape/latest",
            "/scrape/coming_soon"
        ]
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

# ---------- Search ----------

@app.get("/search/{query}")
def search(query: str):
    """
    Search for movies, shows, people using IMDb suggestion or imdbot mirror.
    Returns normalized results.
    """
    try:
        raw = imdb_suggestion(query)
        results = []
        # v3 has key 'd' with list of items
        if isinstance(raw, dict) and "d" in raw:
            for it in raw.get("d", [])[:30]:
                normalized = normalize_suggestion_item(it)
                results.append(normalized)
        else:
            # imdbot mirror might return 'results' or list
            if isinstance(raw, dict) and raw.get("results"):
                for it in raw.get("results")[:30]:
                    # imdbot's person/movie shapes may differ; try to standardize
                    item = {}
                    item["title"] = it.get("title") or it.get("l") or it.get("name")
                    item["year"] = it.get("year") or it.get("y")
                    item["imdb_id"] = it.get("id") or it.get("tt")
                    item["type"] = it.get("type") or it.get("q")
                    item["image"] = it.get("image") or it.get("poster")
                    item["actors"] = it.get("known_for", [])
                    results.append(item)
        return {"count": len(results), "results": results}
    except Exception as e:
        return {"error": str(e)}

# ---------- Details ----------

@app.get("/details/{imdb_id}")
def details(imdb_id: str):
    """
    Return extended details for a title using imdbot mirror (fast) and fallback to JSON-LD from imdb page.
    """
    try:
        # prefer mirror details
        data = imdbot_details(imdb_id)
        if data and isinstance(data, dict) and data.get("title"):
            title = data.get("title")
            year = data.get("year") or data.get("release_year")
            rating = data.get("rating") or data.get("imdb_rating")
            plot = data.get("plot") or data.get("summary")
            genres = data.get("genres") or data.get("genre") or []
            poster = data.get("poster") or data.get("image")
            # extract cast
            cast = extract_top_cast_from_details(data, max_cast=8)
            return {
                "title": title,
                "year": year,
                "imdb_id": imdb_id,
                "rating": rating,
                "plot": plot,
                "genres": genres,
                "poster": poster,
                "cast": cast
            }
        # fallback: try JSON-LD on imdb page
        delay()
        url = f"https://www.imdb.com/title/{imdb_id}/"
        soup = parse_html(url)
        # find ld+json
        script = soup.find("script", type="application/ld+json")
        if script:
            try:
                j = script.string
                import json
                data = json.loads(j)
                title = data.get("name")
                year = None
                if data.get("datePublished"):
                    year = str(data.get("datePublished")).split("-")[0]
                rating = None
                if isinstance(data.get("aggregateRating"), dict):
                    rating = data["aggregateRating"].get("ratingValue")
                genres = data.get("genre") or []
                poster = None
                if data.get("image"):
                    poster = data.get("image")
                cast = []
                if isinstance(data.get("actor"), list):
                    for a in data.get("actor")[:8]:
                        if isinstance(a, dict) and a.get("name"):
                            cast.append(a.get("name"))
                return {
                    "title": title,
                    "year": year,
                    "imdb_id": imdb_id,
                    "rating": rating,
                    "plot": data.get("description"),
                    "genres": genres,
                    "poster": poster,
                    "cast": cast
                }
            except Exception:
                pass
        return {"error": "details-not-found"}
    except Exception as e:
        return {"error": str(e)}

# ---------- Top Movies (chart/top) ----------

@app.get("/scrape/imdb_top_picks")
def imdb_top_picks(limit: int = 20):
    """
    Returns top-rated chart (Top 250) — server-rendered chart page scraping.
    """
    try:
        soup = parse_html("https://www.imdb.com/chart/top/")
        delay()
        items = []
        # classic table rows
        rows = soup.select("tbody.lister-list > tr")
        if not rows:
            # try alternate selector (site redesign safe-guard)
            rows = soup.select("li.ipc-metadata-list-summary-item")
        for row in rows[:limit]:
            try:
                # title column
                title_col = row.select_one("td.titleColumn") or row
                a = title_col.select_one("a")
                title = a.text.strip() if a else None
                href = a["href"] if a and a.has_attr("href") else ""
                imdb_id = None
                if "/title/" in href:
                    imdb_id = href.split("/title/")[1].split("/")[0]
                year_tag = title_col.select_one("span.secondaryInfo")
                year = year_tag.text.strip("()") if year_tag else None
                rating_tag = row.select_one("td.ratingColumn.imdbRating strong") or row.select_one("span.icp-rating-star")
                rating = rating_tag.text.strip() if rating_tag else None
                image = None
                # try to find poster
                img = row.select_one("img")
                if img and img.has_attr("src"):
                    image = img["src"]
                # try to get details via mirror for cast/genres
                details = imdbot_details(imdb_id) if imdb_id else {}
                cast = extract_top_cast_from_details(details, max_cast=6)
                items.append({
                    "title": title,
                    "year": year,
                    "imdb_id": imdb_id,
                    "rating": rating,
                    "image": image,
                    "cast": cast
                })
            except Exception:
                continue
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# ---------- Popular (moviemeter) ----------

@app.get("/scrape/imdb_popular")
def imdb_popular(limit: int = 20):
    """
    Scrape Most Popular Movies (moviemeter). Falls back to suggestion if needed.
    """
    try:
        # first try chart page
        try:
            soup = parse_html("https://www.imdb.com/chart/moviemeter/")
            delay()
            items = []
            rows = soup.select("tbody > tr")
            for row in rows[:limit]:
                try:
                    a = row.select_one("td.titleColumn a")
                    title = a.text.strip() if a else None
                    href = a["href"] if a and a.has_attr("href") else ""
                    imdb_id = href.split("/title/")[1].split("/")[0] if "/title/" in href else None
                    rating_tag = row.select_one("td.ratingColumn .rating")
                    rating = rating_tag.text.strip() if rating_tag else None
                    img = row.select_one("img")
                    image = img["src"] if img and img.has_attr("src") else None
                    details = imdbot_details(imdb_id) if imdb_id else {}
                    cast = extract_top_cast_from_details(details, max_cast=6)
                    items.append({
                        "title": title,
                        "year": details.get("year") or None,
                        "imdb_id": imdb_id,
                        "rating": rating or details.get("rating"),
                        "image": image,
                        "cast": cast
                    })
                except Exception:
                    continue
            if items:
                return {"count": len(items), "items": items}
        except Exception:
            pass

        # fallback: use suggestion endpoint for "popular"
        raw = imdb_suggestion("popular")
        items = []
        if raw and isinstance(raw, dict) and "d" in raw:
            for it in raw.get("d", [])[:limit]:
                norm = normalize_suggestion_item(it)
                # get cast via details
                if norm.get("imdb_id"):
                    det = imdbot_details(norm["imdb_id"])
                    norm["cast"] = extract_top_cast_from_details(det, max_cast=6)
                    norm["year"] = norm.get("year") or det.get("year")
                    norm["rating"] = det.get("rating") or None
                items.append(norm)
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# ---------- Fan Favorites ----------

@app.get("/scrape/imdb_fan_favorites")
def imdb_fan_favorites(limit: int = 20):
    """
    Attempt to return fan favorites. Uses suggestion/imdbot/search fallback.
    """
    try:
        # Try suggestion for "fan favorites"
        raw = imdb_suggestion("fan favorites")
        items = []
        if raw and isinstance(raw, dict) and "d" in raw:
            for it in raw.get("d", [])[:limit]:
                norm = normalize_suggestion_item(it)
                if norm.get("imdb_id"):
                    det = imdbot_details(norm["imdb_id"])
                    norm["cast"] = extract_top_cast_from_details(det, max_cast=6)
                    norm["rating"] = det.get("rating")
                items.append(norm)
            if items:
                return {"count": len(items), "items": items}

        # fallback: do a search for "fan favorites" via imdbot
        try:
            delay()
            r = safe_get("https://search.imdbot.workers.dev/?q=fan%20favorites")
            data = r.json()
            if isinstance(data, dict) and data.get("results"):
                for it in data.get("results")[:limit]:
                    title = it.get("title") or it.get("l")
                    imdb_id = it.get("id") or it.get("tt")
                    det = imdbot_details(imdb_id) if imdb_id else {}
                    items.append({
                        "title": title,
                        "year": det.get("year") or it.get("year"),
                        "imdb_id": imdb_id,
                        "rating": det.get("rating"),
                        "image": it.get("poster") or it.get("image"),
                        "cast": extract_top_cast_from_details(det, max_cast=6)
                    })
                if items:
                    return {"count": len(items), "items": items}
        except Exception:
            pass

        return {"count": 0, "items": []}
    except Exception as e:
        return {"error": str(e)}

# ---------- Latest (in theaters) ----------

@app.get("/scrape/latest")
def imdb_latest(limit: int = 20):
    """
    Movies in theaters. Try server-rendered page first; fallback to imdbot mirror.
    """
    try:
        try:
            soup = parse_html("https://www.imdb.com/movies-in-theaters/")
            delay()
            items = []
            # page often contains div.list_item
            for div in soup.select("div.list_item")[:limit]:
                try:
                    a = div.select_one("h4 a")
                    title = a.text.strip() if a else None
                    href = a["href"] if a and a.has_attr("href") else ""
                    imdb_id = href.split("/title/")[1].split("/")[0] if "/title/" in href else None
                    img = div.select_one("img")
                    image = img["src"] if img and img.has_attr("src") else None
                    summary = None
                    s = div.select_one("div.outline")
                    if s:
                        summary = s.text.strip()
                    det = imdbot_details(imdb_id) if imdb_id else {}
                    items.append({
                        "title": title,
                        "year": det.get("year") or None,
                        "imdb_id": imdb_id,
                        "image": image,
                        "summary": summary,
                        "cast": extract_top_cast_from_details(det, max_cast=6),
                        "rating": det.get("rating")
                    })
                except Exception:
                    continue
            if items:
                return {"count": len(items), "items": items}
        except Exception:
            pass

        # fallback to imdbot upcoming endpoint or search for 'in theaters'
        try:
            delay()
            r = safe_get("https://search.imdbot.workers.dev/?q=in%20theaters")
            data = r.json()
            items = []
            for it in (data.get("results") or [])[:limit]:
                imdb_id = it.get("id") or it.get("tt")
                det = imdbot_details(imdb_id) if imdb_id else {}
                items.append({
                    "title": it.get("title") or it.get("l"),
                    "year": det.get("year") or it.get("year"),
                    "imdb_id": imdb_id,
                    "image": it.get("poster") or it.get("image"),
                    "cast": extract_top_cast_from_details(det, max_cast=6),
                    "rating": det.get("rating")
                })
            return {"count": len(items), "items": items}
        except Exception:
            return {"count": 0, "items": []}
    except Exception as e:
        return {"error": str(e)}

# ---------- Coming Soon ----------

@app.get("/scrape/coming_soon")
def imdb_coming_soon(limit: int = 30):
    """
    Coming soon (upcoming releases). Use a mirror endpoint or parse the "coming soon" pages.
    """
    try:
        # try a mirror JSON that provides upcoming data
        try:
            delay()
            r = safe_get("https://search.imdbot.workers.dev/?q=coming%20soon")
            data = r.json()
            items = []
            for it in (data.get("results") or [])[:limit]:
                imdb_id = it.get("id") or it.get("tt")
                det = imdbot_details(imdb_id) if imdb_id else {}
                items.append({
                    "title": it.get("title") or it.get("l"),
                    "release": det.get("release_date") or it.get("release") or it.get("year"),
                    "imdb_id": imdb_id,
                    "image": it.get("poster") or it.get("image"),
                    "cast": extract_top_cast_from_details(det, max_cast=6)
                })
            if items:
                return {"count": len(items), "items": items}
        except Exception:
            pass

        # fallback: parse IMDb coming soon page (server side content may exist)
        try:
            soup = parse_html("https://www.imdb.com/movies-coming-soon/")
            delay()
            items = []
            for card in soup.select("div.list_item")[:limit]:
                try:
                    a = card.select_one("h4 a")
                    title = a.text.strip() if a else None
                    href = a["href"] if a and a.has_attr("href") else ""
                    imdb_id = href.split("/title/")[1].split("/")[0] if "/title/" in href else None
                    date_tag = card.select_one("div.release_date")
                    release = date_tag.text.strip() if date_tag else None
                    det = imdbot_details(imdb_id) if imdb_id else {}
                    items.append({
                        "title": title,
                        "release": release or det.get("release_date"),
                        "imdb_id": imdb_id,
                        "image": det.get("poster"),
                        "cast": extract_top_cast_from_details(det, max_cast=6)
                    })
                except Exception:
                    continue
            return {"count": len(items), "items": items}
        except Exception:
            return {"count": 0, "items": []}
    except Exception as e:
        return {"error": str(e)}




if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)





