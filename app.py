import requests
from flask import Flask, render_template, request
from bs4 import BeautifulSoup

app = Flask(__name__)

# 🔑 Insert your Google PageSpeed API key here
PAGESPEED_API_KEY = "AIzaSyANSw4Su04NwsTRMehw1Nxh4aRNnQbz2bE"

# --- On-page SEO Analysis Function ---
def analyze_onpage(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")

        title = soup.title.string.strip() if soup.title else None
        description = None
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            description = desc_tag["content"]

        h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
        canonical = None
        can_tag = soup.find("link", attrs={"rel": "canonical"})
        if can_tag and can_tag.get("href"):
            canonical = can_tag["href"]

        images_without_alt = []
        for img in soup.find_all("img"):
            if not img.get("alt"):
                if img.get("src"):
                    images_without_alt.append(img["src"])

        return {
            "title": title,
            "description": description,
            "h1_tags": h1_tags,
            "canonical": canonical,
            "images_without_alt": images_without_alt,
        }
    except Exception as e:
        print("On-page analysis error:", e)
        return {}

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    url = request.form.get("url")
    strategy = request.form.get("strategy", "mobile")  # default: mobile

    if not url:
        return render_template("index.html", error="Please enter a URL")

    # --- Basic SEO analysis ---
    analysis = analyze_onpage(url)

    # --- PageSpeed Insights ---
    pagespeed = None
    if PAGESPEED_API_KEY:
        try:
            resp = requests.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params={"url": url, "key": PAGESPEED_API_KEY, "strategy": strategy}
            )
            if resp.status_code == 200:
                pagespeed = resp.json()
            else:
                print("PageSpeed API error:", resp.text)
        except Exception as e:
            print("PageSpeed error:", e)

    return render_template(
        "results.html",
        analysis=analysis,
        pagespeed=pagespeed,
        strategy=strategy
    )

if __name__ == "__main__":
    app.run(debug=True)
