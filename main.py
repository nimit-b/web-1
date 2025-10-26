from fastapi import FastAPI
import requests
from bs4 import BeautifulSoup
import time
import random
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

# Common Headers (Avoid blocks)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                  " AppleWebKit/537.36 (KHTML, like Gecko)"
                  " Chrome/120.0.0.0 Safari/537.36"
}


def fetch_html(url: str):
    """Fetch and return parsed HTML soup"""
    time.sleep(random.uniform(0.5, 1.2))  # be polite
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


@app.get("/")
def home():
    return {
        "message": "🎬 Smart Bros Real IMDb Scraper API is LIVE 🚀",
        "endpoints": [
            "/scrape/imdb_top_picks",
            "/scrape/imdb_fan_favorites",
            "/scrape/imdb_popular",
            "/scrape/latest"
        ]
    }


@app.get("/scrape/imdb_top_picks")
def scrape_imdb_top_picks():
    """Scrape IMDb's Top Picks section from What to Watch"""
    try:
        url = "https://www.imdb.com/what-to-watch/top-picks/?ref_=hm_tpks_sm"
        soup = fetch_html(url)

        movies = []
        # Look for title cards in the What to Watch section
        for card in soup.select("div.ipc-page-grid__item")[:10]:
            try:
                # Find the title link
                title_link = card.select_one("a.ipc-title-link-wrapper")
                if not title_link:
                    continue
                
                # Extract title
                title_elem = title_link.select_one("h3.ipc-title")
                title = title_elem.text.strip() if title_elem else "Unknown Title"
                
                # Extract IMDb ID from href
                href = str(title_link.get("href", ""))
                imdb_id = ""
                if "/title/" in href:
                    imdb_id = href.split("/title/")[1].split("/")[0]
                
                # Extract year
                year_elem = card.select_one("span.sc-c70ad09b-8")
                year = year_elem.text.strip() if year_elem else "N/A"
                
                # Extract image
                img_elem = card.select_one("img.ipc-image")
                image = str(img_elem.get("src", "")) if img_elem else ""
                
                # Extract rating if available
                rating_elem = card.select_one("span.ipc-rating-star")
                rating = ""
                if rating_elem:
                    rating_text = rating_elem.text.strip()
                    # Extract just the rating number (e.g., "8.1" from "8.1 (10K)")
                    rating = rating_text.split()[0] if rating_text else ""
                
                # Determine if it's a movie or TV show by fetching the detailed page
                content_type = "movie"  # default
                actors = []
                
                if imdb_id:
                    try:
                        # Fetch detailed page for content type and actors
                        detail_url = f"https://www.imdb.com/title/{imdb_id}/"
                        detail_soup = fetch_html(detail_url)
                        
                        # Check for TV series indicator
                        type_elem = detail_soup.select_one("a.ipc-metadata-list-item__label")
                        if type_elem and "TV Series" in type_elem.text:
                            content_type = "tv"
                        
                        # Extract actors
                        actor_elements = detail_soup.select("a[data-testid='cast-item']")
                        for actor_elem in actor_elements[:5]:  # Limit to first 5 actors
                            actor_name = actor_elem.text.strip()
                            if actor_name:
                                actors.append(actor_name)
                    except Exception:
                        # If we can't fetch details, continue with defaults
                        pass
                
                # Only add if we have a title
                if title and title != "Unknown Title":
                    movies.append({
                        "title": title,
                        "year": year,
                        "imdb_id": imdb_id,
                        "image": image,
                        "rating": rating,
                        "type": content_type,
                        "actors": actors
                    })
            except Exception as e:
                # Skip this card if there's an error parsing it
                continue

        # If we couldn't parse any items, use the chart/top as fallback
        if not movies:
            url = "https://www.imdb.com/chart/top/"
            soup = fetch_html(url)
            
            for row in soup.select("li.ipc-metadata-list-summary-item")[:10]:
                title_tag = row.select_one("h3")
                title = title_tag.text.strip() if title_tag else "N/A"

                rating_tag = row.select_one("span.ipc-rating-star")
                rating = rating_tag.text.strip() if rating_tag else "N/A"

                image_tag = row.select_one("img.ipc-image")
                image = image_tag["src"] if image_tag else ""

                link_tag = row.select_one("a.ipc-title-link-wrapper")
                imdb_id = ""
                if link_tag and "href" in link_tag.attrs:
                    imdb_id = str(link_tag["href"]).split("/")[2]

                # Determine if it's a movie or TV show by fetching the detailed page
                content_type = "movie"  # default
                actors = []
                
                if imdb_id:
                    try:
                        # Fetch detailed page for content type and actors
                        detail_url = f"https://www.imdb.com/title/{imdb_id}/"
                        detail_soup = fetch_html(detail_url)
                        
                        # Check for TV series indicator
                        type_elem = detail_soup.select_one("a.ipc-metadata-list-item__label")
                        if type_elem and "TV Series" in type_elem.text:
                            content_type = "tv"
                        
                        # Extract actors
                        actor_elements = detail_soup.select("a[data-testid='cast-item']")
                        for actor_elem in actor_elements[:5]:  # Limit to first 5 actors
                            actor_name = actor_elem.text.strip()
                            if actor_name:
                                actors.append(actor_name)
                    except Exception:
                        # If we can't fetch details, continue with defaults
                        pass

                movies.append({
                    "title": title,
                    "rating": rating,
                    "imdb_id": imdb_id,
                    "image": image,
                    "type": content_type,
                    "actors": actors
                })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


@app.get("/scrape/imdb_fan_favorites")
def scrape_fan_favorites():
    """Scrape IMDb Fan Favorites section"""
    try:
        url = "https://www.imdb.com/what-to-watch/fan-favorites/"
        soup = fetch_html(url)

        movies = []
        for div in soup.select("div.ipc-poster-card")[:10]:
            title_tag = div.select_one("img")
            title = title_tag["alt"] if title_tag else "N/A"

            image = title_tag["src"] if title_tag else ""
            link_tag = div.select_one("a")
            imdb_id = str(link_tag["href"]).split("/")[2] if link_tag else "N/A"

            rating_tag = div.select_one("span.ipc-rating-star")
            rating = rating_tag.text.strip() if rating_tag else "N/A"
            
            # Extract year if available
            year = "N/A"
            year_elem = div.select_one("span.sc-c70ad09b-8")
            if year_elem:
                year = year_elem.text.strip()
            
            # Determine if it's a movie or TV show by fetching the detailed page
            content_type = "movie"  # default
            actors = []
            
            if imdb_id:
                try:
                    # Fetch detailed page for content type and actors
                    detail_url = f"https://www.imdb.com/title/{imdb_id}/"
                    detail_soup = fetch_html(detail_url)
                    
                    # Check for TV series indicator
                    type_elem = detail_soup.select_one("a.ipc-metadata-list-item__label")
                    if type_elem and "TV Series" in type_elem.text:
                        content_type = "tv"
                    
                    # Extract actors
                    actor_elements = detail_soup.select("a[data-testid='cast-item']")
                    for actor_elem in actor_elements[:5]:  # Limit to first 5 actors
                        actor_name = actor_elem.text.strip()
                        if actor_name:
                            actors.append(actor_name)
                except Exception:
                    # If we can't fetch details, continue with defaults
                    pass

            movies.append({
                "title": title,
                "year": year,
                "rating": rating,
                "imdb_id": imdb_id,
                "image": image,
                "type": content_type,
                "actors": actors
            })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


@app.get("/scrape/imdb_popular")
def scrape_imdb_popular():
    """Scrape IMDb Popular movies"""
    try:
        url = "https://www.imdb.com/chart/moviemeter/"
        soup = fetch_html(url)

        movies = []
        for row in soup.select("li.ipc-metadata-list-summary-item")[:10]:
            title_tag = row.select_one("h3")
            title = title_tag.text.strip() if title_tag else "N/A"

            link_tag = row.select_one("a.ipc-title-link-wrapper")
            imdb_id = str(link_tag["href"]).split("/")[2] if link_tag else "N/A"

            image_tag = row.select_one("img.ipc-image")
            image = image_tag["src"] if image_tag else ""

            rating_tag = row.select_one("span.ipc-rating-star")
            rating = rating_tag.text.strip() if rating_tag else "N/A"
            
            # Extract year if available
            year = "N/A"
            year_elem = row.select_one("span.sc-c70ad09b-8")
            if year_elem:
                year = year_elem.text.strip()
            
            # Determine if it's a movie or TV show by fetching the detailed page
            content_type = "movie"  # default
            actors = []
            
            if imdb_id:
                try:
                    # Fetch detailed page for content type and actors
                    detail_url = f"https://www.imdb.com/title/{imdb_id}/"
                    detail_soup = fetch_html(detail_url)
                    
                    # Check for TV series indicator
                    type_elem = detail_soup.select_one("a.ipc-metadata-list-item__label")
                    if type_elem and "TV Series" in type_elem.text:
                        content_type = "tv"
                    
                    # Extract actors
                    actor_elements = detail_soup.select("a[data-testid='cast-item']")
                    for actor_elem in actor_elements[:5]:  # Limit to first 5 actors
                        actor_name = actor_elem.text.strip()
                        if actor_name:
                            actors.append(actor_name)
                except Exception:
                    # If we can't fetch details, continue with defaults
                    pass

            movies.append({
                "title": title,
                "year": year,
                "rating": rating,
                "imdb_id": imdb_id,
                "image": image,
                "type": content_type,
                "actors": actors
            })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


@app.get("/scrape/latest")
def scrape_latest_movies():
    """Scrape IMDb Latest Releases"""
    try:
        url = "https://www.imdb.com/movies-in-theaters/"
        soup = fetch_html(url)

        movies = []
        for movie_div in soup.select("div.list_item")[:10]:
            title_tag = movie_div.select_one("h4 a")
            title = title_tag.text.strip() if title_tag else "N/A"

            imdb_id = ""
            if title_tag and "href" in title_tag.attrs:
                imdb_id = str(title_tag["href"]).split("/")[2]

            image_tag = movie_div.select_one("img.poster")
            image = image_tag["src"] if image_tag else ""

            summary_tag = movie_div.select_one("div.outline")
            summary = summary_tag.text.strip() if summary_tag else "N/A"
            
            # Extract year if available
            year = "N/A"
            year_elem = movie_div.select_one("span.year")
            if year_elem:
                year = year_elem.text.strip()
            
            # Determine if it's a movie or TV show by fetching the detailed page
            content_type = "movie"  # default
            actors = []
            
            if imdb_id:
                try:
                    # Fetch detailed page for content type and actors
                    detail_url = f"https://www.imdb.com/title/{imdb_id}/"
                    detail_soup = fetch_html(detail_url)
                    
                    # Check for TV series indicator
                    type_elem = detail_soup.select_one("a.ipc-metadata-list-item__label")
                    if type_elem and "TV Series" in type_elem.text:
                        content_type = "tv"
                    
                    # Extract actors
                    actor_elements = detail_soup.select("a[data-testid='cast-item']")
                    for actor_elem in actor_elements[:5]:  # Limit to first 5 actors
                        actor_name = actor_elem.text.strip()
                        if actor_name:
                            actors.append(actor_name)
                except Exception:
                    # If we can't fetch details, continue with defaults
                    pass

            movies.append({
                "title": title,
                "year": year,
                "imdb_id": imdb_id,
                "image": image,
                "summary": summary,
                "type": content_type,
                "actors": actors
            })

        return {"count": len(movies), "items": movies}
    except Exception as e:
        return {"error": str(e)}


# Run the API (for Railway/Render)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
