from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(__name__)

def basic_seo_analysis(html, url):
    soup = BeautifulSoup(html, "html.parser")
    results = {}

    # Title tag
    title = soup.title.string.strip() if soup.title else None
    results["title"] = title

    # Meta description
    description = None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()
    results["description"] = description

    # H1 tags
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    results["h1_tags"] = h1s

    # Canonical tag
    canonical = None
    link_canonical = soup.find("link", attrs={"rel": "canonical"})
    if link_canonical and link_canonical.get("href"):
        canonical = link_canonical["href"].strip()
    results["canonical"] = canonical

    # Images without alt
    images = soup.find_all("img")
    no_alt = [img.get("src") for img in images if not img.get("alt")]
    results["images_without_alt"] = no_alt

    return results

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    url = request.form.get("url")
    if not url.startswith("http"):
        url = "http://" + url

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return render_template("index.html", error="Failed to fetch the URL")
    except Exception as e:
        return render_template("index.html", error=f"Error fetching URL: {e}")

    # Perform basic SEO analysis
    analysis = basic_seo_analysis(resp.text, url)

    # Call PageSpeed Insights API
    pagespeed_data = None
    PAGESPEED_API_KEY = os.getenv("AIzaSyANSw4Su04NwsTRMehw1Nxh4aRNnQbz2bE")
    if PAGESPEED_API_KEY:
        try:
            api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            params = {
                "url": url,
                "key": PAGESPEED_API_KEY,
                "strategy": "desktop"  # can also be "mobile"
            }
            r = requests.get(api_url, params=params, timeout=30)
            if r.status_code == 200:
                pagespeed_data = r.json()
        except Exception as e:
            print("Error fetching PageSpeed:", e)

    return render_template("results.html", analysis=analysis, pagespeed=pagespeed_data)

if __name__ == "__main__":
    app.run(debug=True)
