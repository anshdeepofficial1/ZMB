"""Free Kokoro neural narration with model-predicted word timestamps. No robotic fallback."""
import argparse, json, re
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline

SR=24000
def narrate(story, out):
    out=Path(out); out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    pipe=KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", device="cpu")
    samples=[]; scenes=[]; words=[]; cursor=0
    for i, shot in enumerate(story["scenes"]):
        start=cursor/SR; before=len(words)
        for res in pipe(shot["line"], voice=story["voice"], speed=story["speed"], split_pattern=None):
            if res.audio is None: raise RuntimeError("Kokoro returned no audio")
            a=res.audio.detach().cpu().numpy().astype(np.float32).reshape(-1)
            if not len(a) or not np.isfinite(a).all(): raise RuntimeError("Invalid narration")
            for token in (res.tokens or []):
                word=re.sub(r"^[^\w]+|[^\w]+$", "", token.text)
                a_ts=getattr(token,"start_ts",None); b_ts=getattr(token,"end_ts",None)
                if word and a_ts is not None and b_ts is not None and b_ts>a_ts:
                    words.append({"word":word.lower(),"start":cursor/SR+float(a_ts),"end":cursor/SR+min(len(a)/SR,float(b_ts))})
            samples.append(a); cursor+=len(a)
        if len(words)==before: raise RuntimeError(f"No timed tokens in scene {i}")
        pad=np.zeros(round(SR*(.85 if i==len(story["scenes"])-1 else .20)),np.float32)
        samples.append(pad);cursor+=len(pad)
        scenes.append({"start":start,"end":cursor/SR,"line":shot["line"]})
    audio=np.concatenate(samples)
    if np.max(np.abs(audio))<.005: raise RuntimeError("Silent narration")
    sf.write(out/"voice.wav",audio,SR,subtype="PCM_16")
    (out/"timing.json").write_text(json.dumps({"scenes":scenes,"words":words,"duration":cursor/SR},indent=2))
    print(f"Kokoro voice {story['voice']}: {cursor/SR:.2f}s, {len(words)} timed tokens")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--story",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    args=p.parse_args();narrate(json.loads(args.story.read_text()),args.out)
