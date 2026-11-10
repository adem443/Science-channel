import json, os, random, textwrap, wave
import numpy as np
from manim import *

INK, YEL, RED = "#14161a", "#f2b63d", "#ff3b30"
FW, FH = 14.222, 8.0
GROUND = -2.55


# ---------------------------------------------------------------- helpers
def S(m, fill, op=1, stroke=INK, sw=2):
    m.set_fill(fill, op)
    m.set_stroke(stroke, sw)
    return m


def pl(pts, color, w=4):
    m = VMobject()
    m.set_points_as_corners([[x, y, 0] for x, y in pts])
    m.set_fill(opacity=0)
    m.set_stroke(color, w)
    return m


def T(s, size, color=WHITE, outline=True):
    t = Text(str(s), font_size=size, color=color, weight=BOLD)
    if outline:
        t.set_stroke(BLACK, max(3, size / 9), background=True)
    return t


def fit(m, w):
    if m.width > w:
        m.scale_to_fit_width(w)
    return m


def ease_back(x):
    x = min(max(x, 0.0), 1.0)
    return 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


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
    words = (text or "").split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [""]


# ---------------------------------------------------------------- icons
ICONS = {}


def icon(name):
    def deco(fn):
        ICONS[name] = fn
        return fn
    return deco


def drop_shape(color):
    return VGroup(S(Triangle().scale(.62).stretch(1.25, 1).move_to([0, .35, 0]).rotate(0), color),
                  S(Circle(radius=.5), color).move_to([0, -.25, 0]))


@icon("battery")
def _battery():
    body = S(RoundedRectangle(corner_radius=.18, width=1.1, height=1.9), "#4cd964", sw=4)
    cap = S(Rectangle(width=.42, height=.2), "#bbbbbb", sw=3)
    bolt = S(Polygon([.15, .6, 0], [-.25, -.1, 0], [0, -.1, 0], [-.15, -.7, 0], [.28, .05, 0], [.03, .05, 0]), WHITE, sw=2)
    cracks = VGroup(pl([(-.3, .5), (0, .15), (-.2, -.25), (.1, -.6)], "#222222", 4),
                    pl([(.35, .3), (.1, 0), (.3, -.4)], "#222222", 4))
    puffs = VGroup(*[S(Circle(radius=r), "#cfcfcf", .85, stroke="#888888", sw=2) for r in (.22, .3, .18)])
    g = VGroup(puffs, body, cap, bolt, cracks)
    c0, cm, c1 = ManimColor("#4cd964"), ManimColor("#ffb703"), ManimColor("#ff3b30")

    def sp(p, t):
        body.stretch_to_fit_width(1.1 + .85 * p)
        body.stretch_to_fit_height(1.9 + .4 * p)
        body.set_fill(interpolate_color(c0, cm, p * 2) if p < .5 else interpolate_color(cm, c1, p * 2 - 1), 1)
        cap.next_to(body, UP, buff=0)
        cracks.set_opacity(1 if p > .6 else 0)
        cracks.scale(1 + .4 * p)
        for i, pf in enumerate(puffs):
            fr = (t * .55 + i / 3) % 1
            pf.move_to([(-.4 + .4 * i) * (1 + p), body.get_top()[1] + .2 + fr * 1.1, 0])
            pf.set_opacity(0 if p < .2 else (1 - fr) * .9)
    return g, sp


@icon("phone")
def _phone():
    b = S(RoundedRectangle(corner_radius=.2, width=1.15, height=2.1), "#2b2f3a", sw=4)
    sc = S(RoundedRectangle(corner_radius=.1, width=.95, height=1.75), "#7fd1ff", sw=1)
    bt = S(RoundedRectangle(corner_radius=.05, width=.5, height=.25), "#ff3b30", sw=2).move_to([0, .3, 0])
    return VGroup(b, sc, bt), None


@icon("thermometer")
def _thermo():
    tube = S(RoundedRectangle(corner_radius=.25, width=.5, height=1.9), WHITE, sw=4).move_to([0, .1, 0])
    bulb = S(Circle(radius=.5), RED, sw=4).move_to([0, -1.0, 0])
    lvl = S(Rectangle(width=.22, height=.5), RED, sw=0)
    ticks = VGroup(*[Line([.3, .5 + i * .35, 0], [.5, .5 + i * .35, 0]).set_stroke(INK, 3) for i in range(4)])
    g = VGroup(tube, bulb, lvl, ticks)

    def sp(p, t):
        h = .15 + 1.4 * p
        lvl.stretch_to_fit_height(h)
        lvl.move_to([0, -.85 + h / 2, 0])
    return g, sp


@icon("flame")
def _flame():
    o = VGroup(S(Triangle().scale(.7).stretch(1.4, 1).move_to([0, .4, 0]), "#ff7a00"),
               S(Circle(radius=.62), "#ff7a00").move_to([0, -.35, 0]))
    i = VGroup(S(Triangle().scale(.4).stretch(1.3, 1).move_to([0, .1, 0]), "#ffd23f", sw=0),
               S(Circle(radius=.36), "#ffd23f", sw=0).move_to([0, -.5, 0]))
    g = VGroup(o, i)

    def sp(p, t):
        g.stretch(1 + .1 * np.sin(11 * t), 1)
    return g, sp


@icon("bolt")
def _bolt():
    return VGroup(S(Polygon([.3, 1, 0], [-.5, -.1, 0], [-.05, -.1, 0], [-.3, -1, 0], [.5, .15, 0], [.05, .15, 0]), "#ffd23f", sw=4)), None


@icon("sun")
def _sun():
    rays = VGroup(*[Line([1.0 * np.cos(a), 1.0 * np.sin(a), 0], [1.35 * np.cos(a), 1.35 * np.sin(a), 0]).set_stroke("#ffb703", 6)
                    for a in np.linspace(0, TAU, 12, endpoint=False)])
    return VGroup(rays, S(Circle(radius=.8), "#ffd23f", sw=4)), None


@icon("moon")
def _moon():
    try:
        m = Difference(Circle(radius=.9), Circle(radius=.75).shift([.45, .2, 0]))
        S(m, "#f7f1c4", sw=3)
    except Exception:
        m = S(Circle(radius=.9), "#f7f1c4", sw=3)
    return VGroup(m), None


@icon("earth")
def _earth():
    c = S(Circle(radius=1), "#2d8cff", sw=4)
    l1 = S(Ellipse(width=.7, height=.9), "#3bb273", sw=1).move_to([-.25, .2, 0])
    l2 = S(Ellipse(width=.5, height=.4), "#3bb273", sw=1).move_to([.35, -.35, 0])
    return VGroup(c, l1, l2), None


@icon("planet")
def _planet():
    ring = Ellipse(width=2.6, height=.6).set_fill(opacity=0).set_stroke("#f2d9a0", 6).rotate(.3)
    return VGroup(S(Circle(radius=.8), "#d9825b", sw=4), ring), None


@icon("star")
def _star():
    return VGroup(S(Star(n=5, outer_radius=1, inner_radius=.45), "#ffd23f", sw=4)), None


@icon("cloud")
def _cloud():
    cs = [S(Circle(radius=r), WHITE, stroke="#9aa5b1", sw=3).move_to([x, y, 0]) for x, y, r in
          [(-.5, -.1, .45), (0, .2, .6), (.55, -.05, .45)]]
    base = S(Rectangle(width=1.5, height=.4), WHITE, stroke=WHITE, sw=0).move_to([.02, -.28, 0])
    return VGroup(*cs, base), None


@icon("drop")
def _drop():
    return drop_shape("#3aa0ff"), None


@icon("gear")
def _gear():
    return VGroup(S(Star(n=8, outer_radius=1, inner_radius=.75), "#9aa5b1", sw=4), S(Circle(radius=.35), "#555555", sw=3)), None


@icon("magnet")
def _magnet():
    arc = Arc(radius=.7, start_angle=PI, angle=PI).rotate(PI).set_stroke(RED, 36)
    arc = Arc(radius=.7, start_angle=0, angle=PI).rotate(PI).set_stroke(RED, 36).shift([0, .2, 0])
    t1 = S(Rectangle(width=.36, height=.3), "#dddddd", sw=3).move_to([-.7, -.4, 0])
    t2 = S(Rectangle(width=.36, height=.3), "#dddddd", sw=3).move_to([.7, -.4, 0])
    return VGroup(arc, t1, t2), None


@icon("atom")
def _atom():
    els = VGroup(*[Ellipse(width=2.4, height=.8).set_fill(opacity=0).set_stroke("#4cc9f0", 4).rotate(a) for a in (0, PI / 3, 2 * PI / 3)])
    dots = VGroup(*[S(Circle(radius=.09), "#ffd23f", sw=1).move_to(p) for p in ([1.2, 0, 0], [-.6, .5, 0], [-.6, -.5, 0])])
    return VGroup(els, S(Circle(radius=.22), RED, sw=2), dots), None


@icon("dna")
def _dna():
    ys = np.linspace(-1, 1, 40)
    a = pl([(.45 * np.sin(y * 3.2), y) for y in ys], "#4cc9f0", 6)
    b = pl([(-.45 * np.sin(y * 3.2), y) for y in ys], "#f72585", 6)
    rungs = VGroup(*[Line([.45 * np.sin(y * 3.2), y, 0], [-.45 * np.sin(y * 3.2), y, 0]).set_stroke("#ffffff", 3) for y in np.linspace(-.9, .9, 9)])
    return VGroup(rungs, a, b), None


@icon("heart")
def _heart():
    c1 = S(Circle(radius=.5), "#ff3b6b", sw=3).move_to([-.4, .3, 0])
    c2 = S(Circle(radius=.5), "#ff3b6b", sw=3).move_to([.4, .3, 0])
    tr = S(Triangle().rotate(PI).scale(.95).move_to([0, -.25, 0]), "#ff3b6b", sw=3)
    cover = S(Rectangle(width=.8, height=.5), "#ff3b6b", stroke="#ff3b6b", sw=0).move_to([0, .1, 0])
    return VGroup(tr, c1, c2, cover), None


@icon("brain")
def _brain():
    a = S(Ellipse(width=1.3, height=1.4), "#ff9ebb", sw=3).move_to([-.45, 0, 0])
    b = S(Ellipse(width=1.3, height=1.4), "#ff9ebb", sw=3).move_to([.45, 0, 0])
    sq = VGroup(pl([(0, .6), (0, -.6)], "#c2185b", 3), pl([(-.7, .2), (-.3, .1), (-.5, -.3)], "#c2185b", 3),
                pl([(.7, .2), (.3, .1), (.5, -.3)], "#c2185b", 3))
    return VGroup(a, b, sq), None


@icon("virus")
def _virus():
    sp = VGroup(*[Line([.7 * np.cos(a), .7 * np.sin(a), 0], [1.05 * np.cos(a), 1.05 * np.sin(a), 0]).set_stroke("#2e7d32", 5)
                  for a in np.linspace(0, TAU, 12, endpoint=False)])
    tips = VGroup(*[S(Circle(radius=.09), "#2e7d32", sw=1).move_to([1.05 * np.cos(a), 1.05 * np.sin(a), 0]) for a in np.linspace(0, TAU, 12, endpoint=False)])
    return VGroup(sp, tips, S(Circle(radius=.7), "#7bd389", sw=3)), None


@icon("plant")
def _plant():
    pot = S(Polygon([-.5, -.4, 0], [.5, -.4, 0], [.35, -1, 0], [-.35, -1, 0]), "#c8744a", sw=3)
    stem = pl([(0, -.4), (0, .5)], "#2e7d32", 6)
    l1 = S(Ellipse(width=.9, height=.4).rotate(.6).move_to([.4, .3, 0]), "#4caf50", sw=2)
    l2 = S(Ellipse(width=.9, height=.4).rotate(-.6).move_to([-.4, .55, 0]), "#4caf50", sw=2)
    return VGroup(stem, l1, l2, pot), None


@icon("rocket")
def _rocket():
    b = S(Ellipse(width=.9, height=2.0), "#e8eef5", sw=3)
    n = S(Triangle().scale(.45).move_to([0, 1.05, 0]), RED, sw=3)
    f1 = S(Triangle().scale(.35).rotate(PI / 2 + PI).move_to([-.55, -.7, 0]), RED, sw=3)
    f2 = S(Triangle().scale(.35).rotate(PI / 2).move_to([.55, -.7, 0]), RED, sw=3)
    w = S(Circle(radius=.2), "#4cc9f0", sw=3).move_to([0, .3, 0])
    fl = S(Triangle().scale(.35).rotate(PI).move_to([0, -1.2, 0]), "#ff9f1c", sw=0)
    return VGroup(fl, f1, f2, b, n, w), None


@icon("bulb")
def _bulb():
    return VGroup(S(Circle(radius=.7), "#ffe066", sw=4).move_to([0, .3, 0]),
                  S(Rectangle(width=.6, height=.4), "#9aa5b1", sw=3).move_to([0, -.55, 0])), None


@icon("magnifier")
def _mag():
    h = Line([.5, -.5, 0], [1.0, -1.0, 0]).set_stroke("#6d4c41", 14)
    c = Circle(radius=.7).set_fill("#bfe9ff", .5).set_stroke("#444444", 10).move_to([-.1, .1, 0])
    return VGroup(h, c), None


@icon("clock")
def _clock():
    c = S(Circle(radius=1), WHITE, sw=5)
    ticks = VGroup(*[Line([.85 * np.cos(a), .85 * np.sin(a), 0], [.95 * np.cos(a), .95 * np.sin(a), 0]).set_stroke(INK, 4) for a in np.linspace(0, TAU, 12, endpoint=False)])
    hand = Line([0, 0, 0], [0, .65, 0]).set_stroke(INK, 6)
    hand2 = Line([0, 0, 0], [.4, 0, 0]).set_stroke(INK, 6)
    g = VGroup(c, ticks, hand2, hand)

    def sp(p, t):
        hand.rotate(-t * 2.5, about_point=ORIGIN)
    return g, sp


@icon("warning")
def _warn():
    tr = S(Triangle().scale(1.1), "#ffd23f", sw=5)
    ex = T("!", 70, INK, outline=False).move_to([0, -.1, 0])
    return VGroup(tr, ex), None


@icon("check")
def _check():
    return VGroup(S(Circle(radius=.9), "#34c759", sw=4), pl([(-.45, 0), (-.1, -.35), (.5, .35)], WHITE, 12)), None


@icon("cross")
def _cross():
    return VGroup(S(Circle(radius=.9), RED, sw=4), pl([(-.4, .4), (.4, -.4)], WHITE, 12), pl([(-.4, -.4), (.4, .4)], WHITE, 12)), None


@icon("gas")
def _gas():
    return VGroup(*[S(Circle(radius=r), "#dfe6ee", .8, stroke="#8895a3", sw=3).move_to([x, y, 0]) for x, y, r in
                    [(-.4, -.3, .5), (.35, -.1, .6), (0, .5, .45), (-.5, .45, .3), (.6, .6, .25)]]), None


@icon("explosion")
def _boom():
    return VGroup(S(Star(n=12, outer_radius=1.2, inner_radius=.65), "#ff7a00", sw=4),
                  S(Star(n=12, outer_radius=.8, inner_radius=.4), "#ffd23f", sw=0)), None


@icon("shield")
def _shield():
    sh = S(Polygon([-.8, .8, 0], [.8, .8, 0], [.8, -.1, 0], [0, -1, 0], [-.8, -.1, 0]), "#2d8cff", sw=4)
    return VGroup(sh, pl([(-.35, 0), (-.05, -.3), (.4, .3)], WHITE, 10)), None


@icon("wave")
def _wave():
    xs = np.linspace(-1.1, 1.1, 60)
    return VGroup(pl([(x, .5 * np.sin(x * 4)) for x in xs], "#4cc9f0", 10)), None


@icon("question")
def _q():
    return VGroup(S(Circle(radius=.9), "#7b5ea7", sw=4), T("?", 90, WHITE, outline=False).move_to([0, 0, 0])), None


@icon("dollar")
def _dollar():
    return VGroup(S(Circle(radius=.9), "#ffd23f", sw=4), T("$", 90, INK, outline=False)), None


@icon("chart")
def _chart():
    bars = VGroup(*[S(Rectangle(width=.4, height=1.4), c, sw=2) for c in ("#4cc9f0", "#34c759", "#ffd23f", "#ff3b30")])
    bars.arrange(RIGHT, buff=.15, aligned_edge=DOWN)
    base = Line([-1, -.75, 0], [1, -.75, 0]).set_stroke(WHITE, 4)
    bars.move_to([0, 0, 0])
    heights = [.5, .9, 1.2, 1.7]
    g = VGroup(bars, base)

    def sp(p, t):
        for i, b in enumerate(bars):
            h = max(.05, heights[i] * clamp(p * 1.3 - i * .12))
            b.stretch_to_fit_height(h)
            b.move_to([b.get_center()[0], -.75 + h / 2, 0])
    return g, sp


@icon("molecule")
def _mol():
    pts = [(-.7, -.3), (.1, .5), (.8, -.2)]
    ls = VGroup(pl([pts[0], pts[1]], "#bbbbbb", 8), pl([pts[1], pts[2]], "#bbbbbb", 8))
    ds = VGroup(*[S(Circle(radius=r), c, sw=3).move_to([x, y, 0]) for (x, y), r, c in zip(pts, (.4, .32, .4), ("#ff3b30", "#4cc9f0", "#34c759"))])
    return VGroup(ls, ds), None


@icon("snow")
def _snow():
    return VGroup(*[Line([-.9 * np.cos(a), -.9 * np.sin(a), 0], [.9 * np.cos(a), .9 * np.sin(a), 0]).set_stroke("#bfe9ff", 7) for a in (0, PI / 3, 2 * PI / 3)]), None


ICON_NAMES = sorted(ICONS)


def make_icon(name):
    fn = ICONS.get(name) or ICONS["question"]
    g, sp = fn()
    g.move_to(ORIGIN)
    return g, sp


class Slot:
    """One animated prop (icon + optional label)."""

    def __init__(self, spec, x, y, scale, t_in):
        self.name = spec.get("icon") or "question"
        self.anim = spec.get("anim") or "pop"
        self.g, self.sp = make_icon(self.name)
        self.g.save_state()
        self.x, self.y, self.s, self.t_in = x, y, scale, t_in
        lab = spec.get("label")
        self.tag = None
        if lab:
            tx = fit(T(str(lab), 30, WHITE, outline=False), 3.2)
            bx = S(RoundedRectangle(corner_radius=.15, width=tx.width + .5, height=.62), "#14161a", .92, stroke=YEL, sw=2)
            self.tag = VGroup(bx, tx.move_to(bx.get_center()))
            self.tag.move_to([x, y - 1.45 * scale - .5, 0])
            self.tag.save_state()

    def mobs(self):
        return [self.g] + ([self.tag] if self.tag else [])

    def update(self, t, dur):
        x = t - self.t_in
        s = ease_back(x / .4) if x >= 0 else 0.0
        self.g.restore()
        p = 0.0
        sm, rot, dx, dy = 1.0, 0.0, 0.0, 0.0
        a = self.anim
        if a in ("swell", "rise", "grow"):
            p = clamp((x - .4) / max(1.0, dur * .6))
            p = p * p * (3 - 2 * p)
        if self.sp:
            self.sp(p if a in ("swell", "rise", "grow") else 0.0, max(x, 0))
        elif a in ("swell", "grow"):
            sm = .8 + .5 * p
        if a == "pulse":
            sm = 1 + .07 * np.sin(6 * x)
        elif a == "shake":
            dx = .06 * np.sin(32 * x)
        elif a == "spin":
            rot = x * 1.6
        elif a == "float":
            dy = .12 * np.sin(2.6 * x)
        elif a == "rise" and not self.sp:
            dy = .5 * p
        if a == "swell" and self.sp:
            dx = .04 * np.sin(30 * x) * p
        self.g.scale(max(s * self.s * sm, 1e-3))
        if rot:
            self.g.rotate(rot)
        self.g.shift([self.x + dx, self.y + dy, 0])


# ---------------------------------------------------------------- characters
class Char:
    def __init__(self, kind):
        fem = kind == "you"
        self.fem = fem
        skin = "#f1d2b5" if fem else "#f7e3d3"
        top = "#2ec4b6" if fem else "#f4f1ea"
        hair_c = "#4a2f1b" if fem else "#a6a6a6"
        pants = "#7b5ea7" if fem else "#3b4a63"

        def limb(px, py, w, h, col):
            pv = Dot([px, py, 0], radius=.01).set_opacity(0)
            r = S(RoundedRectangle(corner_radius=min(w, h) / 2.5, width=w, height=h), col)
            r.move_to([px, py - h / 2 + .03, 0])
            return VGroup(pv, r)

        if fem:
            hair_back = S(RoundedRectangle(corner_radius=.5, width=1.55, height=2.1), hair_c).move_to([0, .55, 0])
        else:
            hair_back = S(Ellipse(width=1.4, height=1.0), hair_c).move_to([0, 1.3, 0])
        self.leg_l, self.leg_r = limb(-.27, -.95, .34, .85, pants), limb(.27, -.95, .34, .85, pants)
        body = S(RoundedRectangle(corner_radius=.3, width=1.2, height=1.5), top).move_to([0, -.3, 0])
        parts = [hair_back, self.leg_l, self.leg_r]
        if fem:
            parts.append(S(Polygon([-.6, -.6, 0], [.6, -.6, 0], [.9, -1.25, 0], [-.9, -1.25, 0]), pants))
        parts.append(body)
        if not fem:
            parts.append(Line([0, .45, 0], [0, -1.05, 0]).set_stroke(INK, 2))
        self.arm_l, self.arm_r = limb(-.72, .3, .28, 1.1, top), limb(.72, .3, .28, 1.1, top)
        parts += [self.arm_l, self.arm_r]
        self.head = S(Circle(radius=.62), skin).move_to([0, .85, 0])
        self.eyes_w = VGroup(*[S(Circle(radius=.11), WHITE, sw=2).move_to([x, .92, 0]) for x in (-.22, .22)])
        self.pupils = VGroup(*[S(Circle(radius=.055), INK, sw=0).move_to([x, .92, 0]) for x in (-.22, .22)])
        self.brows = VGroup(Line([-.34, 1.12, 0], [-.1, 1.15, 0]).set_stroke(INK, 4), Line([.1, 1.15, 0], [.34, 1.12, 0]).set_stroke(INK, 4))
        self.mouth = S(Ellipse(width=.28, height=.05), "#c0392b" if fem else "#6b2d2d", stroke="#6b2d2d", sw=1).move_to([0, .6, 0])
        face = [self.head]
        if fem:
            face.append(S(Ellipse(width=1.15, height=.4), hair_c, sw=2).move_to([0, 1.3, 0]))
        face += [self.eyes_w, self.pupils, self.brows, self.mouth]
        if not fem:
            face.append(VGroup(*[Circle(radius=.17).set_fill(opacity=0).set_stroke(INK, 2).move_to([x, .92, 0]) for x in (-.22, .22)]))
        self.face = VGroup(*face)
        parts.append(self.face)
        self.g = VGroup(*parts)
        self.g.save_state()

    def pose(self, t, x, ground, scale=1.15, speaking=False, amp=0.0, point=0, emote=None, ep=0.0,
             walking=False, calm=False, wave_hand=False):
        g = self.g
        g.restore()
        jump = 0.0
        if walking:
            a = .4 * np.sin(8 * t)
            self.leg_l.rotate(a, about_point=self.leg_l[0].get_center())
            self.leg_r.rotate(-a, about_point=self.leg_r[0].get_center())
            bob = .06 * abs(np.sin(8 * t))
        else:
            bob = .03 * np.sin(2.2 * t + (0 if not self.fem else 1.3))
        for arm, s in ((self.arm_l, -1), (self.arm_r, 1)):
            ang = 0.0
            if walking:
                ang = s * .35 * np.sin(8 * t)
            elif wave_hand and s == 1:
                ang = 2.3 + .35 * np.sin(9 * t)
            elif point == s:
                ang = s * (1.35 + .05 * np.sin(5 * t))
            elif speaking:
                ang = s * (.1 + .6 * amp) * (.6 + .4 * np.sin(3.3 * t + (1 if s > 0 else 0)))
            if emote == "shock":
                ang = s * (.4 + 1.3 * ep)
            elif emote == "happy":
                ang = s * (.3 + 1.6 * ep * (.5 + .5 * np.sin(10 * t)))
            arm.rotate(ang, about_point=arm[0].get_center())
        h = .05 + (.34 * amp if speaking else 0)
        w = .28
        if emote == "shock":
            h, w = max(h, .05 + .38 * ep), .22
            for pu in self.pupils:
                pu.scale(1 + .6 * ep)
            self.brows.shift(UP * .12 * ep)
            jump = .32 * max(0.0, np.sin(PI * clamp(ep * 1.0))) if ep < 1 else 0.0
        elif emote == "happy":
            w, h = .2 + .28 * ep, max(h, .06)
            jump = .12 * abs(np.sin(9 * t)) * ep
        elif emote == "worried":
            w = .2
            self.brows.rotate(.0)
            self.brows.shift(UP * .05 * ep)
        elif emote == "think":
            self.pupils.shift(UP * .04 * ep + RIGHT * .03 * ep)
            self.brows[1].shift(UP * .1 * ep)
        self.mouth.stretch_to_fit_width(w)
        self.mouth.stretch_to_fit_height(h)
        if (t % 3.3) < .12:
            self.eyes_w.stretch_to_fit_height(.03)
            self.pupils.set_opacity(0)
        tilt = .13 * ep if emote == "think" else (.04 * np.sin(3 * t) if speaking else .05 * np.sin(2.4 * t))
        self.face.rotate(tilt, about_point=[0, .3, 0])
        g.scale(scale * (1 + .03 * amp if speaking else 1), about_point=[0, -1.75, 0])
        g.shift([x, ground + 1.75 + bob + jump, 0])


# ---------------------------------------------------------------- backdrops
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


def backdrop(name):
    g, amb = VGroup(), []
    rnd = random.Random(7)
    if name == "space":
        g.add(box(FW, FH, "#0b1026"))
        for _ in range(60):
            d = dot(rnd.uniform(.02, .05), WHITE, rnd.uniform(-7, 7), rnd.uniform(-4, 4))
            amb.append(("twinkle", d, rnd.uniform(0, 6)))
        g.add(dot(1.2, "#d9825b", -5.4, 2.4))
        g.add(Ellipse(width=3.4, height=.6).set_fill(opacity=0).set_stroke("#f2d9a0", 4).move_to([-5.4, 2.4, 0]), dot(.5, "#bfc4d6", 5.6, 2.8))
        g.add(box(FW, 1.5, "#1a1f3d", y=-3.25))
    elif name == "ocean":
        g.add(box(FW, FH, "#5bb5d9"), box(FW, 5.2, "#1b6a96", y=-1.4, op=.6), box(FW, 1.1, "#e3cf9a", y=-3.45))
        for i in range(6):
            amb.append(("bubble", dot(rnd.uniform(.08, .22), WHITE, rnd.uniform(-6.5, 6.5), rnd.uniform(-3, 3), op=0, sc=WHITE, sw=2), rnd.uniform(0, 5)))
        g.add(box(.2, 1.6, "#2e8b57", -6.4, -2.8), box(.2, 1.2, "#2e8b57", -6.0, -3.0), box(.2, 1.5, "#2e8b57", 6.3, -2.9))
    elif name == "city":
        g.add(box(FW, FH, "#a9cdea"))
        x = -7.0
        while x < 7.2:
            h = rnd.uniform(1.5, 4.4)
            g.add(box(1.2, h, rnd.choice(["#5c6b7e", "#6b7a8f", "#4f5d70"]), x, -2.3 + h / 2))
            x += 1.35
        g.add(box(FW, 1.6, "#444b55", y=-3.2))
        for i in range(3):
            amb.append(("cloud", VGroup(dot(.4, WHITE, 0, 0), dot(.55, WHITE, .5, .1), dot(.4, WHITE, 1.0, 0)).move_to([-5 + i * 5, 3 - i * .4, 0]), i))
    elif name == "nature":
        g.add(box(FW, FH, "#b5e3f5"), dot(.8, YEL, 5.4, 2.9), dot(3.2, "#79c06e", -4, -4.2), dot(4, "#5aa65a", 4, -4.8))
        g.add(box(FW, 1.6, "#6fb36a", y=-3.2), box(.3, 1.2, "#7a5230", -6.1, -1.3), dot(.85, "#3f8f4a", -6.1, -.4))
        for i in range(3):
            amb.append(("cloud", VGroup(dot(.4, WHITE, 0, 0), dot(.55, WHITE, .5, .1), dot(.4, WHITE, 1.0, 0)).move_to([-4 + i * 4.5, 2.8 - i * .5, 0]), i))
    elif name == "bedroom":
        g.add(box(FW, FH, "#cdbfe0"), box(FW, 1.6, "#8b6f5a", y=-3.2))
        g.add(box(2, 2.2, "#1b2550", -5.6, 2, sc=WHITE, sw=3), dot(.4, "#f7f1c4", -5.3, 2.3))
        g.add(box(.12, 1.2, "#555555", 5.6, 1.9), dot(.35, YEL, 5.6, 2.7))
    else:
        g.add(box(FW, FH, "#dfe6ee"), box(FW, 1.6, "#b79c7a", y=-3.2))
        g.add(box(2.8, .12, "#8a6a4a", 5.4, 2.5))
        for x, c in [(4.7, "#e2574c"), (5.4, "#3aa57a"), (6.1, "#4a90d9")]:
            g.add(dot(.28, c, x, 2.85))
        g.add(box(1.6, 2.0, WHITE, -5.7, 2.2, sc="#999999", sw=2))
        for i, c in enumerate(["#e2574c", "#f2b63d", "#3aa57a", "#4a90d9"]):
            g.add(box(.35, .35, c, -6.1 + (i % 2) * .8, 2.6 - (i // 2) * .7))
    return g, amb


def update_ambient(amb, t):
    for kind, m, ph in amb:
        if kind == "twinkle":
            m.set_opacity(.35 + .65 * abs(np.sin(1.3 * t + ph)))
        elif kind == "bubble":
            f = ((t * .25 + ph / 5) % 1)
            y = -3.2 + f * 6.4
            m.move_to([m.get_center()[0], y, 0])
            m.set_stroke(opacity=.9 * (1 - abs(2 * f - 1)))
        elif kind == "cloud":
            x = ((t * .35 + ph * 5) % 18) - 9
            m.move_to([x, m.get_center()[1], 0])


# ---------------------------------------------------------------- shot scene
class SceneRenderer(Scene):
    def construct(self):
        spec = json.load(open(os.environ["SCENE_JSON"], encoding="utf-8"))
        dur = float(os.environ["SCENE_DUR"])
        idx = int(os.environ.get("SCENE_IDX", "0"))
        total = max(1, int(os.environ.get("SCENE_TOTAL", "1")))
        topic = os.environ.get("TOPIC", "")
        enter = os.environ.get("SHOT_ENTER", "1") == "1"
        side = 1 if os.environ.get("SHOT_SIDE", "1") == "1" else -1
        fps = config.frame_rate
        env = envelope(os.environ.get("SCENE_AUDIO"), fps)

        kind = spec.get("kind") or "scene"
        layout = spec.get("layout") or "duo"
        speaker = spec.get("speaker") or "guide"
        if speaker not in ("guide", "you"):
            speaker = "guide"
        props = [p for p in (spec.get("props") or []) if isinstance(p, dict)][:2]
        reaction = spec.get("reaction") or "none"
        self.camera.background_color = INK
        bd, amb = backdrop(spec.get("backdrop") or "lab")
        self.add(bd)
        for _, m, _ in amb:
            self.add(m)

        # --- characters
        chars, tx = {}, {}
        if layout == "duo":
            chars = {"guide": Char("guide"), "you": Char("you")}
            tx = {"guide": -4.9, "you": 4.9}
        elif layout in ("solo", "walk"):
            chars = {speaker: Char(speaker)}
            tx = {speaker: -4.4 * side}
        for c in chars.values():
            self.add(c.g)

        # --- props
        cy = 0.9
        if layout == "walk":
            cy = 1.9
        if layout == "prop_only":
            cy = 0.5
        if kind in ("diagram",):
            cy = -0.2
        if kind in ("title", "stat"):
            cy = 0.1
        cx = {"duo": 0.0, "solo": 1.4 * side, "walk": 0.0, "prop_only": 0.0}.get(layout, 0.0)
        sc1 = 1.45 if layout == "prop_only" else (1.15 if kind in ("title", "stat", "diagram") else 1.3)
        if layout == "walk":
            sc1 = .85
        slots = []
        if len(props) == 1:
            slots.append(Slot(props[0], cx, cy, sc1, .35))
        elif len(props) == 2:
            for i, p in enumerate(props):
                slots.append(Slot(p, cx + (-1.9 if i == 0 else 1.9) * (sc1 / 1.3), cy, sc1 * .78, .35 + .7 * i))
        for s_ in slots:
            for m in s_.mobs():
                self.add(m)

        # --- kind extras
        pops = []
        if kind in ("title", "stat"):
            main = T(spec.get("text") or spec.get("value") or "", 64 if kind == "title" else 96, YEL if kind == "stat" else WHITE)
            fit(main, 11).move_to([0, 2.7, 0])
            sub = T(spec.get("subtitle") or spec.get("label") or "", 30, WHITE)
            fit(sub, 11).move_to([0, 1.7 if kind == "title" else 1.75, 0])
            for m, t0 in ((main, .2), (sub, .8)):
                m.save_state()
                pops.append((m, t0))
                self.add(m)
        if kind == "diagram":
            nodes = (spec.get("nodes") or [])[:4]
            grp = VGroup()
            for n in nodes:
                r = box(2.3, 1.1, WHITE, sc=RED, sw=4, r=.18)
                tt = fit(T(textwrap.fill(str(n), 15), 24, INK, outline=False), 2.1).move_to(r.get_center())
                grp.add(VGroup(r, tt))
            grp.arrange(RIGHT, buff=.6)
            fit(grp, 10.5).move_to([0, 2.2, 0])
            head = spec.get("heading")
            for i, nd in enumerate(grp):
                t0 = .5 + i * max(.8, (dur - 1.5) / (len(nodes) + 1))
                nd.save_state()
                pops.append((nd, t0))
                self.add(nd)
                if i:
                    a = Arrow(grp[i - 1].get_right(), nd.get_left(), buff=.05, color=YEL, stroke_width=6, tip_length=.2)
                    a.save_state()
                    pops.append((a, t0))
                    self.add(a)

        # --- HUD
        tag_t = fit(T(topic, 22, WHITE, outline=False), 5.2)
        tag_p = box(tag_t.width + .5, .62, INK, 0, 0, op=.8, r=.12)
        tag_p.move_to([-6.9 + tag_p.width / 2, 3.45, 0])
        tag_t.move_to(tag_p.get_center())
        bar_bg = box(FW, .12, "#333333", 0, 3.94)
        bar = box(FW, .12, YEL, 0, 3.94)
        self.add(tag_p, tag_t, bar_bg, bar)

        # --- captions
        parts = chunks_of(spec.get("narration"), 6)
        wts = [len(p) + 1 for p in parts]
        cuts, acc = [], 0.1
        usable = max(.5, dur - .3)
        for w_ in wts:
            acc += usable * w_ / sum(wts)
            cuts.append(acc)
        caps = []
        for p in parts:
            c = fit(T(p, 36, WHITE), 11.6).move_to([0, -3.3, 0])
            c.set_opacity(0)
            caps.append(c)
        cap_bg = box(12.2, 1.0, INK, 0, -3.3, op=.55, r=.18)
        self.add(cap_bg, *caps)

        st = {"cap": -1, "amp": 0.0}
        listener = None
        if layout == "duo":
            listener = "you" if speaker == "guide" else "guide"
        react_t0 = .5 * dur

        def tick(_m, dt):
            t = tick.t = getattr(tick, "t", 0.0) + dt
            update_ambient(amb, t)
            # characters
            e = float(env[min(len(env) - 1, int(t * fps))])
            st["amp"] = .6 * st["amp"] + .4 * e
            for k, ch in chars.items():
                x_t = tx[k]
                walking, x = False, x_t
                if layout == "walk":
                    x = -6.8 * side + 13.6 * side * clamp(t / dur)
                    walking = True
                elif enter:
                    f = clamp(t / .9)
                    off = -(1 - f) * (4.2 if x_t < 0 else -4.2)
                    x = x_t + off
                    walking = f < 1
                spk = (k == speaker)
                point = 0
                if spk and slots and 1.0 < t < min(dur - .3, 3.8) and layout in ("duo", "solo"):
                    point = 1 if cx > x_t else -1
                emote, ep = None, 0.0
                if reaction != "none":
                    tgt = listener if listener else speaker
                    if k == tgt and react_t0 < t < react_t0 + 1.4:
                        emote, ep = reaction, clamp((t - react_t0) / .5) * (1 - clamp((t - react_t0 - 1.0) / .4))
                        if reaction == "shock":
                            ep = clamp((t - react_t0) / 1.4)
                ch.pose(t, x, GROUND, speaking=spk, amp=st["amp"] if spk else 0.0, point=point, emote=emote, ep=ep,
                        walking=walking, wave_hand=(kind == "title" and spk and t < 2.5))
            for s_ in slots:
                s_.update(t, dur)
                if s_.tag:
                    ts = ease_back((t - s_.t_in - .25) / .35) if t >= s_.t_in + .25 else 0.0
                    s_.tag.restore()
                    s_.tag.scale(max(ts, 1e-3))
            for m, t0 in pops:
                m.restore()
                m.scale(max(ease_back((t - t0) / .4), 1e-3))
            # HUD + captions
            w = max(.02, FW * (idx + clamp(t / dur)) / total)
            bar.stretch_to_fit_width(w)
            bar.move_to([-FW / 2 + w / 2, 3.94, 0])
            k = next((i for i, c in enumerate(cuts) if t < c), len(caps) - 1)
            if k != st["cap"]:
                st["cap"] = k
                for i, c in enumerate(caps):
                    c.set_opacity(1 if i == k else 0)

        clock = Mobject()
        clock.add_updater(tick)
        self.add(clock)
        for m in list(self.mobjects)[1:]:
            if m is not clock:
                m.add_updater(lambda _m: None)
        self.wait(dur)


# ---------------------------------------------------------------- thumbnail
THEMES = {
    "red": ("#5c0a0a", "#ff5a2e"), "blue": ("#06214d", "#1fa2ff"), "purple": ("#2b0a4d", "#c04bff"),
    "green": ("#06361f", "#2ee66b"), "gold": ("#4a2c00", "#ffb703"),
}


class ThumbScene(Scene):
    def construct(self):
        sp = json.load(open(os.environ["THUMB_JSON"], encoding="utf-8"))
        c1, c2 = THEMES.get(sp.get("theme") or "red", THEMES["red"])
        bg = Rectangle(width=FW + .2, height=FH + .2)
        bg.set_fill([c1, c2], 1)
        bg.set_stroke(width=0)
        bg.set_sheen_direction(DR)
        self.add(bg)
        ic_x, ic_y = 3.7, -.2
        for i in range(16):  # sunburst
            a = i * TAU / 16
            tri = Polygon([ic_x, ic_y, 0], [ic_x + 12 * np.cos(a), ic_y + 12 * np.sin(a), 0],
                          [ic_x + 12 * np.cos(a + TAU / 32), ic_y + 12 * np.sin(a + TAU / 32), 0])
            tri.set_fill(WHITE, .10 if i % 2 else .04).set_stroke(width=0)
            self.add(tri)
        for r, o in ((3.3, .08), (2.7, .12), (2.2, .18)):
            self.add(Circle(radius=r).move_to([ic_x, ic_y, 0]).set_fill(c2, o).set_stroke(width=0))
        g, spf = make_icon(sp.get("icon") or "warning")
        if spf:
            spf(1.0, 3.0)
        g.scale(1.8).move_to([ic_x, ic_y, 0])
        ring = Circle(radius=2.45).move_to([ic_x, ic_y, 0]).set_fill(opacity=0).set_stroke("#ff2d2d", 12)
        self.add(g, ring)
        who = sp.get("character") or "you"
        ch = Char(who if who in ("guide", "you") else "you")
        ch.pose(1.0, -4.6, -5.3, scale=1.9, speaking=True, amp=1.0, emote="shock", ep=1.0)
        self.add(ch.g)
        words = str(sp.get("text") or "WOW").upper().split()
        lines, line = [], ""
        for w in words:
            if len(line) + len(w) < 11:
                line = (line + " " + w).strip()
            else:
                lines.append(line)
                line = w
        lines.append(line)
        lines = lines[:2]
        ys = [3.0, 1.75]
        cols = [WHITE, YEL]
        for i, ln in enumerate(lines):
            t = T(ln, 100, cols[i % 2])
            t.set_stroke(BLACK, 12, background=True)
            fit(t, 8.6)
            t.move_to([-2.4, ys[i], 0]).rotate(-.03)
            self.add(t)
