#!/usr/bin/env python3
"""Between Routes China — Instagram Auto Publisher"""
import os, sys, json, re, glob, datetime, time
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
        return json.loads(body) if body else {}

# 1. Find today's script
today = TEST_DATE or datetime.date.today().strftime("%Y-%m-%d")
print(f"Date: {today}")

scripts = glob.glob("01_INS Operations/scripts/**/*.md", recursive=True)
target = None
for fpath in sorted(scripts):
    with open(fpath, encoding="utf-8") as f:
        content = f.read()
    if f"date: {today}" in content:
        target = (fpath, content)
        break

if not target:
    print(f"No post for {today}. Done.")
    sys.exit(0)

fpath, content = target
print(f"Script: {fpath}")

# 2. Parse caption and image fields
parts = content.split("---")
body = "---".join(parts[2:]).strip()

# Check for direct image URL in IMAGE: field (Pexels CDN URLs)
image_match = re.search(r"^IMAGE:\s*(https://images\.[^\s]+)$", body, re.MULTILINE)
direct_image_url = image_match.group(1).strip() if image_match else None

search_match = re.search(r"^Search:\s*(.+)$", body, re.MULTILINE)
raw_terms = search_match.group(1).strip() if search_match else "china business"

china_keywords = ["china", "chinese", "shanghai", "beijing", "asian", "shenzhen"]
has_china = any(kw in raw_terms.lower() for kw in china_keywords)
search_terms = raw_terms if has_china else f"china {raw_terms}"

lines = [l for l in body.split("\n") if not l.startswith("IMAGE:") and not l.startswith("Search:") and l.strip() != "---"]
caption = "\n".join(lines).strip()
print(f"Terms: {search_terms}")
print(f"Caption: {caption[:80]}...")

# 3. Get image — priority: direct URL in .md > Pexels API > fallback
image_url = None

if direct_image_url:
    image_url = direct_image_url
    print(f"Using embedded image URL")
elif PEXELS_KEY:
    try:
        purl = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
            "query": search_terms, "per_page": 3, "orientation": "square"
        })
        data = http_get(purl, headers={"Authorization": PEXELS_KEY})
        photos = data.get("photos", [])
        if photos:
            image_url = photos[0]["src"]["large2x"]
            print(f"Pexels image found")
    except Exception as e:
        print(f"Pexels failed: {e}")

if not image_url:
    # Fallback: Shanghai night skyline
    image_url = "https://images.pexels.com/photos/19243747/pexels-photo-19243747.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
    print("Using fallback image (Shanghai)")

print(f"Image: {image_url[:70]}...")

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

# 5. Wait for container to be ready (poll up to 60s)
print("Waiting for media to process...")
for attempt in range(12):
    time.sleep(5)
    status_data = http_get(
        f"https://graph.instagram.com/v21.0/{creation_id}?fields=status_code&access_token={IG_TOKEN}"
    )
    status = status_data.get("status_code", "UNKNOWN")
    print(f"  Status [{attempt+1}]: {status}")
    if status == "FINISHED":
        break
    if status == "ERROR":
        print(f"Container error: {status_data}")
        sys.exit(1)
else:
    print("Timeout waiting for media to process")
    sys.exit(1)

# 6. Publish
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
