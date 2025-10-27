from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from bs4 import BeautifulSoup
import requests, re, os, time, random, uvicorn

app = FastAPI(title="Smart Bros IMDb Scraper API")

# ====== CORS ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== Headers / Session ======
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
})

# ====== Error Middleware ======
@app.middleware("http")
async def catch_exceptions_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ====== Helper ======
def fetch_html(url: str):
    time.sleep(random.uniform(0.4, 1.2))
    res = session.get(url, timeout=10)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")

def fetch_title_details(imdb_id: str) -> dict:
    """Fetch title page details like rating, genre, and cast."""
    try:
        if not imdb_id:
            return {}
        url = f"https://www.imdb.com/title/{imdb_id}/"
        soup = fetch_html(url)
        rating_tag = soup.select_one("span.sc-d541859f-1")
        rating = rating_tag.text.strip() if rating_tag else None

        year_tag = soup.select_one("span.sc-d541859f-4")
        year = year_tag.text.strip() if year_tag else None

        genre_tags = [g.text for g in soup.select("a[href*='/search/title/?genres=']")]
        cast_tags = [c.text.strip() for c in soup.select("a[data-testid='title-cast-item__actor']")[:5]]

        img_tag = soup.select_one("img.ipc-image")
        image = img_tag["src"] if img_tag and "src" in img_tag.attrs else None

        return {
            "rating": rating,
            "year": year,
            "genres": genre_tags,
            "cast": cast_tags,
            "image": image,
        }
    except Exception:
        return {}

# ====== Routes ======
@app.get("/")
def home():
    return {
        "message": "🎬 Smart Bros Real IMDb Scraper API is LIVE 🚀",
        "endpoints": {
            "/scrape/imdb_top_picks": "IMDb 'What to Watch - Top Picks'",
            "/scrape/imdb_fan_favorites": "IMDb Fan Favorites section",
            "/scrape/imdb_popular": "IMDb Most Popular Movies",
            "/scrape/latest": "Movies now in theatres",
            "/scrape/coming_soon": "Upcoming movies (region optional)",
            "/health": "Health check endpoint"
        }
    }

@app.get("/health")
def health():
    return {"status": "ok"}

# ====== 1️⃣ Top Picks ======
@app.get("/scrape/imdb_top_picks")
def imdb_top_picks():
    try:
        url = "https://www.imdb.com/what-to-watch/top-picks/"
        soup = fetch_html(url)
        items = []

        for card in soup.select("div.ipc-poster-card")[:10]:
            link = card.select_one("a")
            if not link:
                continue
            title = link.get("aria-label") or link.text.strip()
            href = link.get("href", "")
            imdb_id = re.search(r"tt\d+", href)
            imdb_id = imdb_id.group(0) if imdb_id else None

            details = fetch_title_details(imdb_id) if imdb_id else {}
            items.append({
                "title": title,
                "imdb_id": imdb_id,
                **details
            })
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# ====== 2️⃣ Fan Favorites ======
@app.get("/scrape/imdb_fan_favorites")
def imdb_fan_favorites():
    try:
        url = "https://www.imdb.com/what-to-watch/fan-favorites/"
        soup = fetch_html(url)
        items = []

        for card in soup.select("div.ipc-poster-card")[:10]:
            link = card.select_one("a")
            if not link:
                continue
            title = link.get("aria-label") or link.text.strip()
            href = link.get("href", "")
            imdb_id = re.search(r"tt\d+", href)
            imdb_id = imdb_id.group(0) if imdb_id else None

            details = fetch_title_details(imdb_id) if imdb_id else {}
            items.append({
                "title": title,
                "imdb_id": imdb_id,
                **details
            })
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# ====== 3️⃣ Most Popular ======
@app.get("/scrape/imdb_popular")
def imdb_popular():
    try:
        url = "https://www.imdb.com/chart/moviemeter/"
        soup = fetch_html(url)
        items = []

        for li in soup.select("li.ipc-metadata-list-summary-item")[:10]:
            link = li.select_one("a")
            if not link:
                continue
            title = link.text.strip()
            href = link.get("href", "")
            imdb_id = re.search(r"tt\d+", href)
            imdb_id = imdb_id.group(0) if imdb_id else None

            details = fetch_title_details(imdb_id) if imdb_id else {}
            items.append({
                "title": title,
                "imdb_id": imdb_id,
                **details
            })
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# ====== 4️⃣ Latest in Theatres ======
@app.get("/scrape/latest")
def imdb_latest():
    try:
        url = "https://www.imdb.com/movies-in-theaters/"
        soup = fetch_html(url)
        items = []

        for div in soup.select("div.list_item")[:10]:
            a_tag = div.select_one("h4 a")
            if not a_tag:
                continue
            title = a_tag.text.strip()
            href = a_tag.get("href", "")
            imdb_id = re.search(r"tt\d+", href)
            imdb_id = imdb_id.group(0) if imdb_id else None

            details = fetch_title_details(imdb_id) if imdb_id else {}
            items.append({
                "title": title,
                "imdb_id": imdb_id,
                **details
            })
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# ====== 5️⃣ Coming Soon ======
@app.get("/scrape/coming_soon")
def imdb_coming_soon(region: str = "IN"):
    try:
        url = f"https://www.imdb.com/calendar/?region={region}&type=MOVIE"
        soup = fetch_html(url)
        items = []

        for section in soup.select("section.ipc-page-section"):
            date = section.select_one("h3")
            release_date = date.text.strip() if date else "Unknown"

            for li in section.select("li.ipc-metadata-list-summary-item"):
                link = li.select_one("a")
                if not link:
                    continue
                title = link.text.strip()
                href = link.get("href", "")
                imdb_id = re.search(r"tt\d+", href)
                imdb_id = imdb_id.group(0) if imdb_id else None

                details = fetch_title_details(imdb_id) if imdb_id else {}
                items.append({
                    "title": title,
                    "release_date": release_date,
                    "imdb_id": imdb_id,
                    **details
                })
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}

# ====== Run App ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
