from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import tldextract
from urllib.parse import urljoin, urlparse
import time

app = Flask(__name__)

HEADERS = {
    "User-Agent": "SEO-Analyzer/1.0 (+https://example.com)"
}

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "http://" + url
    return url

def fetch_url(url: str, timeout: int = 10):
    try:
        start = time.perf_counter()
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        elapsed = time.perf_counter() - start
        return resp, elapsed
    except Exception as e:
        return None, None

def check_link_status(url: str, timeout: int = 7):
    try:
        resp = requests.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp.status_code
    except Exception:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            return resp.status_code
        except Exception:
            return None

def is_internal_link(base_domain, link_url):
    try:
        parsed = urlparse(link_url)
        if not parsed.netloc:
            return True
        return tldextract.extract(parsed.netloc).registered_domain == base_domain
    except Exception:
        return False

def compute_score(checks: dict) -> int:
    total = 0
    weight_sum = 0
    checks_map = [
        (checks.get('has_title'), 10),
        (checks.get('title_len_ok'), 10),
        (checks.get('has_meta_description'), 10),
        (checks.get('meta_desc_len_ok'), 10),
        (checks.get('has_h1'), 10),
        (checks.get('has_canonical'), 8),
        (checks.get('uses_https'), 8),
        (checks.get('has_viewport'), 8),
        (checks.get('images_with_alt_ratio', 0), 8),
        (checks.get('robots_txt'), 8),
    ]
    for val, w in checks_map:
        weight_sum += w
        if isinstance(val, bool):
            total += (1 if val else 0) * w
        else:
            try:
                total += float(val) * w
            except Exception:
                pass
    if weight_sum == 0:
        return 0
    return int(round((total / weight_sum) * 100))

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    url = request.form.get('url', '').strip()
    url = normalize_url(url)
    if not url:
        return render_template('index.html', error='Please enter a valid URL')

    resp, elapsed = fetch_url(url)
    if resp is None:
        return render_template('index.html', error='Could not fetch the URL (timeout or network error)')

    status_code = resp.status_code
    final_url = resp.url

    soup = BeautifulSoup(resp.text, 'html.parser')

    title_tag = soup.title.string.strip() if soup.title and soup.title.string else None
    has_title = bool(title_tag)
    title_len_ok = has_title and (len(title_tag) <= 60)

    meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
    meta_desc = meta_desc_tag.get('content').strip() if meta_desc_tag and meta_desc_tag.get('content') else None
    has_meta_description = bool(meta_desc)
    meta_desc_len_ok = has_meta_description and (len(meta_desc) <= 160)

    h1_tags = soup.find_all('h1')
    has_h1 = len(h1_tags) >= 1

    canonical = soup.find('link', rel='canonical')
    has_canonical = bool(canonical and canonical.get('href'))

    parsed_base = urlparse(final_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    robots_resp, _ = fetch_url(urljoin(base_origin, '/robots.txt'))
    robots_txt = False
    if robots_resp and robots_resp.status_code == 200 and robots_resp.text.strip():
        robots_txt = True

    sitemap_resp, _ = fetch_url(urljoin(base_origin, '/sitemap.xml'))
    sitemap_exists = bool(sitemap_resp and sitemap_resp.status_code in (200, 301, 302))

    images = soup.find_all('img')
    images_total = len(images)
    images_with_alt = sum(1 for img in images if img.get('alt') and img.get('alt').strip())
    images_with_alt_ratio = (images_with_alt / images_total) if images_total else 1

    anchors = soup.find_all('a', href=True)
    total_links = len(anchors)
    parsed_host = tldextract.extract(parsed_base.netloc).registered_domain

    internal_links = []
    external_links = []
    for a in anchors:
        href = a.get('href')
        if href.startswith('mailto:') or href.startswith('tel:'):
            continue
        abs_url = urljoin(final_url, href)
        if is_internal_link(parsed_host, abs_url):
            internal_links.append(abs_url)
        else:
            external_links.append(abs_url)

    sample_links = (internal_links + external_links)[:8]
    broken = 0
    checked = 0
    for l in sample_links:
        code = check_link_status(l)
        if code is None or (code >= 400):
            broken += 1
        checked += 1
    broken_rate = (broken / checked) if checked else 0

    viewport = bool(soup.find('meta', attrs={'name': 'viewport'}) or soup.find('meta', attrs={'name': 'Viewport'}))
    json_ld = bool(soup.find('script', type='application/ld+json'))
    uses_https = parsed_base.scheme == 'https'

    checks = {
        'has_title': has_title,
        'title_len_ok': title_len_ok,
        'has_meta_description': has_meta_description,
        'meta_desc_len_ok': meta_desc_len_ok,
        'has_h1': has_h1,
        'has_canonical': has_canonical,
        'robots_txt': robots_txt,
        'sitemap_exists': sitemap_exists,
        'images_with_alt_ratio': images_with_alt_ratio,
        'uses_https': uses_https,
        'has_viewport': viewport,
        'json_ld': json_ld,
    }

    score = compute_score(checks)

    result = {
        'url': url,
        'final_url': final_url,
        'status_code': status_code,
        'fetch_time_s': round(elapsed or 0, 3),
        'title': title_tag,
        'title_length': len(title_tag) if title_tag else 0,
        'meta_description': meta_desc,
        'h1_count': len(h1_tags),
        'canonical': canonical.get('href') if canonical else None,
        'robots_txt': robots_txt,
        'sitemap_exists': sitemap_exists,
        'images_total': images_total,
        'images_with_alt': images_with_alt,
        'images_with_alt_ratio': round(images_with_alt_ratio, 2),
        'total_links': total_links,
        'internal_links_sample': internal_links[:8],
        'external_links_sample': external_links[:8],
        'broken_rate_sample': round(broken_rate, 2),
        'uses_https': uses_https,
        'has_viewport': viewport,
        'json_ld': json_ld,
        'score': score,
        'checks': checks,
    }
    return render_template('results.html', result=result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
