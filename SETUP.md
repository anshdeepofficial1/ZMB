# 🛠️ SETUP GUIDE — Zero se Live Channel tak

Total time: **2-3 ghante** (one-time). Iske baad sab automatic.

---

## Prerequisites

- [ ] Indian phone number/email se Instagram account (naya ya existing)
- [ ] GitHub account
- [ ] PC par: **Python 3.11+** (test ke liye) aur **FFmpeg** (local render test ke liye)
  - Windows: `winget install Python.Python.3.12` aur `winget install Gyan.FFmpeg`
  - FFmpeg install ke baad terminal restart karo, `ffmpeg -version` check karo

---

## PART A — Instagram Side (30 min)

### A1. Account → Professional
1. Instagram app → Settings → **Account type → Switch to Professional** → Creator/Business chuno
2. Username dhyan se chuno (e.g. `zombie.decide.karo` types)
3. Profile: bio mein "Tum decide karo, hum dikhate hain 🧟" + link placeholder

### A2. Meta Developer App
1. [developers.facebook.com](https://developers.facebook.com) → login (koi bhi Facebook account — personal bhi chalega, Page ki zaroorat NAHI hai)
2. **My Apps → Create App** → use case: **"Other"** → type: **"Business"**
3. App Dashboard mein **"Instagram"** product add karo → **"API setup with Instagram business login"** section kholo
4. **Business login settings** mein redirect URI add karo: `https://localhost/` (koi bhi https URL jo tumhare paas ho; sirf token generation ke liye chahiye)
5. Permissions enable karo (app dashboard → Instagram → permissions):
   - `instagram_business_basic`
   - `instagram_business_content_publish`
   - `instagram_business_manage_comments`

> **Note:** Dev mode mein apne hi account ke liye kaam karta hai — **App Review ki zaroorat nahi** jab tak sirf apna account chala rahe ho. Ye personal automation hamesha aise hi chalega.

---

## PART B — Access Token (20 min, phir auto-refresh)

### Option 1 (easy): Dashboard se token
App Dashboard → Instagram → "API setup with Instagram business login" → apna IG account connect karke **Generate Token** button. Jo token mile use **long-lived** mein extend karo (Option 2 ke step 4 jaisa; ya neeche wala script `--exchange-only` ke bina nahi, simple manual: Graph API Explorer se `GET /access_token?grant_type=ig_exchange_token...` chala lo).

### Option 2 (reliable, recommended): `get_token.py` script
```bash
cd Instagram
pip install requests
# 1) Pehle browser mein authorize karo (script URL print karegi):
python scripts/get_token.py --app-id <APP_ID> --app-secret <APP_SECRET>
#    Browser mein Approve karo → page error de sakta hai (localhost) — URL bar se `code` copy karo
# 2) Code exchange karo:
python scripts/get_token.py --app-id <APP_ID> --app-secret <APP_SECRET> --code <CODE>
```
Script output degi:
```
IG_ACCESS_TOKEN=IGAA...   (60-din valid)
IG_USER_ID=17841...
```
**In dono ko note karo — GitHub Secrets mein daalna hai.**

> Secret 'App Dashboard → App settings → Basic → App secret' mein milta hai. Kisi ke saath share mat karo, repo mein mat daalo.

### Token refresh (automatic)
- `refresh-token.yml` workflow hari 1st & 15th ko token refresh karega.
- Simple mode: token ko manually update karna hoga tab (holy mess nahi — workflow fail hone par email aayega).
- **Full-auto mode (recommended):** ek fine-grained Personal Access Token banao (GitHub → Settings → Developer settings → Fine-grained token → sirf tumhara repo → permission: **Secrets: Read & Write**) aur use `GH_PAT` naam se repo secret mein daalo. Ab token refresh workflow khud secret update karega — 100% hands-off.

---

## AI storyboard visuals (needed for selected high-quality mode)

1. Open https://enter.pollinations.ai/keys.
2. Create a server-side secret key with image-generation permission and a budget you are comfortable with.
3. In this repository, open Settings → Secrets and variables → Actions → New repository secret.
4. Name it POLLINATIONS_KEY and paste the key as the value.

AI requests may consume provider credits. Never put the key in chat, source code, browser-side JavaScript or a committed file. Production publishing stops if the key is absent or image generation fails, so the old vector visuals are not silently published again.

## PART C — GitHub Repo (30 min)

### C1. Repo banao (⚠️ PUBLIC karo — ye zaroori hai)
1. github.com → New repository → naam: `zombie-instagram` → **Public** ✅ → Create
   - *Public kyun?* (1) Free plan par private repo ke scheduled workflows reliable nahi hain (2026 verified issue), (2) video hosting ke liye raw URL public chahiye. Koi secret code mein nahi hai, to public safe hai.

### C2. Code push karo
```powershell
cd D:\Storage\Instagram
git init
git add .
git commit -m "Initial commit: zombie apocalypse automation"
git branch -M main
git remote add origin https://github.com/<TUMHARA_USERNAME>/zombie-instagram.git
git push -u origin main
```

### C3. Secrets add karo
Repo → Settings → **Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|---|---|
| `IG_ACCESS_TOKEN` | Part B ka token |
| `IG_USER_ID` | Part B ka user id |
| `GH_PAT` *(optional)* | Full-auto token refresh ke liye fine-grained PAT |
| `POLLINATIONS_KEY` *(optional)* | enter.pollinations.ai se free key (better images, no logo) |
| `PIXABAY_API_KEY` *(optional)* | pixabay.com API key (fallback images ke liye) |

### C4. Repo settings
- Settings → Actions → General → Workflow permissions → **"Read and write permissions"** ✅ (state commit ke liye zaroori)

---

## PART D — Local Dry Run (15 min) — PHIR GHABRANA NAHI

```powershell
cd D:\Storage\Instagram
python -m venv .venv
.venv\Scripts\activate
pip install -r scripts/requirements.txt
copy config.example.json config.json    # phir config.json kholo, handle etc edit karo
python scripts/run_cycle.py --dry-run
```
Ye kya karega:
- `content/scenarios.json` se pehli episode (intro) build karega
- Pollinations se images, edge-tts se Hindi/Indian-English voice, FFmpeg se video → `out/reel_s1_d001.mp4`
- Caption print karega
- **Koi post nahi hoga, koi state change nahi hoga.**

Video dekho. Voice/style pasand nahi aayi to `config.json` mein badlo:
- Voice options suno: `edge-tts --list-voices | findstr hi-IN` (Hindi) / `findstr en-IN` (Indian English)
- Better images: `config.json` mein `"image_provider": "pixabay"` (Pixabay key ke saath) ya Pollinations key daalo
- Music: `assets/music/README.md` ke mutabiq 2-3 free tracks download karke daalo

Repeat: `python scripts/run_cycle.py --dry-run` — jab tak pasand na aaye tune karo (state same rehta hai, hamesha intro banega).

---

## PART E — GO LIVE 🚀

1. GitHub repo → **Actions** tab → workflow `Episode Cycle` → **Run workflow** → ✅ `force_publish: true` (pehli post turant)
   - ⚠️ Pehle `dry_run` manually ek baar GitHub par bhi chala lo (`dry_run: true`) — runner par sab dependencies theek chalein, ye confirm karne ke liye. Artifacts mein video milegi.
2. Pehli reel 5 min mein live hogi. **Comments open** rakho.
3. Uske baad kuch nahi karna — workflow khud 13:00 IST par roz post karega, votes padhega, agla episode banayega.

**Post-launch checklist (pehle hafte):**
- [ ] Comment `1`/`2` karke khud test karo — agle din recap aaya?
- [ ] First comment (choices) reel par dikh raha ho — nahi to manually pin kar do app se
- [ ] Story share + friends ko bhejo (cold start push)
- [ ] Roz 10 min: top comments ko reply/heart karo (engaged audience > dead comments)

---

## PART F — Maintenance (monthly 5 min)

| Kaam | Kab | Kaun |
|---|---|---|
| Token refresh check | 1st & 15th | 🤖 Auto (Actions email fail hue to dekh lo) |
| `content_publishing_limit` sanity | kabhi bhi | Manual (optional): Graph API se GET |
| Naya arc add karna | 2 hafte mein | Tum (`CONTENT-ENGINE.md` dekho) |
| GitHub billing page check | mahine mein 1x | Public repo = $0, bas confirm |

---

## Troubleshooting (error code → fix)

| Error | Matlab | Fix |
|---|---|---|
| `190` / `463` | Token expired/invalid | Part B dubara token banao, secret update karo |
| `9` / `2207042` | Daily publish limit | Impossible daily 1-2 posts par; 24h wait |
| `2207052` / `9004` | Meta video URL fetch nahi kar paya | media branch push hua? URL browser mein khulke check karo; dobara run karo |
| `2207020` | Container expire | 24h mein publish nahi hua — workflow logs dekho, retry |
| `2207027` | Container ready nahi | Script khud poll karta hai; agar phir bhi, re-run |
| `25` / `2207050` | Account restricted | Instagram app mein jaake account status check karo, verification complete karo |
| `36003` | Image aspect ratio | 9:16 fix hai code mein; config na chhero |
| Workflow schedule chal hi nahi raha | GitHub quirk | Repo public hai? Default branch par workflows? Backup: cron-job.org se `workflow_dispatch` (neeche) |
| edge-tts fail | Network/MS service | Retry aata hai; lagatar fail ho to Piper fallback ya baad mein dubara run |

### Optional: Rock-solid scheduling (cron-job.org)
1. [cron-job.org](https://cron-job.org) free account → New cronjob
2. URL: `https://api.github.com/repos/<USER>/<REPO>/actions/workflows/episode.yml/dispatches`
3. Method: POST, Headers: `Authorization: Bearer <GH_PAT>`, `Accept: application/vnd.github+json`, Body: `{"ref":"main"}`
4. Schedule: roz 13:00 IST (07:30 UTC)
5. Fine-grained PAT mein **Actions: Read and write** permission bhi add karo

### Optional: Cloudflare R2 hosting (cleaner, agar GitHub hosting heavy lage)
Free tier: 10GB storage, no egress fees, public bucket URL. `publish.py` mein `media_cdn` section ki jagah R2 URL use kar sakte ho. Zaroorat nahi — GitHub raw kaafi hai.

---

## Files tumhe chhedne hain (baaki touch mat karo)

| File | Kab |
|---|---|
| `config.json` | Voice, timing, hashtags, handle |
| `content/scenarios.json` | Naye story arcs |
| `state/state.json` | Kabhi manually nahi (bot chalata hai) |
| `scripts/*` | Sirf agar technical ho |


## Optional: true AI-generated moving video

The default \`ai_storyboard\` mode produces AI illustrated scenes with cinematic camera movement. For continuous AI-generated character motion, use Pollinations video generation. This is **not guaranteed to be free**.

1. Open https://enter.pollinations.ai/keys and create a server-side key that has video-generation permission.
2. Set a conservative budget in the provider dashboard.
3. Add it to GitHub Actions Secrets as \`POLLINATIONS_KEY\`.
4. After previewing a storyboard, change \`visual_mode\` to \`ai_video\` in the config. Leave it as \`ai_storyboard\` if you need to stay on limited/free image credits.
5. Model \`veo\` and a 6-second source clip are the defaults. Provider duration limits, cost and availability may change. A production run stops on video-generation errors rather than publishing the older vector video.
