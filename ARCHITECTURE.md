# 🏗️ ARCHITECTURE — System Design

## 1. High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GITHUB (free, 24x7)                          │
│                                                                     │
│  ┌──────────────────────────┐      ┌─────────────────────────────┐  │
│  │ Actions: episode.yml     │      │ Actions: refresh-token.yml  │  │
│  │ cron: har 3 ghante       │      │ cron: 1st & 15th monthly    │  │
│  │ (IST 08:00→22:30)        │      │ → new 60-day token          │  │
│  └────────────┬─────────────┘      └──────────────┬──────────────┘  │
│               │                                   │                 │
│               ▼                                   ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              run_cycle.py  (Python 3.12)                    │    │
│  │                                                             │    │
│  │  1. votes.py      →  Instagram comments padho, count karo   │    │
│  │  2. engine.py     →  majority winner + stats + next node    │    │
│  │  3. render.py     →  images + TTS + FFmpeg = reel.mp4       │    │
│  │  4. publish.py    →  GitHub media branch push (public URL)  │    │
│  │                      + IG container + publish + 1st comment │    │
│  │  5. state save    →  git commit (bot)                       │    │
│  └────────────┬──────────────────────────────────────┬─────────┘    │
│               │                                      │              │
│       ┌───────▼────────┐                  ┌──────────▼───────────┐  │
│       │ state/state.json│                  │ media branch (orphan)│  │
│       │ (channel memory)│                  │ → raw.githubusercontent│ │
│       └────────────────┘                  │   .com/.../reel.mp4  │  │
│                                           └──────────┬───────────┘  │
└──────────────────────────────────────────────────────┼──────────────┘
                                                       │ public URL
        ┌──────────────┐   Meta fetches video   ┌───────▼────────────┐
        │  🌐 Internet │ ◄───────────────────── │ Instagram Graph API│
        └──────────────┘                        │  (graph.instagram) │
                                                └───────┬────────────┘
   ┌─────────────┐   comments (votes)  ┌─────────────────▼────────────┐
   │  📱 Viewers │ ──────────────────► │  Instagram Reels + Comments  │
   └─────────────┘                     └──────────────────────────────┘
```

## 2. Daily Cycle (sequence)

```
08:00 IST  run_cycle → votes checkpoint (comments padho, state update, commit) → exit
10:30 IST  idem
13:00 IST  run_cycle:
            1) fetch votes → tally (unique voters)
            2) engine.advance()  → winner + effects + next node
            3) build_episode()   → narration, image prompts, caption, choices
            4) render_episode()  → out/reel_s1_dN.mp4
            5) git push media branch (force, 1 file) → public URL
            6) IG: container → poll FINISHED → media_publish → media_id
            7) first comment (choices) post
            8) state commit (day++, last_episode = {...})
16:30 IST  votes checkpoint (naye votes count)
19:30 IST  idem
22:30 IST  idem
```

## 3. State Machine (story engine)

State file: `state/state.json`

```
{
  "season": 1, "day": 0,
  "arc": "farmhouse",              // abhi kaunsi kahani
  "node": "intro",                 // ab kahan hai plot
  "location": "Punjab ka sunsaan farmhouse",
  "stats": {"hp":100,"noise":20,"supplies":60,"trust":50},
  "history": [ {day, node, media_id, winner, pct} ... ],
  "last_episode": {
      "media_id": "...", "node": "garage_sound",
      "vote": true, "choices": {"run":"RUN...","check":"CHECK..."},
      "voters": {"user1":"run","user2":"check"},   // unique, idempotent
      "votes": {"run":12,"check":9}, "closed": false
  },
  "recent_hashtags": ["#zombieapocalypse", ...]
}
```

**Node kinds (scenarios.json):**
- `story` → koi vote nahi, seedha `next` node par
- `vote` → 2 choices, majority jeeti (tie/low-votes → `default`)
- `ending` → arc khatam; choices = next season ke locations (`next_arc`)

**Transition logic (`engine.advance`):**
1. Agar `last_episode.vote` → tally se winner (min_votes se kam hua to default; tie → default)
2. Winner choice ke `effects` stats par apply (0-100 clamp)
3. `state.node` = winner ka `next` (ya `next_arc` mila to arc/season switch + stats reset)
4. Story node tha → seedha `node.next`

## 4. Rendering Pipeline (FFmpeg)

```
narration text ──► edge-tts ──► voice.mp3 + voice.srt (word-level subs)
image prompts ──► Pollinations/Pixabay ──► img_0..3.jpg
                      │
       per image: scale 1080x1920 (cover) + crop + zoompan (slow ken-burns zoom)
                      │
              concat (all clips) ──► silent.mp4
                      │
   final pass: subtitles (burned) + day-title + stats HUD + choice texts
               + voice + music bed (Pixabay, 12% volume) 
                      │
       H.264 yuv420p 30fps AAC 128k +faststart ──► out/reel_sX_dY.mp4
```

- Voice duration = master clock; images ko proportionally baant te hain (text length ke hisaab se).
- Sab kuch deterministic: same state = same video (seed-based images).
- target: 30-45s per reel.

## 5. Failure Modes & Fallbacks

| Failure | Detection | Fallback |
|---|---|---|
| Pollinations 402 (rate limit) | HTTP status | Retry-After respect karke retry (max 3) → Pixabay fallback → dark placeholder card |
| edge-tts network fail | exception | Retry 3x → run abort → agla cron cycle (24h baad) try karega; channel din skip karta hai |
| IG token expired (error 190) | API error code | Workflow fail → email alert → naya token (`SETUP.md` Part B), phir 2 min mein fix |
| Comments API empty/bug | votes 0 despite comments | Threshold se neeche = default path; story kabhi nahi rukti |
| Meta video fetch fail (2207052) | error code | Container dobara banao, retry 2x; warna next cycle |
| Media publish limit (error 9) | error code | Skip publish; next day (hum 1-2/day karte hain to practically impossible) |
| GitHub scheduler skip | missing run | 6 checkpoints hai — ek miss hua to agla 3h baad; publish window 13:00 ke baad koi bhi run ise pick kar leta hai |
| GitHub Actions down | workflow fail | Rare; agle cycle par state-based catch-up (ek hi din ka content double nahi hoga — date check hai) |

## 6. Security

- Token **GitHub Secrets** mein (public repo mein secret safe rehta hai; logs mein print nahi hota — code se bhi print nahi karte).
- Auto-refresh mode chahiye to `GH_PAT` secret (fine-grained, sirf us repo ke secrets write) + `refresh_token.py` secret ko update karta hai.
- App secret sirf token generation ke waqt (local) use hota hai — repo mein kabhi nahi.
- Repo public hai to bhi: koi API key code mein nahi, config.json mein sirf non-secret settings.

## 7. Why these choices (quick rationale)

- **GitHub Actions**: machine 24x7 nahi chahiye, public repo = unlimited free minutes, cron + compute + storage (repo) ek jagah.
- **Comments > Story polls**: IG story stickers API se set nahi ho sakte; comments automate ho sakte hain + engagement algorithm signal.
- **Template engine (LLM optional)**: deterministic, free, no rate-limit surprises; LLM sirf flavor ke liye later.
- **Public URL hosting (media branch)**: Instagram Login flavor resumable upload support nahi karta (verified), aur GitHub raw CDN free + fast hai.
- **Polling (not webhooks)**: webhook ke liye public HTTPS server + verification chahiye; polling 6x/day trivial hai rate limits ke against.
