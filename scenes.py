import json, os, random, wave
import numpy as np
from manim import *

INK, LIGHT, YEL, RED = "#14161a", "#f4f1ea", "#f2b63d", "#d9402f"
FW, FH = 14.222, 8.0


def box(w, h, color, x=0, y=0, op=1, sc=None, sw=0, r=0):
    m = RoundedRectangle(corner_radius=r, width=w, height=h) if r else Rectangle(width=w, height=h)
    m.set_fill(color, op)
    m.set_stroke(sc or color, sw)
    return m.move_to([x, y, 0])


def dot(r, color, x=0, y=0, op=1, sc=None, sw=0):
    m = Circle(radius=r)
    m.set_fill(color, op)
    m.set_stroke(sc or color, sw)
    return m.move_to([x, y, 0])


def txt(s, size, color, weight=NORMAL):
    return Text(s, font_size=size, color=color, weight=weight)


def fit(m, w):
    if m.width > w:
        m.scale_to_fit_width(w)
    return m


def envelope(path, fps):
    if not path or not os.path.exists(path):
        return np.zeros(1)
    with wave.open(path) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    hop = max(1, int(sr / fps))
    k = len(data) // hop
    if k == 0:
        return np.zeros(1)
    env = np.array([np.abs(data[i * hop:(i + 1) * hop]).mean() for i in range(k)])
    env = env / (np.percentile(env, 95) + 1e-9)
    return np.clip(env, 0, 1)


def chunks_of(text, size=7):
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [""]


def backdrop(name):
    g = VGroup()
    rnd = random.Random(7)
    if name == "space":
        g.add(box(FW, FH, "#0b1026"))
        for _ in range(70):
            g.add(dot(rnd.uniform(.02, .045), "#ffffff", rnd.uniform(-7, 7), rnd.uniform(-4, 4)))
        g.add(dot(1.2, "#d9825b", -5.2, 2.4))
        ring = Ellipse(width=3.4, height=.6).set_fill(opacity=0).set_stroke("#f2d9a0", 4).move_to([-5.2, 2.4, 0])
        g.add(ring, dot(.5, "#bfc4d6", 5.4, 2.8))
    elif name == "ocean":
        g.add(box(FW, FH, "#5bb5d9"), box(FW, 5, "#1b6a96", y=-1.5, op=.55), box(FW, .9, "#e3cf9a", y=-3.55))
        for x, y, r in [(-6, 0, .2), (-5.6, 1, .12), (6, .5, .25), (5.5, 1.6, .15), (6.4, -.6, .1)]:
            g.add(dot(r, "#ffffff", x, y, op=0, sc="#ffffff", sw=2))
        g.add(box(.2, 1.6, "#2e8b57", -6.4, -2.9), box(.2, 1.2, "#2e8b57", -6.0, -3.1), box(.2, 1.5, "#2e8b57", 6.3, -3.0))
    elif name == "city":
        g.add(box(FW, FH, "#a9cdea"))
        x = -7.0
        while x < 7.2:
            h = rnd.uniform(1.5, 4.2)
            g.add(box(1.2, h, rnd.choice(["#5c6b7e", "#6b7a8f", "#4f5d70"]), x, -2.3 + h / 2))
            x += 1.35
        g.add(box(FW, 1.7, "#444b55", y=-3.15))
    elif name == "nature":
        g.add(box(FW, FH, "#b5e3f5"), dot(.8, YEL, 5.2, 2.9), dot(3.2, "#79c06e", -4, -4.2), dot(4, "#5aa65a", 4, -4.8))
        g.add(box(FW, 1.7, "#6fb36a", y=-3.15), box(.3, 1.2, "#7a5230", -6.1, -1.4), dot(.85, "#3f8f4a", -6.1, -.5))
    elif name == "bedroom":
        g.add(box(FW, FH, "#cdbfe0"), box(FW, 1.7, "#8b6f5a", y=-3.15))
        g.add(box(2, 2.2, "#1b2550", -5.4, 2, sc="#ffffff", sw=3), dot(.4, "#f7f1c4", -5.1, 2.3))
        g.add(box(.12, 1.2, "#555555", 5.4, 1.9), dot(.35, YEL, 5.4, 2.7))
    else:
        g.add(box(FW, FH, "#dfe6ee"), box(FW, 1.7, "#b79c7a", y=-3.15))
        g.add(box(2.8, .12, "#8a6a4a", 5.3, 2.5))
        for x, c in [(4.6, "#e2574c"), (5.3, "#3aa57a"), (6.0, "#4a90d9")]:
            g.add(dot(.28, c, x, 2.85))
        g.add(box(1.6, 2.0, "#ffffff", -5.5, 2.2, sc="#999999", sw=2))
        for i, c in enumerate(["#e2574c", "#f2b63d", "#3aa57a", "#4a90d9"]):
            g.add(box(.35, .35, c, -5.9 + (i % 2) * .8, 2.6 - (i // 2) * .7))
    return g


def character(kind):
    guide = kind == "guide"
    skin = "#f7e3d3" if guide else "#f1d2b5"
    top = "#f4f1ea" if guide else "#ff8a3d"
    hair_c = "#a6a6a6" if guide else "#3a2a20"
    hair = Ellipse(width=1.35, height=.95).set_fill(hair_c, 1).set_stroke(INK, 2).move_to([0, 1.3, 0])
    legs = VGroup(*[box(.34, .85, "#3b4a63", x, -1.4) for x in (-.27, .27)])
    body = box(1.2, 1.5, top, 0, -.3, sc=INK, sw=2, r=.3)
    arms = VGroup(*[box(.28, 1.1, top, x, -.35, sc=INK, sw=2, r=.12) for x in (-.75, .75)])
    head = dot(.62, skin, 0, .85, sc=INK, sw=2)
    eyes = VGroup(dot(.06, INK, -.22, .95), dot(.06, INK, .22, .95))
    mouth = Ellipse(width=.28, height=.05).set_fill("#6b2d2d", 1).set_stroke("#6b2d2d", 1).move_to([0, .62, 0])
    parts = [hair, legs, body, arms, head, eyes, mouth]
    if guide:
        parts.insert(5, VGroup(dot(.17, WHITE, -.22, .95, op=0, sc=INK, sw=2), dot(.17, WHITE, .22, .95, op=0, sc=INK, sw=2)))
        parts.insert(3, Line([0, .45, 0], [0, -1.05, 0]).set_stroke(INK, 2))
    else:
        parts.insert(3, Line([-.35, .45, 0], [.35, .45, 0]).set_stroke(INK, 2))
    return VGroup(*parts), head, mouth


class SceneRenderer(Scene):
    def construct(self):
        spec = json.load(open(os.environ["SCENE_JSON"], encoding="utf-8"))
        dur = float(os.environ["SCENE_DUR"])
        idx = int(os.environ.get("SCENE_IDX", "0"))
        total = max(1, int(os.environ.get("SCENE_TOTAL", "1")))
        topic = os.environ.get("TOPIC", "")
        env = envelope(os.environ.get("SCENE_AUDIO"), config.frame_rate)
        self.camera.background_color = INK
        self.add(backdrop(spec.get("backdrop", "lab")))

        speaker = spec.get("speaker", "guide")
        chars = {}
        for kind, x in (("guide", -4.7), ("you", 4.7)):
            grp, head, mouth = character(kind)
            grp.scale(1.15).move_to([x, -0.8, 0])
            chars[kind] = (grp, head, mouth)
            self.add(grp)

        board_bg, items = self.build_board(spec)
        self.add(board_bg, *[o for o, _ in items])

        tag = box(2.8, .7, INK, 5.4, 3.5, op=.85, r=.12)
        tag_t = txt(f"FACT {idx + 1} / {total}", 24, YEL, BOLD).move_to([5.4, 3.6, 0])
        bar_bg = box(2.4, .07, "#444444", 5.4, 3.3)
        bw = 2.4 * (idx + 1) / total
        bar = box(bw, .07, YEL, 4.2 + bw / 2, 3.3)
        topic_t = fit(txt(topic, 22, LIGHT), 5.2)
        topic_p = box(topic_t.width + .5, .7, INK, 0, 0, op=.85, r=.12)
        topic_p.move_to([-6.8 + topic_p.width / 2, 3.5, 0])
        topic_t.move_to(topic_p.get_center())
        self.add(tag, tag_t, bar_bg, bar, topic_p, topic_t)

        cap_box = box(12, .95, INK, 0, -3.3, op=.78, r=.15)
        parts = chunks_of(spec.get("narration", ""))
        weights = [len(p) + 1 for p in parts]
        cuts, acc = [], 0.15
        usable = max(0.5, dur - 0.3)
        for w_ in weights:
            acc += usable * w_ / sum(weights)
            cuts.append(acc)
        caps = []
        for p in parts:
            c = fit(txt(p, 30, WHITE), 11.4).move_to([0, -3.3, 0])
            c.set_opacity(0)
            caps.append(c)
        self.add(cap_box, *caps)

        st = {"t": 0.0, "cap": -1, "bob": {"guide": 0.0, "you": 0.0}}
        gm = chars[speaker][2] if speaker in chars else chars["guide"][2]

        def tick(_m, dt):
            st["t"] += dt
            t = st["t"]
            board_bg.set_opacity(min(1.0, t / 0.5))
            for o, at in items:
                o.set_opacity(max(0.0, min(1.0, (t - at) / 0.35)))
            k = next((i for i, c in enumerate(cuts) if t < c), len(caps) - 1)
            if k != st["cap"]:
                st["cap"] = k
                for i, c in enumerate(caps):
                    c.set_opacity(1 if i == k else 0)
            for kind, (grp, head, mouth) in chars.items():
                off = 0.04 * np.sin(2.2 * t + (0 if kind == "guide" else 1.3))
                grp.shift(UP * (off - st["bob"][kind]))
                st["bob"][kind] = off
                if mouth is gm:
                    o = float(env[min(len(env) - 1, int(t * config.frame_rate))])
                    h = (0.05 + 0.3 * o) * 1.15
                else:
                    h = 0.05 * 1.15
                mouth.stretch_to_fit_height(h)
                mouth.move_to(head.get_center() + DOWN * 0.23 * 1.15)

        clock = Mobject()
        clock.add_updater(tick)
        self.add(clock)
        self.wait(dur)

    def build_board(self, s):
        cy = 1.2
        panel = box(5.8, 3.3, LIGHT, 0, cy, sc=INK, sw=3, r=.2)
        bg = VGroup(panel)
        items = []
        kind = s.get("type", "bullets")
        head = s.get("heading") or s.get("text") or ""
        if head:
            h = fit(txt(head, 34 if kind != "title" else 44, RED, BOLD), 5.2).move_to([0, cy + 1.1, 0])
            bg.add(h)
        if kind == "title":
            sub = fit(txt(s.get("subtitle", ""), 28, "#444444"), 5.2).move_to([0, cy - .3, 0])
            items.append((sub, 0.8))
        elif kind == "stat":
            v = fit(txt(str(s.get("value", "")), 76, INK, BOLD), 5.2).move_to([0, cy + .1, 0])
            l = fit(txt(s.get("label", ""), 30, "#444444"), 5.2).move_to([0, cy - 1.0, 0])
            items += [(v, 0.6), (l, 1.5)]
        elif kind == "diagram":
            nodes = s.get("nodes", [])[:4]
            grp = VGroup()
            for n in nodes:
                r = box(1.2, .9, WHITE, sc=RED, sw=3, r=.12)
                t = fit(txt(n, 20, INK), 1.05).move_to(r.get_center())
                grp.add(VGroup(r, t))
            grp.arrange(RIGHT, buff=.45)
            fit(grp, 5.2).move_to([0, cy - .3, 0])
            gap = max(0.6, 1.5)
            for i, nd in enumerate(grp):
                items.append((nd, 0.8 + i * gap))
                if i:
                    a = Arrow(grp[i - 1].get_right(), nd.get_left(), buff=.04, color=YEL, stroke_width=4, tip_length=.15)
                    items.append((a, 0.8 + i * gap))
        else:
            for i, it in enumerate(s.get("items", [])[:4]):
                t = txt("• " + it, 28, INK)
                fit(t, 5.2)
                t.move_to([-2.7 + t.width / 2, cy + .35 - i * .62, 0])
                items.append((t, 0.8 + i * 1.2))
        for o, _ in items:
            o.set_opacity(0)
        return bg, items
