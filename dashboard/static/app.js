/* ZMB Control Room SPA — vanilla JS, polling-based realtime */
const $ = s => document.querySelector(s);
const el = t => document.createElement(t);
const fmtMB = b => (b / 1e6).toFixed(1) + " MB";

const CFG_FIELDS = [
  ["visual_mode", "Visual mode (procedural / ai_storyboard / ai_video)"],
  ["ai_visual_model", "AI image model"],
  ["ai_video_model", "AI video model ID (e.g. google/veo-3.1-fast)"],
  ["ai_video_clip_seconds", "AI video clip duration (4–8 seconds)"],
  ["publish_time_ist", "Daily publish time (IST, HH:MM)"],
  ["publish_every_hours", "Publish cadence hours"],
  ["publish_prepare_hours", "Preparation window hours"],
  ["voice", "Narration voice"],
  ["voice_rate", "Narration speed"],
  ["hashtags_per_post", "Hashtags per post"],
  ["music_volume", "Background music volume"],
  ["render.width", "Internal render width"],
  ["render.height", "Internal render height"],
  ["render.out_width", "Output width"],
  ["render.out_height", "Output height"],
  ["render.fps", "Output FPS"],
  ["render.jobs", "Frame render workers"],
  ["render.crf", "Video quality CRF"],
  ["render.caption_size", "Caption size"]
];
const STATE_KEYS = ["post_to_instagram","caption_footer","publish_after_ist_hour",
  "first_comment","hashtags","music_file","caption_size"];
const RENDER_KEYS = ["width","height","out_w","out_h","fps","jobs","crf"];

/* ── toasts ── */
function toast(msg, cls = "") {
  const t = el("div");
  t.className = "toast " + cls; t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 350); }, 3800);
}

/* ── ember particles ── */
(() => {
  const c = $("#embers"), x = c.getContext("2d");
  let W, H, parts = [];
  const init = () => {
    W = c.width = innerWidth; H = c.height = innerHeight;
    parts = Array.from({length: Math.min(46, W / 30)}, () => ({
      x: Math.random() * W, y: Math.random() * H,
      r: .6 + Math.random() * 2.4, vy: .25 + Math.random() * .8,
      vx: (Math.random() - .5) * .35, a: .1 + Math.random() * .5,
      hue: 22 + Math.random() * 18,
    }));
  };
  addEventListener("resize", init); init();
  (function loop() {
    x.clearRect(0, 0, W, H);
    for (const p of parts) {
      p.y -= p.vy; p.x += p.vx + Math.sin(p.y / 60) * .15;
      if (p.y < -10) { p.y = H + 10; p.x = Math.random() * W; }
      const g = x.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
      g.addColorStop(0, `hsla(${p.hue},100%,62%,${p.a})`);
      g.addColorStop(1, "transparent");
      x.fillStyle = g; x.fillRect(p.x - p.r * 4, p.y - p.r * 4, p.r * 8, p.r * 8);
    }
    requestAnimationFrame(loop);
  })();
})();

/* ── api helper ── */
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let m = "HTTP " + r.status;
    try { m = (await r.json()).detail || m; } catch {}
    throw new Error(m);
  }
  return r.json();
}

/* ── clock ── */
setInterval(() => {
  $("#clock").textContent = new Date().toLocaleTimeString("en-IN", {hour12: false});
}, 1000);

/* ── overview ── */
function gauge(label, key, val) {
  const f = {hp: "f-hp", noise: "f-noise", food: "f-food", dog: "f-dog"}[key] || "f-food";
  const pct = Math.max(3, Math.min(100, val));
  return `<div class="gauge ${f}">
    <div class="glbl"><b>${(label || key).toUpperCase()}</b><span class="num" data-count="${val}">${val}</span></div>
    <div class="grow"><div class="fill" style="width:${pct}%"></div></div></div>`;
}

async function loadOverview() {
  try {
    const o = await api("/api/overview");
    $("#handle").textContent = `${o.handle} · S${o.season} D${o.day} · ${o.posted} posted`;
    $("#tagSeason").textContent = `S${o.season} D${o.day}`;
    $("#arcTitle").textContent = o.arc_title || "—";
    $("#location").textContent = o.location || "—";
    const labels = o.stats_labels || {};
    $("#gauges").innerHTML = Object.entries(o.stats || {})
      .map(([k, v]) => gauge(labels[k], k, v)).join("");
    if (o.next_node) {
      $("#nextNode").innerHTML = `<span class="nodeid">${o.next_node.id}</span>` +
        `<span class="nplace">${o.next_node.place || ""}</span>`;
      $("#nodeChoices").innerHTML = (o.next_node.choices || [])
        .map(c => `<span class="choice">🗳 ${c}</span>`).join("");
    }
    $("#tokenState").textContent = o.token ? "live" : "missing";
    $("#tokenState").className = "val " + (o.token ? "ok" : "warn");
    $("#setupCheck").innerHTML = o.token
      ? `✅ Token detected — <b>full publish</b> mode available.`
      : `⚠️ <b>IG_ACCESS_TOKEN</b> set nahi hai — render dry-run par chal raha hai. Setup steps follow karo.`;
    if (o.latest_video) loadVideo(o.latest_video.name);
  } catch (e) { toast("overview: " + e.message, "err"); }
}

function glitchDigits(node) {
  node.querySelectorAll("[data-count]").forEach(n => {
    const v = +n.dataset.count; if (!v) return;
    let cur = 0; const step = Math.max(0.4, v / 24);
    const iv = setInterval(() => {
      cur = Math.min(v, cur + step); n.textContent = Math.round(cur);
      if (cur >= v) clearInterval(iv);
    }, 28);
  });
}
const _mo = new MutationObserver(() =>
  glitchDigits(document.querySelector("#gauges") || document.body));
document.addEventListener("DOMContentLoaded", () => _mo.observe($("#gauges"), {childList: true}));

/* ── episodes ── */
async function loadVideo(name) {
  const v = $("#player");
  $("#playerWrap").classList.add("has");
  v.src = "/api/video/" + encodeURIComponent(name);
  v.load();
}
async function loadEpisodes() {
  try {
    const d = await api("/api/episodes");
    $("#epCount").textContent = d.videos.length;
    $("#vidList").innerHTML = d.videos.map(v =>
      `<div class="viditem" data-n="${v.name}"><span>${v.name}</span><span class="sz">${fmtMB(v.bytes)}</span></div>`)
      .join("") || `<div style="color:var(--dim);font-size:12px">no reels yet</div>`;
    document.querySelectorAll(".viditem").forEach(it => it.onclick = () => loadVideo(it.dataset.n));
    if (d.videos[0] && !$("#player").src) loadVideo(d.videos[0].name);
  } catch (e) {}
}

/* ── story map ── */
async function loadStory() {
  try {
    const s = await api("/api/story");
    $("#arcName").textContent = s.current_arc;
    $("#map").innerHTML = s.nodes.map(n => {
      const isEnd = /^end/.test(n.id);
      const cls = ["mnode", n.vote ? "vote" : "", isEnd ? "end" : "",
                   n.id === s.node ? "cur" : ""].join(" ");
      return `<div class="${cls}" title="${n.place}"><b>${n.id}</b>${n.day ? "Day " + n.day : ""}${n.vote ? " · 🗳" : ""}</div>`;
    }).join("");
    if (s.nodes.length) {
      const cur = document.querySelector(".mnode.cur");
      if (cur) cur.scrollIntoView({block: "nearest", inline: "nearest"});
    }
  } catch (e) {}
}

/* ── config form ── */
function flatten(cfg, base) {
  const dotted = [];
  const walk = (o, pfx) => {
    for (const [k, v] of Object.entries(o || {})) {
      if (v && typeof v === "object" && !Array.isArray(v)) walk(v, pfx + k + ".");
      else dotted.push([pfx + k, v]);
    }
  };
  walk(cfg, "");
  return dotted;
}
async function loadConfig() {
  try {
    const cfg = await api("/api/config");
    const flat = new Map(flatten(cfg));
    const form = $("#cfgForm"); form.innerHTML = "";
    for (const [path, label] of CFG_FIELDS) {
      const val = flat.get(path);
      if (val === undefined) continue;
      const row = el("div"); row.className = "fld";
      const isLong = typeof val === "string" && val.length > 48;
      row.innerHTML = `<label title="${path}">${label}</label>`;
      const inp = el(isLong ? "textarea" : "input");
      if (!isLong) inp.type = typeof val === "number" ? "number" : "text";
      inp.value = val === true ? "true" : val === false ? "false" : val;
      inp.dataset.path = path;
      row.appendChild(inp); form.appendChild(row);
    }
  } catch (e) {}
}
$("#btnSaveCfg").onclick = async () => {
  const body = {};
  for (const inp of document.querySelectorAll("#cfgForm input,#cfgForm textarea")) {
    let v = inp.value;
    const path = inp.dataset.path;
    if (/^(true|false)$/i.test(v)) v = v.toLowerCase() === "true";
    else if (v !== "" && !isNaN(v)) v = +v;
    let cur = body;
    const segs = path.split(".");
    segs.forEach((s, i) => {
      if (i === segs.length - 1) cur[s] = v;
      else { cur[s] = cur[s] || {}; cur = cur[s]; }
    });
  }
  try {
    await api("/api/config", {method: "PUT", headers: {"Content-Type": "application/json"},
                              body: JSON.stringify(body)});
    toast("config saved ✓", "ok");
  } catch (e) { toast("save failed: " + e.message, "err"); }
};

/* ── runs / pipeline ── */
let curRun = null, runTimer = null;
async function startRun(mode) {
  try {
    const r = await api("/api/trigger?mode=" + mode, {method: "POST"});
    if (!r.ok) { toast(r.error, "err"); return; }
    curRun = r.id; watchRun(r.id, mode);
    toast(`run started: ${mode} (${r.id.slice(-6)})`, "ok");
  } catch (e) { toast("trigger: " + e.message, "err"); }
}
async function watchRun(rid, mode) {
  clearInterval(runTimer);
  $("#stepper").querySelectorAll(".step").forEach(s => { s.className = "step"; });
  const steps = [...$("#stepper").querySelectorAll(".step")];
  let lastLen = 0;
  runTimer = setInterval(async () => {
    try {
      const d = await api(`/api/runs/${rid}/log`);
      if (d.log.length !== lastLen) {
        const box = $("#runLog");
        box.textContent = d.log;
        box.scrollTop = box.scrollHeight;
        lastLen = d.log.length;
      }
      const finished = d.log.includes("[exit]");
      const fail = finished && !/SUCCESS|dry-run complete|codes?=\s*0|code=0/.test(d.log.split("[exit]")[0]);
      // map progress from log text to steps
      const marks = [["votes tallied", 0], ["episode:", 1], ["voice", 2], ["frame ", 3],
                     ["encoded ->", 4], ["SUCCESS", 5]];
      let upto = -1;
      for (const [needle, idx] of marks)
        if (d.log.slice(0, d.log.lastIndexOf(needle) + 1).toLowerCase().includes(needle)) upto = idx;
      steps.forEach((s, i) => {
        if (!finished) s.className = "step" + (i < upto ? " done" : i === upto + 1 ? " cur" : "");
        else s.className = "step " + (fail ? "cur" : " done");
      });
      $("#runMeta").textContent = finished
        ? `run ${rid.slice(-6)} finished — reload data…`
        : `run ${rid.slice(-6)} (${mode}) running… ${lastLen} bytes logged`;
      if (finished) {
        clearInterval(runTimer);
        loadOverview(); loadEpisodes(); loadStory();
        toast(fail ? "run finished (check log)" : "run complete ✓", fail ? "err" : "ok");
      }
    } catch (e) { clearInterval(runTimer); toast("log: " + e.message, "err"); }
  }, 1200);
}

/* ── buttons ── */
$("#btnDry").onclick = () => { $("#runLog").textContent = ""; startRun("dry"); };
$("#btnStills").onclick = () => { $("#runLog").textContent = ""; startRun("stills"); };
$("#btnFull").onclick = () => startRun("full");

/* ── boot + refresh loop ── */
document.addEventListener("DOMContentLoaded", () => {
  loadOverview(); loadEpisodes(); loadStory(); loadConfig();
  setInterval(loadOverview, 20000);
  setInterval(loadEpisodes, 30000);
});
