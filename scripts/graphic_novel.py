"""Original editorial 2D graphic-novel pilot. No old scene or actor renderer.
Every beat is a separately composed 9:16 shot; motion is driven by narration time.
"""
import math
import random
import svgkit as s

W,H=1080,1920
INK="#17213a"
PAPER="#f7e6c8"
TEAL="#42b7ad"
RUST="#e97c51"
AMBER="#ffca75"
def g(x,y,scale,body):
    return s.g(f"translate({s.n(x)} {s.n(y)}) scale({s.n(scale)})",body)
def p(d,c,stroke=INK,sw=7,op=None):
    return s.path(d,c,stroke,sw,op=op)
def line(x,y,X,Y,c=INK,w=6,op=None):
    return s.line(x,y,X,Y,c,w,op=op)
def smooth(x): return s.ease(s.clamp(x,0,1))
def wave(t,f=1): return math.sin(t*math.tau*f)
def poly(points,c,stroke=INK,w=6):
    return p("M "+" L ".join(f"{s.n(x)} {s.n(y)}" for x,y in points)+" Z",c,stroke,w)
def text(x,y,v,size,c=PAPER,anchor="start"):
    return s.text(x,y,v,size,"Barlow",c,anchor=anchor,weight="bold",ls=2)

DEFS=(
    s.lin_grad("sky",[(0,"#263e65",1),(55,"#508f99",1),(100,"#efbb91",1)])
    +s.lin_grad("road",[(0,"#526579",1),(100,"#273449",1)])
    +s.lin_grad("coat",[(0,"#637e85",1),(100,"#273b4a",1)])
    +s.lin_grad("glass",[(0,"#8ed4cd",1),(100,"#315975",1)])
    +s.lin_grad("warm",[(0,"#fff0a4",1),(100,"#e89656",1)])
    +s.rad_grad("lamp",[(0,"#ffe5a2",.85),(55,"#f0b96f",.25),(100,"#f0b96f",0)])
    +s.lin_grad("fade",[(0,"#24394b",0),(100,"#18283d",1)])
    +'<pattern id="hatch" width="15" height="15" patternUnits="userSpaceOnUse"><path d="M -3 15 L 15 -3 M 8 18 L 18 8" stroke="#192941" stroke-width="2" opacity=".15"/></pattern>'
)
# An angular, consistent illustrated Max. No old character rig.
def head(t, fear=0, facing=1):
    blink=abs(wave(t*.34+0.14))>.995
    eye=2 if blink else 13+fear*4
    b=[
        p("M -82 1 Q -95 -83 -22 -113 Q 55 -135 88 -65 L 76 30 L 47 71 L -14 83 L -65 50 Z","#202837"),
        p("M -60 -51 Q -39 -81 40 -70 L 73 -39 L 84 10 L 65 48 L 30 78 Q -21 76 -56 39 Z","#efb48e"),
        p("M 37 -63 L 73 -39 L 84 10 L 64 48 L 30 78 L 11 50 L 34 20 Z","#cd825f","none",0),
        s.ell(-60,1,15,22,"#e4a27d",INK,5),
        p("M -80 -30 L -89 -81 L -54 -75 L -25 -121 L -12 -88 L 24 -126 L 38 -97 L 79 -104 L 89 -51 L 62 -32 L 47 -70 L 10 -53 L -15 -78 L -49 -41 Z","#202837",INK,6),
        p("M -65 -78 Q -20 -109 35 -100","none","#596879",6),
        p(f"M -35 {s.n(-27-fear*12)} L -9 -31 M 19 -31 L 45 {s.n(-24-fear*12)}","none",INK,7),
        s.ell(-21,-9,13,eye,"#fff0d7",INK,4),
        s.ell(30,-9,13,eye,"#fff0d7",INK,4),
        s.circ(-17,-8,5,INK),s.circ(34,-8,5,INK),
        p("M 8 -3 L 19 18 L 8 22","none","#9a523f",5),
        (s.ell(12,43,16,10+fear*5,"#542c32",INK,4) if fear>.55 else p("M -7 43 Q 11 36 28 44","none",INK,5)),
        p("M -35 28 L -22 33 M 36 30 L 47 27","none","#bf7258",4)
    ]
    return s.g(f"scale({facing} 1)","".join(b))
def max_actor(t, action="walk",fear=0,pack=True,light=False):
    walk=action=="walk"
    stride=wave(t,1.05)*42 if walk else 0
    bob=abs(wave(t,1.05))*9 if walk else wave(t,.34)*4
    # The limbs share explicit endpoints; flashlight follows the right wrist.
    right=(104+stride*.2,-213) if not light else (146,-298+wave(t,.7)*9)
    if action=="point": right=(203+wave(t,.4)*6,-340+wave(t,.6)*9)
    if action=="freeze": right=(108,-277)
    left=(-105-stride*.38,-194)
    if action=="grab": left=(-147,-278)
    out=[s.ell(0,4,111,16,"#142638",op=.45)]
    if pack:
        out += [p("M -70 -392 Q -153 -397 -158 -316 L -143 -225 L -60 -220 Z","#a66045"),
                p("M -136 -328 L -83 -323 L -77 -262 L -135 -263 Z","#cf8b54"),
                line(-145,-297,-79,-291,"#f5c38a",5)]
    for x,off in [(-37,stride),(37,-stride)]:
        knee=(x+off*.5,-94)
        foot=(x+off,0)
        out += [p(f"M {x-25} -180 L {s.n(knee[0]-24)} -91 L {s.n(foot[0]-20)} -14 L {s.n(foot[0]+23)} -14 L {s.n(knee[0]+23)} -91 L {x+25} -180 Z","#8b705a"),
                line(x,-169,knee[0],-90,"#c29b72",5),p(f"M {s.n(foot[0]-24)} -27 L {s.n(foot[0]+21)} -27 L {s.n(foot[0]+46)} -9 L {s.n(foot[0]+46)} 2 L {s.n(foot[0]-26)} 2 Z","#26354a")]
    out += [p(f"M -65 -353 L -103 -295 L {left[0]} {left[1]} L {left[0]+32} {left[1]+7} L -55 -288 Z","url(#coat)"),
            s.circ(left[0]+13,left[1]+8,18,"#efb48e",INK,5),
            p("M -66 -359 Q -20 -398 66 -359 L 87 -185 Q 0 -161 -91 -185 Z","url(#coat)"),
            p("M -66 -359 L -21 -310 L -2 -350 L 37 -309 L 66 -359 L 40 -386 L -35 -389 Z","#314654"),
            line(0,-346,0,-181,"#152c3d",7),
            p("M -77 -239 L -28 -247 L -28 -213 L -76 -208 Z","#56757b",INK,4),
            p("M 26 -247 L 74 -240 L 78 -210 L 26 -213 Z","#56757b",INK,4),
            line(-53,-347,-39,-186,RUST,7)]
    if pack: out += [p("M -50 -365 Q -77 -328 -61 -239","none","#b67952",12),p("M 42 -368 Q 65 -335 57 -241","none","#b67952",12)]
    out += [p(f"M 54 -346 L 102 -321 L {s.n(right[0]+12)} {s.n(right[1]-12)} L {s.n(right[0]-14)} {s.n(right[1]+14)} L 69 -280 Z","url(#coat)"),
            s.circ(right[0],right[1],19,"#efb48e",INK,5),
            g(0,-427-bob, .73,head(t,fear))]
    if light:
        x,y=right
        out += [s.g("translate(0 0)",poly([(x+20,y-10),(x+300,y-100),(x+335,y+90),(x+20,y+10)],"#ffeab2","none",0),op=.28),
                s.rect(x-5,y-13,49,26,"#33485b",5,INK,5),
                s.rect(x+29,y-18,19,36,"#ffefab",4,INK,4)]
    return "".join(out)
def dog(t,walk=False,fear=0):
    leg=wave(t,1.6)*17 if walk else 0
    out=[s.ell(0,4,68,9,INK,op=.35),
         p(f"M -49 -63 Q -88 -83 -85 {-101+leg}","none","#a46c4b",12)]
    for x,k in [(-37,leg),(31,-leg)]:
        out.append(p(f"M {x-9} -43 L {s.n(x+k-10)} 0 L {s.n(x+k+10)} 0 L {x+10} -45 Z","#b98258",INK,4))
    out += [s.ell(-3,-53,55,31,"#c99564",INK,5),p("M 18 -75 L 44 -42 L 23 -28 L 6 -54 Z","#f4d5a1","none",0),
            s.circ(53,-81,32,"#d6a16c",INK,5),
            p("M 33 -108 Q 5 -103 15 -70 L 36 -69 Z","#735043",INK,4),
            p("M 72 -107 Q 93 -101 86 -72 L 71 -72 Z","#735043",INK,4),
            s.ell(75,-72,22,13,"#edca99",INK,4),s.circ(88,-75,7,INK),
            s.circ(57,-87,5,INK),line(30,-51,60,-44,RUST,9)]
    if fear: out.append(p("M 92 -58 Q 103 -53 108 -61","none","#f5cf8b",4))
    return "".join(out)
def wheel(x,y,angle):
    return g(x,y,1,s.circ(0,0,69,INK,"#647783",8)+s.circ(0,0,39,"#b2ac9b",INK,6)
        +s.g(f"rotate({s.n(angle)})",line(-31,0,31,0,INK,7)+line(0,-31,0,31,INK,7)+line(-22,-22,22,22,INK,5)+line(22,-22,-22,22,INK,5))+s.circ(0,0,10,"#efe0bd"))
def sedan(t, speed=1, lamps=1,door=0,driver=True):
    out=[s.ell(430,15,453,34,INK,op=.4),
         p("M 18 -29 L 27 -112 Q 35 -137 101 -148 L 224 -160 L 348 -279 Q 385 -307 550 -299 L 688 -177 L 843 -144 Q 878 -131 885 -80 L 878 -28 L 18 -29 Z","#368f92",INK,10),
         p("M 37 -110 L 220 -130 L 680 -146 L 865 -105 L 865 -74 L 40 -70 Z","#77c1b3","none",0),
         p("M 248 -168 L 365 -273 L 461 -278 L 461 -168 Z","url(#glass)",INK,7),
         p("M 479 -278 L 545 -278 L 655 -168 L 479 -168 Z","url(#glass)",INK,7)]
    if driver:
        out += [g(530,-220,.43,head(t,0.25)),p("M 479 -278 L 545 -278 L 655 -168 L 479 -168 Z","none",INK,7)]
    out += [p("M 239 -159 L 237 -54 M 470 -160 L 470 -54 M 681 -151 L 669 -54","none","#1b5360",5),
            line(495,-144,538,-144,PAPER,7),line(273,-144,313,-144,PAPER,7),
            s.rect(42,-113,42,30,"#e96d61",7,INK,5),s.rect(808,-123,65,35,"#ffe2a0",7,INK,5),
            wheel(192,-22,t*460*speed),wheel(728,-22,t*460*speed)]
    if door:
        out += [s.g(f"translate(470 -164) scale({s.n(1-.65*door)} 1)",p("M 0 0 L -103 -8 L -110 111 L 0 111 Z","#31828b")+p("M -7 8 L -94 4 L -94 49 L -7 52 Z","#8ecbc3")+line(-82,68,-50,68,PAPER,7))]
    if lamps:
        out += [s.ell(874,-104,85,67,"url(#lamp)",op=lamps),p("M 872 -119 L 1230 -180 L 1230 35 L 872 -87 Z","#ffe1a1","none",0,op=.19*lamps)]
    return "".join(out)
def landscape(t,shift=0,station=False):
    out=[s.rect(0,0,W,H,"url(#sky)"),s.circ(822,242,89,"#ffdbac",op=.88)]
    # Hand-composed ridge layers and moving roadside texture.
    for j,(y,c) in enumerate([(430,"#567b8e"),(510,"#42697b"),(655,"#355568")]):
        pts=[(-100,y)]+[(i*120-80,y+35*math.sin(i*.87+j*2)) for i in range(11)]+[(1180,1450),(-100,1450)]
        out.append(poly(pts,c,"none",0))
    for i in range(13):
        x=(i*126-shift*.22)%1450-180
        h=95+(i*37)%135
        y=708+(i%3)*16
        out += [line(x,y-h,x,y,"#344d61",7),poly([(x,y-h),(x-37,y-29),(x+37,y-29)],"#344d61","none",0)]
    out += [poly([(0,770),(1080,770),(1080,H),(0,H)],"url(#road)","none",0),
            p("M 0 805 L 1080 805 M 0 1045 L 1080 1045","none","#7f9295",4)]
    for i in range(10):
        x=(i*173-shift)%1730-270
        out.append(s.rect(x,998,100,9,"#d2b98e",4,op=.75))
    for i in range(6):
        x=(i*211-shift*.45)%1450-200
        out.append(s.ell(x,711+i%2*25,178,19,"#f5dfc5",op=.14))
    return "".join(out)
def station(t):
    out=[s.rect(0,0,W,H,"url(#sky)"),s.circ(880,160,81,"#ffdca8",op=.75),
         poly([(0,670),(1080,585),(1080,H),(0,H)],"#536f7a","none",0),
         p("M 0 888 L 1080 888 L 1080 1360 L 0 1360 Z","url(#road)","none",0),
         s.ell(780,710,430,350,"url(#lamp)"),
         p("M 245 369 L 930 369 L 1020 465 L 184 465 Z","#efc393",INK,10),
         p("M 184 465 L 1020 465 L 1020 509 L 184 509 Z","#a95748",INK,8),
         s.rect(263,510,690,380,"#c9b493",0,INK,8),
         s.rect(300,549,235,242,"url(#glass)",0,INK,9),
         s.rect(565,548,325,342,"#34516b",0,INK,10),
         s.rect(587,569,281,299,"url(#glass)",0,INK,6),
         line(727,569,727,868,INK,8),line(587,710,868,710,"#a4d8d0",4),
         s.rect(727,725,24,10,PAPER,3,INK,3),
         s.rect(280,307,634,65,"#343e53",8,INK,7),
         text(596,350,"LAST LIGHT  /  OPEN 24H",32,AMBER,"middle"),
         s.rect(113,509,32,374,"#b4a78d",0,INK,6),
         s.rect(957,509,32,374,"#b4a78d",0,INK,6),
         s.rect(88,760,96,130,"#cf6b4c",13,INK,6),
         s.rect(106,774,59,42,"#f4dbb1",5,INK,5)]
    return "".join(out)
def cabin(t,pct):
    # Separate close-up: visible ignition hand, dead dashboard, worried dog.
    power=1-smooth((pct-.42)/.22)
    twist=math.sin(smooth(pct/.32)*math.pi)*35
    out=[s.rect(0,0,W,H,"#273d57"),p("M 35 45 L 1045 45 L 930 450 L 152 450 Z","url(#glass)",INK,14),
         p("M 146 415 L 430 233 L 642 233 L 940 415 Z","#465b73",INK,7),
         line(534,254,534,400,"#d9c6a4",6),
         s.rect(0,458,1080,700,"#344d61",22,INK,10),
         g(230,420,1.75,head(t,.85)),g(810,675,1.55,dog(t,False,1)),
         p("M 0 700 Q 174 515 333 640 L 416 1040 L 0 1040 Z","url(#coat)"),
         s.circ(325,775,144,"#26364b",INK,12),s.circ(325,775,105,"#586f7b",INK,8),
         line(224,775,426,775,INK,17),line(325,775,325,876,INK,17),
         s.rect(488,580,290,162,"#182b3c",20,INK,8)]
    for x in (560,697):
        out += [s.circ(x,648,43,"#2a3d4a","#849a9b",5),line(x,648,x+22,625,"#ffcf80",6,op=.15+.85*power)]
    out += [s.rect(487,815,260,115,"#283a4c",18,INK,8),s.circ(623,865,29,"#a9b6ad",INK,6),
            p("M 445 950 Q 509 890 573 870 L 595 904 Q 529 954 469 1000 Z","url(#coat)"),
            s.g(f"translate(623 865) rotate({s.n(twist)})",p("M -14 -7 L 64 -7 L 64 9 L -14 9 Z","#ded0a7")+s.ell(61,1,25,15,"#efb48e",INK,5)),
            text(635,711,"IGNITION",23,"#ffcf80" if power>.2 else "#77888d","middle")]
    return "".join(out)
def close_door(t,pct,knock=False):
    out=[s.rect(0,0,W,H,"#d9b68e"),s.rect(75,20,930,1080,"#544b54",18,INK,13),
         s.rect(103,50,874,1010,"url(#glass)",5,INK,11),
         line(540,55,540,1055,"#314c5c",12),line(104,880,977,880,"#314c5c",9)]
    x=470+80*wave(t,.23)
    out += [s.ell(x,364,119,145,"#24384a",op=.82),
            p(f"M {s.n(x-130)} 500 Q {s.n(x)} 420 {s.n(x+130)} 500 L {s.n(x+205)} 880 L {s.n(x-210)} 880 Z","#24384a","none",0,op=.85),
            p("M 135 90 L 270 90 L 785 815 L 677 815 Z","#d6f6dc","none",0,op=.18),
            s.rect(667,590,94,153,"#b09974",15,INK,8),s.circ(714,667,29,"#f7d591",INK,7)]
    rotation=0
    if knock:
        rotation=65*smooth((pct-.50)/.43)
        for k in (.13,.27,.41):
            u=abs(pct-k)
            if u<.065:
                rr=45+(u/.065)*100
                out.append(s.circ(714,667,rr,"none","#fdf0b6",7,op=1-u/.065))
    out.append(s.g(f"translate(714 667) rotate({s.n(rotation)})",s.rect(-12,-15,178,30,"#f8ce81",10,INK,7)))
    return "".join(out)
def scene(beat,t,pct):
    if beat=="car_driving":
        return landscape(t,t*280)+g(85+35*wave(t,.16),860,.94,sedan(t,1,1))+text(78,160,"2:47 AM",65,PAPER)
    if beat=="engine_stall":
        stop=smooth(pct/.59)
        travel=1-(1-stop)**2
        lamp=1 if pct<.12 else (.95 if int(t*11)%3==0 else .08) if pct<.58 else .05
        phase=min(pct/.59,1.0)
        stop_time=t/max(pct,.001)*.59
        wheel_time=stop_time*(phase-phase**2/2)
        car=sedan(wheel_time,1,lamp)
        out=landscape(t,travel*550)+g(85+95*travel,885+wave(t,5)*7*(1-stop),.9,car)
        for i in range(5):
            out+=s.ell(895+i*12,710-i*28-wave(t+i*.2,.3)*12,25+i*8,14+i*7,"#e6c8a4",op=.20)
        return out
    if beat=="car_interior": return cabin(t,pct)
    if beat=="flashlight_exit":
        door=smooth(pct/.24)
        step=smooth((pct-.22)/.36)
        light=pct>.72
        body=landscape(t,0)+g(-180,875,.83,sedan(t,0,0,door,False))
        body+=g(480+170*step,1008,1.13,max_actor(t,"grab" if pct<.30 else "walk",.35,pct>.13,light))
        body+=g(300+145*step,1009,1.24,dog(t,pct>.22,.5))
        return body
    if beat=="spot_station":
        return station(t)+g(170,1035,1.13,max_actor(t,"point",.35,True,False))+g(375,1033,1.4,dog(t,False,.5))
    if beat=="door_shadow":
        # Foreground reaction in a graphic split composition, door and Max both visible.
        return close_door(t,pct)+poly([(0,530),(392,540),(446,1040),(0,1040)],"#31495b","none",0)+g(193,675,1.46,head(t,.9))+p("M 0 850 Q 190 714 392 863 L 446 1040 L 0 1040 Z","url(#coat)")
    if beat=="door_handle": return close_door(t,pct,True)
    raise ValueError("No graphic-novel scene for "+str(beat))
def frame_svg(ep,cfg,shots,t,Texts,cache,seed=1):
    import animate as old
    shot=next((a for a in shots if a.start<=t<a.end),shots[-1])
    local=max(0,t-shot.start)
    pct=s.clamp(local/max(.1,shot.dur),0,1)
    beat=shot.meta.get("beat")
    if shot.kind!="line":
        raise ValueError("Pilot expects authored Day 1 narration only")
    body=scene(beat,local,pct)
    # Rich paper-ink texture is static and deterministic, not temporal noise.
    if "grain" not in cache:
        rng=random.Random(72)
        cache["grain"]="".join(s.circ(rng.randrange(W),rng.randrange(1060),rng.choice([1,1,2,3]),"#f6dfbd",op=.12) for _ in range(700))
    body+=s.rect(0,0,W,1060,"url(#hatch)",op=.33)+cache["grain"]
    # Designed editorial lower panel; captions never obscure the acting.
    body+=s.rect(0,1020,W,900,"url(#fade)")
    idx=next(i for i,a in enumerate(shots) if a is shot)+1
    body+=text(70,1390,"ZMB  /  THE LAST LIGHT",29,"#f4d1a1")
    body+=s.rect(70,1420,754,4,"#587586")+s.rect(70,1420,754*((idx-1+pct)/len(shots)),4,RUST)
    # Reuse the validated caption timing only, not the old visuals or HUD.
    key=("graphic-novel-captions",id(shot))
    if key not in cache:
        cache[key]=old.chunk_words([dict(w) for w in shot.words],Texts,59,max_w=710,max_words=4,source_text=shot.text) if shot.words else old._fake_words(shot,Texts,59)
    active=next((c for c in cache[key] if c["start"]-.08<=local<=c["end"]),None)
    if active:
        words=active["words"]
        width=sum(Texts.w(str(w["w"])+" ",59) for w in words)-Texts.w(" ",59)
        x=488-width/2
        for wd in words:
            value=str(wd["w"])
            color=AMBER if wd["start"]<=local<=wd["end"]+.12 else PAPER
            body+=s.text(x,1196,value,59,"Barlow",color,anchor="start",weight="bold",stroke="#18293d",sw=5)
            x+=Texts.w(value+" ",59)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"><defs>{DEFS}</defs>{body}</svg>'
