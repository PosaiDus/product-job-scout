import os
import json
import urllib.parse
import feedparser
import requests
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv

load_dotenv()

# --- 1. YOUR NICHE PROFILE ---
MY_PROFILE = """
Primary Niche: 3D Product Modeling & Product Animation.

Core Skills & Industry Synonyms (match any of these terms):
- 3D Product Animation, Product Visualization (Product Viz / ProdViz), CGI Product Ads, Commercial 3D Rendering
- 3D Packshots, Animated Packshots, Packaging Mockups, 3D Product Mockups, Industrial Visualization
- Hard-Surface Product Modeling, Photorealistic Product Rendering, Studio Lighting, Look Development (Lookdev), Texturing & Shading
- E-commerce 3D Renders (Amazon/Shopify product videos), Cosmetic/Bottle/Tech Gadget Visualization, Exploded View Animation, Turntable Animation

Software:
- Blender (preferred, but optional — open to roles that don't specify a DCC tool or focus on final rendered output)

Target Roles:
- Remote freelance gigs, contract projects, per-project CGI commercials, or full-time/part-time remote 3D Product Artist / Product Animator roles.

Strict Dealbreakers (Automatically reject and score 1/10 if ANY apply):
- Any mention of "on-site", "onsite", "in-office", "hybrid", or relocation requirements (work MUST be 100% remote / online only).
- Unpaid internships, spec work, or revenue-share-only gigs.
- Roles focused purely on character animation, game environments, or architectural visualization (ArchViz) with no product focus.
"""

# --- 2. DIRECT RSS FEEDS (REDDIT + REMOTE BOARDS) ---
DIRECT_RSS_FEEDS = [
    # Reddit Hiring Communities
    "https://www.reddit.com/r/forhire/search.rss?q=%5Bhiring%5D+(3d+OR+product+OR+animation+OR+blender+OR+render)&restrict_sr=1&sort=new",
    "https://www.reddit.com/r/Freelance_forhire/search.rss?q=%5Bhiring%5D+(3d+OR+animation+OR+render+OR+product)&restrict_sr=1&sort=new",
    "https://www.reddit.com/r/3Dmodeling/search.rss?q=(hiring+OR+looking+for+OR+paid+OR+commission)&restrict_sr=1&sort=new",
    "https://www.reddit.com/r/blender/search.rss?q=(hiring+OR+paid+OR+commission+OR+product+animation)&restrict_sr=1&sort=new",
    "https://www.reddit.com/r/DesignJobs/search.rss?q=%5Bhiring%5D+(3d+OR+product+OR+animation+OR+mockup)&restrict_sr=1&sort=new",
    "https://www.reddit.com/r/HungryArtists/search.rss?q=%5Bhiring%5D+(3d+OR+product+OR+animation+OR+render)&restrict_sr=1&sort=new",
    "https://www.reddit.com/r/MotionDesign/search.rss?q=(hiring+OR+freelance+OR+product+OR+3d)&restrict_sr=1&sort=new",

    # Remote Job Boards
    "https://remoteok.com/remote-jobs.rss?tags=3d,animation",
    "https://www.workingnomads.com/jobs?category=design&format=rss",
    "https://remotive.com/remote-jobs/design/feed",
]

# --- 3. AUTOMATED SITE-WIDE SEARCHES (COVERS ALL MAJOR 3D, FREELANCE & STUDIO BOARDS) ---
SEARCH_QUERIES = [
    # Dedicated 3D & Creative Boards (ArtStation, Behance, Motionographer, 80 Level, CGTrader, Dribbble)
    '(site:artstation.com/jobs OR site:behance.net/joblist OR site:motionographer.com/jobs OR site:80.lv/talent OR site:cgtrader.com OR site:dribbble.com/jobs) ("3d" OR "product animation" OR "product visualization" OR "lookdev") "remote"',

    # Freelance Marketplaces (Upwork, Contra, PeoplePerHour, Freelancer)
    '(site:upwork.com/freelance-jobs OR site:contra.com OR site:peopleperhour.com OR site:freelancer.com) ("3d product" OR "product animation" OR "3d packshot" OR "cgi ad" OR "product render")',

    # Major Job Boards (LinkedIn, Wellfound, Indeed, JustRemote)
    '(site:linkedin.com/jobs OR site:wellfound.com OR site:indeed.com OR site:justremote.co) ("3d product" OR "product visualization" OR "product animation" OR "3d generalist") "remote"',

    # Studio & Brand Career Pages (Greenhouse, Lever, Ashby, Workable)
    '(site:boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com OR site:apply.workable.com) ("3d artist" OR "product visualization" OR "product animation" OR "3d generalist") "remote"',
]

def build_all_feeds() -> list[str]:
    feeds = list(DIRECT_RSS_FEEDS)
    for query in SEARCH_QUERIES:
        encoded = urllib.parse.quote(query)
        feeds.append(f"https://news.google.com/rss/search?q={encoded}+when:7d&hl=en-US&gl=US&ceid=US:en")
    return feeds

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen_jobs.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProductJobScout/1.0"
client = genai.Client()

class JobEvaluation(BaseModel):
    is_good_fit: bool
    match_score: int
    why_it_fits: str

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_ids: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids)[-2000:], f, indent=2)

def evaluate_job(title: str, summary: str) -> JobEvaluation:
    prompt = f"""
    Compare this job posting against my profile.
    CRITICAL RULE: If the job requires on-site, in-office, or hybrid attendance, immediately set is_good_fit=False and match_score=1.
    
    MY PROFILE:
    {MY_PROFILE}
    
    JOB TITLE: {title}
    JOB DESCRIPTION: {summary[:3000]}
    """
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": JobEvaluation,
            "temperature": 0.2,
        },
    )
    return JobEvaluation.model_validate_json(response.text)

def post_to_discord(title: str, link: str, evaluation: JobEvaluation):
    payload = {
        "username": "3D Product Job Scout",
        "embeds": [
            {
                "title": f"🎯 [{evaluation.match_score}/10] {title}",
                "url": link,
                "description": evaluation.why_it_fits,
                "color": 3447003,
                "fields": [
                    {"name": "Apply Here", "value": f"[Open Job Listing]({link})", "inline": False}
                ],
            }
        ],
    }
    requests.post(WEBHOOK_URL, json=payload)

def run():
    if not WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL is missing!")

    seen = load_seen()
    new_matches = 0
    all_feeds = build_all_feeds()

    for feed_url in all_feeds:
        feed = feedparser.parse(feed_url, agent=USER_AGENT)
        for entry in feed.entries[:10]:  # Check 10 newest entries per source
            job_id = entry.get("id") or entry.get("link")
            if not job_id or job_id in seen:
                continue

            seen.add(job_id)
            title = entry.get("title", "Untitled Role")
            desc = entry.get("summary", "")

            try:
                evaluation = evaluate_job(title, desc)
                if evaluation.is_good_fit and evaluation.match_score >= 7:
                    post_to_discord(title, entry.get("link", ""), evaluation)
                    new_matches += 1
                    print(f"Posted: {title} ({evaluation.match_score}/10)")
            except Exception as e:
                print(f"Error evaluating '{title}': {e}")

    save_seen(seen)
    print(f"Run complete. Checked {len(all_feeds)} sources and posted {new_matches} new job(s).")

if __name__ == "__main__":
    run()
