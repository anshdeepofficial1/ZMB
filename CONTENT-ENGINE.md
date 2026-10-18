# 🧠 CONTENT ENGINE — Story Format & Authoring Guide

## 1. Episode Format (30-45 sec reel)

```
[0-3s]   HOOK: masla + tension       "Raat 2 baje... garage se awaaz aayi 🧟"
[3-25s]  SCENE: story + stakes        "Gaadi, tools, kal ka ration sab andar hai..."
[25-35s] CHOICE: clearly 2 options    "RUN ya CHECK? Comment 1 ya 2"
[35-40s] CTA: urgency + follow        "Kal majority jeetegi. Follow karo!"
```

Rules:
- Pehle 1.5 second mein visual hook (dark garage/darwaza/chehra) — thumbnail face/scene matter karta hai
- Narration: chhote sentences. Har line < 12 words. "Tum" address karo (viewer = protagonist)
- Choice labels **super clear** (screen par bhi + narration + caption + first comment — 4 jagah)
- Numbers do choices ko: **1 = pehla, 2 = dusra** (comment parsing easy)
- Cliffhanger har episode ke end mein — "agle din pata chalega" nahi, balki choice ke saath end karo

## 2. Voting Rules (engine mein implemented)

| Situation | Result |
|---|---|
| Normal | Sabse zyada votes wala jeeta |
| Tie | `default` choice jeeti |
| Votes < `min_votes` (default 10) | `default` path (story kabhi nahi rukti) |
| Ek user ne multiple comments | Uska **pehla** vote count hota hai (idempotent) |
| Bot/own comments | Ignore |
| Label matching | `1`, `2`, `run`, `bhago`, `check`, `dekhо` etc. — labels list `scenarios.json` mein per choice |

**Recap format (agli episode ke shuru mein):**
`"Kal tumme se 68% ne kaha: CHECK. Ab dekho kya hua..."` — engine automatically narration mein prepend karta hai.

## 3. Stats System

Screen par HUD: `HP 100 · NOISE 20 · SUPPLIES 60`

| Stat | Meaning | Kaise badalta hai |
|---|---|---|
| HP | Health/risk | Danger choices -5..-25 |
| NOISE | Kitni awaaz kar rahe ho | Loot/bhaag -10, chupke se +5 (less noise = safe) |
| SUPPLIES | Ration/tools | Careful choices +, wasteful - |
| TRUST | (optional) companion trust | Risky choices badalte hain |

Endings stats se narratively flavoured hote hain (visual only — engine abhi fixed endings deta hai; extended version mein stat-based endings add ho sakte hain).

## 4. Caption System (auto-generated)

```
{hook line} 🧟

{recap line — agar kal votes the}

Tum decide karoge:
1️⃣ RUN – bhaag jao
2️⃣ CHECK – jaake dekho
Comment mein 1 ya 2 likho. Kal sabse zyada votes wala hi hoga!

🎬 Ye fiction hai. Story tum la-o-ge.
#{4-5 rotated hashtags}
```

- Hashtags: pool se 4-5 rotate hote hain, same block repeat nahi hota (policy-safe)
- Hashtag pool (config): `#zombieapocalypse #survivalreels #interactivereels #hindireels #chooseyourownadventure #hindustory #reelsindia #apocalypse #zombieindia`
- AI disclosure: `is_ai_generated=true` API par auto-set

## 5. Posting Cadence & Timing

- **1 reel/day @ 13:00 IST** (lunch scroll peak, India)
- Optional 2nd @ 20:00 IST (prime time) — quota 50-100/day hai, koi issue nahi
- Weekly Sunday: "story so far" recap reel (manual trigger se auto-generate ho sakti hai)
- Har episode ke baad ~6 checkpoints (3h apart) mein votes update hote hain

## 6. Story Graph — Farmhouse Arc (built-in)

```
intro (DIN 1: setting + qaida)
  └─► garage_sound (DIN 2: RUN ya CHECK?)          ← TUMHARA EXAMPLE
        ├─ RUN ──► run_fields (khet: pipe ya figure?)
        │            ├─ pipe ──► pipe_hide ──► figure_meet
        │            └─ figure ──► figure_meet (reply ya bhaago?)
        │                            ├─ reply ──► friend_found ──► radio_room
        │                            └─ bhaago ──► solo_escape ──► truck_problem
        └─ CHECK ─► check_garage (basement ya trunk?)
                     ├─ basement ──► basement_dark ──► radio_room
                     └─ trunk ──► truck_keys ──► truck_problem (petrol ya depot?)
                                         ├─ petrol ──► truck_ready (raat ya subah?)
                                         │                └─ ending: night_drive / dawn_drive
                                         └─ depot ──► depot_run (ending)
                          radio_room (depot ya radio tower?)
                             ├─ depot ──► depot_run (ending)
                             └─ tower ──► tower_run (ending — BEST if stats high)
```

4 endings + season-2 location meta-vote. ~2 hafte ka content.

## 7. Naya Arc Likhne ka Tarika (tumhara creative kaam)

`content/scenarios.json` mein naya arc add karo:

```json
"factory": {
  "title": "Factory ka Andhera",
  "start": "intro",
  "nodes": {
    "intro": {
      "kind": "story",
      "day_title": "DIN 1 · Factory",
      "hook": "Factory ka gate khula hai... andar se machine ki awaaz aa rahi hai. Par bijli 3 din se gayi hai.",
      "narration": ["{location} mein tum ho...", "...", "..."],
      "images": ["dark abandoned indian factory interior, shafts of light, dust", "..."],
      "effects": {"noise": 5},
      "next": "machine_sound"
    },
    "machine_sound": {
      "kind": "vote",
      "day_title": "DIN 2 · Chalu Machine",
      "hook": "Machine chal rahi hai. Koi ise chala raha hai... ya kuch aur?",
      "narration": ["...", "...", "Ab batao:"],
      "images": ["...", "..."],
      "choices": [
        {"key": "off", "text": "BAND KARO 🔌", "labels": ["off","band","1"], "next": "power_room", "effects": {"noise": -10}},
        {"key": "follow", "text": "DIKHO KAUN HAI 🔎", "labels": ["follow","dekho","2"], "next": "foreman", "effects": {"hp": -5}}
      ],
      "default": "off"
    }
  }
}
```

**Rules of thumb:**
- 10-14 nodes per arc, 2 endings minimum
- Har vote node mein `default` zaroor
- `effects` chhote rakho (-25..+15)
- Images: 3-4 per episode, prompts cinematic + specific (aap `config.json` ka `image_style_prefix` automatically lagta hai)
- `{location}` placeholder use karo — season 2 ke liye wahi arc nayi jagah chala sakte ho
- Ending node: `"kind": "ending"`, choices mein `"next_arc": "factory"` + `"location_text": "..."`

## 8. Growth Playbook (manual, chhota par powerful)

1. **First hour is king:** post ke pehle 60 min mein comments ka reply (manual, app se). Har reply = dusra comment = algorithm boost.
2. **Comment bait choices:** kabhi kabhi controversial choice do ("gun lo ya radio — dono nahi le sakte") — log argue karenge, comments double.
3. **Pin (manually):** app se apna first comment pin karte raho (API se nahi ho sakta).
4. **Shoutout swaps:** same-niche pages (horror/gaming/story) se reel-for-reel promo.
5. **Story flood:** har nayi reel ko apni story par 2x share karo (poll sticker "1 ya 2?" ke saath — story stickers manual hain).
6. **Cross-post:** same video YouTube Shorts/Facebook par (ek hi baar manually, 2 min).
7. **Trending audio ka jugaad:** hafte mein 1 reel manually (template se bani video download + IG app mein trending audio + post) — reach injection.
8. **Bench:** kya kaam kar raha hai — hook style, voice, time. Har 2 hafte review.

## 9. Safety & Compliance (non-negotiable)

- ✅ Fiction disclaimer hamesha caption mein (script ek fixed line daalta hai)
- ✅ `is_ai_generated=true` API par ON
- ❌ Koi auto-like/auto-follow/auto-DM nahi — sirf content publish + apne media ke comments padhna
- ❌ Gore/violence extreme nahi — thriller-horror tone (community guidelines safe)
- ✅ Hashtags rotate, same caption pattern nahi — anti-spam
- ✅ Music sirf Pixabay (license-free) — Instagram library music API se lagti hi nahi hai

## 10. Tuning Troubleshooting

| Problem | Fix |
|---|---|
| Votes kam (<10) | CTA bold karo; reel end mein 2 sec zyada choice dikhao; first comment aur pinned karo; time 20:00 IST try karo |
| Views kam | Hook 1.5s mein punch; thumbnail scene (chehra/darwaza) choose karo; cover image set karo (`thumb_offset`) |
| Log bore ho rahe | Stats visible karo, arc chhota karo (10 episodes max), ending jaldi do |
| Comments mein "video kaise banti hai" | Engage karo + agla reel idea (meta content pillar!) |
