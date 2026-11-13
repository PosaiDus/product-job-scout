import os
import json
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

# --- 2. JOB SOURCES ---
RSS_FEEDS = [
    "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "https://remoteok.com/remote-3d-jobs.rss",
    # PASTE YOUR TWO GOOGLE ALERTS RSS LINKS BELOW:
    # "https://www.google.com/alerts/feeds/...",
    # "https://www.google.com/alerts/feeds/...",
]

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen_jobs.json"
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
        json.dump(list(seen_ids)[-1000:], f, indent=2)  # Keep last 1,000 IDs

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

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:15]:
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
    print(f"Run complete. Posted {new_matches} new job(s).")

if __name__ == "__main__":
    run()
