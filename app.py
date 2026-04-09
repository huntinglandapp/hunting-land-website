#!/usr/bin/env python3
"""
Hunting Land Apps — Website & Webhook Server
Deploy to Render.com (free tier)

Environment variables to set in Render dashboard:
  FIREBASE_SERVICE_ACCOUNT  — contents of your Firebase service account JSON (one line)
  GUMROAD_SELLER_ID         — your Gumroad seller ID (found in Gumroad Settings)
  GUMROAD_LINK_50           — Gumroad checkout URL for 50-token pack
  GUMROAD_LINK_200          — Gumroad checkout URL for 200-token pack
  GUMROAD_LINK_500          — Gumroad checkout URL for 500-token pack
"""

import os
import json
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ── Gumroad product config ───────────────────────────────────────────────────
# These permalink slugs must match exactly what you set on Gumroad
TOKEN_PACKS = {
    'tokens-200':  200,
    'tokens-500':  500,
    'tokens-1000': 1000,
}

GUMROAD_SELLER_ID = os.environ.get('GUMROAD_SELLER_ID', '')

BUY_LINKS = {
    200:      os.environ.get('GUMROAD_LINK_200',    '#'),
    500:      os.environ.get('GUMROAD_LINK_500',    '#'),
    1000:     os.environ.get('GUMROAD_LINK_1000',   '#'),
    'custom': os.environ.get('GUMROAD_LINK_CUSTOM', '#'),  # "Pay what you want" Gumroad product
}

# Windows installer download link — set this to your Gumroad product link once uploaded
WINDOWS_DOWNLOAD_URL = os.environ.get('WINDOWS_DOWNLOAD_URL', '#')

# ── Firebase Admin (lazy init) ───────────────────────────────────────────────
_fb_app  = None
_fb_auth = None
_fb_db   = None

def firebase():
    global _fb_app, _fb_auth, _fb_db
    if _fb_db is not None:
        return _fb_auth, _fb_db
    try:
        import firebase_admin
        from firebase_admin import credentials, auth, firestore
        sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if not sa_json:
            return None, None
        sa_dict = json.loads(sa_json)
        cred = credentials.Certificate(sa_dict)
        _fb_app = firebase_admin.initialize_app(cred)
        _fb_auth = auth
        _fb_db   = firestore.client()
        return _fb_auth, _fb_db
    except Exception as e:
        print(f"Firebase init error: {e}")
        return None, None


# ── Shared CSS / layout ──────────────────────────────────────────────────────
BASE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} — Hunting Land Apps</title>
<style>
  :root {
    --bg:      #141a10;
    --surface: #1e2619;
    --card:    #252e1e;
    --border:  #3a4a30;
    --green:   #5a9e3f;
    --green2:  #4a8a32;
    --tan:     #c8a86b;
    --text:    #e8e4d8;
    --muted:   #8a9e78;
    --red:     #c0392b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; }

  /* Nav */
  nav { background: var(--surface); border-bottom: 1px solid var(--border); padding: 0 24px; display: flex; align-items: center; justify-content: space-between; height: 56px; position: sticky; top: 0; z-index: 100; }
  .nav-brand { font-size: 17px; font-weight: 700; color: var(--tan); text-decoration: none; display: flex; align-items: center; gap: 8px; }
  .nav-links { display: flex; gap: 6px; }
  .nav-links a { color: var(--muted); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 14px; transition: background .15s, color .15s; }
  .nav-links a:hover, .nav-links a.active { background: var(--card); color: var(--text); }

  /* Hero */
  .hero { background: linear-gradient(160deg, #1e2e14 0%, #0e1a0a 100%); padding: 72px 24px; text-align: center; border-bottom: 1px solid var(--border); }
  .hero h1 { font-size: clamp(28px, 5vw, 48px); font-weight: 800; color: var(--tan); margin-bottom: 16px; }
  .hero p  { font-size: 18px; color: var(--muted); max-width: 560px; margin: 0 auto 32px; }
  .hero-btns { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }

  /* Buttons */
  .btn { display: inline-block; padding: 12px 28px; border-radius: 8px; font-size: 15px; font-weight: 600; text-decoration: none; cursor: pointer; border: none; transition: opacity .15s; }
  .btn:hover { opacity: .85; }
  .btn-green  { background: var(--green);  color: #fff; }
  .btn-tan    { background: var(--tan);    color: #111; }
  .btn-ghost  { background: transparent; border: 2px solid var(--border); color: var(--text); }
  .btn-sm     { padding: 8px 18px; font-size: 13px; }

  /* Layout */
  .container { max-width: 960px; margin: 0 auto; padding: 48px 24px; }
  .section-title { font-size: 22px; font-weight: 700; color: var(--tan); margin-bottom: 24px; }

  /* App cards */
  .app-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin-bottom: 56px; }
  .app-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 28px; }
  .app-card h2 { font-size: 20px; color: var(--tan); margin-bottom: 8px; }
  .app-card .platform { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 14px; }
  .app-card p { color: var(--muted); font-size: 14px; margin-bottom: 20px; line-height: 1.65; }
  .app-card .btn { display: block; text-align: center; }

  /* Feature list */
  .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 48px; }
  .feature { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
  .feature .icon { font-size: 28px; margin-bottom: 10px; }
  .feature h3 { font-size: 15px; color: var(--text); margin-bottom: 6px; }
  .feature p  { font-size: 13px; color: var(--muted); }

  /* Token pricing */
  .price-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 40px; }
  .price-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 28px; text-align: center; position: relative; }
  .price-card.popular { border-color: var(--green); }
  .popular-badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: var(--green); color: #fff; font-size: 11px; font-weight: 700; padding: 3px 12px; border-radius: 20px; letter-spacing: .05em; }
  .price-card .tokens { font-size: 42px; font-weight: 800; color: var(--tan); line-height: 1; }
  .price-card .token-label { font-size: 14px; color: var(--muted); margin-bottom: 16px; }
  .price-card .price { font-size: 26px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
  .price-card .per { font-size: 12px; color: var(--muted); margin-bottom: 20px; }
  .price-card .btn { width: 100%; }

  /* Privacy / text pages */
  .prose { max-width: 760px; }
  .prose h2 { font-size: 18px; color: var(--tan); margin: 32px 0 10px; }
  .prose h3 { font-size: 15px; color: var(--text); margin: 20px 0 8px; }
  .prose p  { color: var(--muted); font-size: 14px; margin-bottom: 14px; line-height: 1.75; }
  .prose ul { color: var(--muted); font-size: 14px; padding-left: 20px; margin-bottom: 14px; }
  .prose ul li { margin-bottom: 6px; line-height: 1.65; }
  .prose .updated { font-size: 12px; color: var(--muted); margin-bottom: 28px; }

  /* FAQ */
  .faq-item { border-top: 1px solid var(--border); padding: 18px 0; }
  .faq-item h3 { font-size: 15px; color: var(--text); margin-bottom: 8px; }
  .faq-item p  { font-size: 14px; color: var(--muted); }

  /* Footer */
  footer { border-top: 1px solid var(--border); background: var(--surface); padding: 24px; text-align: center; font-size: 13px; color: var(--muted); }
  footer a { color: var(--muted); text-decoration: none; margin: 0 10px; }
  footer a:hover { color: var(--tan); }

  @media (max-width: 600px) {
    .nav-links a { padding: 6px 8px; font-size: 13px; }
    .hero { padding: 48px 16px; }
  }
</style>
</head>
<body>

<nav>
  <a class="nav-brand" href="/">&#x1F98C; Hunting Land Apps</a>
  <div class="nav-links">
    <a href="/" class="{{ 'active' if active == 'home' else '' }}">Home</a>
    <a href="/photo-sorter" class="{{ 'active' if active == 'sorter' else '' }}">Photo Sorter</a>
    <a href="/tokens" class="{{ 'active' if active == 'tokens' else '' }}">Buy Tokens</a>
    <a href="/privacy" class="{{ 'active' if active == 'privacy' else '' }}">Privacy</a>
  </div>
</nav>

{{ content | safe }}

<footer>
  <div>
    <a href="/">Home</a>
    <a href="/photo-sorter">Photo Sorter</a>
    <a href="/tokens">Buy Tokens</a>
    <a href="/privacy">Privacy Policy</a>
  </div>
  <div style="margin-top:8px;"><a href="/delete-account">Delete My Account</a></div>
  <div style="margin-top:10px;">&copy; 2025 Hunting Land Apps. All rights reserved.</div>
</footer>

</body>
</html>'''


# ── Home page ────────────────────────────────────────────────────────────────
HOME_CONTENT = '''
<div class="hero">
  <h1>&#x1F98C; Hunting Land Apps</h1>
  <p>Tools built for serious hunters — track your land, manage cameras, and sort thousands of trail photos in minutes.</p>
  <div class="hero-btns">
    <a class="btn btn-green" href="https://play.google.com/store" target="_blank">&#x1F4F1; Get the Android App</a>
    <a class="btn btn-tan" href="/photo-sorter">&#x1F4F7; Photo Sorter for PC &amp; Mac</a>
  </div>
</div>

<div class="container">
  <div class="section-title">Two Apps, One Mission</div>
  <div class="app-grid">
    <div class="app-card">
      <h2>&#x1F4F1; Hunting Land App</h2>
      <div class="platform">Android &bull; Free to download</div>
      <p>Map your stands, food plots, and cameras. Log harvests, track observations, and share your hunting area with your crew — all in one place.</p>
      <a class="btn btn-green" href="https://play.google.com/store" target="_blank">Download on Google Play</a>
    </div>
    <div class="app-card">
      <h2>&#x1F4F7; Trail Camera Photo Sorter</h2>
      <div class="platform">Windows &amp; Mac &bull; Powered by Claude AI</div>
      <p>Drop in a folder of trail camera photos. AI automatically sorts them into Buck, Doe, Turkey, Bear, and more — in minutes, not hours. Photos never leave your computer.</p>
      <a class="btn btn-tan" href="/photo-sorter">Learn More</a>
    </div>
  </div>

  <div class="section-title">Why Hunters Love These Apps</div>
  <div class="features">
    <div class="feature">
      <div class="icon">&#x1F5FA;</div>
      <h3>Map Everything</h3>
      <p>Drop pins for stands, cameras, scrapes, and food plots on your hunting property map.</p>
    </div>
    <div class="feature">
      <div class="icon">&#x1F6C2;</div>
      <h3>Log Harvests &amp; Sightings</h3>
      <p>Record every harvest and observation with photos, notes, and GPS location.</p>
    </div>
    <div class="feature">
      <div class="icon">&#x1F916;</div>
      <h3>AI Photo Sorting</h3>
      <p>Claude AI identifies deer, turkey, hogs, bear, and more — 1 token per photo.</p>
    </div>
    <div class="feature">
      <div class="icon">&#x1F4F1;</div>
      <h3>Share with Your Crew</h3>
      <p>Invite hunting partners to your area with a 6-digit code. Share maps and cameras.</p>
    </div>
    <div class="feature">
      <div class="icon">&#x1F512;</div>
      <h3>Your Photos Stay Private</h3>
      <p>The Photo Sorter runs entirely on your computer. Photos are never uploaded anywhere.</p>
    </div>
    <div class="feature">
      <div class="icon">&#x1F4F7;</div>
      <h3>Upload Sorted Photos</h3>
      <p>After sorting, upload deer photos directly to your trail camera in the Hunting Land app.</p>
    </div>
  </div>
</div>
'''


# ── Photo Sorter page ────────────────────────────────────────────────────────
SORTER_CONTENT = '''
<div class="hero" style="padding: 48px 24px;">
  <h1 style="font-size: clamp(24px, 4vw, 38px);">&#x1F4F7; Trail Camera Photo Sorter</h1>
  <p>Stop manually going through hundreds of trail camera photos. Let AI do it in minutes.</p>
  <div class="hero-btns">
    <a class="btn btn-tan" href="#download">Download for Windows / Mac</a>
    <a class="btn btn-ghost" href="/tokens">Buy Tokens</a>
  </div>
</div>

<div class="container">
  <div class="section-title">How It Works</div>
  <div class="features" style="margin-bottom: 56px;">
    <div class="feature">
      <div class="icon">1&#xFE0F;&#x20E3;</div>
      <h3>Log In</h3>
      <p>Sign in with your Hunting Land app account. A Standard plan or higher is required.</p>
    </div>
    <div class="feature">
      <div class="icon">2&#xFE0F;&#x20E3;</div>
      <h3>Select Your Folder</h3>
      <p>Point the app at the folder where your trail camera SD card photos are saved.</p>
    </div>
    <div class="feature">
      <div class="icon">3&#xFE0F;&#x20E3;</div>
      <h3>AI Scans Every Photo</h3>
      <p>Claude AI looks at each photo and identifies the animal (or flags empty/dark shots). Uses 1 token per photo.</p>
    </div>
    <div class="feature">
      <div class="icon">4&#xFE0F;&#x20E3;</div>
      <h3>Move &amp; Upload</h3>
      <p>Photos are moved into animal folders (Buck, Doe, Turkey&hellip;) and can be uploaded straight to your trail cameras in the Hunting Land app.</p>
    </div>
  </div>

  <div class="section-title">What Animals Does It Recognize?</div>
  <div style="display:flex; flex-wrap:wrap; gap:10px; margin-bottom:48px;">
    {% for animal in animals %}
    <span style="background:var(--card); border:1px solid var(--border); border-radius:6px; padding:6px 14px; font-size:14px; color:var(--text);">{{ animal }}</span>
    {% endfor %}
  </div>

  <div class="section-title" id="download">Download</div>
  <div class="app-grid" style="margin-bottom: 48px;">
    <div class="app-card">
      <h2>&#x1FA9F; Windows</h2>
      <div class="platform">Windows 10 / 11</div>
      <p>Download the installer, double-click to install, and you're ready to go. No Python or technical knowledge required.</p>
      <a class="btn btn-green" href="{{ windows_download }}" target="_blank">Download for Windows</a>
    </div>
    <div class="app-card" style="opacity:0.6;">
      <h2>&#x1F34E; Mac</h2>
      <div class="platform">macOS &mdash; Coming Soon</div>
      <p>The Mac version is currently in development. Check back soon or sign up below to be notified when it's available.</p>
      <span class="btn btn-ghost" style="cursor:default; text-align:center; display:block;">Coming Soon</span>
    </div>
  </div>

  <div class="section-title">Frequently Asked Questions</div>
  <div>
    <div class="faq-item">
      <h3>Do my photos get uploaded to the internet?</h3>
      <p>No. The Photo Sorter runs entirely on your computer. Only a compressed version of each photo is temporarily sent to Claude AI for identification — it is never stored. Your original photos never leave your machine.</p>
    </div>
    <div class="faq-item">
      <h3>What is a token?</h3>
      <p>One token lets the AI analyze one photo. Tokens are purchased in packs. <a href="/tokens" style="color:var(--green);">See pricing &rarr;</a></p>
    </div>
    <div class="faq-item">
      <h3>Do I need a Hunting Land app account?</h3>
      <p>Yes — you sign in with your Hunting Land app account. A Standard plan or higher is required to use the Photo Sorter.</p>
    </div>
    <div class="faq-item">
      <h3>How accurate is the AI?</h3>
      <p>Very accurate for common animals like deer, turkey, and hogs. For rare or unusual animals it may sort them into "Other Animal." You can always correct individual photos before moving them.</p>
    </div>
    <div class="faq-item">
      <h3>What image formats are supported?</h3>
      <p>JPEG (.jpg / .jpeg), PNG, HEIC, TIFF, BMP, and GIF.</p>
    </div>
  </div>
</div>
'''


# ── Tokens page ──────────────────────────────────────────────────────────────
TOKENS_CONTENT = '''
<div class="hero" style="padding: 48px 24px;">
  <h1 style="font-size: clamp(24px, 4vw, 38px);">&#x1FA99; Buy Photo Sorter Tokens</h1>
  <p>One token sorts one trail camera photo. Tokens never expire — use them anytime.</p>
</div>

<div class="container">
  <div class="section-title">Token Packs</div>
  <div class="price-grid">
    <div class="price-card">
      <div class="tokens">200</div>
      <div class="token-label">tokens</div>
      <div class="price">$8.00</div>
      <div class="per">$0.04 per photo</div>
      <a class="btn btn-ghost" href="{{ buy_200 }}" target="_blank">Buy Now</a>
    </div>
    <div class="price-card popular">
      <div class="popular-badge">MOST POPULAR</div>
      <div class="tokens">500</div>
      <div class="token-label">tokens</div>
      <div class="price">$13.00</div>
      <div class="per">$0.026 per photo</div>
      <a class="btn btn-green" href="{{ buy_500 }}" target="_blank">Buy Now</a>
    </div>
    <div class="price-card">
      <div class="popular-badge" style="background:var(--tan); color:#111;">BEST VALUE</div>
      <div class="tokens">1,000</div>
      <div class="token-label">tokens</div>
      <div class="price">$22.00</div>
      <div class="per">$0.022 per photo</div>
      <a class="btn btn-tan" href="{{ buy_1000 }}" target="_blank">Buy Now</a>
    </div>
  </div>

  <!-- Custom amount calculator -->
  <div style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:28px; margin-bottom:24px;">
    <div style="font-size:18px; font-weight:700; color:var(--tan); margin-bottom:6px;">&#x1F9EE; Custom Amount</div>
    <div style="font-size:13px; color:var(--muted); margin-bottom:20px;">Need more tokens? Choose any amount in increments of 1,000.</div>

    <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:20px;">
      <div style="display:flex; align-items:center; gap:0; border:1px solid var(--border); border-radius:8px; overflow:hidden;">
        <button onclick="changeCustom(-1)" style="background:var(--surface); border:none; color:var(--text); font-size:20px; width:44px; height:44px; cursor:pointer; transition:background .15s;"
                onmouseover="this.style.background='var(--border)'" onmouseout="this.style.background='var(--surface)'">&#x2212;</button>
        <div style="padding:0 20px; font-size:18px; font-weight:700; color:var(--text); background:var(--bg); height:44px; display:flex; align-items:center;" id="custom-packs">1</div>
        <button onclick="changeCustom(1)" style="background:var(--surface); border:none; color:var(--text); font-size:20px; width:44px; height:44px; cursor:pointer; transition:background .15s;"
                onmouseover="this.style.background='var(--border)'" onmouseout="this.style.background='var(--surface)'">&#x2B;</button>
      </div>
      <div>
        <div style="font-size:28px; font-weight:800; color:var(--text);" id="custom-tokens">1,000 tokens</div>
        <div style="font-size:13px; color:var(--muted);" id="custom-rate">$0.022 per photo</div>
      </div>
      <div style="margin-left:auto; text-align:right;">
        <div style="font-size:13px; color:var(--muted);">Total</div>
        <div style="font-size:32px; font-weight:800; color:var(--tan);" id="custom-price">$22.00</div>
      </div>
    </div>

    <div style="background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:14px 16px; margin-bottom:16px; font-size:13px; color:var(--muted);">
      &#x2139;&#xFE0F;&nbsp; When you click Buy, Gumroad will open. Enter <strong id="custom-price-note">$22.00</strong> as the payment amount. Your tokens will be credited automatically based on the amount paid.
    </div>

    <a id="custom-buy-btn" class="btn btn-green" href="{{ buy_custom }}" target="_blank" style="display:inline-block;">Buy <span id="custom-btn-tokens">1,000</span> Tokens for <span id="custom-btn-price">$22.00</span></a>
  </div>

  <script>
  var customPacks = 1;
  var PACK_SIZE  = 1000;
  var PACK_PRICE = 22.00;

  function changeCustom(delta) {
    customPacks = Math.max(1, customPacks + delta);
    var tokens = customPacks * PACK_SIZE;
    var price  = (customPacks * PACK_PRICE).toFixed(2);
    var rate   = (PACK_PRICE / PACK_SIZE).toFixed(4);
    document.getElementById('custom-packs').textContent  = customPacks;
    document.getElementById('custom-tokens').textContent = tokens.toLocaleString() + ' tokens';
    document.getElementById('custom-price').textContent  = '$' + price;
    document.getElementById('custom-rate').textContent   = '$' + rate + ' per photo';
    document.getElementById('custom-price-note').textContent = '$' + price;
    document.getElementById('custom-btn-tokens').textContent = tokens.toLocaleString();
    document.getElementById('custom-btn-price').textContent  = '$' + price;
  }
  </script>

  <div style="background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:20px 24px; margin-bottom: 48px; font-size:14px; color:var(--muted);">
    &#x2139;&#xFE0F;&nbsp; After purchase you will receive a confirmation email from Gumroad. Your tokens will be added to your account automatically within a few minutes. Make sure the email you use for Gumroad matches your Hunting Land app login email.
  </div>

  <div class="section-title">Frequently Asked Questions</div>
  <div>
    <div class="faq-item">
      <h3>Do tokens expire?</h3>
      <p>No. Tokens never expire. Buy a large pack and use them across multiple hunting seasons.</p>
    </div>
    <div class="faq-item">
      <h3>When are tokens deducted?</h3>
      <p>One token is used for each photo that the AI successfully analyzes. Photos that fail due to a network error are not charged.</p>
    </div>
    <div class="faq-item">
      <h3>How long does it take for tokens to appear after purchase?</h3>
      <p>Usually within 1–2 minutes. If they don't appear after 10 minutes, close and reopen the Photo Sorter app and log in again.</p>
    </div>
    <div class="faq-item">
      <h3>What email should I use on Gumroad?</h3>
      <p>Use the same email address you use to log in to the Hunting Land app. That's how we match your purchase to your account.</p>
    </div>
    <div class="faq-item">
      <h3>Can I get a refund?</h3>
      <p>If you have not used any tokens, contact us within 7 days of purchase for a full refund.</p>
    </div>
  </div>
</div>
'''


# ── Delete Account page ──────────────────────────────────────────────────────
DELETE_CONTENT = '''
<div class="container">
  <div class="prose">
    <h1 style="font-size:26px; color:var(--tan); margin-bottom:8px;">Delete Your Account</h1>
    <p>If you would like to delete your Hunting Land account and all associated data, please submit your request below. We will process your request within 30 days.</p>

    <div style="background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:20px; margin:24px 0;">
      <p style="margin-bottom:6px; font-size:13px; color:var(--muted);">&#x26A0;&#xFE0F; &nbsp;Deleting your account will permanently remove:</p>
      <ul>
        <li>Your login credentials</li>
        <li>All stand, camera, food plot, and sign locations</li>
        <li>All harvest logs and journal entries</li>
        <li>All trail camera photos you uploaded to the app</li>
        <li>Your remaining Photo Sorter token balance</li>
      </ul>
      <p style="margin-top:10px; font-size:13px; color:var(--muted);">This action cannot be undone.</p>
    </div>

    <div id="delete-form">
      <div style="margin-bottom:16px;">
        <label style="display:block; font-size:14px; color:var(--text); margin-bottom:6px;">Email address on your account</label>
        <input type="email" id="del-email" placeholder="you@email.com"
               style="width:100%; max-width:400px; padding:10px 12px; background:var(--surface); border:1px solid var(--border); border-radius:6px; color:var(--text); font-size:14px; font-family:inherit;">
      </div>
      <div style="margin-bottom:20px;">
        <label style="display:block; font-size:14px; color:var(--text); margin-bottom:6px;">Reason for leaving <span style="color:var(--muted);">(optional)</span></label>
        <textarea id="del-reason" rows="3" placeholder="Let us know why you&apos;re leaving..."
                  style="width:100%; max-width:400px; padding:10px 12px; background:var(--surface); border:1px solid var(--border); border-radius:6px; color:var(--text); font-size:14px; font-family:inherit; resize:vertical;"></textarea>
      </div>
      <button onclick="submitDeleteRequest()"
              style="background:var(--red,#c0392b); color:#fff; border:none; padding:12px 28px; border-radius:8px; font-size:15px; font-weight:600; cursor:pointer;">
        Submit Deletion Request
      </button>
      <div id="del-msg" style="margin-top:16px; font-size:14px;"></div>
    </div>

    <script>
    async function submitDeleteRequest() {
      const email  = document.getElementById('del-email').value.trim();
      const reason = document.getElementById('del-reason').value.trim();
      const msg    = document.getElementById('del-msg');
      if (!email || !email.includes('@')) {
        msg.style.color = '#e05252';
        msg.textContent = 'Please enter a valid email address.';
        return;
      }
      msg.style.color = 'var(--muted)';
      msg.textContent = 'Submitting...';
      const r = await fetch('/api/delete-request', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, reason})
      }).then(r => r.json()).catch(() => ({error: 'Network error. Please try again.'}));
      if (r.error) {
        msg.style.color = '#e05252';
        msg.textContent = r.error;
      } else {
        document.getElementById('delete-form').innerHTML =
          '<div style="background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:24px; text-align:center;">' +
          '<div style="font-size:32px; margin-bottom:12px;">&#x2705;</div>' +
          '<div style="font-size:16px; font-weight:600; color:var(--text); margin-bottom:8px;">Request Received</div>' +
          '<div style="font-size:14px; color:var(--muted);">We have received your deletion request for <strong>' + email + '</strong>. ' +
          'Your account and all associated data will be permanently deleted within 30 days.</div></div>';
      }
    }
    </script>
  </div>
</div>
'''

# ── Privacy Policy page ──────────────────────────────────────────────────────
PRIVACY_CONTENT = '''
<div class="container">
  <div class="prose">
    <h1 style="font-size:26px; color:var(--tan); margin-bottom:8px;">Privacy Policy</h1>
    <div class="updated">Last updated: April 7, 2025 &nbsp;&bull;&nbsp; Applies to: Hunting Land App (Android) and Trail Camera Photo Sorter (Windows/Mac)</div>

    <p>This Privacy Policy describes how Hunting Land Apps (&ldquo;we,&rdquo; &ldquo;our,&rdquo; or &ldquo;us&rdquo;) collects, uses, and protects information when you use our applications. We take your privacy seriously and are committed to being transparent about what we do with your data.</p>

    <h2>1. Information We Collect</h2>

    <h3>Hunting Land App (Android)</h3>
    <ul>
      <li><strong>Account information:</strong> Email address and password (stored securely via Google Firebase Authentication — we never see your password in plaintext).</li>
      <li><strong>Hunting property data:</strong> Stand locations, camera locations, food plot locations, harvest records, and observation notes that you choose to enter.</li>
      <li><strong>Photos you upload:</strong> Trail camera photos you choose to upload to your hunting area within the app.</li>
      <li><strong>Device information:</strong> Basic device identifiers used by Firebase for app functionality and crash reporting.</li>
      <li><strong>Location (optional):</strong> Used only when you tap &ldquo;Use my location&rdquo; to drop a pin. We do not track your location in the background.</li>
    </ul>

    <h3>Trail Camera Photo Sorter (Windows / Mac)</h3>
    <ul>
      <li><strong>Account login:</strong> Your email address is used to authenticate with your Hunting Land app account via Firebase.</li>
      <li><strong>Token balance:</strong> The number of AI sorting tokens remaining on your account, stored in your Firebase user profile.</li>
      <li><strong>Photo analysis:</strong> When you scan a folder, each photo is temporarily compressed and sent to Anthropic&rsquo;s Claude AI API for animal identification. The photo is sent only for analysis and is <strong>not stored</strong> by Anthropic or by us. Your original photos never leave your computer.</li>
    </ul>

    <h2>2. How We Use Your Information</h2>
    <ul>
      <li>To provide app functionality (maps, logs, photo sorting).</li>
      <li>To verify your subscription and token balance.</li>
      <li>To credit token purchases to your account after a Gumroad transaction.</li>
      <li>To allow you to share your hunting area with invited members.</li>
    </ul>
    <p>We do not sell your data. We do not use your data for advertising.</p>

    <h2>3. Third-Party Services</h2>
    <p>We use the following third-party services, each with their own privacy policies:</p>
    <ul>
      <li><strong>Google Firebase</strong> (Authentication &amp; Firestore) — stores account data and app content. <a href="https://firebase.google.com/support/privacy" style="color:var(--green);" target="_blank">Firebase Privacy</a></li>
      <li><strong>Google Firebase Storage</strong> — stores photos you choose to upload to your hunting area.</li>
      <li><strong>Anthropic Claude AI</strong> — analyzes trail camera photos for animal identification in the Photo Sorter. Photos are processed and immediately discarded; they are not stored or used to train AI models. <a href="https://www.anthropic.com/privacy" style="color:var(--green);" target="_blank">Anthropic Privacy</a></li>
      <li><strong>Gumroad</strong> — processes token pack purchases. We receive only your email address and purchase amount from Gumroad. <a href="https://gumroad.com/privacy" style="color:var(--green);" target="_blank">Gumroad Privacy</a></li>
    </ul>

    <h2>4. Data Storage and Security</h2>
    <p>Your account data and hunting records are stored in Google Firebase, which is hosted on Google Cloud servers in the United States. We use Firebase Authentication which provides industry-standard security including encrypted passwords and token-based authentication.</p>
    <p>Trail camera photos on your computer are never transmitted to our servers. Only temporary compressed copies are sent to Anthropic for AI analysis.</p>

    <h2>5. Data Retention</h2>
    <p>We retain your account and hunting data for as long as your account is active. If you delete your account, your data will be removed from our Firebase database within 30 days.</p>

    <h2>6. Children&rsquo;s Privacy</h2>
    <p>Our apps are not directed at children under 13. We do not knowingly collect personal information from children under 13. If you believe a child has provided us personal information, please contact us and we will delete it.</p>

    <h2>7. Your Rights</h2>
    <p>You have the right to:</p>
    <ul>
      <li>Access the data we hold about you.</li>
      <li>Request correction of inaccurate data.</li>
      <li>Request deletion of your account and associated data.</li>
      <li>Export your hunting records.</li>
    </ul>
    <p>To exercise these rights, contact us at the email below.</p>

    <h2>8. Changes to This Policy</h2>
    <p>We may update this Privacy Policy from time to time. We will post the updated policy on this page with a new &ldquo;Last updated&rdquo; date. Continued use of the apps after changes constitutes acceptance of the updated policy.</p>

    <h2>9. Contact Us</h2>
    <p>If you have questions about this Privacy Policy or want to request data deletion, please contact us at:</p>
    <p style="color:var(--text);"><strong>huntinglandapps@gmail.com</strong></p>
  </div>
</div>
'''


# ── Routes ────────────────────────────────────────────────────────────────────
ANIMALS = [
    'Buck', 'Doe', 'Fawn',
    'Bull Elk', 'Cow Elk',
    'Moose', 'Pronghorn', 'Mule Deer',
    'Bear', 'Mountain Lion', 'Wolf',
    'Coyote', 'Turkey', 'Raccoon',
    'Fox', 'Hog', 'Bobcat',
    'Squirrel', 'Bird', 'Other Animal', 'No Animal',
]

@app.route('/')
def home():
    html = render_template_string(BASE, title='Home', active='home',
                                  content=render_template_string(HOME_CONTENT))
    return html

@app.route('/photo-sorter')
def photo_sorter():
    content = render_template_string(SORTER_CONTENT, animals=ANIMALS, windows_download=WINDOWS_DOWNLOAD_URL)
    return render_template_string(BASE, title='Photo Sorter', active='sorter', content=content)

@app.route('/tokens')
def tokens():
    content = render_template_string(TOKENS_CONTENT,
                                     buy_200=BUY_LINKS[200],
                                     buy_500=BUY_LINKS[500],
                                     buy_1000=BUY_LINKS[1000],
                                     buy_custom=BUY_LINKS['custom'])
    return render_template_string(BASE, title='Buy Tokens', active='tokens', content=content)

@app.route('/privacy')
def privacy():
    return render_template_string(BASE, title='Privacy Policy', active='privacy',
                                  content=render_template_string(PRIVACY_CONTENT))


@app.route('/delete-account', methods=['GET'])
def delete_account():
    return render_template_string(BASE, title='Delete Account', active='',
                                  content=DELETE_CONTENT)


@app.route('/api/delete-request', methods=['POST'])
def api_delete_request():
    email = request.json.get('email', '').strip().lower()
    reason = request.json.get('reason', '').strip()
    if not email or '@' not in email:
        return jsonify({'error': 'Please enter a valid email address.'}), 400
    fb_auth, db = firebase()
    if db is not None:
        try:
            db.collection('deletionRequests').add({
                'email': email,
                'reason': reason,
                'requestedAt': __import__('datetime').datetime.utcnow().isoformat(),
                'status': 'pending'
            })
        except Exception as e:
            print(f"Delete request save error: {e}")
    return jsonify({'ok': True})


# ── Gumroad webhook ───────────────────────────────────────────────────────────
@app.route('/webhook/gumroad', methods=['POST'])
def webhook_gumroad():
    data = request.form

    # Basic seller verification — Gumroad posts your seller_id in every ping
    seller_id = data.get('seller_id', '')
    if GUMROAD_SELLER_ID and seller_id != GUMROAD_SELLER_ID:
        print(f"Webhook: seller_id mismatch — got {seller_id}")
        return jsonify({'error': 'Unauthorized'}), 401

    buyer_email     = data.get('email', '').strip().lower()
    product_slug    = data.get('product_permalink', '').strip().lower()
    sale_id         = data.get('sale_id', '')
    refunded        = data.get('refunded', 'false').lower() == 'true'

    if not buyer_email or not product_slug:
        return jsonify({'error': 'Missing email or product'}), 400

    tokens_to_add = TOKEN_PACKS.get(product_slug)
    if tokens_to_add is None:
        # Check if this is a custom-amount purchase — calculate tokens from price paid
        if product_slug == 'tokens-custom':
            price_cents = int(data.get('price', 0))   # Gumroad sends price in cents
            tokens_to_add = round(price_cents / 2200) * 1000  # $22.00 = 1000 tokens
            if tokens_to_add <= 0:
                return jsonify({'error': 'Could not determine token amount from price'}), 400
        else:
            print(f"Webhook: unknown product slug '{product_slug}'")
            return jsonify({'ok': True, 'note': 'Product not a token pack — ignored'})

    if refunded:
        tokens_to_add = -tokens_to_add  # deduct on refund

    # Look up the Firebase user by email and update their token balance
    fb_auth, db = firebase()
    if fb_auth is None or db is None:
        print("Webhook: Firebase not configured")
        return jsonify({'error': 'Server configuration error'}), 500

    try:
        from firebase_admin import firestore as fs
        user = fb_auth.get_user_by_email(buyer_email)
        uid  = user.uid
        user_ref = db.collection('users').document(uid)
        user_ref.update({'tokenBalance': fs.Increment(tokens_to_add)})
        print(f"Webhook: {'added' if tokens_to_add > 0 else 'deducted'} {abs(tokens_to_add)} tokens "
              f"for {buyer_email} (sale {sale_id})")
        return jsonify({'ok': True, 'tokens_added': tokens_to_add, 'uid': uid})
    except Exception as e:
        print(f"Webhook error for {buyer_email}: {e}")
        return jsonify({'error': str(e)}), 500


# ── Health check (Render pings this to keep the service alive) ───────────────
@app.route('/health')
def health():
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
