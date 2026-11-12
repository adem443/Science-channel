import asyncio, glob, json, os, random, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import edge_tts
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(line_buffering=True)
# Voice gender must always match the character on screen: Spark (guide) = male, Why (you) = female.
VOICES = {"guide": [os.environ.get("TTS_VOICE", "en-US-AndrewNeural"), "en-US-GuyNeural", "en-GB-RyanNeural", "en-US-ChristopherNeural"],
          "you": [os.environ.get("TTS_VOICE_YOU", "en-US-AvaNeural"), "en-US-JennyNeural", "en-US-AriaNeural", "en-GB-SoniaNeural"]}
VOICE_OK = {}  # speaker -> voice that worked first time; reused for the whole video
QUALITY = os.environ.get("RENDER_MODE", "1080")  # old MANIM_QUALITY env is ignored on purpose  # "1080" = native 1920x1080@30; or l=480p15, m=720p30, h=1080p60
QARGS = ["-r", "1920,1080", "--frame_rate", "30"] if QUALITY == "1080" else [f"-q{QUALITY}"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WORKERS = int(os.environ.get("RENDER_WORKERS", str(max(1, min(4, os.cpu_count() or 1)))))
UPSCALE = QUALITY != "1080" and os.environ.get("UPSCALE_1080", "1") == "1"
MUSIC = os.environ.get("MUSIC", "1") == "1"
FALLBACKS = []

ICONS = ("battery phone thermometer flame bolt sun moon earth planet star cloud drop gear magnet atom dna heart "
         "brain virus plant rocket bulb magnifier clock warning check cross gas explosion shield wave question "
         "dollar chart molecule snow wifi block server chat pin cart lock plug signal zombie mushroom ant hospital fire").split()

SHOT_SCHEMA = """{"kind": "scene|title|stat|diagram",
   "speaker": "guide|you",
   "narration": "8-22 words (one or two short sentences) spoken in this shot",
   "layout": "duo|solo|walk|prop_only|closeup",
   "backdrop": "lab|space|ocean|city|nature|bedroom|night|forest|map|alert",
   "mood": "calm|tense|danger|relief",
   "props": [{"icon": "<icon>", "anim": "pop|pulse|shake|spin|float|grow|rise|swell", "label": "max 3 words"}],
   "reaction": "none|shock|think|happy|worried",
   "punch": "(optional) 1-3 ALL-CAPS words flashed on screen for impact",
   "text": "(title/stat only) big text or number, e.g. HOUR 12", "subtitle": "(title/stat only) caption",
   "nodes": ["(diagram only) 3-4 short steps"]}"""

CAST = ('Two cartoon characters: "guide" = Spark, a warm, witty male scientist who explains; '
        '"you" = Why, a curious, funny young woman who asks the questions viewers think and reacts.')

META_PROMPT = """You are the head writer of a fast, funny, visually rich English science-explainer YouTube channel ("Spark & Why") for a global audience.
Topic: "__TOPIC__"
__BRIEF__
__CAST__
Plan a video of about 6 minutes (it must stay between 5 and 7 minutes). Return ONLY valid JSON:
{"title": "max 70 chars, curiosity-driven, not misleading",
 "description": "3-4 paragraphs + hashtags. Mention that visuals and narration are made with AI tools.",
 "tags": ["..."],
 "thumb": {"text": "headline in up to 3 lines separated by |, e.g. WHAT IF THE INTERNET|SHUT DOWN|FOR 2 DAYS? (line 1 small, lines 2-3 huge, max 16 chars per line)", "icon": "<icon that shows the topic>", "icons": ["up to 4 extra icons about the topic"], "strike": true or false (true when the idea is something disappearing / failing / forbidden: draws a big red slash over the icon), "scene": "(optional) zombie = a full zombie-apocalypse thumbnail, only for zombie topics",
   "theme": "red|blue|purple|green|gold", "character": "you|guide"},
 "claims_to_check": ["key factual claims a human should verify"],
 "sections": [ exactly 6 sections in story order, each {"name": "short name", "beats": ["4-6 specific points/facts/questions this section covers"]} ] }
Allowed icons: __ICONS__
Rules: section 1 is the hook: it begins with a cold open (the most dramatic moment shown first, no greeting), then a title card, then why it matters and a promise of what is coming. The last section is a practical takeaway. In between, build tension: a surprising twist or misconception correction every section. Never invent statistics. Be scientifically accurate."""

SECTION_PROMPT = """You are the head writer of the English science-explainer YouTube channel "Spark & Why".
Video topic: "__TOPIC__"
__BRIEF__
__CAST__
Video outline (sections in order): __OUTLINE__
Now write ONLY section __N__ of __TOTAL__: "__NAME__". Points to cover: __BEATS__
__CONTEXT__
Return ONLY valid JSON: {"shots": [ __COUNT__ shots, each:
  __SCHEMA__ ] }
Allowed icons: __ICONS__
Rules:
- This section must contain __WORDS__ words of narration in total. Respect both limits: the whole video must last about 6 minutes (never above 7), so do not write much more or much less.
- __SPECIAL__
- EVERY shot's props must visually illustrate exactly what that shot's narration says. Use at most 2 props and no long on-screen text.
- Use anim "swell" only for battery, "rise" only for thermometer, "grow" only for chart.
- Backdrops: night = dark city with lit windows (blackouts, fear), forest = dark misty forest (mysterious nature), map = world map with red dots spreading (outbreaks, spread over countries), alert = red emergency room (alarms, crisis). Mood: use danger for the scariest moments (camera shakes, red tint), tense for rising worry, relief for the calming reassurance at the end (warm glow), calm otherwise. Build a clear emotional arc: curiosity, rising danger, peak, then relief.
- Pace: change layout or backdrop almost every shot; never repeat the same layout+backdrop twice in a row. Use "walk" now and then, "closeup" for emotional or dramatic lines, "prop_only" (speaker must be "guide") for cinematic explanation moments, "solo" for emphasis, "stat" shots for big numbers or timeline marks, "diagram" for cause-and-effect chains.
- "you" speaks in about one shot of three: short funny questions, jokes or wrong guesses (max 20 words) that "guide" answers. "reaction" (for the listener) in about 1 shot of 3. "punch" in about 1 shot of 4, always a different word.
- Tell it like a story: concrete real-life examples, analogies, humor, and end the section with a mini cliffhanger that leads into the next one (except in the last section).
- NEVER invent statistics; skip any number you are not sure about. Be scientifically accurate."""

MIN_MINUTES = float(os.environ.get("MIN_MINUTES", "5"))
MIN_SECTION_WORDS = 100
MIN_TOTAL_WORDS = 700
MAX_MINUTES_EST = float(os.environ.get("MAX_MINUTES", "7"))
WORDS_PER_SEC = 2.8  # measured: Edge neural voice at +4% rate


def ensure_fonts():
    """Roboto gives the captions/headlines their look. Install it on the GitHub runner if missing (harmless elsewhere)."""
    if sys.platform.startswith("linux") and not glob.glob("/usr/share/fonts/truetype/roboto*"):
        try:
            subprocess.run("sudo apt-get install -y -q fonts-roboto && fc-cache -f", shell=True, timeout=240,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print("Could not install fonts-roboto (continuing with default font):", e)


def pick_topic():
    """Returns (key, topic, brief). A topics.txt line may be 'Topic || notes for the writer'."""
    used = set(open("used.txt", encoding="utf-8").read().splitlines()) if os.path.exists("used.txt") else set()
    for line in open("topics.txt", encoding="utf-8").read().splitlines():
        if line.strip() and line not in used:
            topic, _, brief = line.partition("||")
            return line, topic.strip(), brief.strip()
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


def est_seconds(shots):
    return count_words(shots) / WORDS_PER_SEC + .35 * len(shots)


def trim_shots(shots, max_minutes=MAX_MINUTES_EST):
    """Safety net: if the script would run too long, drop the longest ordinary middle shots."""
    shots = list(shots)
    removed = 0
    while est_seconds(shots) > max_minutes * 60 and len(shots) > 12:
        cands = [i for i in range(5, len(shots) - 4) if shots[i].get("kind") == "scene"]
        if not cands:
            break
        shots.pop(max(cands, key=lambda i: len((shots[i].get("narration") or "").split())))
        removed += 1
    if removed:
        print(f"Trimmed {removed} shots to keep the video under {max_minutes:g} minutes", flush=True)
    return shots


def count_words(shots):
    return sum(len((x.get("narration") or "").split()) for x in shots if isinstance(x, dict))


def generate(topic, brief="", client=None, sleep=time.sleep):
    if client is None:
        try:
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"timeout": 240000})
        except Exception:
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg = {"response_mime_type": "application/json", "max_output_tokens": 30000, "temperature": 0.9}
    primary = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    cands = [primary] + [m for m in other_models(client) if m != primary]
    print("Models to try:", cands, flush=True)
    dead, errors = set(), []

    def ask(prompt, label):
        for rnd in range(5):  # each round tries every live model once, then waits
            wait_hint = 0.0
            for m in cands:
                if m in dead:
                    continue
                try:
                    r = client.models.generate_content(model=m, contents=prompt, config=cfg)
                    data = parse_json(r.text)
                    print(f"Gemini [{label}] model {m} round {rnd + 1} ok", flush=True)
                    return data
                except Exception as e:
                    text = str(e)
                    msg = f"{label} {m} round {rnd + 1}: {type(e).__name__}: {text[:260]}"
                    print("GEMINI ERROR ->", msg, flush=True)
                    errors.append(msg)
                    if "NOT_FOUND" in text or "PerDay" in text or "limit: 0" in text:
                        dead.add(m)
                    elif "429" in text or "RESOURCE_EXHAUSTED" in text:
                        wait_hint = max(wait_hint, retry_delay(text) or 30)
            if len(dead) == len(cands):
                break
            w = max(wait_hint, 20 * (rnd + 1))
            print(f"All models busy; waiting {w:.0f}s before round {rnd + 2}", flush=True)
            sleep(w)
        raise SystemExit("Gemini failed. Last errors:\n" + "\n".join(errors[-4:]))

    icons = ", ".join(ICONS)
    fill = lambda t: (t.replace("__TOPIC__", topic).replace("__BRIEF__", ("Writer's notes for this topic: " + brief) if brief else "")
                      .replace("__CAST__", CAST).replace("__ICONS__", icons))
    meta = None
    for attempt in range(3):
        meta = ask(fill(META_PROMPT), "outline")
        secs = [x for x in (meta.get("sections") or []) if isinstance(x, dict) and x.get("name")]
        if len(secs) >= 5:
            meta["sections"] = secs[:8]
            break
        print(f"Outline had only {len(secs)} sections, retrying", flush=True)
    else:
        raise SystemExit("Gemini returned no usable outline")
    secs = meta["sections"]
    outline = " | ".join(f"{i + 1}. {x['name']}" for i, x in enumerate(secs))
    shots, prev_tail = [], ""

    def write_section(i, sec, extra="", words="130-170", count="9-13"):
        ctx = ("Previous section ended with: " + prev_tail) if prev_tail else "This is the very beginning of the video."
        special = (('THIS SECTION STARTS WITH A COLD OPEN, because the first 10 seconds decide whether people keep watching. '
                    'Shots 1-3 (about 30 words in total) are the most gripping, dramatic moment of the whole video, told as if it is happening right now, '
                    'WITHOUT any greeting, introduction or channel name. Use kind "scene" (not title), layouts closeup/solo/prop_only, '
                    'mood "danger" or "tense", a dark backdrop (alert, night, map or forest), a shock reaction in shot 2, and a short ALL-CAPS "punch" word on the peak. '
                    'End shot 3 on an unanswered question or cliffhanger. '
                    'Shot 4 must be kind "title" (layout "solo", speaker "guide", text = a 2-3 word ALL-CAPS version of the topic, narration = a short friendly welcome to Spark and Why plus a promise of what the viewer will learn and the reassuring answer at the end). '
                    'After that, continue with the rest of this section.') if i == 0 else
                   ('End with a practical takeaway and a warm sign-off inviting viewers to subscribe for more everyday science.' if i == len(secs) - 1 else
                    'Do not repeat the intro; continue the story.'))
        p = fill(SECTION_PROMPT).replace("__OUTLINE__", outline).replace("__N__", str(i + 1)).replace("__TOTAL__", str(len(secs)))
        p = (p.replace("__NAME__", str(sec["name"])).replace("__BEATS__", "; ".join(str(b) for b in (sec.get("beats") or [])))
             .replace("__CONTEXT__", ctx + extra).replace("__COUNT__", count).replace("__WORDS__", words)
             .replace("__SCHEMA__", SHOT_SCHEMA).replace("__SPECIAL__", special))
        best = []
        for attempt in range(3):
            d = ask(p, f"section {i + 1}/{len(secs)}")
            got = [x for x in (d.get("shots") or []) if isinstance(x, dict) and (x.get("narration") or "").strip()]
            w = count_words(got)
            print(f"  section {i + 1}: {len(got)} shots, {w} words", flush=True)
            if w > count_words(best):
                best = got
            if w >= MIN_SECTION_WORDS:
                break
            p += f"\nYour previous answer had only {w} words. Write MORE: at least {words} words, with more shots."
        return best

    for i, sec in enumerate(secs):
        got = write_section(i, sec)
        shots += got
        if got:
            prev_tail = " ".join((x.get("narration") or "") for x in got[-2:])[:300]
    if count_words(shots) < MIN_TOTAL_WORDS:
        print(f"Only {count_words(shots)} words so far; adding a bonus section", flush=True)
        bonus = {"name": "Myths and surprising facts", "beats": ["two common myths about this topic and the truth", "one surprising real-world example", "one thing most people never think about"]}
        extra = write_section(max(1, len(secs) - 2), bonus, words="120-160", count="8-12")
        shots = shots[:-len(got)] + extra + got if got else shots + extra
    meta["shots"] = shots
    print(f"Script ready: {len(shots)} shots, {count_words(shots)} words", flush=True)
    return meta


def clean(data):
    shots = []
    for s in data.get("shots") or []:
        if not isinstance(s, dict) or not (s.get("narration") or "").strip():
            continue
        s["speaker"] = s.get("speaker") if s.get("speaker") in ("guide", "you") else "guide"
        s["layout"] = s.get("layout") if s.get("layout") in ("duo", "solo", "walk", "prop_only", "closeup") else "duo"
        if s["layout"] == "prop_only" and s["speaker"] == "you":
            s["layout"] = "solo"
        s["punch"] = str(s.get("punch") or "")[:28]
        s["mood"] = s.get("mood") if s.get("mood") in ("calm", "tense", "danger", "relief") else "calm"
        s["backdrop"] = s.get("backdrop") if s.get("backdrop") in ("lab", "space", "ocean", "city", "nature", "bedroom", "night", "forest", "map", "alert") else "lab"
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
    data["shots"] = shots[:150]
    th = data.get("thumb") or {}
    th["icon"] = th.get("icon") if th.get("icon") in ICONS else "warning"
    th["text"] = str(th.get("text") or data.get("title", "WOW"))[:40]
    th["icon2"] = th.get("icon2") if th.get("icon2") in ICONS else ""
    th["strike"] = bool(th.get("strike"))
    th["scene"] = "zombie" if th.get("scene") == "zombie" else ""
    th["icons"] = [i for i in (th.get("icons") or []) if i in ICONS][:4]
    data["thumb"] = th
    return data


START = time.time()
BUDGET = float(os.environ.get("TIME_BUDGET_MIN", "150")) * 60


def run(cmd, timeout=900, **env):
    subprocess.run(cmd, check=True, timeout=timeout, env={**os.environ, **env})


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=nw=1:nk=1", path]))


async def _edge_save(text, voice, path):
    """Saves the voice and (when available) word timings to <path>.words.json for karaoke captions."""
    words = []
    try:
        com = edge_tts.Communicate(text, voice, rate="+4%", boundary="WordBoundary")
    except TypeError:
        com = edge_tts.Communicate(text, voice, rate="+4%")
    with open(path, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append([ch["text"], ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7])
    try:
        json.dump(words, open(path + ".words.json", "w"))
    except Exception:
        pass


def tts(text, speaker, path):
    text = (text or "").strip() or "."
    if os.environ.get("FAKE_TTS"):  # offline test hook
        n = max(1, len(text.split()))
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={140 if speaker == 'guide' else 240}:duration={n * .38}", path])
        return
    voices = VOICES.get(speaker, VOICES["guide"])
    order = ([VOICE_OK[speaker]] if speaker in VOICE_OK else []) + [v for v in voices if VOICE_OK.get(speaker) != v]
    for voice in order:
        for attempt in range(3):
            try:
                asyncio.run(asyncio.wait_for(_edge_save(text, voice, path), 60))
                if os.path.getsize(path) > 1000:
                    VOICE_OK.setdefault(speaker, voice)
                    return
            except Exception as e:
                print(f"edge-tts {voice} attempt {attempt + 1} failed:", str(e)[:120])
            time.sleep(2)
    if speaker == "you":  # gTTS is a female voice: only acceptable for the female character
        print("Falling back to gTTS (female) for", speaker)
        from gtts import gTTS
        gTTS(text, lang="en", tld="co.uk").save(path)
        return
    # never voice the male character with a female voice
    raise SystemExit(f"TTS failed for speaker '{speaker}'. Refusing to use a mismatched voice.")


def prepare_shot(i, sh, work, prev, rnd, total):
    mp3, wav, js = f"{work}/{i:02d}.mp3", f"{work}/{i:02d}.wav", f"{work}/{i:02d}.json"
    tts(sh["narration"], sh["speaker"], mp3)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "16000", wav])
    d = duration(mp3) + 0.35
    json.dump(sh, open(js, "w", encoding="utf-8"), ensure_ascii=False)
    enter = prev is None or prev.get("backdrop") != sh.get("backdrop") or prev.get("layout") != sh.get("layout")
    env = dict(SCENE_JSON=js, SCENE_DUR=str(d), SCENE_AUDIO=wav, SCENE_IDX=str(i), SCENE_TOTAL=str(total),
               SCENE_CUES=f"{work}/{i:02d}.cues.json", SCENE_WORDS=mp3 + ".words.json", TOPIC=TOPIC_NAME[0],
               SHOT_ENTER="1" if enter else "0", SHOT_SIDE=rnd.choice(["1", "-1"]))
    return mp3, d, env


TOPIC_NAME = [""]


def render_shot(i, work, mp3, d, env):
    import audio_fx
    name = f"s{i:02d}"
    md = f"{work}/media{i:02d}"
    if time.time() - START > BUDGET:
        raise SystemExit(f"Time budget exceeded before shot {i}. Lower MANIM_QUALITY or shorten the script.")
    try:
        run(["manim", *QARGS, "--media_dir", md, "-o", name, "scenes.py", "SceneRenderer"], **env)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        FALLBACKS.append(i)
        print(f"!!! Shot {i}: SCENE FAILED, using simple fallback", flush=True)
        sh = json.load(open(env["SCENE_JSON"], encoding="utf-8"))
        json.dump({"type": "title", "text": (sh.get("narration") or "")[:70], "subtitle": ""}, open(env["SCENE_JSON"], "w"))
        run(["manim", *QARGS, "--media_dir", md, "-o", name, "scenes_fallback.py", "SceneRenderer"], **env)
    vid = glob.glob(f"{md}/videos/*/*/{name}.mp4")[0]
    seg = f"{work}/seg{i:02d}.mp4"
    cues = []
    try:
        cues = [tuple(c) for c in json.load(open(env["SCENE_CUES"]))]
    except Exception:
        pass
    fx = f"{work}/{i:02d}.fx.wav"
    audio_fx.shot_sfx(cues, d, fx)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", mp3, "-i", fx,
         "-filter_complex", "[1:a]apad,volume=1.0[v];[2:a]volume=0.55[f];[v][f]amix=inputs=2:duration=longest:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{d:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", seg])
    import shutil
    shutil.rmtree(md, ignore_errors=True)  # keep disk small
    print(f"shot {i + 1} rendered (elapsed {int(time.time() - START)}s)", flush=True)
    return os.path.abspath(seg)


def build_video(data, topic="", work="work"):
    import audio_fx
    os.makedirs(work, exist_ok=True)
    TOPIC_NAME[0] = topic
    rnd = random.Random(topic)
    total = len(data["shots"])
    # 1) voices (parallel, fast)
    jobs, prev = [], None
    for i, sh in enumerate(data["shots"]):
        jobs.append((i, sh, prev))
        prev = sh
    # decide the working voice per speaker first (serial) so one voice is used for the whole video
    for sp in ("guide", "you"):
        probe = f"{work}/probe_{sp}.mp3"
        tts("Hello there.", sp, probe)
    prepared = {}
    with ThreadPoolExecutor(min(4, WORKERS + 1)) as ex:
        futs = {i: ex.submit(prepare_shot, i, sh, work, pv, random.Random(f"{topic}{i}"), total) for i, sh, pv in jobs}
        for i, f in futs.items():
            prepared[i] = f.result()
    mins = sum(p[1] for p in prepared.values()) / 60
    print(f"voices ready: {total} shots, {mins:.1f} min of narration", flush=True)
    if mins > 8.5 and not os.environ.get("FAKE_TTS"):
        raise SystemExit(f"Video would be {mins:.1f} min, far over the 5-7 min target. Stopping before rendering; run again.")
    if mins < MIN_MINUTES and not os.environ.get("FAKE_TTS"):
        raise SystemExit(f"Video would only be {mins:.1f} min (minimum {MIN_MINUTES:g}). Stopping before rendering; run again.")
    # 2) render shots in parallel
    segs = [None] * total
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {i: ex.submit(render_shot, i, work, *prepared[i]) for i in range(total)}
        for i, f in futs.items():
            segs[i] = f.result()
    lst = f"{work}/list.txt"
    open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
    joined = f"{work}/joined.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    # 3) music + optional 1080p upscale (YouTube gives 1080p uploads a better bitrate)
    final = f"{work}/final.mp4"
    total_dur = duration(joined)
    grade = "eq=contrast=1.06:saturation=1.12:gamma=0.98,noise=alls=2:allf=t"  # light colour grade + subtle film grain
    vf = ["-vf", ("scale=1920:1080:flags=lanczos," if UPSCALE else "") + grade]
    if MUSIC:
        audio_fx.music(total_dur + 2, f"{work}/music.wav")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", f"{work}/music.wav",
             "-filter_complex", "[1:a]volume=0.09[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "0:v", "-map", "[a]", *vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", final], timeout=3600)
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, *vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "copy", final], timeout=3600)
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


def read_settings():
    """settings.txt (repo root): upload=1, publish_at=2026-11-12T19:00:00+03:00, privacy=private, auto=0"""
    d = {}
    if os.path.exists("settings.txt"):
        for line in open("settings.txt", encoding="utf-8").read().splitlines():
            line = line.split("#")[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                d[k.strip().lower()] = v.strip()
    return d


def publish_time(cfg):
    """Returns a UTC ISO string if publish_at is set and still in the future, else None."""
    import datetime as dt
    v = cfg.get("publish_at", "")
    daily = cfg.get("publish_daily", "")  # e.g. 01:00 = every video goes public at the next 01:00 Turkey time
    if daily and not v:
        try:
            hh, mm = [int(x) for x in daily.split(":")]
            tr = dt.timezone(dt.timedelta(hours=3))
            now = dt.datetime.now(tr)
            cand = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if cand < now + dt.timedelta(hours=3):
                cand += dt.timedelta(days=1)
            return cand.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except Exception:
            print("publish_daily could not be read, ignoring:", daily)
            return None
    if not v:
        return None
    try:
        t = dt.datetime.fromisoformat(v)
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone(dt.timedelta(hours=3)))
        t = t.astimezone(dt.timezone.utc)
    except Exception:
        print("publish_at could not be read, ignoring:", v)
        return None
    if t < dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=20):
        print("publish_at is in the past (or too soon): the video stays private for manual publishing")
        return None
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def upload(video, thumb, data, cfg=None):
    cfg = cfg or {}
    c = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=c)
    pub = publish_time(cfg)
    privacy = cfg.get("privacy") or os.environ.get("PRIVACY", "private")
    status = {"privacyStatus": "private" if pub else privacy, "selfDeclaredMadeForKids": False}
    if pub:
        status["publishAt"] = pub
        print("Scheduled to go public at", pub)
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
    cfg = read_settings()
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and cfg.get("auto", "0") != "1":
        print("Scheduled run skipped: auto=0 in settings.txt (manual runs only).")
        sys.exit(0)
    open("used.txt", "a").close()
    ensure_fonts()
    key, topic, brief = pick_topic()
    print("Topic:", topic)
    if os.environ.get("TEST_DATA"):
        data = json.load(open(os.environ["TEST_DATA"]))
    else:
        data = generate(topic, brief)
    data = clean(data)
    data["shots"] = trim_shots(data["shots"])
    print(f"Estimated length: {est_seconds(data['shots']) / 60:.1f} min", flush=True)
    os.makedirs("work", exist_ok=True)
    json.dump(data, open("work/script.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Claims to verify:", *data.get("claims_to_check", []), sep="\n - ")
    video = build_video(data, topic)
    thumb = make_thumbnail(data)
    try:
        Image.open(thumb).save("work/thumb.png")  # the workflow artifact list expects thumb.png
    except Exception:
        pass
    if (os.environ.get("UPLOAD") == "1" or cfg.get("upload") == "1") and os.environ.get("YT_REFRESH_TOKEN"):
        vid = upload(video, thumb, data, cfg)
        open("used.txt", "a", encoding="utf-8").write(key + "\n")
        print("Uploaded: https://youtu.be/" + vid)
    else:
        print("Upload is off (settings.txt upload=1 turns it on) or secrets missing: video saved in work/ only, nothing was uploaded.")
