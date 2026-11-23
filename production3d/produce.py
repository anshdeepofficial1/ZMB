"""Render the exact reviewed 3D pilot with offline neural TTS and retimed sound design."""
from pathlib import Path
import hashlib,json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"out"; OUT.mkdir(exist_ok=True)
STORY=ROOT/"hourglass.json"
bundle=ROOT/"hourglass-engine.tar.xz"
assert hashlib.sha256(bundle.read_bytes()).hexdigest()=="306e102e29837fcc3fa3fa1d1e82d1e809b3a79c9335ee2377be236f24df2cc3"
with tarfile.open(bundle) as archive:
    assert set(archive.getnames())=={"render.py","sound.py"}
    archive.extractall(OUT,filter="data")
def run(*args):subprocess.run([str(x) for x in args],check=True)
story=json.loads(STORY.read_text()); base=story["scenes"]
# Render the original authored score and foley against its baseline timeline.
(OUT/"timing.json").write_text(json.dumps({"scenes":base,"words":[],"duration":base[-1]["end"]}))
run(sys.executable,OUT/"sound.py")
(OUT/"sound.wav").rename(OUT/"sound_base.wav")
run(sys.executable,ROOT/"neural_voice.py","--story",STORY,"--out",OUT)
timing=json.loads((OUT/"timing.json").read_text()); new=timing["scenes"]
assert len(new)==len(base)==11
# Fail closed when neural token timestamps cannot drive a single coherent caption track.
# This checks the real Kokoro timing output before rendering any caption frames.
words=timing.get("words", [])
if not words:
    raise RuntimeError("Missing neural word timestamps for captions")
last_start=-1.0
for index, token in enumerate(words):
    start=float(token["start"]); end=float(token["end"])
    if not token.get("word") or not (0 <= start < end <= timing["duration"] + 0.05):
        raise RuntimeError(f"Invalid caption token {index}: {token}")
    if start < last_start - 0.02:
        raise RuntimeError(f"Out-of-order caption token {index}: {token}")
    if not any(shot["start"] - 0.05 <= start < shot["end"] + 0.05
               and end <= shot["end"] + 0.15 for shot in new):
        raise RuntimeError(f"Caption token outside narration scene {index}: {token}")
    last_start=start
for index, shot in enumerate(new):
    if not any(shot["start"] - 0.05 <= float(w["start"]) < shot["end"] + 0.05 for w in words):
        raise RuntimeError(f"Scene {index+1} has no timed caption words")
# Stretch each music/foley segment to its matching spoken shot, keeping pitch.
filters=[]
for i,(a,b) in enumerate(zip(base,new)):
    dur=b["end"]-b["start"]; ratio=(a["end"]-a["start"])/dur
    factors=[]
    while ratio<.5: factors.append(.5);ratio/=.5
    while ratio>2: factors.append(2);ratio/=2
    factors.append(ratio)
    atempo=",".join(f"atempo={f:.8f}" for f in factors)
    filters.append(f"[0:a]atrim=start={a['start']}:end={a['end']},asetpts=PTS-STARTPTS,{atempo},apad,atrim=duration={dur:.8f}[s{i}]")
filters.append("".join(f"[s{i}]" for i in range(len(base)))+f"concat=n={len(base)}:v=0:a=1[s]")
run("ffmpeg","-y","-v","error","-i",OUT/"sound_base.wav","-filter_complex",";".join(filters),"-map","[s]","-c:a","pcm_s16le",OUT/"sound.wav")
# Retain exact render geometry, caption timing and scene action. Only output resolution is upscaled.
run(sys.executable,OUT/"render.py","--preview")
run(sys.executable,OUT/"render.py")
mix="[1:a]highpass=f=70,acompressor=threshold=0.125:ratio=2:attack=10:release=100,volume=2.3[v];[2:a]volume=0.65[s];[v][s]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.92:level=0[a]"
dest=OUT/"hourglass_guardian_neural.mp4"
run("ffmpeg","-y","-v","error","-i",OUT/"visual.mp4","-i",OUT/"voice.wav","-i",OUT/"sound.wav","-filter_complex",mix,"-map","0:v","-map","[a]","-vf","scale=1080:1920:flags=lanczos,fps=30","-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest",dest)
run("ffmpeg","-v","error","-i",dest,"-f","null","-")
info=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(dest)]))
v=next(s for s in info["streams"] if s["codec_type"]=="video");a=next(s for s in info["streams"] if s["codec_type"]=="audio")
assert (v["width"],v["height"],v["codec_name"])==(1080,1920,"h264") and a["codec_name"]=="aac"
assert abs(float(info["format"]["duration"])-timing["duration"])<.4
# Fail closed on silent or static shots, and export evidence from the final encoded video.
import re
def metric(*args):
    return subprocess.run(["ffmpeg","-hide_banner","-nostats",*map(str,args),"-f","null","-"],capture_output=True,text=True,check=True).stderr
shot_qa=[]
for i, shot in enumerate(new):
    start=shot["start"]; duration=shot["end"]-start
    log=metric("-ss",start,"-t",duration,"-i",dest,"-an","-vf","fps=5,scale=180:320,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG")
    values=[float(x) for x in re.findall(r"lavfi.signalstats.YAVG=([0-9.]+)",log)]
    if not values or max(values)<0.35:
        raise RuntimeError(f"Static or unmeasurable shot {i+1}: {values}")
    # Measure the upper 65% separately: changing lower captions must not pass as scene motion.
    action_log=metric("-ss",start,"-t",duration,"-i",dest,"-an","-vf","fps=5,crop=iw:ih*0.65:0:0,scale=180:208,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG")
    action_values=[float(x) for x in re.findall(r"lavfi.signalstats.YAVG=([0-9.]+)",action_log)]
    if not action_values or max(action_values)<0.35:
        raise RuntimeError(f"No measurable upper-frame action in shot {i+1}")
    action_mean=sum(action_values)/len(action_values)
    # Low motion is a review flag, not proof of missing physical action.
    action_review=action_mean<1.0
    # A single camera cut cannot substitute for sustained on-screen action.
    sustained_action_fraction=sum(v>=0.35 for v in action_values)/len(action_values)
    if sustained_action_fraction<0.25:
        action_review=True
    audio_log=metric("-ss",start,"-t",duration,"-i",OUT/"voice.wav","-vn","-af","volumedetect")
    m=re.search(r"mean_volume: (-?[0-9.]+) dB",audio_log)
    if not m or float(m.group(1)) < -45:
        raise RuntimeError(f"Silent narration in shot {i+1}")
    run("ffmpeg","-y","-v","error","-ss",start+duration*.5,"-i",dest,"-frames:v","1","-vf","scale=360:640",OUT/f"preview_final_{i+1:02d}.jpg")
    shot_qa.append({"scene":i+1,"line":shot["line"],"start":start,"end":shot["end"],"motion_mean":sum(values)/len(values),"motion_peak":max(values),"upper_action_mean":action_mean,"upper_action_peak":max(action_values),"low_action_review":action_review,"sustained_action_fraction":sustained_action_fraction,"voice_mean_db":float(m.group(1))})
review_blockers=[f"Scene {shot['scene']}: insufficient sustained upper-frame motion" for shot in shot_qa if shot["low_action_review"]]
# These metrics cannot establish correct physical action, glass transparency, or voice quality.
review_blockers.extend(["Human review required: sand/glass physics, story-to-action continuity, captions, narration and soundtrack", "Owner approval and exact target account/caption missing"])
(OUT/"qa.json").write_text(json.dumps({"release_ready":False,"review_blockers":review_blockers,"decoded":True,"shots":shot_qa,"voice":story["voice"],"duration":timing["duration"],"scene_count":len(new),"publish_approved":False,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest()},indent=2))
print("Verified rendered MP4:",dest)
