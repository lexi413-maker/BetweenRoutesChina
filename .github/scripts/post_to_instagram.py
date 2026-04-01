#!/usr/bin/env python3
"""
Between Routes China — Instagram Auto Publisher
Reads today's script from 01_INS Operations/scripts/YYYY-MM/
Fetches image from Pexels, posts to Instagram via Graph API.
"""
import os, sys, json, re, glob, datetime
import urllib.request, urllib.parse, urllib.error, ssl

IG_TOKEN   = os.environ["INSTAGRAM_ACCESS_TOKEN"]
IG_USER_ID = os.environ["INSTAGRAM_USER_ID"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
TEST_DATE  = os.environ.get("TEST_DATE", "").strip()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read())

def post(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

# 1. Find today's script
today = TEST_DATE or datetime.date.today().strftime("%Y-%m-%d")
print(f"Looking for post date: {today}")

scripts = glob.glob("01_INS Operations/scripts/**/*.md", recursive=True)
target = None
for path in scripts:
    with open(path) as f:
        content = f.read()
    if f"date: {today}" in content:
        target = (path, content)
        break

if not target:
    print(f"No post scheduled for {today}. Exiting.")
    sys.exit(0)

path, content = target
print(f"Found: {path}")

# 2. Parse script
parts = content.split("---")
body = "---".join(parts[2:]).strip()

search_match = re.search(r"^Search:\s*(.+)$", body, re.MULTILINE)
search_terms = search_match.group(1).strip() if search_match else "china business professional"

lines = []
for line in body.split("\n"):
    if line.startswith("IMAGE:") or line.startswith("Search:"):
        continue
    lines.append(line)
caption = "\n".join(lines).strip()

print(f"Search terms: {search_terms}")
print(f"Caption preview: {caption[:80]}...")

# 3. Get image from Pexels
pexels_url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
    "query": search_terms,
    "per_page": 1,
    "orientation": "square"
})
pexels_data = get(pexels_url, headers={"Authorization": PEXELS_KEY})
photos = pexels_data.get("photos", [])
if not photos:
    print("No image found on Pexels. Exiting.")
    sys.exit(1)

image_url = photos[0]["src"]["large2x"]
print(f"Image URL: {image_url}")

# 4. Create Instagram media container
container = post(
    f"https://graph.instagram.com/v21.0/{IG_USER_ID}/media",
    {"image_url": image_url, "caption": caption, "access_token": IG_TOKEN}
)
creation_id = container.get("id")
if not creation_id:
    print(f"Error creating media container: {container}")
    sys.exit(1)
print(f"Media container created: {creation_id}")

# 5. Publish
result = post(
    f"https://graph.instagram.com/v21.0/{IG_USER_ID}/media_publish",
    {"creation_id": creation_id, "access_token": IG_TOKEN}
)
if "id" in result:
    post_id = result["id"]
    print(f"Posted successfully! Instagram post ID: {post_id}")
else:
    print(f"Publish error: {result}")
    sys.exit(1)
