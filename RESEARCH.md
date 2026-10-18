# 🔬 RESEARCH — Verified Findings (18 Oct 2026)

Har claim ke saath source. Ye document update hote rehna chahiye jab Meta/GitHub kuch badle.

---

## 1. Instagram Content Publishing API (posting via code)

| Cheez | Verified Reality | Source |
|---|---|---|
| Cost | API **free** hai, koi pricing nahi | Meta docs |
| Rate limit | Content Publishing page: **100 posts / 24h**; carousel page + `content_publishing_limit` field: **50/24h**. Conflicting hai — live check karo: `GET /<IG_ID>/content_publishing_limit` (quota_duration=86400, quota_total=50) | developers.facebook.com Content Publishing (updated 2025/2026) |
| Reels publish | 3 steps: (1) `POST /<IG_ID>/media` with `media_type=REELS` (2) poll `GET /<CONTAINER>?fields=status_code` until `FINISHED` (3) `POST /<IG_ID>/media_publish` with `creation_id` | Meta docs |
| Video source | `video_url` **public URL honi chahiye** (Meta khud fetch karta hai) — ya `upload_type=resumable` se direct file upload | Meta docs |
| ⚠️ Resumable upload | **Sirf Facebook Login for Business** wale apps ke liye. **Instagram Login flavor par resumable NAHI hai** → video public URL se dena padega | Meta docs: "Only for apps that have implemented Facebook Login for Business" |
| Video specs | MOV/MP4, H264/HEVC + AAC, 3s–15min, ≤300MB, 23–60fps, 9:16 recommended | Meta IG User Media reference |
| Container expiry | 24h mein publish nahi kiya to `EXPIRED`; status query 1x/min, max 5 min karo | Meta docs |
| AI disclosure | `is_ai_generated=true` parameter container banate waqt — dono login flavors par available | Meta docs (Content Publishing) |
| Scheduling | API mein future-scheduling **nahi** hai — jab call karoge tabhi publish hoga (isliye hamara cron 3-hourly hai, ek window pick karta hai) | Meta docs |
| Trial reels | `trial_params.graduation_strategy` = `MANUAL`/`SS_PERFORMANCE` — non-followers ko test karne ke liye useful | Meta docs |

## 2. Do Login Flavors — humara chunav

| | Instagram API with **Instagram Login** ✅ (humara pick) | Instagram API with Facebook Login |
|---|---|---|
| Facebook Page chahiye? | **Nahi** | Haan |
| Host | `graph.instagram.com` | `graph.facebook.com` + `rupload.facebook.com` |
| Token | Instagram User Access Token (60 din, refreshable) | FB Page token |
| Permissions | `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments` | `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`... |
| Resumable upload | ❌ | ✅ (isliye FB Login ko chhoda nahi — video public URL se dena manageable hai) |

**Decision:** Instagram Login — kyunki Facebook Page banane/link karne ka jhanjhat nahi, personal automation ke liye simplest, aur hamare pipeline mein video public URL se dena easy hai (GitHub raw URL).

## 3. Token Lifecycle (verified)

- Short-lived token: **1 hour** — `POST https://api.instagram.com/oauth/access_token` (OAuth code exchange)
- Long-lived token: **60 days** — `GET https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=...&access_token=...`
- Refresh (expire hone se pehle, kam se kam 24h purana ho): `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=...` → naya 60-day token
- **Refresh tab tak kaam karta hai jab tak purana token expire na ho chuka ho** — isliye hamara workflow 1st & 15th ko chalta hai (30-day buffer hamesha).
- App secret sirf server-side/Actions secrets mein rakhna.

Sources: Meta Access Token reference (updated Mar 2026), Refresh Access Token reference.

## 4. Comments (votes padhna)

- Endpoint: `GET /<IG_MEDIA_ID>/comments` — **max 50 comments per call**, paging cursors, sirf top-level comments (replies alag se).
- Permission: `instagram_business_manage_comments`.
- Meta kehta hai webhooks better (rate limits se bachne ke liye), par webhook ke liye public HTTPS server chahiye — hamara polling (din mein ~6 baar, 1-3 calls) rate limit ke liye koi issue nahi: **IG Platform rate limit = 4800 × impressions per 24h** (kam-traffic account bhi 1M+ calls kar sakta hai).
- ⚠️ Known bug reports (2026): kuch apps ko `data: []` aata hai jabki comments manch par dikh rahe hote hain. Mitigation: retry + votes kam hone par default story path (channel kabhi nahi rukti).
- Reply/comment karna: `POST /<IG_MEDIA_ID>/comments` (message) — pinned comment API se nahi ho sakta, par first comment post kar sakte hain.

Sources: Meta Comment Moderation guide, IG Comment reference, Meta dev community threads (2026).

## 5. Automation Rules (kya allowed hai, kya nahi — "2026 policy")

- ✅ Official API se **own content publish + schedule + comment moderation** = 100% allowed.
- ❌ Auto-likes, auto-follow/unfollow, mass DM, comments spam = ban territory. Hum kuch nahi karte isme.
- Hashtags: **3-5 relevant** tags, har post par same block nahi (looks automated) — hum pool se rotate karte hain.
- "First comment" strategy allowed hai (caption clean rakho, choices first comment mein bhi).
- AI content: disclose karo (`is_ai_generated=true`) — Meta khud ye param deta hai.

Sources: Instagram Terms, Mixpost/Brand-update policy guides (2026), Inflowave hashtag guide (2026).

## 6. Free Tools — verified status (Oct 2026)

| Tool | Status | Limits/Notes |
|---|---|---|
| **GitHub Actions** | ✅ Active | Public repo = unlimited free minutes. ⚠️ **Private repo + free plan = scheduled workflows unreliable/broken** (kaafi 2026 reports). → **Public repo use karo**, ya external cron se `workflow_dispatch`. Private repo minutes: 2,000/month. Self-hosted runners par Mar 2026 se $0.002/min (private) — irrelevant for us. |
| **edge-tts** | ✅ Active (v7.3.1, Oct 2026) | Free Microsoft Neural voices, no key. 12k+ stars. Hindi voices: `hi-IN-SwaraNeural`, `hi-IN-MadhurNeural`; Indian English: `en-IN-PrabhaNeural`, `en-IN-NeerjaNeural`. Fallback: Piper (offline). |
| **Pollinations.ai** | ✅ Free tier active | Classic anonymous API: 1 image per 45s per IP, 768×768 max area, logo. With key (enter.pollinations.ai, free daily credits): better models, no logo, no per-IP limit. Hamara code dono support karta hai. |
| **Pixabay API** | ✅ Free | 100 req/60s, **24h caching required**, hotlink nahi karna (download karo). Images+videos+audio. |
| **Pexels API** | ⚠️ Key issuance **paused** (2026) | Isliye primary stock source Pixabay rakha hai. |
| **Groq** | ✅ Free tier | 30 req/min, 14,400 req/day, no credit card. (Optional LLM scriptwriter ke liye.) |
| **Gemini API** | ⚠️ Free tier shrink ho gaya (Apr 2026: Pro paid-only, flash quotas cut) | Groq better choice hai free tier ke liye ab. |
| **cron-job.org** | ✅ Free | External trigger (workflow_dispatch) — GitHub scheduler flaky ho to backup. |
| **Cloudflare Workers** | ✅ Free | 5 cron triggers/account, `workflow_dispatch` fire karne ke liye; R2 storage 10GB free (optional video hosting upgrade). |

## 7. Trend Research (content angle)

- **Zombie AI love story / apocalypse AI reels**: Oct 2026 tak strong viral trend (Hindi creators bhi kar rahe hain — "Zombie AI video kaise banaye" type videos 12K+ views).
- **"Choose your own adventure" reels**: exist karte hain par mostly one-off; **continuous, vote-driven series** almost koi nahi kar raha — yahi hamara wedge hai.
- Interactive formats (polls/votes/comments) = engagement multiplier; comments algorithm ke liye strongest signal.
- Hinglish zombie content ka audience: huge (India + NRI), competition: low.

## 8. Rejected Options (aur kyun)

| Option | Kyun nahi |
|---|---|
| instagrapi / unofficial private API | ToS violation, ban risk — jab official API free hai to risk kyun |
| Paid tools (Buffer $6+, Blotato, Postpeer) | Free API se khud kar sakte hain; zero-budget goal |
| n8n self-hosted | Free hai par PC 24x7 on chahiye + setup heavy; GitHub Actions simpler aur machine-independent |
| LLM har episode ke liye | Optional hai; template engine deterministic + reliable; LLM ko optional upgrade rakha |
| Instagram ka trending audio | API-published reels mein use nahi ho sakta (licensing) — isliye Pixabay music + weekly manual post ka hybrid strategy |
| Story polls (sticker) | API se stories par interactive stickers nahi lag sakte — comments hi sahi mechanism hai |
| MoviePy | v2 API changes + heavy; direct FFmpeg subprocess zyada reliable aur fast |

## 9. Open Questions (jo monitor karte raho)

- [ ] Content Publishing limit 50 vs 100 — `content_publishing_limit` endpoint live number par bharosa karo
- [ ] Pollinations classic API long-term stability (they've had outages Feb 2026) → Pixabay fallback ready hai
- [ ] GitHub private-repo schedule issue ka koi official fix? → abhi public repo = safe
- [ ] Meta app policy: dev-mode apps apne accounts ke liye OK hai; agar kabhi "App Review" maanga jaye to us time dekhenge
- [ ] Comments `data: []` bug app-specific hai ya broad — fallback already coded
