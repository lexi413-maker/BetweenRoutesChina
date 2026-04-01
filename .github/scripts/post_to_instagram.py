#!/usr/bin/env python3
"""
Between Routes China — Instagram Auto Publisher
"""
import os, sys, json, re, glob, datetime
import urllib.request, urllib.parse, urllib.error, ssl

IG_TOKEN   = os.environ["INSTAGRAM_ACCESS_TOKEN"]
IG_USER_ID = os.environ["INSTAGRAM_USER_ID"]
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
TEST_DATE  = os.environ.get("TEST_DATE", "").strip()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read())

def http_post(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}")
        return json.loads(body) if body else {}

# 1. Find today's script
today = TEST_DATE or datetime.date.today().strftime("%Y-%m-%d")
print(f"Date: {today}")

scripts = glob.glob("01_INS Operations/scripts/**/*.md", recursive=True)
target = None
for path in sorted(scripts):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if f"date: {today}" in content:
        target = (path, content)
        break

if not target:
    print(f"No post for {today}. Done.")
    sys.exit(0)

path, content = target
print(f"Script: {path}")

# 2. Parse caption and image search terms
parts = content.split("---")
body = "---".join(parts[2:]).strip()

search_match = re.search(r"^Search:\s*(.+)$", body, re.MULTILINE)
search_terms = search_match.group(1).strip() if search_match else "china business"

lines = [l for l in body.split("\n") if not l.startswith("IMAGE:") and not l.startswith("Search:")]
caption = "\n".join(lines).strip()
print(f"Terms: {search_terms}")
print(f"Caption: {caption[:60]}...")

# 3. Get image — try Pexels, fallback to Unsplash source
image_url = None

if PEXELS_KEY:
    try:
        purl = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
            "query": search_terms, "per_page": 1, "orientation": "square"
        })
        data = http_get(purl, headers={"Authorization": PEXELS_KEY})
        photos = data.get("photos", [])
        if photos:
            image_url = photos[0]["src"]["large2x"]
            print(f"Pexels image: {image_url[:60]}...")
        else:
            print("Pexels: no results")
    except Exception as e:
        print(f"Pexels failed: {e}")

if not image_url:
    # Fallback: use a reliable public image based on search category
    fallback_queries = urllib.parse.quote(search_terms.replace(" ", "-"))
    image_url = f"https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg"
    print(f"Using fallback image")

print(f"Image: {image_url[:80]}")

# 4. Create media container
print("Creating media container...")
container = http_post(
    f"https://graph.instagram.com/v21.0/{IG_USER_ID}/media",
    {"image_url": image_url, "caption": caption, "access_token": IG_TOKEN}
)
creation_id = container.get("id")
if not creation_id:
    print(f"Container error: {container}")
    sys.exit(1)
print(f"Container ID: {creation_id}")

# 5. Publish
print("Publishing...")
result = http_post(
    f"https://graph.instagram.com/v21.0/{IG_USER_ID}/media_publish",
    {"creation_id": creation_id, "access_token": IG_TOKEN}
)
if "id" in result:
    print(f"SUCCESS! Post ID: {result['id']}")
else:
    print(f"Publish error: {result}")
    sys.exit(1)
