from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx, re, asyncio
from selectolax.parser import HTMLParser

app = FastAPI(title="IMDb Unlimited API", version="1.0")

# --- Allow All Origins ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://www.imdb.com"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


# ---------- UTIL ----------
async def fetch(url):
    async with httpx.AsyncClient(headers=headers, timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
        return HTMLParser(r.text)


def extract_id(href):
    if not href:
        return None
    match = re.search(r"/title/(tt\d+)/", href)
    return match.group(1) if match else None


# ---------- ROUTES ----------
@app.get("/")
async def root():
    return {
        "message": "🎬 IMDb Unlimited API is Running",
        "routes": [
            "/search/{query}",
            "/details/{imdb_id}",
            "/top",
            "/popular",
            "/upcoming",
            "/actor/{name}",
            "/by_genre/{genre}",
        ],
    }


@app.get("/search/{query}")
async def search(query: str):
    url = f"{BASE_URL}/find/?q={query}&s=tt"
    tree = await fetch(url)
    results = []
    for item in tree.css("tr.findResult"):
        title = item.css_first(".result_text")
        img = item.css_first("img")
        if not title:
            continue
        href = title.css_first("a").attributes.get("href", "")
        imdb_id = extract_id(href)
        results.append({
            "title": title.text(strip=True),
            "imdb_id": imdb_id,
            "image": img.attributes.get("src") if img else None
        })
    return {"count": len(results), "items": results}


@app.get("/details/{imdb_id}")
async def details(imdb_id: str):
    url = f"{BASE_URL}/title/{imdb_id}/"
    tree = await fetch(url)
    title = tree.css_first("h1").text(strip=True) if tree.css_first("h1") else None
    year = tree.css_first("a.ipc-link--baseAlt span") 
    rating = tree.css_first("span.sc-d541859f-1") 
    genres = [g.text(strip=True) for g in tree.css("a[href*='/search/title/?genres']")]
    cast = [a.text(strip=True) for a in tree.css("a.sc-bfec09a1-1")]
    img = tree.css_first("img.ipc-image")
    return {
        "title": title,
        "year": year.text(strip=True) if year else None,
        "rating": rating.text(strip=True) if rating else None,
        "genres": genres,
        "cast": cast[:10],
        "image": img.attributes.get("src") if img else None
    }


@app.get("/top")
async def top_movies():
    url = f"{BASE_URL}/chart/top/"
    tree = await fetch(url)
    items = []
    for row in tree.css("li.ipc-metadata-list-summary-item"):
        title_tag = row.css_first("h3")
        href = row.css_first("a.ipc-title-link")
        imdb_id = extract_id(href.attributes.get("href", "")) if href else None
        rating = row.css_first("span.ipc-rating-star")
        img = row.css_first("img")
        items.append({
            "title": title_tag.text(strip=True) if title_tag else "",
            "imdb_id": imdb_id,
            "rating": rating.text(strip=True) if rating else None,
            "image": img.attributes.get("src") if img else None
        })
    return {"count": len(items), "items": items}


@app.get("/popular")
async def popular():
    url = f"{BASE_URL}/chart/moviemeter/"
    tree = await fetch(url)
    items = []
    for row in tree.css("li.ipc-metadata-list-summary-item"):
        title_tag = row.css_first("h3")
        href = row.css_first("a.ipc-title-link")
        imdb_id = extract_id(href.attributes.get("href", "")) if href else None
        img = row.css_first("img")
        items.append({
            "title": title_tag.text(strip=True) if title_tag else "",
            "imdb_id": imdb_id,
            "image": img.attributes.get("src") if img else None
        })
    return {"count": len(items), "items": items}


@app.get("/upcoming")
async def upcoming():
    url = f"{BASE_URL}/calendar/?region=IN&type=MOVIE"
    tree = await fetch(url)
    items = []
    for li in tree.css("li.ipc-metadata-list-summary-item"):
        title_tag = li.css_first("a.ipc-metadata-list-summary-item__t")
        imdb_id = extract_id(title_tag.attributes.get("href", "")) if title_tag else None
        date_tag = li.css_first("h3")
        img = li.css_first("img")
        items.append({
            "title": title_tag.text(strip=True) if title_tag else "",
            "release": date_tag.text(strip=True) if date_tag else None,
            "imdb_id": imdb_id,
            "image": img.attributes.get("src") if img else None
        })
    return {"count": len(items), "items": items}


@app.get("/actor/{name}")
async def actor(name: str):
    # Step 1 — search IMDb for the actor
    url = f"{BASE_URL}/find/?q={name}&s=nm"
    tree = await fetch(url)

    # IMDb changed layout: look for modern React list class
    actor_tag = tree.css_first("a.ipc-metadata-list-summary-item__t")
    if not actor_tag:
        # fallback for classic layout
        actor_tag = tree.css_first("td.result_text a")

    if not actor_tag:
        return {"error": "Actor not found"}

    href = actor_tag.attributes.get("href", "")
    match = re.search(r"/name/(nm\d+)/", href)
    if not match:
        return {"error": "Actor ID not found"}

    actor_id = match.group(1)
    actor_name = actor_tag.text(strip=True)

    # Step 2 — open actor profile
    profile = await fetch(f"{BASE_URL}/name/{actor_id}/")

    # Get profile image (most reliable)
    img = profile.css_first("img.ipc-image")
    image_url = img.attributes.get("src") if img else None

    # Get “Known For” titles (updated selector)
    known_for = []
    for a in profile.css("a.ipc-primary-image-list-card__title, a.ipc-metadata-list-summary-item__t"):
        title = a.text(strip=True)
        href = a.attributes.get("href", "")
        imdb_id = extract_id(href)
        if title and imdb_id:
            known_for.append({"title": title, "imdb_id": imdb_id})

    return {
        "name": actor_name,
        "imdb_id": actor_id,
        "image": image_url,
        "known_for": known_for[:10]
    }


@app.get("/by_genre/{genre}")
async def by_genre(genre: str):
    """
    Fetch movies by genre from IMDb (supports classic + new layouts).
    """
    url = f"{BASE_URL}/search/title/?genres={genre}&sort=moviemeter,asc"
    tree = await fetch(url)
    items = []

    # --- Classic IMDb "lister-item" layout ---
    for div in tree.css("div.lister-item.mode-advanced"):
        title_tag = div.css_first("h3 a")
        year_tag = div.css_first("span.lister-item-year")
        img_tag = div.css_first("img")
        rating_tag = div.css_first("div.inline-block.ratings-imdb-rating strong")

        title = title_tag.text(strip=True) if title_tag else None
        href = title_tag.attributes.get("href", "") if title_tag else ""
        imdb_id = extract_id(href)
        image = (
            img_tag.attributes.get("loadlate")
            or img_tag.attributes.get("src")
            if img_tag
            else None
        )
        rating = rating_tag.text(strip=True) if rating_tag else None

        if imdb_id and title:
            items.append({
                "title": title,
                "year": year_tag.text(strip=True) if year_tag else None,
                "imdb_id": imdb_id,
                "image": image,
                "rating": rating
            })

    # --- New IMDb React layout (fallback) ---
    if not items:
        for li in tree.css("li.ipc-metadata-list-summary-item"):
            title_tag = li.css_first("h3, a.ipc-title-link")
            href_tag = li.css_first("a.ipc-title-link")
            img_tag = li.css_first("img")
            rating_tag = li.css_first("span.ipc-rating-star--imdb, span.ipc-rating-star")

            title = title_tag.text(strip=True) if title_tag else ""
            href = href_tag.attributes.get("href", "") if href_tag else ""
            imdb_id = extract_id(href)
            image = img_tag.attributes.get("src") if img_tag else None
            rating = rating_tag.text(strip=True) if rating_tag else None

            if imdb_id and title:
                items.append({
                    "title": title,
                    "imdb_id": imdb_id,
                    "image": image,
                    "rating": rating
                })

    return {"count": len(items), "items": items[:50]}


# --- For Railway / Render ---
if __name__ == "__main__":
    import uvicorn, os
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)



