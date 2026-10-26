"""AI storyboard renderer for ZMB. Requires a server-side POLLINATIONS_KEY."""
from __future__ import annotations
import hashlib, os, time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from common import ROOT, log, run

ENDPOINT="https://gen.pollinations.ai/image/"
IW,IH=720,1280

def build_prompt(ep:dict,line:dict)->str:
    sh=line.get("shot") or {}
    place=str(sh.get("place") or "abandoned highway").replace("_"," ")
    beat=str(sh.get("beat") or "survival moment").replace("_"," ")
    mood=str(sh.get("mood") or "tense")
    tod=str(sh.get("time") or "night")
    action=str(line.get("text") or ep.get("subtitle") or "Survival moment")
    cam=str(sh.get("cam") or "cinematic medium shot").replace("_"," ")
    return ("Premium cinematic stylized 3D animated survival-horror feature frame, highly detailed production "
      "design, expressive faces, believable anatomy, rich textures, volumetric fog, dramatic practical lighting, "
      "atmospheric perspective, teal-blue shadows with warm amber lights, subtle film grain, strong depth, "
      "portrait 9:16 composition. Keep recurring character designs consistent: Max is a young adult survivor "
      "with messy dark hair, charcoal hooded jacket, worn dark backpack and brown cargo trousers; Biscuit is a "
      "small tan dog with dark ears and expressive eyes; Ada is a capable young woman in practical field clothing; "
      "zombies are eerie, non-graphic. "
      f"Season {ep.get('season',1)}, day {ep.get('day',1)}. Location {place}. Time {tod}. Mood {mood}. "
      f"Camera intent {cam}. Beat {beat}. Action {action}. One coherent animated-movie moment, clear staging "
      "and a calm darker lower section for subtitles. No written text, logos, watermarks, UI, collage, split-screen "
      "or storyboard panels.")

def _generate(prompt,key,model,path,seed):
    r=requests.get(ENDPOINT+quote(prompt,safe=""),
      params={"model":model,"width":IW,"height":IH,"seed":seed},
      headers={"Authorization":"Bearer "+key,"Accept":"image/*"},timeout=(20,240))
    if r.status_code>=400:raise RuntimeError("image provider HTTP "+str(r.status_code))
    typ=str(r.headers.get("Content-Type","")).lower()
    if typ and not typ.startswith("image/"):raise RuntimeError("image provider returned non-image content")
    with Image.open(BytesIO(r.content)) as src:
      im=ImageOps.fit(src.convert("RGB"),(IW,IH),method=Image.Resampling.LANCZOS,centering=(.5,.48))
      tmp=path.with_suffix(".tmp.jpg");im.save(tmp,"JPEG",quality=94,optimize=True);tmp.replace(path)

def generate_storyboard_images(cfg,ep,work,Log=log):
    key=(os.environ.get("POLLINATIONS_KEY") or "").strip()
    if not key:raise RuntimeError("POLLINATIONS_KEY required for AI storyboard mode")
    model=str(cfg.get("ai_visual_model") or "flux")
    folder=work/"ai_storyboard"/"images";folder.mkdir(parents=True,exist_ok=True)
    out=[];lines=ep.get("lines") or []
    for i,line in enumerate(lines):
      prompt=build_prompt(ep,line);digest=hashlib.sha256(prompt.encode()).hexdigest()
      path=folder/f"{i:02d}_{digest[:12]}.jpg"
      if path.exists() and path.stat().st_size>20000:
        out.append(path);Log(f"[ai-storyboard] cache hit {i+1}/{len(lines)}");continue
      failure=None
      for attempt in range(3):
        try:
          Log(f"[ai-storyboard] generating scene {i+1}/{len(lines)} ({model})")
          _generate(prompt,key,model,path,int(digest[:8],16)&0x7fffffff);failure=None;break
        except Exception as exc:
          failure=exc;Log(f"[ai-storyboard] scene {i+1} attempt {attempt+1}/3 failed: {type(exc).__name__}")
          if attempt<2:time.sleep(2+attempt*3)
      if failure:raise RuntimeError(f"AI artwork failed on scene {i+1}; check API key, model access and budget") from failure
      out.append(path)
    if not out:raise RuntimeError("episode has no scenes")
    return out

def _font(name,size):
    try:return ImageFont.truetype(str(ROOT/"assets"/"fonts"/name),size)
    except OSError:return ImageFont.load_default()

def _wrap(draw,text,font,maxw,maxlines=3):
    out=[];cur=""
    for word in str(text or "").split():
      trial=word if not cur else cur+" "+word;b=draw.textbbox((0,0),trial,font=font,stroke_width=1)
      if b[2]-b[0]<=maxw or not cur:cur=trial
      else:out.append(cur);cur=word
    if cur:out.append(cur)
    if len(out)>maxlines:out=out[:maxlines];out[-1]=out[-1].rstrip(".,!?")+"…"
    return out

def _center(draw,text,font,cx,y,maxw,fill,maxlines=3):
    for line in _wrap(draw,text,font,maxw,maxlines):
      b=draw.textbbox((0,0),line,font=font,stroke_width=1);tw,th=b[2]-b[0],b[3]-b[1]
      draw.text((cx-tw//2,y),line,font=font,fill=fill,stroke_width=1,stroke_fill=(0,0,0,210));y+=th+9

def _overlay(path,ep,kind,text,w,h):
    im=Image.new("RGBA",(w,h),(0,0,0,0));d=ImageDraw.Draw(im,"RGBA");m=int(w*.058)
    eyebrow=_font("Barlow-Bold.ttf",max(16,int(w*.023)))
    title=_font("ArchivoBlack-Regular.ttf",max(33,int(w*.066)))
    body=_font("Barlow-Bold.ttf",max(22,int(w*.039)))
    small=_font("Barlow-Bold.ttf",max(18,int(w*.032)))
    d.rounded_rectangle((m,58,w-m,122),radius=20,fill=(4,8,15,190),outline=(255,255,255,50),width=1)
    d.text((m+22,77),"ZMB STORIES / INTERACTIVE SURVIVAL",font=eyebrow,fill=(245,248,255,245))
    if kind=="title":
      d.rounded_rectangle((m,180,w-m,470),radius=26,fill=(3,7,14,168),outline=(255,255,255,55),width=2)
      _center(d,"ZOMBIE SURVIVAL",title,w//2,225,w-m*2-36,(255,255,255,255),2)
      _center(d,f"SEASON {ep.get('season',1)} • DAY {ep.get('day',1)}",small,w//2,370,w-m*2-40,(255,103,91,255),1)
    elif kind=="vote":
      top=h-570;d.rounded_rectangle((m,top,w-m,h-58),radius=30,fill=(3,7,14,226),outline=(255,255,255,55),width=2)
      _center(d,"YOU DECIDE",title,w//2,top+30,w-m*2-40,(255,96,88,255),1);y=top+145
      for n,ch in enumerate(ep.get("choices") or [],1):
        d.rounded_rectangle((m+20,y,w-m-20,y+78),radius=18,fill=(24,33,48,238),outline=(255,255,255,40),width=1)
        d.text((m+42,y+18),f"{n}. {str(ch.get('text') or ch.get('key') or '').strip()}",font=body,fill=(248,249,253,255));y+=92
      d.text((m+28,h-110),"COMMENT YOUR CHOICE",font=eyebrow,fill=(255,211,126,255))
    elif kind=="ending":
      top=h-435;d.rounded_rectangle((m,top,w-m,h-58),radius=30,fill=(3,7,14,220),outline=(255,255,255,55),width=2)
      _center(d,"SEASON FINALE",title,w//2,top+48,w-m*2-40,(255,96,88,255),1)
      _center(d,text,body,w//2,top+180,w-m*2-54,(245,248,255,255),2)
    else:
      top=h-365;d.rounded_rectangle((m,top,w-m,h-58),radius=28,fill=(3,7,14,214),outline=(255,255,255,46),width=2)
      _center(d,text,body,w//2,top+42,w-m*2-52,(255,255,255,255),3)
    path.parent.mkdir(parents=True,exist_ok=True);im.save(path,"PNG",optimize=True);return path

def _clip(image,overlay,duration,out,fps,w,h,Log):
    graph=(f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
      f"zoompan=z='min(zoom+0.00034,1.065)':x='max(0,min(iw-iw/zoom,iw/2-iw/zoom/2+sin(on/83)*10))':"
      f"y='max(0,min(ih-ih/zoom,ih/2-ih/zoom/2+cos(on/97)*13))':d=1:s={w}x{h}:fps={fps},setsar=1[bg];"
      f"[1:v]scale={w}:{h},format=rgba[ol];[bg][ol]overlay=0:0,format=yuv420p[v]")
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-loop","1","-framerate",str(fps),"-i",str(image),
      "-loop","1","-framerate",str(fps),"-i",str(overlay),"-filter_complex",graph,"-map","[v]",
      "-t",f"{max(.5,duration):.3f}","-r",str(fps),"-c:v","libx264","-preset","veryfast","-crf","19",
      "-pix_fmt","yuv420p","-an","-movflags","+faststart",str(out)])
    Log(f"[ai-storyboard] encoded {out.name}")

def render_storyboard(cfg,ep,voices,shots,total,audio,work,out_path,fps,out_w,out_h,crf,Log=log):
    started=time.time();images=generate_storyboard_images(cfg,ep,work,Log)
    base=work/"ai_storyboard";od=base/"overlays";cd=base/"clips"
    od.mkdir(parents=True,exist_ok=True);cd.mkdir(parents=True,exist_ok=True);clips=[];line=0
    for i,shot in enumerate(shots):
      if shot.kind=="title":image,kind,text=images[0],"title",""
      elif shot.kind=="line":
        j=min(line,len(images)-1);image,kind,text=images[j],"line",voices[min(line,len(voices)-1)].get("text",shot.text or "");line+=1
      elif shot.kind=="vote":image,kind,text=images[-1],"vote",ep.get("subtitle","")
      elif shot.kind=="ending":image,kind,text=images[-1],"ending",ep.get("subtitle","")
      else:image,kind,text=images[-1],"line",str(shot.text or "")
      ov=_overlay(od/f"overlay_{i:02d}.png",ep,kind,text,out_w,out_h)
      clip=cd/f"clip_{i:02d}.mp4";_clip(image,ov,float(shot.dur),clip,fps,out_w,out_h,Log);clips.append(clip)
    if not clips:raise RuntimeError("AI storyboard produced no clips")
    concat=base/"concat.txt";concat.write_text("".join("file '"+p.resolve().as_posix()+"'\n" for p in clips),encoding="utf-8")
    out_path.parent.mkdir(parents=True,exist_ok=True)
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(concat),"-i",str(audio),
      "-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","medium","-crf",str(crf),"-pix_fmt",
      "yuv420p","-movflags","+faststart","-c:a","aac","-b:a","160k","-ac","2","-ar","44100",
      "-shortest","-t",f"{total:.3f}",str(out_path)])
    probe=run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(out_path)])
    try:dur=float((probe.stdout or "0").strip())
    except ValueError:dur=0.0
    if not out_path.exists() or out_path.stat().st_size<100000 or dur<=0:raise RuntimeError("AI storyboard output validation failed")
    result={"video_path":str(out_path),"duration":dur,"frames":int(round(dur*fps)),"shots":len(shots),
      "render_seconds":round(time.time()-started,1),"visual_mode_used":"ai_storyboard"}
    Log(f"[render] AI STORYBOARD DONE {out_path.name} {dur:.1f}s {out_path.stat().st_size/1e6:.2f} MB")
    return result
