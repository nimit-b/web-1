from fastapi import FastAPI
import requests
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn

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
                  " Chrome/120.0.0.0 Safari/537.36"
}

BASE_URL = "https://v3.sg.media-imdb.com/suggestion/"

# Utility to fetch IMDb suggestion API
def imdb_json(letter: str, query: str):
    url = f"{BASE_URL}{letter}/{query}.json"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return res.json()
    return None


@app.get("/")
def home():
    return {
        "message": "🎬 Smart Bros IMDb Hidden API Scraper is LIVE 🚀",
        "endpoints": [
            "/search/{query}",
            "/trending",
            "/fan_favorites",
            "/top_movies"
        ]
    }


@app.get("/search/{query}")
def search_imdb(query: str):
    """Search movies or shows using IMDb’s hidden JSON API"""
    letter = query[0].lower()
    data = imdb_json(letter, query)
    if not data or "d" not in data:
        return {"count": 0, "items": []}

    movies = []
    for item in data["d"]:
        if "id" not in item:
            continue
        movies.append({
            "title": item.get("l", "N/A"),
            "year": item.get("y", "N/A"),
            "imdb_id": item.get("id"),
            "type": item.get("q", "N/A"),
            "image": item.get("i", {}).get("imageUrl") if "i" in item else "",
            "actors": item.get("s", "").split(", ") if "s" in item else [],
        })
    return {"count": len(movies), "items": movies}


@app.get("/trending")
def trending():
    """Get trending movies/shows"""
    # IMDb’s trending list is often around "trending"
    data = imdb_json("t", "trending")
    if not data or "d" not in data:
        return {"count": 0, "items": []}

    movies = []
    for item in data["d"]:
        movies.append({
            "title": item.get("l", "N/A"),
            "year": item.get("y", "N/A"),
            "imdb_id": item.get("id"),
            "type": item.get("q", "N/A"),
            "image": item.get("i", {}).get("imageUrl") if "i" in item else "",
            "actors": item.get("s", "").split(", ") if "s" in item else [],
        })
    return {"count": len(movies), "items": movies}


@app.get("/fan_favorites")
def fan_favorites():
    """Simulate IMDb fan favorites using related keyword"""
    data = imdb_json("f", "fan favorites")
    if not data or "d" not in data:
        return {"count": 0, "items": []}

    movies = []
    for item in data["d"]:
        movies.append({
            "title": item.get("l", "N/A"),
            "year": item.get("y", "N/A"),
            "imdb_id": item.get("id"),
            "type": item.get("q", "N/A"),
            "image": item.get("i", {}).get("imageUrl") if "i" in item else "",
            "actors": item.get("s", "").split(", ") if "s" in item else [],
        })
    return {"count": len(movies), "items": movies}


@app.get("/top_movies")
def top_movies():
    """Fetch top IMDb movies via keyword"""
    data = imdb_json("t", "top rated")
    if not data or "d" not in data:
        return {"count": 0, "items": []}

    movies = []
    for item in data["d"]:
        movies.append({
            "title": item.get("l", "N/A"),
            "year": item.get("y", "N/A"),
            "imdb_id": item.get("id"),
            "type": item.get("q", "N/A"),
            "image": item.get("i", {}).get("imageUrl") if "i" in item else "",
            "actors": item.get("s", "").split(", ") if "s" in item else [],
        })
    return {"count": len(movies), "items": movies}


# Run the API (for Railway/Render)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
