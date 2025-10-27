from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import random
import time

app = FastAPI(title="IMDb Hybrid Scraper API", version="2.0")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# --- Helper Functions ---

def delay():
    """Small delay to reduce scraping load."""
    time.sleep(random.uniform(0.5, 1.5))

def fetch_html(url: str):
    """Safely fetch HTML content."""
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


# --- Routes ---

@app.get("/")
def root():
    return {
        "message": "🎬 IMDb Hybrid Scraper API",
        "version": "2.0",
        "endpoints": [
            "/health",
            "/search/{query}",
            "/details/{imdb_id}",
            "/top_movies",
            "/top_tv",
            "/coming_soon",
            "/by_genre/{genre}",
            "/actor/{actor_name}"
        ]
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

# --- SEARCH ---

@app.get("/search/{query}")
def search(query: str):
    """Search IMDb using public suggestion API."""
    try:
        url = f"https://v2.sg.media-imdb.com/suggestion/{query[0].lower()}/{query}.json"
        res = requests.get(url, headers=HEADERS)
        data = res.json()
        results = []
        for item in data.get("d", []):
            results.append({
                "title": item.get("l"),
                "type": item.get("qid", "movie"),
                "year": item.get("y"),
                "imdb_id": item.get("id"),
                "image": item.get("i", {}).get("imageUrl") if isinstance(item.get("i"), dict) else item.get("i", [None, None])[0]
            })
        return {"count": len(results), "results": results}
    except Exception as e:
        return {"error": str(e)}

# --- DETAILS ---

@app.get("/details/{imdb_id}")
def details(imdb_id: str):
    """Fetch movie details using IMDb mirror API."""
    try:
        url = f"https://imdb.iamidiotareyoutoo.com/search/{imdb_id}"
        res = requests.get(url, headers=HEADERS)
        data = res.json()
        return {
            "title": data.get("title"),
            "year": data.get("year"),
            "rating": data.get("rating"),
            "plot": data.get("plot"),
            "genres": data.get("genres"),
            "directors": data.get("directors"),
            "stars": data.get("stars"),
            "image": data.get("poster"),
        }
    except Exception as e:
        return {"error": str(e)}

# --- TOP MOVIES ---

@app.get("/top_movies")
def top_movies():
    """Scrape IMDb Top 250 Movies."""
    try:
        soup = fetch_html("https://www.imdb.com/chart/top/")
        delay()
        movies = []
        for row in soup.select("li.ipc-metadata-list-summary-item")[:20]:
            title_el = row.select_one("h3")
            rating_el = row.select_one("span.ipc-rating-star")
            image_el = row.select_one("img")
            imdb_id = None
            a_tag = row.select_one("a.ipc-title-link-wrapper")
            if a_tag and "href" in a_tag.attrs:
                imdb_id = a_tag["href"].split("/")[2]
            movies.append({
                "title": title_el.text.strip() if title_el else None,
                "rating": rating_el.text.strip() if rating_el else None,
                "imdb_id": imdb_id,
                "image": image_el["src"] if image_el else None
            })
        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}

# --- TOP TV SHOWS ---

@app.get("/top_tv")
def top_tv():
    """Scrape IMDb Top 250 TV shows."""
    try:
        soup = fetch_html("https://www.imdb.com/chart/toptv/")
        delay()
        shows = []
        for row in soup.select("li.ipc-metadata-list-summary-item")[:20]:
            title_el = row.select_one("h3")
            rating_el = row.select_one("span.ipc-rating-star")
            image_el = row.select_one("img")
            imdb_id = None
            a_tag = row.select_one("a.ipc-title-link-wrapper")
            if a_tag and "href" in a_tag.attrs:
                imdb_id = a_tag["href"].split("/")[2]
            shows.append({
                "title": title_el.text.strip() if title_el else None,
                "rating": rating_el.text.strip() if rating_el else None,
                "imdb_id": imdb_id,
                "image": image_el["src"] if image_el else None
            })
        return {"count": len(shows), "items": shows}
    except Exception as e:
        return {"error": str(e)}

# --- COMING SOON ---

@app.get("/coming_soon")
def coming_soon():
    """Use IMDb mirror for upcoming movies."""
    try:
        url = "https://imdb.iamidiotareyoutoo.com/upcoming"
        res = requests.get(url, headers=HEADERS)
        data = res.json()
        items = [{
            "title": m.get("title"),
            "release": m.get("release"),
            "imdb_id": m.get("id"),
            "image": m.get("poster"),
        } for m in data.get("results", [])]
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# --- BY GENRE ---

@app.get("/by_genre/{genre}")
def by_genre(genre: str):
    """Fetch movies by genre using IMDb mirror."""
    try:
        url = f"https://imdb.iamidiotareyoutoo.com/genre/{genre.lower()}"
        res = requests.get(url, headers=HEADERS)
        data = res.json()
        items = [{
            "title": m.get("title"),
            "year": m.get("year"),
            "rating": m.get("rating"),
            "imdb_id": m.get("id"),
            "image": m.get("poster"),
        } for m in data.get("results", [])]
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# --- ACTOR INFO ---

@app.get("/actor/{actor_name}")
def actor(actor_name: str):
    """Search for actor and get info."""
    try:
        url = f"https://imdb.iamidiotareyoutoo.com/search?q={actor_name}"
        res = requests.get(url, headers=HEADERS)
        data = res.json()
        if "results" not in data or len(data["results"]) == 0:
            return {"error": "No actor found"}
        person = next((x for x in data["results"] if x["type"] == "person"), None)
        if not person:
            return {"error": "No person found"}
        return {
            "name": person.get("title"),
            "imdb_id": person.get("id"),
            "image": person.get("poster"),
            "known_for": person.get("known_for", []),
        }
    except Exception as e:
        return {"error": str(e)}



# Run the API (for Railway/Render)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

