from fastapi import FastAPI
import requests
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware
import json
import time, random, os, uvicorn

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                  " AppleWebKit/537.36 (KHTML, like Gecko)"
                  " Chrome/122.0.0.0 Safari/537.36"
}

def fetch_html(url: str):
    """Fetch and return BeautifulSoup"""
    time.sleep(random.uniform(0.5, 1.2))
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")

def extract_json_data(soup):
    """Extract structured data from IMDb script tag"""
    try:
        script = soup.find("script", type="application/ld+json")
        if script:
            return json.loads(script.text)
    except Exception:
        pass
    return None

def get_details(imdb_id):
    """Get detailed info like actors, year, and type"""
    detail_url = f"https://www.imdb.com/title/{imdb_id}/"
    soup = fetch_html(detail_url)
    data = extract_json_data(soup)
    result = {"actors": [], "year": "N/A", "type": "movie"}

    if data:
        # Year
        if "datePublished" in data:
            result["year"] = str(data["datePublished"]).split("-")[0]

        # Actors
        if "actor" in data:
            result["actors"] = [a["name"] for a in data["actor"][:5]]

        # Type
        if "@type" in data:
            t = data["@type"].lower()
            result["type"] = "tv" if "series" in t else "movie"

    return result


@app.get("/")
def home():
    return {
        "message": "🎬 Smart Bros Real IMDb Scraper API LIVE 🚀",
        "endpoints": [
            "/scrape/imdb_top_picks",
            "/scrape/imdb_popular",
            "/scrape/latest",
        ]
    }


@app.get("/scrape/imdb_top_picks")
def scrape_imdb_top_picks():
    try:
        url = "https://www.imdb.com/what-to-watch/top-picks/"
        soup = fetch_html(url)

        movies = []
        for card in soup.select("a.ipc-poster-card")[:10]:
            href = card.get("href", "")
            if not href or "/title/" not in href:
                continue
            imdb_id = href.split("/title/")[1].split("/")[0]
            img = card.select_one("img")
            title = img.get("alt", "N/A") if img else "N/A"
            image = img.get("src", "") if img else ""

            rating_tag = card.select_one("span.ipc-rating-star")
            rating = rating_tag.text.strip() if rating_tag else "N/A"

            # Fetch detail data
            details = get_details(imdb_id)

            movies.append({
                "title": title,
                "imdb_id": imdb_id,
                "year": details["year"],
                "rating": rating,
                "image": image,
                "type": details["type"],
                "actors": details["actors"]
            })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


@app.get("/scrape/imdb_popular")
def scrape_imdb_popular():
    try:
        url = "https://www.imdb.com/chart/moviemeter/"
        soup = fetch_html(url)

        movies = []
        for row in soup.select("li.ipc-metadata-list-summary-item")[:10]:
            link = row.select_one("a.ipc-title-link-wrapper")
            if not link:
                continue
            imdb_id = link.get("href", "").split("/")[2]
            title = link.text.strip()
            img_tag = row.select_one("img")
            image = img_tag.get("src", "") if img_tag else ""
            rating_tag = row.select_one("span.ipc-rating-star")
            rating = rating_tag.text.strip() if rating_tag else "N/A"

            details = get_details(imdb_id)

            movies.append({
                "title": title,
                "imdb_id": imdb_id,
                "year": details["year"],
                "rating": rating,
                "image": image,
                "type": details["type"],
                "actors": details["actors"]
            })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


@app.get("/scrape/latest")
def scrape_latest_movies():
    try:
        url = "https://www.imdb.com/movies-in-theaters/"
        soup = fetch_html(url)

        movies = []
        for div in soup.select("div.list_item")[:10]:
            title_tag = div.select_one("h4 a")
            if not title_tag:
                continue
            title = title_tag.text.strip()
            imdb_id = title_tag["href"].split("/")[2]
            image_tag = div.select_one("img")
            image = image_tag.get("src", "") if image_tag else ""
            summary_tag = div.select_one("div.outline")
            summary = summary_tag.text.strip() if summary_tag else ""

            details = get_details(imdb_id)

            movies.append({
                "title": title,
                "imdb_id": imdb_id,
                "year": details["year"],
                "rating": "N/A",
                "image": image,
                "summary": summary,
                "type": details["type"],
                "actors": details["actors"]
            })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
