from fastapi import FastAPI
import requests
from bs4 import BeautifulSoup
import re
import os
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import random
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36'
})

def random_delay():
    time.sleep(random.uniform(0.4, 1.2))

# ---------------------- HOME ----------------------
@app.get("/")
def home():
    return {
        "message": "🎬 IMDb Hybrid Movie Scraper API",
        "routes": [
            "/health",
            "/scrape/imdb_top_picks",
            "/scrape/imdb_popular",
            "/scrape/imdb_fan_favorites",
            "/scrape/latest",
            "/scrape/coming_soon"
        ]
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

# ---------------------- HELPERS ----------------------
def fetch_title_details(imdb_id):
    """Fetch extra details like genres, plot, and cast"""
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        res = session.get(url)
        soup = BeautifulSoup(res.text, "html.parser")

        title = soup.find("h1").text.strip() if soup.find("h1") else ""
        year = ""
        y = soup.find("span", string=re.compile(r"\d{4}"))
        if y:
            year = y.text.strip()

        rating_tag = soup.find("span", {"class": re.compile("rating")})
        rating = rating_tag.text.strip() if rating_tag else None

        genres = [g.text for g in soup.select("a[href*='genres']")][:3]

        cast = [a.text.strip() for a in soup.select("a[data-testid='title-cast-item__actor']")][:5]
        return {
            "title": title,
            "year": year,
            "rating": rating,
            "genres": genres,
            "cast": cast
        }
    except Exception:
        return {}

# ---------------------- SCRAPERS ----------------------

@app.get("/scrape/imdb_popular")
def scrape_popular():
    url = "https://www.imdb.com/chart/moviemeter/"
    res = session.get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    movies = []
    for row in soup.select("tbody tr")[:10]:
        title_tag = row.select_one(".titleColumn a")
        if not title_tag: continue
        title = title_tag.text
        imdb_id = re.findall(r"tt\d+", title_tag["href"])[0]
        year_tag = row.select_one(".secondaryInfo")
        year = year_tag.text.strip("()") if year_tag else ""
        image_tag = row.select_one("img")
        image = image_tag["src"] if image_tag else ""
        rating_tag = row.select_one("strong")
        rating = rating_tag.text if rating_tag else ""
        movies.append({
            "title": title,
            "year": year,
            "imdb_id": imdb_id,
            "image": image,
            "rating": rating
        })
    return {"count": len(movies), "items": movies}

@app.get("/scrape/imdb_top_picks")
def scrape_top_picks():
    url = "https://v3.sg.media-imdb.com/suggestion/t/top.json"
    res = session.get(url)
    data = res.json()
    movies = []
    for m in data.get("d", [])[:10]:
        imdb_id = m.get("id", "")
        details = fetch_title_details(imdb_id)
        movies.append({
            "title": details.get("title", m.get("l")),
            "year": details.get("year"),
            "imdb_id": imdb_id,
            "image": m.get("i", [None, ""])[0] if "i" in m else "",
            "rating": details.get("rating"),
            "genres": details.get("genres"),
            "cast": details.get("cast")
        })
    return {"count": len(movies), "items": movies}

@app.get("/scrape/imdb_fan_favorites")
def scrape_fan_favorites():
    url = "https://v3.sg.media-imdb.com/suggestion/f/fan.json"
    res = session.get(url)
    data = res.json()
    items = []
    for m in data.get("d", [])[:10]:
        imdb_id = m.get("id", "")
        details = fetch_title_details(imdb_id)
        items.append({
            "title": details.get("title", m.get("l")),
            "year": details.get("year"),
            "imdb_id": imdb_id,
            "image": m.get("i", ["", ""])[0] if "i" in m else "",
            "rating": details.get("rating"),
            "genres": details.get("genres"),
            "cast": details.get("cast")
        })
    return {"count": len(items), "items": items}

@app.get("/scrape/latest")
def scrape_latest():
    url = "https://v3.sg.media-imdb.com/suggestion/n/new.json"
    res = session.get(url)
    data = res.json()
    movies = []
    for m in data.get("d", [])[:10]:
        imdb_id = m.get("id", "")
        details = fetch_title_details(imdb_id)
        movies.append({
            "title": details.get("title", m.get("l")),
            "year": details.get("year"),
            "imdb_id": imdb_id,
            "image": m.get("i", ["", ""])[0] if "i" in m else "",
            "rating": details.get("rating"),
            "genres": details.get("genres"),
            "cast": details.get("cast")
        })
    return {"count": len(movies), "items": movies}
@app.get("/scrape/coming_soon")
def scrape_coming_soon(region: str = "IN"):
    """
    Scrape upcoming movies from IMDb by region.
    Example: /scrape/coming_soon?region=US
    """
    try:
        url = f"https://www.imdb.com/calendar/?region={region}&type=MOVIE&ref_=rlm"
        res = session.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        movies = []
        for date_section in soup.select("section.ipc-page-section"):
            date_header = date_section.select_one("h3")
            release_date = date_header.text.strip() if date_header else "Unknown"

            for li in date_section.select("ul li.ipc-metadata-list-summary-item"):
                title_tag = li.select_one("a.ipc-metadata-list-summary-item__t")
                if not title_tag:
                    continue
                title = title_tag.text.strip()
                imdb_id_match = re.findall(r"tt\d+", title_tag["href"])
                imdb_id = imdb_id_match[0] if imdb_id_match else ""
                image_tag = li.select_one("img")
                image = image_tag["src"] if image_tag else ""
                details = fetch_title_details(imdb_id)
                movies.append({
                    "title": title,
                    "release_date": release_date,
                    "imdb_id": imdb_id,
                    "image": image,
                    "genres": details.get("genres"),
                    "cast": details.get("cast")
                })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


# ---------------------- DEPLOY ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)







