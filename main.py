import asyncio, glob, json, os, random, re, subprocess, sys, time
import edge_tts
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(line_buffering=True)
VOICES = {"guide": os.environ.get("TTS_VOICE", "en-US-AndrewNeural"),
          "you": os.environ.get("TTS_VOICE_YOU", "en-US-AvaNeural")}
QUALITY = os.environ.get("MANIM_QUALITY", "m")  # l=480p15, m=720p30, h=1080p60
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FALLBACKS = []

ICONS = ("battery phone thermometer flame bolt sun moon earth planet star cloud drop gear magnet atom dna heart "
         "brain virus plant rocket bulb magnifier clock warning check cross gas explosion shield wave question "
         "dollar chart molecule snow").split()

PROMPT = """You are the head writer of an English science-explainer YouTube channel for a global audience.
Topic: "__TOPIC__"
Create a 8-11 minute animated explainer as a list of SHOTS (short 5-12 second cuts). Two cartoon characters appear:
"guide" (a friendly male scientist who explains) and "you" (a curious young woman who asks questions and reacts).
Return ONLY valid JSON:
{"title": "max 70 chars, curiosity-driven, not misleading",
 "description": "3-4 paragraphs + hashtags",
 "tags": ["..."],
 "thumb": {"text": "2-4 punchy words that create shock or curiosity", "icon": "<one icon>", "theme": "red|blue|purple|green|gold", "character": "you|guide"},
 "claims_to_check": ["key factual claims a human should verify"],
 "shots": [ 40-55 shots, each:
  {"kind": "scene|title|stat|diagram",
   "speaker": "guide|you",
   "narration": "15-40 words (1-3 sentences) spoken in this shot",
   "layout": "duo|solo|walk|prop_only",
   "backdrop": "lab|space|ocean|city|nature|bedroom",
   "props": [{"icon": "<icon>", "anim": "pop|pulse|shake|spin|float|grow|rise|swell", "label": "max 3 words"}],
   "reaction": "none|shock|think|happy|worried",
   "text": "(title/stat only) big text or number", "subtitle": "(title/stat only) caption",
   "nodes": ["(diagram only) 3-4 short steps"]} ] }
Allowed icons: __ICONS__
Rules:
- Total narration 1300-1600 words. First shot is kind "title" (layout "solo", speaker "guide").
- EVERY shot's props must visually illustrate exactly what that shot's narration says. Use at most 2 props and no long on-screen text.
- Use anim "swell" only for battery, "rise" only for thermometer, "grow" only for chart.
- Vary layout, backdrop and props; never repeat the same combination more than twice in a row. Use "walk" a few times, "prop_only" (speaker must be "guide") for cinematic explanation moments, "solo" for emphasis.
- "you" asks a short curious question (max 20 words) every 4-6 shots, then "guide" answers. "reaction" is for the listener; use it in about 1 shot of 4.
- Open with a hook in the first 30 seconds. Every ~60 seconds give a surprising fact. End with a practical takeaway.
- Correct at least one common misconception and give one practical tip: original insight, not generic filler.
- NEVER invent statistics; skip any number you are not sure about. Be scientifically accurate."""


def pick_topic():
    used = set(open("used.txt", encoding="utf-8").read().splitlines()) if os.path.exists("used.txt") else set()
    for t in open("topics.txt", encoding="utf-8").read().splitlines():
        if t.strip() and t not in used:
            return t
    raise SystemExit("No unused topics left in topics.txt")


def parse_json(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def other_models(client):
    full, lite = [], []
    try:
        for m in client.models.list():
            n = m.name.split("/")[-1]
            acts = getattr(m, "supported_actions", None) or []
            if "flash" in n and "generateContent" in acts and not any(x in n for x in ("image", "tts", "live", "audio", "embed", "omni")):
                (lite if "lite" in n else full).append(n)
    except Exception as e:
        print("Could not list models:", str(e)[:200])
    return sorted(full, reverse=True)[:2] + sorted(lite, reverse=True)[:2]


def retry_delay(msg):
    m = re.search(r"retry in ([0-9.]+)s", msg) or re.search(r"retryDelay'?\"?: ?'?\"?([0-9.]+)s", msg)
    return min(75.0, float(m.group(1)) + 3) if m else None


def generate(topic):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = PROMPT.replace("__TOPIC__", topic).replace("__ICONS__", ", ".join(ICONS))
    cfg = {"response_mime_type": "application/json", "max_output_tokens": 60000, "temperature": 0.9}
    primary = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    errors = []
    cands = [primary] + [m for m in other_models(client) if m != primary]
    print("Models to try:", cands, flush=True)
    for m in cands:
        for attempt in range(3):
            try:
                r = client.models.generate_content(model=m, contents=prompt, config=cfg)
                data = parse_json(r.text)
                print("Gemini model used:", m, "attempt", attempt + 1)
                return data
            except Exception as e:
                text = str(e)
                msg = f"{m} attempt {attempt + 1}: {type(e).__name__}: {text[:300]}"
                print("GEMINI ERROR ->", msg, flush=True)
                errors.append(msg)
                if "NOT_FOUND" in text or "PerDay" in text or "limit: 0" in text:
                    break  # this model is unavailable or its daily quota is gone: go to the next model
                wait = retry_delay(text) if "429" in text or "RESOURCE_EXHAUSTED" in text else 8 * (attempt + 1)
                print(f"waiting {wait or 20:.0f}s before retry", flush=True)
                time.sleep(wait or 20)
    raise SystemExit("Gemini failed. Last errors:\n" + "\n".join(errors[-4:]))


def clean(data):
    shots = []
    for s in data.get("shots") or []:
        if not isinstance(s, dict) or not (s.get("narration") or "").strip():
            continue
        s["speaker"] = s.get("speaker") if s.get("speaker") in ("guide", "you") else "guide"
        s["layout"] = s.get("layout") if s.get("layout") in ("duo", "solo", "walk", "prop_only") else "duo"
        if s["layout"] == "prop_only" and s["speaker"] == "you":
            s["layout"] = "solo"
        if s.get("kind") not in ("scene", "title", "stat", "diagram"):
            s["kind"] = "scene"
        props = []
        for p in (s.get("props") or [])[:2]:
            if isinstance(p, dict):
                p["icon"] = p.get("icon") if p.get("icon") in ICONS else "star"
                p["label"] = str(p.get("label") or "")[:28]
                props.append(p)
        s["props"] = props
        shots.append(s)
    if len(shots) < 5:
        raise SystemExit("Gemini returned too few usable shots")
    data["shots"] = shots[:70]
    th = data.get("thumb") or {}
    th["icon"] = th.get("icon") if th.get("icon") in ICONS else "warning"
    th["text"] = str(th.get("text") or data.get("title", "WOW"))[:40]
    data["thumb"] = th
    return data


def run(cmd, **env):
    subprocess.run(cmd, check=True, env={**os.environ, **env})


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=nw=1:nk=1", path]))


def tts(text, speaker, path):
    text = (text or "").strip() or "."
    if os.environ.get("FAKE_TTS"):  # offline test hook
        n = max(1, len(text.split()))
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={n * .38}", path])
        return
    voice = VOICES.get(speaker, VOICES["guide"])
    for attempt in range(3):
        try:
            asyncio.run(edge_tts.Communicate(text, voice, rate="+5%").save(path))
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            print("edge-tts attempt", attempt + 1, "failed:", str(e)[:120])
        time.sleep(2)
    print("Falling back to gTTS")
    from gtts import gTTS
    gTTS(text, lang="en", tld="com" if speaker != "you" else "co.uk").save(path)


def build_video(data, topic="", work="work"):
    os.makedirs(work, exist_ok=True)
    rnd = random.Random(topic)
    segs, total, prev = [], len(data["shots"]), None
    for i, sh in enumerate(data["shots"]):
        mp3, wav, js, name = f"{work}/{i:02d}.mp3", f"{work}/{i:02d}.wav", f"{work}/{i:02d}.json", f"s{i:02d}"
        tts(sh["narration"], sh["speaker"], mp3)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "16000", wav])
        d = duration(mp3) + 0.35
        json.dump(sh, open(js, "w", encoding="utf-8"), ensure_ascii=False)
        enter = prev is None or prev.get("backdrop") != sh.get("backdrop") or prev.get("layout") != sh.get("layout")
        env = dict(SCENE_JSON=js, SCENE_DUR=str(d), SCENE_AUDIO=wav, SCENE_IDX=str(i), SCENE_TOTAL=str(total),
                   TOPIC=topic, SHOT_ENTER="1" if enter else "0", SHOT_SIDE=rnd.choice(["1", "-1"]))
        prev = sh
        try:
            run(["manim", f"-q{QUALITY}", "--media_dir", f"{work}/media", "-o", name, "scenes.py", "SceneRenderer"], **env)
        except subprocess.CalledProcessError:
            FALLBACKS.append(i)
            print(f"!!! Shot {i}: SCENE FAILED, using simple fallback", flush=True)
            json.dump({"type": "title", "text": (sh.get("narration") or "")[:70], "subtitle": ""}, open(js, "w"))
            run(["manim", f"-q{QUALITY}", "--media_dir", f"{work}/media", "-o", name, "scenes_fallback.py", "SceneRenderer"], **env)
        vid = glob.glob(f"{work}/media/videos/*/*/{name}.mp4")[0]
        seg = f"{work}/seg{i:02d}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", mp3, "-map", "0:v", "-map", "1:a",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-shortest", seg])
        segs.append(os.path.abspath(seg))
        print(f"shot {i + 1}/{total} done", flush=True)
    lst = f"{work}/list.txt"
    open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
    final = f"{work}/final.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final])
    if FALLBACKS:
        print("WARNING: fallback shots:", FALLBACKS, flush=True)
        if len(FALLBACKS) > max(3, total // 5):
            raise SystemExit("Too many shots failed to render; fix scenes.py")
    return final


def make_thumbnail(data, work="work"):
    th = data["thumb"]
    js = f"{work}/thumb.json"
    json.dump(th, open(js, "w", encoding="utf-8"))
    out = f"{work}/thumb.jpg"
    try:
        run(["manim", "-s", "-r", "1280,720", "--media_dir", f"{work}/tmedia", "-o", "thumb", "scenes.py", "ThumbScene"], THUMB_JSON=js)
        png = glob.glob(f"{work}/tmedia/images/*/thumb*.png")[0]
        Image.open(png).convert("RGB").save(out, quality=92)
        return out
    except Exception as e:
        print("Thumbnail scene failed, using simple thumbnail:", str(e)[:150])
    img = Image.new("RGB", (1280, 720), "#7a0f0f")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 120)
    d.text((60, 250), th["text"].upper()[:18], font=f, fill="#f2b63d", stroke_width=8, stroke_fill="#000000")
    img.save(out, quality=92)
    return out


def upload(video, thumb, data):
    c = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=c)
    status = {"privacyStatus": os.environ.get("PRIVACY", "private"), "selfDeclaredMadeForKids": False}
    if os.environ.get("SYNTHETIC", "1") == "1":
        status["containsSyntheticMedia"] = True
    body = {"snippet": {"title": data["title"][:100], "description": data["description"],
                        "tags": data.get("tags", [])[:15], "categoryId": "28", "defaultLanguage": "en"},
            "status": status}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    try:
        yt.thumbnails().set(videoId=resp["id"], media_body=MediaFileUpload(thumb)).execute()
    except Exception as e:
        print("Thumbnail upload failed (is the channel verified?):", e)
    return resp["id"]


if __name__ == "__main__":
    open("used.txt", "a").close()
    topic = pick_topic()
    print("Topic:", topic)
    if os.environ.get("TEST_DATA"):
        data = json.load(open(os.environ["TEST_DATA"]))
    else:
        data = generate(topic)
    data = clean(data)
    os.makedirs("work", exist_ok=True)
    json.dump(data, open("work/script.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Claims to verify:", *data.get("claims_to_check", []), sep="\n - ")
    video = build_video(data, topic)
    thumb = make_thumbnail(data)
    if os.environ.get("YT_REFRESH_TOKEN"):
        vid = upload(video, thumb, data)
        open("used.txt", "a", encoding="utf-8").write(topic + "\n")
        print("Uploaded: https://youtu.be/" + vid)
    else:
        print("YouTube secrets not set: skipping upload (test mode).")
