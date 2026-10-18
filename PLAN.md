# 📋 MASTER PLAN — Zero-Cost Automated Zombie Apocalypse Channel

*Research date: 18 Oct 2026. Saare limits/features verify kiye gaye hain (sources: `RESEARCH.md`).*

---

## 1. Concept (kya banana hai)

**"Zombie Apocalypse: Tum Decide Karo"** — ek interactive survival story jo Instagram Reels par roz chalti hai:

- Protagonist = **viewer khud** ("tum"). Start: ek farmhouse mein phanse ho.
- Har episode ke end mein **2 choices** (A/B) — viewers **comments mein vote** karte hain.
- Agli episode mein: _"72% ne kaha CHECK…"_ + us choice ka natija, phir nayi choice.
- Stats continuity: `HP · NOISE · SUPPLIES` (screen par HUD) — choices stats badalti hain, endings stats par depend karti hain.
- Season end par meta-vote: "Season 2 kahan ho? Pahad / Shehar / Gaon".

**Why this works (2026 trend research):**
- Zombie/apocalypse AI reels + "choose your own adventure" formats viral ho rahe hain (Oct 2026 tak Instagram par active trend).
- **Interactive = comment machine.** Comment count = algorithm fuel. Interactive reels ko normal reels se 3-10x zyada comments milte hain → reach explode.
- Hinglish niche: zombie content ka Hindi audience huge hai, par **interactive** zombie content ka competition almost zero.
- 100% AI-generated visuals + voice = consistent style, koi camera/shooting/facetime nahi.

---

## 2. Architecture (one-liner)

> **GitHub Actions** (free scheduler + compute) har 3 ghante uth kar: comments se votes padhta hai → story engine majority decide karta hai → **FFmpeg + edge-tts + AI images** se nayi reel banata hai → **Instagram Graph API** se post karta hai → state commit karke sota hai. **Zero manual kaam, zero cost.**

Detail: `ARCHITECTURE.md`.

---

## 3. Cost Breakdown (sab verify kiya gaya — Oct 2026)

| Component | Tool | Free Tier | Humara usage | Cost |
|---|---|---|---|---|
| Scheduler + Compute | GitHub Actions (public repo) | Unlimited minutes | ~15 min/day | $0 |
| Instagram posting | Graph API Content Publishing | 50-100 posts/24h | 1-2/day | $0 |
| Comment padhna | Graph API comments | Rate limit: 4800×impressions/24h | ~20 calls/day | $0 |
| Script/narration text | Templates (built-in) ya Groq/Gemini free tier | 14,400 req/day (Groq) | ~5 req/day | $0 |
| Voice (TTS) | edge-tts (Microsoft Neural) | Unlimited*, no key | ~40s voice/day | $0 |
| Images | Pollinations.ai (free tier) / Pixabay API | 1 img/45s (anon), 100 req/60s (Pixabay) | ~5 imgs/episode | $0 |
| Video assembly | FFmpeg (runner preinstalled) | Open source | ~2 min/episode | $0 |
| Video hosting | GitHub `media` branch (raw.githubusercontent) | Free CDN | 1 file/day, auto-replace | $0 |
| Story state DB | `state/state.json` (repo mein) | Free | Tiny | $0 |
| **TOTAL** | | | | **$0/month** |

\* edge-tts unofficial-but-widely-used client hai Microsoft ke Neural TTS ka. Free hai, signup nahi. Iska fallback plan: Piper TTS (offline). Details `RESEARCH.md`.

**Optional upgrades (agar aage jana ho):** GitHub Pro ($4), Cloudflare R2 storage (free tier 10GB, cleaner hosting), paid image APIs. Zaroorat nahi hai start ke liye.

---

## 4. Phases & Roadmap

### Phase 0 — Setup (Day 0–1, ~2–3 ghante, one-time)
- [ ] Instagram pe naya account banao (ya purana use karo) → **Professional > Creator/Business** mein convert karo
- [ ] Meta developer app banao + "Instagram business login" product add karo
- [ ] Access token generate → **60-day long-lived** banao (auto-refresh workflow laga do)
- [ ] Public GitHub repo banao → folder push karo → Secrets set karo (`SETUP.md`)
- [ ] Local dry-run: bahut pehle `python scripts/run_cycle.py --dry-run` — video banao, dekho, tune karo (voice, style, pacing)

### Phase 1 — Soft Launch (Week 1)
- [ ] Day 0: "Trailer" reel (intro node) — aaj hi test karo ki API se post ho raha hai
- [ ] Din 1–7: roz 1 reel (13:00 IST) — Farmhouse arc
- [ ] Roz 10 min manual: top comments ko heart/reply karo (bots nahi chalane!)
- [ ] Har reel ke baad: pinned/first comment mein choices repeat karo (script auto karta hai)
- [ ] Family/friends WhatsApp groups + apni story par share (pehla push)
- **Ab tak kharcha: $0. Ab tak manual kaam: roj 10 min.**

### Phase 2 — Consistency (Week 2–4)
- [ ] Ark reaching `min_votes: 10` → voting kaam kar rahi hai
- [ ] 2nd arc banao (`CONTENT-ENGINE.md` mein guide) — factory / metro station
- [ ] Analytics dekh: kौn-se hooks chal rahe hain → templates tweak karo
- [ ] Target: 50+ votes/reel, 1,000+ views/reel, 100+ followers/week
- [ ] (Optional) Reach experiment: hafte mein 1 reel manually post karo trending audio ke saath (API wale reels par IG library music nahi lag sakti)

### Phase 3 — Growth (Month 2–3)
- [ ] 2 reels/day (13:00 + 20:00 IST) — quota me easily fit (50-100/day limit hai)
- [ ] "Story so far" recap reel har Sunday (auto-generate ho sakta hai)
- [ ] Cross-post: YouTube Shorts (same video manually/dusra script)
- [ ] Target: 10K followers, 20K+ avg views, brand-shoutout offers

### Phase 4 — Monetize (Month 3+)
- [ ] Instagram bonuses / brand shoutouts (zombie-gaming, survival gear, horror games)
- [ ] "Season 2" ko paid giveaway/brand collab se launch karo
- [ ] Apna bot/SaaS isi engine se banao (dusre creators ko bech sakte ho!) — full circle 😄

---

## 5. Daily Rhythm (kya automatic hai, kya tumhara)

| Time (IST) | Kaam | Kaun karta hai |
|---|---|---|
| 08:00, 10:30 | Vote tally update (comments padho) | 🤖 Auto |
| **13:00** | **Nayi reel publish** (votes resolve → generate → post) | 🤖 Auto |
| 14:00–22:00 | Top comments par heart/reply (10 min) | 👤 Tum (optional but recommended) |
| 16:30, 19:30, 22:30 | Vote tally update | 🤖 Auto |
| 1st & 15th monthly | Access token auto-refresh | 🤖 Auto |

**Total manual effort: 0-15 min/day (bas engagement ke liye). Content production: 0.**

---

## 6. KPIs (kya measure karna)

| Metric | Week 1 | Week 4 | Month 3 |
|---|---|---|---|
| Reels posted | 7 | 30 | 90 |
| Avg votes per reel | 5+ | 50+ | 500+ |
| Avg views | 300+ | 3K+ | 20K+ |
| Followers | 100 | 1K | 10K+ |
| Save rate | >2% | >3% | >4% |

Red flag: agar 2 hafte tak votes < 10 → CTA strong karo, hook punchy karo, post time adjust karo (CONTENT-ENGINE.md troubleshooting).

---

## 7. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Token expire (60 days) | Certain without action | Auto-refresh workflow 1st & 15th ko + error alert (workflow fail hone par email aata hai) |
| GitHub schedule flaky (free tier) | Medium | Public repo use karo (schedule reliable); backup: cron-job.org se workflow_dispatch trigger |
| Pollinations rate limit (402) | Medium | Built-in retry + Retry-After; fallback Pixabay; images between requests 45s |
| API comments empty (known bug) | Low-Medium | Retry; votes < threshold par default path chal jata hai (story kabhi rukti nahi) |
| Account flag/restrict | Low | Sirf official API, koi engagement automation nahi, AI disclosure ON, fiction label, hashtags vary |
| Reel fetch fail (2207052) | Low | video_url public hai, retry 2x; warna next cycle |
| Repo bloat (video files) | Certain if careless | `media` branch har baar force-replace (always 1 file), main repo clean |
| 6 महीने baad bore/fatigue | Real | Naye arcs + stats + endings + meta-votes = cliffhanger engine already hai |

---

## 8. Content Pillars (episode ideas bank)

1. **Farmhouse arc** (built-in) — garage sound, fields, well, friend Raj, radio, endings
2. Factory / godown — machinery, trap doors, toxic fumes
3. Metro station — dark tunnels, train, paani
4. Village — kuan, mandir, tractor
5. Hospital — medicines, ICU, basement
6. Highway — surviving cars, petrol siphoning
7. School/hostel — kids ko bachana
8. Boat/beach — ferry, samundar
9. Pahad — snow, cable car, cave
10. Shehar — high-rise, terrace, helicopter

Har arc = ~10-14 episodes = ~2 hafte ek arc. 10 arcs = 5 mahine content. Season boundaries par meta-vote.

---

## 9. Success Checklist (poora system ke liye)

- [ ] Reel Instagram par API se post hui (manual nahi)
- [ ] Comments padhkar votes count hue (state.json mein dikhe)
- [ ] Majority winner agli episode mein recap hua
- [ ] Har episode bilkul automatic bani (koi manual edit nahi)
- [ ] 30 din lagataar chalaya bina rukawat
- [ ] Pehla brand deal / 10K followers 🙂
