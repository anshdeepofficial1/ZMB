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
mix="[1:a]highpass=f=70,acompressor=threshold=0.125:ratio=2:attack=10:release=100,volume=1.15[v];[2:a]volume=0.65[s];[v][s]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.92[a]"
dest=OUT/"hourglass_guardian_neural.mp4"
run("ffmpeg","-y","-v","error","-i",OUT/"visual.mp4","-i",OUT/"voice.wav","-i",OUT/"sound.wav","-filter_complex",mix,"-map","0:v","-map","[a]","-vf","scale=1080:1920:flags=lanczos,fps=30","-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest",dest)
run("ffmpeg","-v","error","-i",dest,"-f","null","-")
info=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(dest)]))
v=next(s for s in info["streams"] if s["codec_type"]=="video");a=next(s for s in info["streams"] if s["codec_type"]=="audio")
assert (v["width"],v["height"],v["codec_name"])==(1080,1920,"h264") and a["codec_name"]=="aac"
assert abs(float(info["format"]["duration"])-timing["duration"])<.4
(OUT/"qa.json").write_text(json.dumps({"decoded":True,"voice":story["voice"],"duration":timing["duration"],"scene_count":len(new),"publish_approved":False,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest()},indent=2))
print("Verified rendered MP4:",dest)
