"""Harvest local-business emails at scale via Google Places API (New) + website scraping.

Uses the gcloud OAuth token (no API key) against the already-enabled Places API on
project lifecoach-dev-zvb6d. For each (category x area) query it collects businesses
with a website, then scrapes each site (home + contact/about) for an email address.
Writes results to /tmp/harvest.json as [[name, cat, area, email, rating, count], ...].
"""
import subprocess, json, re, time
import httpx
from concurrent.futures import ThreadPoolExecutor

PROJECT = 'lifecoach-dev-zvb6d'
AREAS = ['Islington', 'Angel Islington', 'Highbury London', 'Hackney London', 'Hackney Central',
         'Hackney Wick', 'Dalston', 'Shoreditch', 'Hoxton', 'Stoke Newington', 'Clapton London',
         'London Fields', 'Broadway Market London', 'Walthamstow', 'Leyton', 'Leytonstone']
CATS = ['restaurant', 'fine dining restaurant', 'gastropub', 'pub', 'cafe', 'coffee shop', 'bakery',
        'deli', 'wine bar', 'brewery taproom', 'cocktail bar', 'gift shop', 'boutique clothing',
        'homeware shop', 'bookshop', 'florist', 'hair salon', 'barber', 'beauty salon', 'nail salon',
        'spa', 'gym', 'yoga studio', 'pilates studio', 'toy shop', 'record shop', 'butcher',
        'cheese shop', 'chocolate shop', 'ice cream shop', 'jeweller', 'art gallery']

def token():
    return subprocess.run(['gcloud', 'auth', 'print-access-token'],
                          capture_output=True, text=True).stdout.strip()

def search(q, tok):
    r = httpx.post('https://places.googleapis.com/v1/places:searchText',
        headers={'Authorization': f'Bearer {tok}', 'X-Goog-User-Project': PROJECT,
                 'Content-Type': 'application/json',
                 'X-Goog-FieldMask': 'places.displayName,places.websiteUri,places.rating,places.userRatingCount'},
        json={'textQuery': q, 'maxResultCount': 20}, timeout=30)
    return r.json()

SKIP_DOM = ('instagram', 'facebook', 'deliveroo', 'ubereats', 'just-eat', 'justeat',
            'tripadvisor', 'google.', 'linktr.ee', 'opentable', 'thefork', 'yelp', 'booking.com')
biz = {}
tok = token(); n = 0
for a in AREAS:
    for c in CATS:
        n += 1
        if n % 60 == 0:
            tok = token()
        try:
            d = search(f'{c} in {a}', tok)
        except Exception:
            continue
        for p in d.get('places', []):
            w = p.get('websiteUri', '')
            if not w:
                continue
            dom = re.sub(r'^https?://(www\.)?', '', w).split('/')[0].lower()
            if any(s in dom for s in SKIP_DOM) or dom in biz:
                continue
            biz[dom] = {'name': p.get('displayName', {}).get('text', ''), 'web': w, 'area': a,
                        'cat': c, 'rating': p.get('rating'), 'cnt': p.get('userRatingCount')}
        time.sleep(0.05)
print('Unique businesses with websites:', len(biz), flush=True)

EMAILRE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
JUNK = ('sentry', 'wixpress', 'example.', 'godaddy', 'squarespace', 'shopify', 'wix.com',
        '@2x', 'core-js', 'sentry.io', 'fontawesome', 'cloudflare', '.png', '.jpg', '.jpeg',
        '.gif', '.webp', '.svg', 'yourdomain', 'domain.com', 'email@', 'name@', 'protonmail-bridge')

def scrape(item):
    dom, info = item
    base = info['web'].rstrip('/')
    urls = [info['web']] + [base + p for p in ['/contact', '/contact-us', '/about', '/about-us', '/pages/contact']]
    found = set()
    for u in urls:
        try:
            r = httpx.get(u, timeout=8, follow_redirects=True,
                          headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36'})
            if r.status_code != 200:
                continue
            for m in EMAILRE.findall(r.text):
                ml = m.lower()
                if any(j in ml for j in JUNK):
                    continue
                found.add(ml)
        except Exception:
            pass
        if found:
            break
    if not found:
        return (info, None)
    core = dom.split('.')[0]
    best = None
    for e in found:
        if core and core in e.split('@')[1]:
            best = e; break
    if not best:
        best = sorted(found, key=len)[0]
    return (info, best)

results = []
items = list(biz.items())
with ThreadPoolExecutor(max_workers=24) as ex:
    for info, email in ex.map(scrape, items):
        if email:
            results.append([info['name'], info['cat'], info['area'], email, info.get('rating'), info.get('cnt')])

# dedup by email
seen = set(); uniq = []
for row in results:
    e = row[3].lower()
    if e in seen:
        continue
    seen.add(e); uniq.append(row)
json.dump(uniq, open('/tmp/harvest.json', 'w'))
print('Emails harvested (unique):', len(uniq), flush=True)
