# 🧟 ZMB — Zombie Survival (Interactive Animated Instagram Channel)

Ek **fully-automated Instagram Reels channel** jahan **viewers comment karke story decide karte hain**.

- Har reel ek cartoon scene dikhati hai — English narration ke saath, worldwide audience ke liye
- Max (aur his dog Biscuit) + Ada, zombie apocalypse mein survive karte hue
- Reel ka last card poochta hai: **"Comment 1 or 2"** → viewers vote karte hain
- Majority vote ke hisaab se **agli episode apne aap generate** hoti hai
  (script → procedural cartoon animation → voice → video → Instagram post)
- Poora pipeline **GitHub Actions + official Instagram Graph API** par chalta hai = **$0/month**,
  koi PC 24x7 on rakhne ki zaroorat nahi. Aur **koi AI image API nahi** — animation
  poora tarah se khud-renders hota hai (procedural SVG → PNG → FFmpeg), isliye kabhi
  rate-limits ya broken-image failures nahi.

## 🎬 Kya-dikhta hai reel mein

- **Vector cartoon animation**: human rig (walk/run/sit/crouch), dog rig (trot/bark/scared/sit),
  zombie hordes, parallax camera push/pan/shake, fog/rain/embers effects
- **Karaoke captions** (yellow highlight, word-timed) — har line par
- **HUD**: HP / NOISE / FOOD / DOG trust stat pills, "SEASON 1 · DAY 4" counter
- **Title card + vote card + ending card** — poori episode format ready
- **Michael-style narration**: en-US Christopher voice, har shot ke saath synced

**Season 1 "The Long Road"** (17 nodes): highway → gas station → motel 3:04AM →
forest/bridge routes → lookout tower → broadcast… **Endings: Coast ya City** →
Season 2 "The Metro" unlock. Scenes sab **globally-common places** hain (highway, gas
station, motel, forest road, radio tower, coast — koi India-specific cheez nahi).

## 📁 Folder Map

| File / Folder | Kya hai |
|---|---|
| `content/scenarios.json` | **Story graph** — S1 Road (17 nodes) + S2 Metro (7 nodes), English |
| `scripts/engine.py` | Story engine: state machine, votes advance, episode builder |
| `scripts/animate.py` | **Compositor** — camera, HUD, captions, title/vote/ending cards, fx |
| `scripts/characters.py` | Human/dog/zombie rigs — positions, poses, actions |
| `scripts/scenes.py` | 15 scene builders (highway, motel, metro, coast, forest…), parallax |
| `scripts/svgkit.py` | SVG helper kit (vector primitives, gradients, glow, text) |
| `scripts/svgrender.py` | resvg-py parallel frame render + FFmpeg encode (lanczos upscale) |
| `scripts/render.py` | Full pipeline: voices (edge-tts) → timeline → mix → frames → mp4 |
| `scripts/run_cycle.py` | **Orchestrator** — jo workflow chalata hai |
| `scripts/votes.py` | Instagram comments tally system |
| `scripts/publish.py` | Reels publish (Graph API) + GitHub media hosting |
| `dashboard/` | **Control room GUI** (FastAPI + vanilla SPA) — monitor/trigger/edit |
| `config.example.json` | Saari settings (voice, render size, hashtags, timing) |
| `state/state.json` | Channel ki "memory" — season/day, node, stats, votes |
| `.github/workflows/` | GitHub Actions — daily episode cycle |
| `assets/fonts/` | Bundled fonts (Archivo Black, Barlow) — text render offline |

## 🖥 Dashboard (local control room)

```powershell
python dashboard/server.py     # → http://127.0.0.1:8787
```

- **Story State**: gauges HP/NOISE/FOOD/DOG + current arc + next node + choices
- **Pipeline**: "Render next (dry)" / "Stills only" / "Full publish run" buttons;
  6-step stepper + live log jab tak run chalta hai
- **Episodes**: 9:16 video player + file list (purani reels replay karo)
- **Story Map**: cast ka whole-arc map — current node highlight hoti hai
- **Engine Settings**: config.json edit (render size, hashtags, captions...) — save button
- **Publish Setup**: token missing hone par setup steps ka live checklist
- Sirf local dependencies chahiye: `pip install fastapi uvicorn`

## ⚡ Ek Line Mein Kaam Kaise Karta Hai

```
GitHub Actions (har 3 ghante, free)
   └─ 1. Pichhli reel ke COMMENTS padho (votes count)
   └─ 2. Majority winner → story engine state advance
   └─ 3. Nayi episode banao:
         script (scenarios graph) → narration (edge-tts English)
         → frames (resvg procedural cartoon, 720×1280 internal)
         → FFmpeg (libx264, 1080×1920 lanczos upscale)
   └─ 4. Video GitHub media branch par host (public URL)
   └─ 5. Instagram Graph API → REELS post (AI disclosure set)
   └─ 6. State commit — repeat forever
```

## 💰 Cost

| Cheez | Tool | Cost |
|---|---|---|
| Scheduler/Server | GitHub Actions (public repo) | **$0** |
| Posting | Instagram Content Publishing API | **$0** |
| Voice | edge-tts (Microsoft Neural, English) | **$0** |
| Animation | Procedural SVG + resvg-py (local) | **$0** |
| Video banane | FFmpeg | **$0** |
| Video hosting | GitHub `media` branch (raw URL) | **$0** |
| **Total** | | **$0/month** |

## 🚦 Quick Start (2-3 ghante ka one-time setup)

1. `SETUP.md` → Part A: Instagram account ko **Professional** banao + Meta app banao
2. `SETUP.md` → Part B: Access token generate karo (60-day, auto-refresh hoga)
3. `SETUP.md` → Part C: Ye folder ek **public GitHub repo** mein daalo + Secrets set karo
4. `SETUP.md` → Part D: `python scripts/run_cycle.py --dry-run` se pehli video locally banao
5. Part D2: `python dashboard/server.py` kholo — control room se next run trigger karo
6. `SETUP.md` → Part E: Workflow enable karo → channel live 🚀

## ⚠️ Important Notes

- Sirf **official Meta APIs** — koi unofficial bot/scraper nahi (account-ban risk nahi, engagement spam karne jaisa bhi kuch nahi).
- Content **fiction** hai — reels par **AI-content disclosure automatically set** hota hai (`is_ai_generated=true`).
- Pehle hafte **manual push** karna (friends/groups share) — algorithm ko initial signal chahiye. Plan `PLAN.md` mein.
- GitHub runner par pehli val `dry_run: true` chalakar sanity-check, phir `force_publish` se live jao.


## AI storyboard visuals

The selected AI storyboard mode creates a detailed illustration per narration beat, with subtle camera movement and readable subtitles. Add a server-side POLLINATIONS_KEY from https://enter.pollinations.ai/keys. AI requests may consume provider credits. Production stops if the key is missing or generation fails, rather than silently posting the old vector animation.
