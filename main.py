import asyncio, glob, json, os, subprocess, sys, time
import edge_tts
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(line_buffering=True)
VOICES = {"guide": os.environ.get("TTS_VOICE", "en-US-AndrewNeural"), "you": os.environ.get("TTS_VOICE_YOU", "en-US-AvaNeural")}
QUALITY = os.environ.get("MANIM_QUALITY", "m")  # l=480p, m=720p, h=1080p
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PROMPT = """You are the scriptwriter of an English science-explainer YouTube channel for a global audience. Topic: "{topic}"
Write a 8-11 minute explainer (about 1300-1600 words of narration).
Return ONLY valid JSON with this schema:
{{"title": "max 70 chars, curiosity-driven but not misleading",
 "description": "3-4 paragraphs + hashtags",
 "tags": ["..."], "thumb_text": "max 4 words",
 "claims_to_check": ["key factual claims a human should verify"],
 "scenes": [ 16-20 scenes. Each scene:
  {{"speaker": "guide or you", "backdrop": "lab|space|ocean|city|nature|bedroom",
    "type": "title|bullets|stat|diagram", "narration": "60-90 words of narration",
    "text": "(title) main title", "subtitle": "(title) subtitle",
    "heading": "(bullets/diagram) heading", "items": ["(bullets) max 4 short items"],
    "value": "(stat) big number", "label": "(stat) caption",
    "nodes": ["(diagram) 3-4 short steps"]}} ]}}
Rules: Two characters appear: "guide" (a friendly scientist who explains) and "you" (a curious viewer who asks short questions). Most scenes use speaker "guide"; use "you" for a short 1-2 sentence question (max 25 words) every 3-4 scenes, followed by a "guide" answer. Pick the backdrop that fits each scene's topic. The first scene must be "title". Open a curiosity gap in the first 30 seconds. Add a new surprising fact every ~2 minutes.
NEVER invent statistics; skip any number you are not sure about. Be scientifically accurate and clear. Avoid filler and repetition."""

def pick_topic():
    used = set(open("used.txt", encoding="utf-8").read().splitlines()) if os.path.exists("used.txt") else set()
    for t in open("topics.txt", encoding="utf-8").read().splitlines():
        if t.strip() and t not in used: return t
    raise SystemExit("No unused topics left in topics.txt")

def generate(topic):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    models = [os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"), "gemini-flash-latest"]
    last = None
    for m in models:
        try:
            r = client.models.generate_content(
                model=m, contents=PROMPT.format(topic=topic),
                config={"response_mime_type": "application/json"})
            print("Gemini model used:", m)
            return json.loads(r.text)
        except Exception as e:
            print("Model", m, "failed:", str(e)[:200])
            last = e
    raise last

def run(cmd, **env):
    subprocess.run(cmd, check=True, env={**os.environ, **env})

def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=nw=1:nk=1", path]))

def tts(text, speaker, path):
    text = (text or "").strip() or "."
    voice = VOICES.get(speaker, VOICES["guide"])
    for attempt in range(3):
        try:
            asyncio.run(edge_tts.Communicate(text, voice).save(path))
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
    segs = []
    total = len(data["scenes"])
    for i, sc in enumerate(data["scenes"]):
        mp3, wav, js, name = f"{work}/{i:02d}.mp3", f"{work}/{i:02d}.wav", f"{work}/{i:02d}.json", f"s{i:02d}"
        tts(sc["narration"], sc.get("speaker", "guide"), mp3)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "16000", wav])
        d = duration(mp3) + 0.5
        json.dump(sc, open(js, "w", encoding="utf-8"), ensure_ascii=False)
        env = dict(SCENE_JSON=js, SCENE_DUR=str(d), SCENE_AUDIO=wav, SCENE_IDX=str(i), SCENE_TOTAL=str(total), TOPIC=topic)
        try:
            run(["manim", f"-q{QUALITY}", "--media_dir", f"{work}/media", "-o", name, "scenes.py", "SceneRenderer"], **env)
        except subprocess.CalledProcessError:
            print(f"Scene {i}: character scene failed, using simple fallback")
            run(["manim", f"-q{QUALITY}", "--media_dir", f"{work}/media", "-o", name, "scenes_fallback.py", "SceneRenderer"], **env)
        vid = glob.glob(f"{work}/media/videos/*/*/{name}.mp4")[0]
        seg = f"{work}/seg{i:02d}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", mp3, "-map", "0:v", "-map", "1:a",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-shortest", seg])
        segs.append(os.path.abspath(seg))
    lst = f"{work}/list.txt"
    open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
    final = f"{work}/final.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final])
    return final

def make_thumbnail(text, path):
    img = Image.new("RGB", (1280, 720), "#14161a")
    d = ImageDraw.Draw(img)
    for y in range(720):
        d.line([(0, y), (1280, y)], fill=(20 + y // 12, 22 + y // 40, 26))
    size = 150
    while True:
        f = ImageFont.truetype(FONT, size)
        lines, line = [], ""
        for wd in text.upper().split():
            t = (line + " " + wd).strip()
            if d.textlength(t, font=f) < 1100: line = t
            else: lines.append(line); line = wd
        lines.append(line)
        if len(lines) * size * 1.15 < 560 or size < 70: break
        size -= 10
    y = (720 - len(lines) * size * 1.15) / 2
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((1280 - w) / 2, y), ln, font=f, fill="#f2b63d", stroke_width=6, stroke_fill="#000000")
        y += size * 1.15
    img.save(path)

def upload(video, thumb, data):
    c = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=c)
    status = {"privacyStatus": os.environ.get("PRIVACY", "private"), "selfDeclaredMadeForKids": False}
    if os.environ.get("SYNTHETIC") == "1":
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
    topic = pick_topic()
    print("Topic:", topic)
    data = generate(topic)
    os.makedirs("work", exist_ok=True)
    print("Claims to verify:", *data.get("claims_to_check", []), sep="\n - ")
    video = build_video(data, topic)
    make_thumbnail(data.get("thumb_text", data["title"]), "work/thumb.png")
    if os.environ.get("YT_REFRESH_TOKEN"):
        vid = upload(video, "work/thumb.png", data)
        open("used.txt", "a", encoding="utf-8").write(topic + "\n")
        print("Uploaded: https://youtu.be/" + vid)
    else:
        print("YouTube secrets not set: skipping upload (test mode).")
