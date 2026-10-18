# 🧟 Zombie Apocalypse — Interactive Instagram Channel (100% Free Automation)

Ek **fully-automated Instagram Reels channel** jahan **viewers comment karke story decide karte hain**.

- Har reel ek scene dikhati hai: _"Garage se awaaz aa rahi hai… RUN ya CHECK?"_
- Viewers comment karte hain: **1** ya **2**
- Majority vote ke hisaab se **agli episode apne aap generate** hoti hai (script → images → voice → video → Instagram post)
- Poora pipeline **GitHub Actions + official Instagram Graph API** par chalta hai = **$0/month**, koi PC 24x7 on rakhne ki zaroorat nahi.

> Ye folder ek **complete, tested blueprint** hai — poora render pipeline (images → voice → FFmpeg → reel) locally verify ho chuka hai, aur bina votes wala fallback bhi. Setup ke liye `SETUP.md` follow karo.

---

## 📁 Folder Map

| File / Folder | Kya hai |
|---|---|
| `PLAN.md` | **Master plan** — phases, roadmap, KPIs, risks, costs (sab $0) |
| `RESEARCH.md` | Poori research — verified limits, sources, decision log (Oct 2026) |
| `ARCHITECTURE.md` | System diagram, pipeline, state machine, failure modes |
| `SETUP.md` | Step-by-step setup (Instagram + Meta app + GitHub + testing) |
| `CONTENT-ENGINE.md` | Story format, voting rules, caption/hashtag system, naye arcs likhne ka tarika |
| `content/scenarios.json` | **Story graph** — Farmhouse arc (Day 1 se ending tak, Hinglish) |
| `config.example.json` | Saari settings (voice, timing, hashtags, providers) |
| `scripts/` | Automation ka code (engine, render, votes, publish, token refresh) |
| `state/state.json` | Channel ki "memory" — day counter, plot position, votes |
| `.github/workflows/` | GitHub Actions — daily episode cycle + token refresh |

---

## ⚡ Ek Line Mein Kaam Kaise Karta Hai

```
GitHub Actions (har 3 ghante, free)
   └─ 1. Pichhli reel ke COMMENTS padho (votes count karo)
   └─ 2. Majority winner decide karo → story aage badhao
   └─ 3. Nayi episode banao:
         script (template/LLM) → AI images → TTS voice → FFmpeg video
   └─ 4. Video ko GitHub par host karo (public URL)
   └─ 5. Instagram Graph API se REELS post karo
   └─ 6. State save karo → repeat (forever, bina kisi kaam ke)
```

## 💰 Cost

| Cheez | Tool | Cost |
|---|---|---|
| Scheduler/Server | GitHub Actions (public repo) | **$0** |
| Posting | Instagram Content Publishing API | **$0** |
| Voice | edge-tts (Microsoft Neural voices) | **$0** |
| Images | Pollinations.ai / Pixabay | **$0** |
| Video banane | FFmpeg | **$0** |
| Video hosting | GitHub `media` branch (raw URL) | **$0** |
| **Total** | | **$0/month** |

---

## 🚦 Quick Start (2-3 ghante ka one-time setup)

1. `SETUP.md` → Part A: Instagram account ko **Professional** banao + Meta app banao
2. `SETUP.md` → Part B: Access token generate karo (60-day, auto-refresh hoga)
3. `SETUP.md` → Part C: Ye folder ek **public GitHub repo** mein daalo + Secrets set karo
4. `SETUP.md` → Part D: `python scripts/run_cycle.py --dry-run` se pehli video locally banao
5. `SETUP.md` → Part E: Workflow enable karo → channel live 🚀

---

## ⚠️ Important Notes

- Ye project **sirf official Meta APIs** use karta hai — koi unofficial bot/scraper nahi (account ban ka risk nahi, jab tak engagement spam nahi karoge).
- Content **fiction** hai (zombie story) — reels par AI-content disclosure automatically set hota hai (`is_ai_generated=true`).
- Pehle hafte **thoda manual push** karna padega (friends/groups mein share) — algorithm ko signal chahiye. Poori growth plan `PLAN.md` mein hai.
- Ye **v1** hai — local dry-run pass hai. GitHub runner par pehli baar `dry_run: true` chala kar sanity-check kar lena, phir `force_publish` se live jao. Tuning guide `CONTENT-ENGINE.md` mein hai.
