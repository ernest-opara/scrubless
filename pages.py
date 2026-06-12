"""Static marketing pages — /blog, /blog/{slug}, /pricing, /about.

These live outside the SPA so each one has its own crawlable URL, title,
description, OG tags, and indexable content. They share the design system
via /scrubby/scrubless.css (extracted from index.html) so styling stays in
one place."""
import html
import re
from pathlib import Path

import markdown as md
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from config import ROOT

POSTS_DIR = ROOT / "posts"
CANONICAL = "https://www.getscrubless.com"


def _parse_post(path: Path):
    """Return {title, description, audience, date, body_html, slug} or None."""
    if not path.exists() or not path.is_file():
        return None
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
        body = m.group(2)
    else:
        body = text
    meta["body_html"] = md.markdown(
        body, extensions=["fenced_code", "tables", "smarty"]
    )
    meta["slug"] = path.stem
    return meta


def list_posts():
    if not POSTS_DIR.exists():
        return []
    posts = [_parse_post(p) for p in POSTS_DIR.glob("*.md")]
    posts = [p for p in posts if p]
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    return posts


_HEAD = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <meta name="description" content="{description}" />
    <meta name="theme-color" content="#f2efe8" media="(prefers-color-scheme: light)" />
    <meta name="theme-color" content="#14151a" media="(prefers-color-scheme: dark)" />
    <link rel="canonical" href="{canonical}" />
    <link rel="icon" type="image/svg+xml" href="/scrubby/scrubby-avatar.svg" />
    <link rel="apple-touch-icon" href="/scrubby/scrubby-avatar.svg" />
    <meta property="og:type" content="{og_type}" />
    <meta property="og:site_name" content="Scrubless" />
    <meta property="og:title" content="{og_title}" />
    <meta property="og:description" content="{description}" />
    <meta property="og:url" content="{canonical}" />
    <meta property="og:image" content="https://www.getscrubless.com/scrubby/og.png" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{og_title}" />
    <meta name="twitter:description" content="{description}" />
    <meta name="twitter:image" content="https://www.getscrubless.com/scrubby/og.png" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="/scrubby/scrubless.css" />
    <style>
      .prose {{ max-width: 680px; margin: 0 auto; }}
      .prose h1 {{ font-family: var(--font-display); font-weight: 400; font-size: clamp(36px, 6vw, 56px); line-height: 1.05; letter-spacing: -0.012em; margin: 0 0 18px; }}
      .prose h2 {{ font-family: var(--font-display); font-weight: 400; font-size: 30px; letter-spacing: -0.005em; line-height: 1.15; margin: 36px 0 12px; }}
      .prose h3 {{ font-size: 18px; font-weight: 600; margin: 28px 0 8px; }}
      .prose p, .prose ul, .prose ol {{ font-size: 17px; line-height: 1.65; color: var(--fg); margin: 0 0 18px; }}
      .prose li {{ margin-bottom: 6px; }}
      .prose blockquote {{ border-left: 3px solid var(--accent); padding: 4px 18px; margin: 24px 0; color: var(--fg-muted); font-style: italic; }}
      .prose code {{ font-family: var(--font-mono); font-size: 14px; background: var(--bg-soft); padding: 1px 6px; border-radius: 4px; }}
      .prose a {{ color: var(--accent); text-decoration: underline; text-underline-offset: 3px; }}
      .post-meta {{ font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.10em; text-transform: uppercase; color: var(--accent); margin: 0 0 10px; }}
      .post-meta .sep {{ color: var(--fg-faint); margin: 0 8px; }}
      .post-cta {{ margin: 56px 0 0; padding: 28px; background: var(--bg-card); border: 1px solid var(--line); border-radius: var(--radius); text-align: center; }}
      .post-cta h3 {{ font-family: var(--font-display); font-weight: 400; font-size: 28px; margin: 0 0 6px; letter-spacing: -0.005em; }}
      .post-cta p {{ color: var(--fg-muted); margin: 0 0 18px; font-size: 15px; }}
      .blog-list {{ list-style: none; padding: 0; margin: 0; }}
      .blog-list li {{ padding: 22px 0; border-top: 1px solid var(--line-soft); }}
      .blog-list li:first-child {{ border-top: 0; padding-top: 0; }}
      .blog-list h2 {{ font-family: var(--font-display); font-weight: 400; font-size: 30px; letter-spacing: -0.005em; line-height: 1.1; margin: 4px 0 6px; }}
      .blog-list h2 a {{ color: var(--fg); text-decoration: none; }}
      .blog-list h2 a:hover {{ color: var(--accent); }}
      .blog-list p {{ color: var(--fg-muted); margin: 0; font-size: 15.5px; line-height: 1.5; }}
      .pricing-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 36px; }}
      @media (max-width: 760px) {{ .pricing-grid {{ grid-template-columns: 1fr; }} }}
      .plan {{ padding: 28px; background: var(--bg-card); border: 1px solid var(--line); border-radius: var(--radius); display: flex; flex-direction: column; }}
      .plan.featured {{ background: var(--accent-soft); }}
      .plan h3 {{ font-family: var(--font-display); font-weight: 400; font-size: 26px; margin: 0; letter-spacing: -0.005em; }}
      .plan .price {{ font-family: var(--font-display); font-size: 40px; line-height: 1; margin: 14px 0 4px; }}
      .plan .price small {{ font-size: 14px; color: var(--fg-muted); font-family: var(--font-body); }}
      .plan ul {{ list-style: none; padding: 0; margin: 18px 0 24px; flex: 1; font-size: 14.5px; }}
      .plan li {{ padding: 6px 0; border-top: 1px solid var(--line-soft); color: var(--fg-muted); }}
      .plan li:first-child {{ border-top: 0; }}
      footer.site {{ margin-top: 80px; padding-top: 24px; border-top: 1px solid var(--line-soft); display: flex; justify-content: space-between; gap: 12px; font-size: 13px; color: var(--fg-muted); flex-wrap: wrap; }}
      footer.site a {{ color: var(--fg-muted); text-decoration: none; margin-right: 14px; }}
      footer.site a:hover {{ color: var(--accent); }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <header class="site">
        <a class="brand" href="/" aria-label="Scrubless — home">
          <img class="logo" src="/scrubby/scrubby-avatar.svg" alt="" />
          <span class="brand-wordmark">Scrubless</span>
        </a>
        <nav class="nav">
          <a href="/blog">Blog</a>
          <a href="/pricing">Pricing</a>
          <a href="/about">About</a>
          <a href="/api/auth/login">Log in</a>
          <button class="btn" onclick="location.href='/'">Get started</button>
        </nav>
      </header>
      <main>
"""

_FOOT = """      </main>
      <footer class="site">
        <div>
          <a href="/">Home</a>
          <a href="/blog">Blog</a>
          <a href="/pricing">Pricing</a>
          <a href="/about">About</a>
        </div>
        <div>© Scrubless · <a href="mailto:e@getscrubless.com">e@getscrubless.com</a></div>
      </footer>
    </div>
  </body>
</html>
"""


def _page(*, title, description, body, canonical, og_type="website", og_title=None):
    head = _HEAD.format(
        title=title,
        description=html.escape(description, quote=True),
        canonical=canonical,
        og_type=og_type,
        og_title=html.escape(og_title or title, quote=True),
    )
    return head + body + _FOOT


router = APIRouter()


@router.get("/blog", response_class=HTMLResponse)
def blog_index():
    posts = list_posts()
    if posts:
        items = "\n".join(
            '<li>'
            '<p class="post-meta">For ' + html.escape(p.get("audience", "everyone")) +
            ' <span class="sep">·</span> ' + html.escape(p.get("date", "")) + '</p>'
            '<h2><a href="/blog/' + p["slug"] + '">' + html.escape(p.get("title", p["slug"])) + '</a></h2>'
            '<p>' + html.escape(p.get("description", "")) + '</p>'
            '</li>'
            for p in posts
        )
        body = (
            '<div class="prose">'
            '<p class="post-meta">The Scrubless blog</p>'
            '<h1>Who uses Scrubless</h1>'
            '<p>Real workflows from people who got tired of scrubbing — short stories on how creators, podcasters, teams, and ordinary people use semantic video search to find the moment that matters.</p>'
            '<ul class="blog-list">' + items + '</ul>'
            '</div>'
        )
    else:
        body = '<div class="prose"><h1>Coming soon</h1><p>No posts published yet.</p></div>'
    return HTMLResponse(_page(
        title="Blog · Scrubless",
        description="Stories on how creators, podcasters, teams, and individuals use Scrubless to search inside their videos — by what was said and what was shown.",
        body=body,
        canonical=CANONICAL + "/blog",
    ))


@router.get("/blog/{slug}", response_class=HTMLResponse)
def blog_post(slug: str):
    if not re.match(r"^[a-z0-9-]+$", slug):
        raise HTTPException(status_code=404)
    post = _parse_post(POSTS_DIR / (slug + ".md"))
    if not post:
        raise HTTPException(status_code=404)
    body = (
        '<article class="prose">'
        '<p class="post-meta">For ' + html.escape(post.get("audience", "everyone")) +
        ' <span class="sep">·</span> ' + html.escape(post.get("date", "")) + '</p>'
        '<h1>' + html.escape(post.get("title", slug)) + '</h1>'
        + post["body_html"] +
        '<div class="post-cta">'
        '<h3>Try it on your own video.</h3>'
        '<p>Search inside any video in plain English. Free to try, no account needed.</p>'
        '<a class="btn" href="/" style="text-decoration:none">Open Scrubless</a>'
        '</div>'
        '</article>'
    )
    return HTMLResponse(_page(
        title=post.get("title", slug) + " · Scrubless",
        description=post.get("description", ""),
        body=body,
        canonical=CANONICAL + "/blog/" + slug,
        og_type="article",
        og_title=post.get("title", slug),
    ))


@router.get("/pricing", response_class=HTMLResponse)
def pricing_page():
    from config import ANNUAL_ENABLED

    # Per-tier numbers come straight from config so this page can never drift
    # from what the API actually enforces.
    plans = [
        {
            "id": "free", "name": "Free", "audience": "No account needed.",
            "price_monthly": 0, "price_yearly": 0,
            "features": [
                "500MB per video",
                "2 hr indexed / month",
                "10 Q&amp;A questions / month",
                "Search, chapters, highlight reels",
                "Auto-deletes after 24h",
            ],
            "cta": ("/", "Try it now", "btn-ghost"),
        },
        {
            "id": "pro", "name": "Pro", "audience": "For creators &amp; individuals.",
            "price_monthly": 15, "price_yearly": 12,
            "features": [
                "2GB per video",
                "20 hr indexed / month",
                "200 Q&amp;A / month",
                "Videos persist forever",
                "Folder search + highlight reels",
            ],
            "featured": True,
            "cta": ("/api/auth/login", "Get Pro", "btn"),
        },
        {
            "id": "studio", "name": "Studio", "audience": "For podcasters &amp; large archives.",
            "price_monthly": 39, "price_yearly": 32,
            "features": [
                "10GB per video",
                "100 hr indexed / month",
                "1,000 Q&amp;A / month",
                "Everything in Pro",
                "Priority indexing + direct support",
            ],
            "cta": ("/api/auth/login", "Get Studio", "btn-ghost"),
        },
        {
            "id": "team", "name": "Team", "audience": "For 3+ seat teams.",
            "price_monthly": 99, "price_yearly": 79,
            "per_seat": True,
            "features": [
                "25GB per video",
                "Unlimited indexing &amp; Q&amp;A",
                "Shared team library",
                "Single sign-on (SSO)",
                "Audit log + dedicated support",
            ],
            "cta": ("mailto:e@getscrubless.com?subject=Scrubless%20Team%20plan", "Talk to us", "btn-ghost"),
        },
    ]

    cards = []
    for p in plans:
        featured = " featured" if p.get("featured") else ""
        suffix = "/seat/mo" if p.get("per_seat") else "/mo"
        # Two price spans (monthly + yearly) — the JS toggle swaps which one's
        # visible. Falls back to the monthly one if yearly billing isn't wired.
        price_block = (
            '<div class="price" data-price="monthly"><span class="amt">$' + str(p["price_monthly"]) + '</span><small>' + suffix + '</small></div>'
            '<div class="price hidden" data-price="yearly"><span class="amt">$' + str(p["price_yearly"]) + '</span><small>' + suffix + '</small><small class="muted" style="display:block;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;margin-top:4px">billed annually</small></div>'
        )
        cta_href, cta_text, cta_class = p["cta"]
        items = "".join('<li>' + f + '</li>' for f in p["features"])
        cards.append(
            '<div class="plan' + featured + '">'
            '<h3>' + p["name"] + '</h3>'
            + price_block +
            '<p class="muted">' + p["audience"] + '</p>'
            '<ul>' + items + '</ul>'
            '<a class="' + cta_class + '" href="' + cta_href + '" style="text-decoration:none;text-align:center">' + cta_text + '</a>'
            '</div>'
        )

    annual_toggle = ""
    if ANNUAL_ENABLED:
        annual_toggle = (
            '<div class="tabs" id="pricingCycle" style="margin:24px auto 8px;display:inline-flex">'
            '  <button class="tab active" data-cycle="monthly">Monthly</button>'
            '  <button class="tab" data-cycle="yearly">Yearly <span class="tag" style="margin-left:6px;color:var(--accent)">−20%</span></button>'
            '</div>'
        )

    body = (
        '<div class="prose" style="text-align:center">'
        '<p class="post-meta">Pricing</p>'
        '<h1>Search any video, on any plan.</h1>'
        '<p>Every plan includes semantic search, library mode, Q&amp;A with citations, auto-chapters, and highlight reels. What changes is how much you upload and ask each month.</p>'
        + annual_toggle +
        '</div>'
        '<div class="pricing-grid" style="grid-template-columns:repeat(4, 1fr)">' + "".join(cards) + '</div>'
        '<div class="prose" style="margin-top:48px">'
        '<h2>Frequently asked</h2>'
        '<h3>Do I need an account to try it?</h3>'
        '<p>No. Anyone can drop a video at <a href="/">getscrubless.com</a> and search it immediately. Anonymous uploads auto-delete after 24 hours. Q&amp;A requires a free account.</p>'
        '<h3>What counts toward the hours-indexed cap?</h3>'
        '<p>It’s the total duration of videos you’ve had Scrubless index this calendar month. The counter resets on the 1st. Reuploads of the same file count again.</p>'
        '<h3>Can I cancel anytime?</h3>'
        '<p>Yes. Plans are billed through Stripe; the Customer Portal handles upgrades, downgrades, and cancellations in one click.</p>'
        '<h3>What if I go over my monthly cap?</h3>'
        '<p>New uploads or Q&amp;A requests will pause until the start of next month or until you upgrade. Existing videos stay searchable.</p>'
        '<h3>Do you offer enterprise / on-prem?</h3>'
        '<p>Yes — that’s the Team plan, plus optional self-hosted deploys for larger orgs. <a href="mailto:e@getscrubless.com">Email us</a>.</p>'
        '</div>'
        # Toggle script for monthly/yearly. No-op if the toggle isn't rendered.
        '<script>'
        '(function(){var t=document.getElementById("pricingCycle");if(!t)return;'
        'function set(c){t.querySelectorAll(".tab").forEach(function(b){b.classList.toggle("active",b.dataset.cycle===c)});'
        'document.querySelectorAll("[data-price]").forEach(function(el){el.classList.toggle("hidden",el.dataset.price!==c)});}'
        't.querySelectorAll(".tab").forEach(function(b){b.addEventListener("click",function(){set(b.dataset.cycle)})});'
        '})();'
        '</script>'
    )
    return HTMLResponse(_page(
        title="Pricing · Scrubless — Semantic video search",
        description="Free to try, no account required. Pro $15/mo for creators. Studio $39/mo for podcasters. Team $99/seat for organizations. Every plan includes semantic search, Q&A with citations, auto-chapters, and highlight reels.",
        body=body,
        canonical=CANONICAL + "/pricing",
    ))


@router.get("/about", response_class=HTMLResponse)
def about_page():
    body = (
        '<div class="prose">'
        '<p class="post-meta">About</p>'
        '<h1>The story behind Scrubless.</h1>'
        '<p>Scrubless exists because finding a single moment inside a long video is still painful in 2026 — and that’s absurd.</p>'
        '<p>Every other medium got searchable years ago. Documents have <code>Ctrl+F</code>. Email has full-text search. Music streaming has lyrics search. But the medium people <em>actually</em> spend their time on — video — is still stuck at "drag the timeline back and forth until you guess right." That’s the gap Scrubless fills.</p>'
        '<h2>What it does</h2>'
        '<p>You upload a video (or point Scrubless at a whole folder of videos), and then you can search it like you’d search a document — in plain English. Type <em>"the part where someone says we should ship it"</em> and Scrubless takes you to that exact second. Type <em>"the rabbit"</em> and it finds every shot of the rabbit. It searches what was <strong>said</strong> and what was <strong>shown</strong>, not just the captions.</p>'
        '<p>It also writes auto-chapters and summaries for every video, answers questions about your videos with cited timestamps, and lets you stitch search-result moments into a highlight reel.</p>'
        '<h2>Who it’s for</h2>'
        '<p>Creators, editors, podcasters, teachers, researchers, support teams, security analysts — anyone who has more video than they can remember. Read <a href="/blog">the blog</a> for specific workflows.</p>'
        '<h2>Who built it</h2>'
        '<p>Scrubless is built by <a href="https://linkedin.com/in/ernest-opara" target="_blank">Chukwuebuka Ernest-Opara</a>, an ML &amp; platform engineer who spent years working with embedding infrastructure and video before turning the two into a product.</p>'
        '<p>Reach out: <a href="mailto:e@getscrubless.com">e@getscrubless.com</a>.</p>'
        '<div class="post-cta">'
        '<h3>Try it on your own video.</h3>'
        '<p>No account needed. Free.</p>'
        '<a class="btn" href="/" style="text-decoration:none">Open Scrubless</a>'
        '</div>'
        '</div>'
    )
    return HTMLResponse(_page(
        title="About · Scrubless — Semantic video search",
        description="Scrubless makes any video searchable by description — what was said and what was shown. Built by Chukwuebuka Ernest-Opara, an ML & platform engineer.",
        body=body,
        canonical=CANONICAL + "/about",
    ))
