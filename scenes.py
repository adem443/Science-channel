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


try:
    import manimpango
    _FONTS = set(manimpango.list_fonts())
except Exception:
    _FONTS = set()
FONT_REG = "Roboto" if "Roboto" in _FONTS else ("DejaVu Sans" if "DejaVu Sans" in _FONTS else "Sans")
FONT_HEAVY = "Roboto Black" if "Roboto Black" in _FONTS else FONT_REG


def T(s, size, color=WHITE, outline=True, heavy=False):
    t = Text(str(s), font_size=size, color=color, weight=BOLD, font=FONT_HEAVY if heavy else FONT_REG)
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
    env = np.array([np.sqrt(np.mean(data[i * hop:(i + 1) * hop] ** 2)) for i in range(k)])
    env = env / (np.percentile(env, 92) + 1e-9)
    env = np.where(env < .12, 0.0, env)  # real pauses close the mouth fully
    return np.clip(env ** .8, 0, 1)


def mouth_shape(path, fps):
    """0 = round 'oo/oh' sounds, 1 = wide 'ee/ah' sounds (zero-crossing rate as a cheap vowel proxy)."""
    if not path or not os.path.exists(path):
        return np.full(1, .5)
    with wave.open(path) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    hop = max(1, int(sr / fps))
    k = len(data) // hop
    if k == 0:
        return np.full(1, .5)
    z = np.array([np.mean(np.abs(np.diff(np.sign(data[i * hop:(i + 1) * hop])))) / 2 for i in range(k)])
    z = np.convolve(z, np.ones(3) / 3, mode="same")
    lo, hi = np.percentile(z, 10), np.percentile(z, 90)
    return np.clip((z - lo) / (hi - lo + 1e-9), 0, 1)


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


@icon("wifi")
def _wifi():
    arcs = VGroup(*[Arc(radius=r, start_angle=PI / 4, angle=PI / 2, arc_center=[0, -.7, 0]).set_stroke("#4cc9f0", 16) for r in (.7, 1.2, 1.7)])
    return VGroup(arcs, S(Circle(radius=.17), "#4cc9f0", sw=2).move_to([0, -.7, 0])), None


@icon("block")
def _block():
    r = S(Circle(radius=1.0), "#ff3b30", sw=0)
    r.set_fill(opacity=0).set_stroke("#ff3b30", 16)
    return VGroup(r, Line([-.7, .7, 0], [.7, -.7, 0]).set_stroke("#ff3b30", 16)), None


@icon("server")
def _server():
    rows = VGroup(*[VGroup(S(RoundedRectangle(corner_radius=.1, width=1.8, height=.5), "#3a4a6b", sw=3),
                           S(Circle(radius=.08), c, sw=1).move_to([-.7, 0, 0])) for c in ("#34c759", "#ffd23f", "#ff3b30")])
    for i, r_ in enumerate(rows):
        r_.shift([0, .6 - .6 * i, 0])
    return rows, None


@icon("chat")
def _chat():
    b = S(RoundedRectangle(corner_radius=.3, width=1.8, height=1.2), "#34c759", sw=4)
    tail = S(Triangle().scale(.25).rotate(PI).move_to([-.5, -.7, 0]), "#34c759", sw=3)
    dots = VGroup(*[S(Circle(radius=.09), WHITE, sw=0).move_to([x, 0, 0]) for x in (-.4, 0, .4)])
    return VGroup(tail, b, dots), None


@icon("pin")
def _pin():
    return VGroup(S(Triangle().scale(.55).rotate(PI).move_to([0, -.5, 0]), "#ff3b30", sw=3),
                  S(Circle(radius=.6), "#ff3b30", sw=4).move_to([0, .3, 0]),
                  S(Circle(radius=.22), WHITE, sw=0).move_to([0, .3, 0])), None


@icon("cart")
def _cart():
    b = S(Polygon([-.9, .5, 0], [.9, .5, 0], [.65, -.4, 0], [-.6, -.4, 0]), "#ffb703", sw=4)
    return VGroup(pl([(-1.3, .8), (-1, .8), (-.9, .5)], "#bbbbbb", 8), b,
                  S(Circle(radius=.18), "#444444").move_to([-.45, -.7, 0]),
                  S(Circle(radius=.18), "#444444").move_to([.45, -.7, 0])), None


@icon("lock")
def _lock():
    sh = Arc(radius=.5, start_angle=0, angle=PI, arc_center=[0, .35, 0]).set_stroke("#bbbbbb", 14)
    return VGroup(sh, S(RoundedRectangle(corner_radius=.15, width=1.4, height=1.1), "#ffd23f", sw=4).move_to([0, -.2, 0]),
                  S(Circle(radius=.13), INK, sw=0).move_to([0, -.2, 0])), None


@icon("plug")
def _plug():
    return VGroup(S(RoundedRectangle(corner_radius=.2, width=1.2, height=1.0), "#8e9aaf", sw=4).move_to([0, -.2, 0]),
                  S(Rectangle(width=.18, height=.5), "#dddddd", sw=2).move_to([-.3, .55, 0]),
                  S(Rectangle(width=.18, height=.5), "#dddddd", sw=2).move_to([.3, .55, 0]),
                  pl([(0, -.7), (0, -1.3), (.5, -1.5)], "#444444", 8)), None


@icon("signal")
def _signal():
    return VGroup(*[S(Rectangle(width=.28, height=.4 + .35 * i), "#34c759" if i < 2 else "#555555", sw=2) for i in range(4)]).arrange(RIGHT, buff=.14, aligned_edge=DOWN), None


@icon("zombie")
def _zombie():
    head = S(Circle(radius=.8), "#8fcf7a", sw=4)
    eyes = VGroup(S(Circle(radius=.2), WHITE, sw=2).move_to([-.3, .15, 0]), S(Circle(radius=.2), WHITE, sw=2).move_to([.3, .15, 0]),
                  S(Circle(radius=.07), BLACK, sw=0).move_to([-.25, .12, 0]), S(Circle(radius=.07), BLACK, sw=0).move_to([.35, .1, 0]))
    mouth = pl([(-.4, -.35), (-.2, -.25), (0, -.4), (.2, -.25), (.4, -.38)], "#3a1d1d", 6)
    stitch = pl([(-.7, .5), (-.35, .62)], "#2d5a2a", 5)
    return VGroup(head, eyes, mouth, stitch), None


@icon("mushroom")
def _mush():
    cap = S(Arc(radius=1.0, start_angle=0, angle=PI).append_points([[-1, 0, 0], [1, 0, 0]]) if False else Ellipse(width=2.1, height=1.3), "#e8423a", sw=4).move_to([0, .35, 0])
    dots = VGroup(*[S(Circle(radius=r), WHITE, sw=0).move_to([x, y, 0]) for x, y, r in [(-.5, .5, .17), (.2, .7, .2), (.6, .3, .13)]])
    stem = S(RoundedRectangle(corner_radius=.2, width=.7, height=.9), "#f3e6c8", sw=4).move_to([0, -.55, 0])
    return VGroup(stem, cap, dots), None


@icon("ant")
def _ant():
    parts = VGroup(S(Circle(radius=.3), "#5a2d12", sw=3).move_to([-.7, 0, 0]), S(Circle(radius=.26), "#5a2d12", sw=3).move_to([-.15, 0, 0]),
                   S(Ellipse(width=.9, height=.6), "#5a2d12", sw=3).move_to([.55, 0, 0]))
    legs = VGroup(*[Line([x, -.1, 0], [x + dx, -.6, 0]).set_stroke("#3b1c0a", 5) for x, dx in [(-.3, -.2), (-.1, 0), (.1, .25)]])
    ant_ = VGroup(pl([(-.85, .2), (-1.1, .6)], "#3b1c0a", 4), pl([(-.7, .25), (-.6, .7)], "#3b1c0a", 4))
    return VGroup(legs, parts, ant_), None


@icon("hospital")
def _hosp():
    return VGroup(S(RoundedRectangle(corner_radius=.15, width=1.8, height=1.6), WHITE, sw=4),
                  S(Rectangle(width=.9, height=.28), "#e63946", sw=0), S(Rectangle(width=.28, height=.9), "#e63946", sw=0)), None


@icon("fire")
def _fire():
    return VGroup(S(Polygon([0, 1, 0], [.7, 0, 0], [.5, -.8, 0], [-.5, -.8, 0], [-.7, 0, 0]), "#ff6b1a", sw=3),
                  S(Polygon([0, .3, 0], [.35, -.2, 0], [.25, -.7, 0], [-.25, -.7, 0], [-.35, -.2, 0]), "#ffd23f", sw=0)), None


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
        self.halo = VGroup(Circle(radius=1.7).set_fill("#ffffff", .13).set_stroke("#ffd23f", 4, opacity=.45),
                           Circle(radius=2.1).set_fill(opacity=0).set_stroke("#ffffff", 2, opacity=.18))
        self.halo.save_state()
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
        return [self.halo, self.g] + ([self.tag] if self.tag else [])

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
        self.halo.restore()
        self.halo.scale(max(s * self.s * .85 * (1 + .04 * np.sin(4 * x)), 1e-3)).shift([self.x, self.y, 0])
        self.g.scale(max(s * self.s * sm, 1e-3))
        if rot:
            self.g.rotate(rot)
        self.g.shift([self.x + dx, self.y + dy, 0])


# ---------------------------------------------------------------- characters
def shade(col, k):
    c = ManimColor(col)
    return interpolate_color(c, ManimColor("#000000"), k) if k > 0 else interpolate_color(c, ManimColor("#ffffff"), -k)


class Char:
    """Chibi-style cartoon character. Ground is local y=-1.75, head top ~y=1.85."""

    def __init__(self, kind):
        fem = kind == "you"
        self.fem = fem
        skin = "#f6c9a4" if fem else "#f0b98d"
        skin_d = shade(skin, .12)
        top = "#27b3a6" if fem else "#ffffff"
        top_d = shade(top, .14)
        hair_c = "#7a3b1d" if fem else "#e9e9ef"
        hair_d = shade(hair_c, .18)
        pants = "#6c4fa3" if fem else "#31415e"
        shoe = "#ffffff" if fem else "#5b3a24"
        iris = "#2f9e8f" if fem else "#4a6fa5"

        def limb(px, py, w, h, col, foot=None):
            pv = Dot([px, py, 0], radius=.01).set_opacity(0)
            r = S(RoundedRectangle(corner_radius=w / 2.2, width=w, height=h), col)
            r.move_to([px, py - h / 2 + .04, 0])
            parts = [pv, r]
            if foot:
                parts.append(S(Ellipse(width=w * 1.5, height=.3), foot).move_to([px + (.06 if px > 0 else -.06), py - h + .06, 0]))
            return VGroup(*parts)

        self.shadow = Ellipse(width=2.1, height=.32).set_fill(BLACK, .22).set_stroke(width=0).move_to([0, -1.76, 0])
        self.leg_l = limb(-.3, -1.0, .36, .78, pants, shoe)
        self.leg_r = limb(.3, -1.0, .36, .78, pants, shoe)

        # hair behind head
        if fem:
            self.hair_back = VGroup(
                S(RoundedRectangle(corner_radius=.45, width=1.95, height=1.55), hair_c).move_to([0, .9, 0]),
                S(Circle(radius=.42), hair_c).move_to([-.98, 1.45, 0]),       # bun left
                S(Circle(radius=.42), hair_c).move_to([.98, 1.45, 0]),        # bun right
            )
        else:
            self.hair_back = VGroup(*[S(Circle(radius=r), hair_c).move_to([x, y, 0]) for x, y, r in
                                      [(-.8, 1.1, .38), (-.55, 1.62, .42), (-.1, 1.88, .44), (.42, 1.78, .42), (.8, 1.25, .38), (.9, .7, .28), (-.92, .65, .26)]])
        # torso
        self.body = VGroup(S(RoundedRectangle(corner_radius=.32, width=1.28, height=1.35), top).move_to([0, -.35, 0]))
        self.body.add(S(RoundedRectangle(corner_radius=.2, width=.34, height=1.2), top_d, op=.55, sw=0).move_to([.46, -.38, 0]))
        if fem:
            self.skirt = S(Polygon([-.62, -.72, 0], [.62, -.72, 0], [.95, -1.3, 0], [-.95, -1.3, 0]), pants)
            self.body.add(S(Rectangle(width=.5, height=.12), "#ffd23f", sw=0).move_to([0, .1, 0]))      # collar band
            self.body.add(S(Circle(radius=.09), "#ffd23f", sw=1).move_to([0, -.25, 0]))
        else:
            self.skirt = VGroup()
            self.body.add(S(Polygon([-.3, .3, 0], [.3, .3, 0], [0, -.15, 0]), "#2b4a8a", sw=2))     # shirt
            self.body.add(S(Polygon([-.34, .32, 0], [-.05, .32, 0], [-.2, -.2, 0]), WHITE, sw=2))   # collar l
            self.body.add(S(Polygon([.34, .32, 0], [.05, .32, 0], [.2, -.2, 0]), WHITE, sw=2))      # collar r
            self.body.add(S(Triangle().scale(.11).rotate(PI), "#e63946", sw=2).move_to([0, .02, 0]))  # tie
            self.body.add(S(Rectangle(width=.3, height=.3), "#dfe3ea", sw=2).move_to([-.4, -.55, 0]))   # pocket
            self.body.add(Line([-.46, -.4, 0], [-.46, -.1, 0]).set_stroke("#e63946", 4))                # pen
            self.body.add(Line([0, -.2, 0], [0, -1.0, 0]).set_stroke(INK, 2))
        # arms (sleeve + hand), pivot at shoulder
        def arm(sx):
            pv = Dot([sx * .72, .12, 0], radius=.01).set_opacity(0)
            sl = S(RoundedRectangle(corner_radius=.15, width=.32, height=.95), top).move_to([sx * .72, -.35, 0])
            hd = S(Circle(radius=.19), skin).move_to([sx * .72, -.86, 0])
            return VGroup(pv, sl, hd)
        self.arm_l, self.arm_r = arm(-1), arm(1)

        # head
        self.head = VGroup(S(Circle(radius=.9), skin).move_to([0, .95, 0]))
        self.head.add(S(Circle(radius=.9), skin_d, op=.0, sw=0).move_to([0, .95, 0]))
        for sx in (-1, 1):
            self.head.add(S(Circle(radius=.16), skin).move_to([sx * .9, .9, 0]))  # ears
        if fem:
            fringe = VGroup(S(Ellipse(width=1.9, height=.75), hair_c).move_to([0, 1.62, 0]),
                            S(Circle(radius=.24), hair_c).move_to([-.6, 1.42, 0]),
                            S(Circle(radius=.22), hair_c).move_to([.05, 1.5, 0]),
                            S(Circle(radius=.22), hair_c).move_to([.62, 1.42, 0]))
            ribbon = VGroup(S(Triangle().scale(.2).rotate(PI / 2), "#ff4d6d").move_to([-.88, 1.7, 0]),
                            S(Triangle().scale(.2).rotate(-PI / 2), "#ff4d6d").move_to([-.56, 1.7, 0]),
                            S(Circle(radius=.07), "#ff4d6d").move_to([-.72, 1.7, 0]))
            self.hair_front = VGroup(fringe, ribbon)
        else:
            self.hair_front = VGroup(S(Ellipse(width=1.3, height=.36), hair_c).move_to([0, 1.78, 0]),
                                     S(Triangle().scale(.2).move_to([-.3, 1.92, 0]), hair_c), S(Triangle().scale(.22).move_to([.25, 1.95, 0]).rotate(.2), hair_c))
        # eyes
        ex = .33
        self.eyes_w = VGroup(*[S(Ellipse(width=.46, height=.58), WHITE, sw=2).move_to([sx * ex, 1.0, 0]) for sx in (-1, 1)])
        self.irises = VGroup(*[S(Circle(radius=.17), iris, sw=0).move_to([sx * ex, .98, 0]) for sx in (-1, 1)])
        self.pupils = VGroup(*[S(Circle(radius=.09), INK, sw=0).move_to([sx * ex, .98, 0]) for sx in (-1, 1)])
        self.glints = VGroup(*[S(Circle(radius=.05), WHITE, sw=0).move_to([sx * ex + .06, 1.06, 0]) for sx in (-1, 1)])
        self.happy_eyes = VGroup(*[Arc(radius=.2, start_angle=.35, angle=PI - .7).set_stroke(INK, 7).move_to([sx * ex, 1.0, 0]) for sx in (-1, 1)])
        self.eyes = VGroup(self.eyes_w, self.irises, self.pupils, self.glints)
        brow_c = hair_d if fem else "#7d8392"
        by = 1.43 if fem else 1.5
        self.brows = VGroup(Line([-.58, by - .05, 0], [-.12, by, 0]).set_stroke(brow_c, 8), Line([.12, by, 0], [.58, by - .05, 0]).set_stroke(brow_c, 8))
        self.lashes = VGroup(*[Line([sx * ex + sx * .2, 1.08, 0], [sx * ex + sx * .32, 1.2, 0]).set_stroke(INK, 4) for sx in (-1, 1)]) if fem else VGroup()
        self.cheeks = VGroup(*[Circle(radius=.15).set_fill("#ff7a8a", .45).set_stroke(width=0).move_to([sx * .6, .6, 0]) for sx in (-1, 1)])
        self.nose = S(Ellipse(width=.16, height=.12), shade(skin, .1), sw=1.5).move_to([0, .78, 0])
        if not fem:
            self.nose = S(Circle(radius=.12), "#e9967a", sw=1.5).move_to([0, .8, 0])
        # mouth: smile arc + open mouth + frown arc
        self.smile = Arc(radius=.3, start_angle=PI + .5, angle=PI - 1.0).set_stroke("#6b2d2d", 5).move_to([0, .46, 0])
        self.frown = Arc(radius=.25, start_angle=.5, angle=PI - 1.0).set_stroke("#6b2d2d", 5).move_to([0, .42, 0])
        self.mouth = S(Ellipse(width=.3, height=.3), "#8e2f3a", stroke="#5a1d25", sw=2).move_to([0, .46, 0])
        self.tongue = S(Ellipse(width=.2, height=.12), "#ff8fa3", sw=0).move_to([0, .4, 0])
        # accessories
        acc = []
        if not fem:
            acc.append(VGroup(*[Circle(radius=.27).set_fill(opacity=0).set_stroke("#2b2f3a", 5).move_to([sx * ex, 1.0, 0]) for sx in (-1, 1)],
                              Line([-.06, 1.02, 0], [.06, 1.02, 0]).set_stroke("#2b2f3a", 5)))
            acc.append(VGroup(S(Ellipse(width=.5, height=.17), "#f4f4f8", sw=2).move_to([-.14, .68, 0]), S(Ellipse(width=.5, height=.17), "#f4f4f8", sw=2).move_to([.14, .68, 0])))  # mustache
        self.acc = VGroup(*acc)
        self.sweat = VGroup(S(Triangle().scale(.1).stretch(1.4, 1).move_to([0, .1, 0]), "#7fd1ff", sw=1.5), S(Circle(radius=.1), "#7fd1ff", sw=1.5).move_to([0, -.04, 0])).move_to([.95, 1.5, 0])
        self.burst = VGroup(*[Line([.0, .15, 0], [.0, .5, 0]).set_stroke(YEL, 7).rotate(a, about_point=[0, 0, 0]) for a in (-.7, 0, .7)]).move_to([1.1, 1.95, 0])

        self.face = VGroup(self.nose, self.cheeks, self.eyes, self.happy_eyes, self.lashes, self.brows, self.smile, self.frown, self.mouth, self.tongue, self.acc)
        self.headg = VGroup(self.head, self.face, self.hair_front, self.sweat, self.burst)
        self.g = VGroup(self.shadow, self.hair_back, self.leg_l, self.leg_r, self.skirt, self.body, self.arm_l, self.arm_r, self.headg)
        self.g.save_state()

    def pose(self, t, x, ground, scale=1.15, speaking=False, amp=0.0, point=0, emote=None, ep=0.0,
             walking=False, calm=False, wave_hand=False, look=0.0, shape=.5):
        g = self.g
        g.restore()
        jump, squash = 0.0, 0.0
        if walking:
            a = .45 * np.sin(8 * t)
            self.leg_l.rotate(a, about_point=self.leg_l[0].get_center())
            self.leg_r.rotate(-a, about_point=self.leg_r[0].get_center())
            bob = .09 * abs(np.sin(8 * t))
        else:
            bob = .035 * np.sin(2.2 * t + (0 if not self.fem else 1.3))
        for arm, s in ((self.arm_l, -1), (self.arm_r, 1)):
            ang = 0.0
            if walking:
                ang = s * .5 * np.sin(8 * t)
            elif wave_hand and s == 1:
                ang = 2.5 + .4 * np.sin(10 * t)
            elif point == s:
                ang = s * (1.5 + .06 * np.sin(5 * t))
            elif speaking:
                ang = s * (.12 + .75 * amp) * (.55 + .45 * np.sin(3.6 * t + (1 if s > 0 else 0)))
            else:
                ang = s * (.08 + .05 * np.sin(2.0 * t + s))
            if emote == "shock":
                ang = s * (.5 + 1.9 * ep)
            elif emote == "happy":
                ang = s * (.4 + 1.9 * ep * (.55 + .45 * np.sin(11 * t)))
            elif emote == "think" and s == 1:
                ang = s * (2.2 * ep + .1)
            elif emote == "worried":
                ang = s * (.3 + .9 * ep)
            arm.rotate(ang, about_point=arm[0].get_center())
        # ---- face
        openness = .04 + (.62 * amp if speaking else 0)
        smile_w = 1.0
        eye_h, pupil_k, brow_up, brow_tilt = 1.0, 1.0, 0.0, 0.0
        show = "smile"
        if emote == "shock":
            openness, show, eye_h, pupil_k, brow_up = max(openness, .25 + .6 * ep), "open", 1 + .28 * ep, 1 - .45 * ep, .22 * ep
            jump = .35 * max(0.0, np.sin(PI * clamp(ep))) if ep < 1 else 0.0
            squash = -.05 * ep
        elif emote == "happy":
            show, eye_h, smile_w, brow_up = ("open" if openness > .1 else "smile"), 1 - .5 * ep, 1 + .5 * ep, .08 * ep
            jump = .15 * abs(np.sin(9 * t)) * ep
        elif emote == "worried":
            show, brow_tilt, brow_up = ("open" if openness > .12 else "frown"), .3 * ep, .1 * ep
        elif emote == "think":
            brow_up = .1 * ep
        if show == "smile" and speaking and openness > .12:
            show = "open"
        self.smile.set_opacity(1 if show == "smile" else 0)
        self.frown.set_opacity(1 if show == "frown" else 0)
        op = 1 if show == "open" else 0
        self.mouth.set_fill(opacity=op).set_stroke(opacity=op)
        self.tongue.set_fill(opacity=op if openness > .22 else 0)
        if op:
            self.mouth.stretch_to_fit_height(max(.06, min(.66, openness * (1.25 - .45 * shape))))
            self.mouth.stretch_to_fit_width(.2 + .3 * shape + (.1 if emote == "happy" else 0) - (.06 if emote == "shock" else 0))
            self.mouth.move_to([0, .46 - (.04 if openness > .3 else 0), 0])
            self.tongue.move_to([0, .46 - openness * .35, 0])
        self.smile.stretch(smile_w, 0)
        self.eyes_w.stretch(eye_h, 1)
        for pu in self.pupils:
            pu.scale(pupil_k)
        lk = look + (.05 * ep if emote == "think" else 0)
        for grp in (self.irises, self.pupils, self.glints):
            grp.shift(RIGHT * lk * .08 + (UP * .05 * ep if emote == "think" else 0))
        hap = emote == "happy" and ep > .35
        self.happy_eyes.set_stroke(opacity=1 if hap else 0)
        if hap:
            self.eyes.set_opacity(0)
            self.lashes.set_opacity(0)
        self.brows.shift(UP * brow_up)
        if brow_tilt:
            self.brows[0].rotate(-brow_tilt); self.brows[1].rotate(brow_tilt)
        if emote == "think":
            self.brows[1].shift(UP * .1 * ep)
        if emote == "shock":
            self.sweat.set_opacity(ep); self.burst.set_opacity(ep)
        else:
            self.sweat.set_opacity(0); self.burst.set_opacity(0)
        if (t % 3.1) < .13:  # blink
            self.eyes_w.stretch_to_fit_height(.04)
            for grp in (self.irises, self.pupils, self.glints):
                grp.set_opacity(0)
        tilt = .1 * ep if emote == "think" else (.05 * np.sin(3 * t) if speaking else .04 * np.sin(2.4 * t))
        self.headg.rotate(tilt, about_point=[0, .3, 0])
        self.headg.shift(UP * (.04 * amp if speaking else 0))
        self.hair_back.rotate(.025 * np.sin(2.5 * t + 1), about_point=[0, 1.6, 0])
        sc = scale * (1 + (.035 * amp if speaking else 0) + squash)
        g.scale(sc, about_point=[0, -1.75, 0])
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
            for wy in np.arange(-2.0, -2.3 + h - .3, .6):
                for wx in (-.3, .3):
                    if rnd.random() < .6:
                        g.add(box(.2, .26, "#dce9f7", x + wx, wy + .1, op=.8))
            x += 1.35
        g.add(box(FW, 1.6, "#444b55", y=-3.2))
        for i in range(3):
            amb.append(("cloud", VGroup(dot(.4, WHITE, 0, 0), dot(.55, WHITE, .5, .1), dot(.4, WHITE, 1.0, 0)).move_to([-5 + i * 5, 3 - i * .4, 0]), i))
    elif name == "nature":
        g.add(box(FW, FH, "#b5e3f5"), dot(.8, YEL, 5.4, 2.9), dot(3.2, "#79c06e", -4, -4.2), dot(4, "#5aa65a", 4, -4.8))
        g.add(box(FW, 1.6, "#6fb36a", y=-3.2), box(.3, 1.2, "#7a5230", -6.1, -1.3), dot(.85, "#3f8f4a", -6.1, -.4))
        for i in range(3):
            amb.append(("cloud", VGroup(dot(.4, WHITE, 0, 0), dot(.55, WHITE, .5, .1), dot(.4, WHITE, 1.0, 0)).move_to([-4 + i * 4.5, 2.8 - i * .5, 0]), i))
    elif name == "night":
        g.add(box(FW, FH, "#080d24"), box(FW, 3, "#141a3d", y=-1.8, op=.7))
        g.add(dot(.9, "#f4f1d0", 5.3, 2.8), dot(1.3, "#f4f1d0", 5.3, 2.8, op=.15))
        for _ in range(35):
            amb.append(("twinkle", dot(rnd.uniform(.02, .04), WHITE, rnd.uniform(-7, 7), rnd.uniform(.5, 4)), rnd.uniform(0, 6)))
        x = -7.0
        while x < 7.2:
            h = rnd.uniform(1.8, 4.6)
            g.add(box(1.25, h, rnd.choice(["#1c2347", "#232b55", "#171d3c"]), x, -2.3 + h / 2))
            for wy in np.arange(-2.0, -2.3 + h - .3, .55):
                for wx in (-.3, .3):
                    if rnd.random() < .55:
                        w_ = box(.22, .3, "#ffd76a", x + wx, wy + .1, op=.9)
                        g.add(w_)
                        amb.append(("flicker", w_, rnd.uniform(0, 30)))
            x += 1.4
        g.add(box(FW, 1.6, "#0d1128", y=-3.2))
    elif name == "forest":
        g.add(box(FW, FH, "#0e2a1f"), box(FW, 3.5, "#143d2c", y=-1.2, op=.6))
        g.add(dot(.8, "#cfe8d8", -4.8, 2.9, op=.55), dot(1.2, "#cfe8d8", -4.8, 2.9, op=.1))
        for x in np.arange(-7.2, 7.4, 1.1):
            h = rnd.uniform(3.2, 5.5)
            g.add(box(.34, h, "#08160f", x, -3.2 + h / 2))
            g.add(Triangle().scale(.8).stretch(1.4, 1).set_fill("#0c2418", 1).set_stroke(width=0).move_to([x, -1.2 + h * .45, 0]))
        g.add(box(FW, 1.6, "#0a1b12", y=-3.2))
        for i in range(10):
            amb.append(("firefly", dot(.07, "#b9ff66", rnd.uniform(-6.5, 6.5), rnd.uniform(-2.6, 2.6)), rnd.uniform(0, 20)))
        for i in range(3):
            amb.append(("fog", Ellipse(width=9, height=1.3).set_fill("#cfe8d8", .09).set_stroke(width=0).move_to([-5 + i * 5, -2.4 + i * .5, 0]), i))
    elif name == "map":
        g.add(box(FW, FH, "#0a1a33"))
        for x in np.arange(-7, 7.1, 1.0):
            g.add(Line([x, -4, 0], [x, 4, 0]).set_stroke("#1d3a66", 1.5))
        for y in np.arange(-4, 4.1, 1.0):
            g.add(Line([-7.2, y, 0], [7.2, y, 0]).set_stroke("#1d3a66", 1.5))
        land = [(-4.2, .8, 3.4, 2.6), (-3.2, -1.9, 1.6, 2.5), (.4, 1.2, 1.8, 1.8), (.9, -.8, 1.9, 2.7), (3.8, 1.2, 4.2, 2.4), (5.6, -2.2, 1.7, 1.1)]
        for cx_, cy_, w_, h_ in land:
            g.add(Ellipse(width=w_, height=h_).set_fill("#1e4f87", .85).set_stroke("#3b82c4", 3).move_to([cx_, cy_, 0]))
        spots = [(-4.2, 1.0), (-3.0, -1.8), (.4, 1.3), (1.0, -.7), (3.0, 1.4), (4.6, .9), (5.7, -2.2), (-5.3, .2), (2.2, .2), (3.9, 2.0), (.8, -1.9), (-3.5, 2.0)]
        for i, (px_, py_) in enumerate(spots):
            amb.append(("spread", dot(.2, "#ff3b30", px_, py_, op=0), i))
            amb.append(("spreadring", Circle(radius=.2).set_fill(opacity=0).set_stroke("#ff3b30", 3).move_to([px_, py_, 0]).set_stroke(opacity=0), i))
    elif name == "alert":
        g.add(box(FW, FH, "#2a0a0e"))
        for i in range(9):
            g.add(box(1.4, 14, "#5a1018", -8 + i * 2.2, 0, op=.5).rotate(.5))
        sir = dot(2.2, "#ff2a2a", -6.2, 3.3, op=.25)
        amb.append(("siren", sir, 0))
        g.add(box(FW, 1.6, "#1a0508", y=-3.2))
        g.add(box(FW, .35, "#ffd23f", y=-2.5), *[box(.5, .35, BLACK, x, -2.5) for x in np.arange(-7, 7.5, 1.0)])
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
        elif kind == "flicker":
            m.set_opacity(.9 if np.sin(t * .8 + ph) > -.92 else .15)
        elif kind == "firefly":
            m.set_fill(opacity=.2 + .8 * abs(np.sin(1.7 * t + ph)))
            m.shift([.004 * np.sin(1.1 * t + ph), .003 * np.cos(.9 * t + ph), 0])
        elif kind == "fog":
            m.move_to([((t * .25 + ph * 5) % 20) - 10, m.get_center()[1], 0])
        elif kind == "spread":
            a = clamp((t - .15 * ph) / .5)
            m.set_fill(opacity=a * (.75 + .25 * np.sin(5 * t + ph)))
        elif kind == "spreadring":
            f = (t * .8 + ph * .13) % 1
            m.scale_to_fit_width(.4 + 1.0 * f) if False else None
            m.set_stroke(opacity=(1 - f) * clamp((t - .15 * ph) / .5) * .9)
        elif kind == "siren":
            m.set_fill(opacity=.1 + .35 * abs(np.sin(4 * t)))


# ---------------------------------------------------------------- shot scene
def soft_vignette():
    g = VGroup()
    for i in range(9):
        g.add(Annulus(inner_radius=5.2 + .38 * i, outer_radius=14).set_fill(BLACK, .045).set_stroke(width=0))
    return g


def ease_io(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


WIPE_COL = {"lab": "#4a90d9", "space": "#7b5ea7", "ocean": "#1b6a96", "city": "#f2b63d", "nature": "#34c759", "bedroom": "#ff7ad9", "night": "#3b3f9a", "forest": "#1f7a4a", "map": "#d93a3a", "alert": "#ff2a2a"}


class SceneRenderer(MovingCameraScene):
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
        shp = mouth_shape(os.environ.get("SCENE_AUDIO"), fps)
        rnd = random.Random(idx * 7919 + 13)

        kind = spec.get("kind") or "scene"
        layout = spec.get("layout") or "duo"
        speaker = spec.get("speaker") or "guide"
        if speaker not in ("guide", "you"):
            speaker = "guide"
        props = [p for p in (spec.get("props") or []) if isinstance(p, dict)][:2]
        reaction = spec.get("reaction") or "none"
        punch = str(spec.get("punch") or "").strip()[:28]
        bdname = spec.get("backdrop") or "lab"
        self.camera.background_color = INK
        bd, amb = backdrop(bdname)
        self.add(bd)
        for _, m, _ in amb:
            self.add(m)

        # --- characters: name -> (x, ground, scale)
        cfg = {}
        if layout == "duo":
            cfg = {"guide": (-4.5, GROUND, 1.15), "you": (4.5, GROUND, 1.15)}
        elif layout == "solo":
            cfg = {speaker: (-4.4 * side, GROUND, 1.2)}
        elif layout == "walk":
            cfg = {speaker: (-4.4 * side, GROUND, 1.1)}
        elif layout == "closeup":
            cfg = {speaker: (-3.9 * side, -3.2, 1.5)}
        elif layout == "prop_only":
            cfg = {"guide": (-5.5, -2.65, .72)}
        chars = {k: Char(k) for k in cfg}
        for c in chars.values():
            self.add(c.g)

        # --- props
        cy = 0.75
        if layout == "walk":
            cy = 2.55
            for p in props:
                p["label"] = ""
        if layout == "prop_only":
            cy = 0.6
        if layout == "closeup":
            cy = 0.5
        if kind == "diagram":
            cy = -0.2
        if kind in ("title", "stat"):
            cy = 0.1
        cx = {"duo": 0.0, "solo": 1.5 * side, "walk": 0.0, "prop_only": 0.4, "closeup": 3.0 * side}.get(layout, 0.0)
        sc1 = 1.5 if layout in ("prop_only", "closeup") else (1.2 if kind in ("title", "stat", "diagram") else 1.25)
        if layout == "walk":
            sc1 = .7
        slots = []
        if len(props) == 1:
            slots.append(Slot(props[0], cx, cy, sc1, .35))
        elif len(props) == 2:
            for i, p in enumerate(props):
                slots.append(Slot(p, cx + (-2.0 if i == 0 else 2.0) * (sc1 / 1.3), cy, sc1 * .78, .35 + .7 * i))
        for s_ in slots:
            for m in s_.mobs():
                self.add(m)

        # --- kind extras
        pops, rays = [], None
        if kind in ("title", "stat"):
            rays = VGroup(*[Polygon([0, 0, 0], [12 * np.cos(a), 12 * np.sin(a), 0], [12 * np.cos(a + TAU / 36), 12 * np.sin(a + TAU / 36), 0]).set_fill(WHITE, .07).set_stroke(width=0)
                            for a in np.arange(0, TAU, TAU / 18)])
            rays.move_to([0, .3, 0])
            self.add(rays)
            self.bring_to_back(rays)
            self.bring_to_back(bd)
            tx0 = 1.7 * side if layout in ("solo", "closeup") else 0.0
            main = T(spec.get("text") or spec.get("value") or "", 84 if kind == "title" else 120, YEL if kind == "stat" else WHITE, heavy=True)
            fit(main, 9.2 if tx0 else 11).move_to([tx0, 2.35, 0])
            sub = T(spec.get("subtitle") or spec.get("label") or "", 36, WHITE)
            fit(sub, 9.2 if tx0 else 11).move_to([tx0, 1.4, 0])
            for m, t0 in ((main, .2), (sub, .8)):
                m.save_state()
                pops.append((m, t0))
                self.add(m)
        if kind == "diagram":
            nodes = (spec.get("nodes") or [])[:4]
            grp = VGroup()
            for n in nodes:
                r = box(2.4, 1.05, WHITE, sc=RED, sw=5, r=.2)
                tt = fit(T(textwrap.fill(str(n), 15), 28, INK, outline=False, heavy=True), 2.2).move_to(r.get_center())
                grp.add(VGroup(r, tt))
            grp.arrange(RIGHT, buff=.65)
            fit(grp, 10.8).move_to([0, 2.5, 0])
            for i, nd in enumerate(grp):
                t0 = .5 + i * max(.8, (dur - 1.5) / (len(nodes) + 1))
                nd.save_state()
                pops.append((nd, t0))
                self.add(nd)
                if i:
                    a = Arrow(grp[i - 1].get_right(), nd.get_left(), buff=.05, color=YEL, stroke_width=7, tip_length=.22)
                    a.save_state()
                    pops.append((a, t0))
                    self.add(a)

        # --- punch word
        pun, punch_rays = None, None
        punch_t = max(.9, .38 * dur)
        if punch and kind == "scene" and dur > 2.6:
            pun = fit(T(punch.upper(), 90, YEL, heavy=True), 6.8 if layout == "closeup" else 10)
            pun.set_stroke(BLACK, 14, background=True)
            pun.move_to([3.4 * side if layout == "closeup" else 0, 2.55, 0]).rotate(-.05 * rnd.choice([1, -1]))
            pun.save_state()
            self.add(pun)
            punch_rays = VGroup(*[Line([0, 0, 0], [1.4, 0, 0]).rotate(a).set_stroke(WHITE, 5) for a in np.arange(0, TAU, TAU / 14)])
            punch_rays.move_to(pun.get_center()).save_state()
            self.add(punch_rays)

        # --- HUD (follows the camera)
        hud = []
        vig = soft_vignette()
        hud.append(vig)
        mood = spec.get("mood") or "calm"
        tint = box(FW + .6, FH + .6, "#000000", 0, 0, op=0)
        hud.append(tint)
        tag_t = fit(T(topic, 22, WHITE, outline=False), 5.2)
        tag_p = box(tag_t.width + .5, .62, INK, 0, 0, op=.8, r=.12)
        tag_p.move_to([-6.9 + tag_p.width / 2, 3.45, 0])
        tag_t.move_to(tag_p.get_center())
        bar_bg = box(FW, .12, "#333333", 0, 3.94)
        bar = box(FW, .12, YEL, 0, 3.94)
        hud += [tag_p, tag_t, bar_bg, bar]

        parts = chunks_of(spec.get("narration"), 5)
        wts = [len(p) + 1 for p in parts]
        cuts, acc = [], 0.1
        usable = max(.5, dur - .3)
        for w_ in wts:
            acc += usable * w_ / sum(wts)
            cuts.append(acc)
        caps = []
        for p in parts:
            c = fit(T(p, 44, WHITE, heavy=True), 11.6).move_to([0, -3.3, 0])
            c.set_stroke(BLACK, 8, background=True)
            c.set_opacity(0)
            caps.append(c)
        cap_bg = box(12.4, 1.05, INK, 0, -3.3, op=.5, r=.2)
        hud += [cap_bg] + caps
        for m in hud:
            self.add(m)
            m.save_state()

        # --- wipe transition
        wipe = None
        if enter:
            wipe = Polygon([-9, -6, 0], [8, -6, 0], [10.5, 6, 0], [-6.5, 6, 0]).set_fill(WIPE_COL.get(bdname, "#4a90d9"), 1).set_stroke(width=0)
            wipe.move_to([0, 0, 0]).save_state()
            self.add(wipe)

        # --- camera plan
        cam = rnd.choice(["push", "push", "pull", "pan", "hold"])
        if kind in ("title",) or layout == "closeup":
            cam = "push"
        if layout == "walk":
            cam = "hold"
        fx = 0.0
        if cfg.get(speaker):
            fx = cfg[speaker][0]
        react_t0 = .55 * dur
        cues = []
        if enter:
            cues.append((0.02, "whoosh"))
        for i, s_ in enumerate(slots):
            cues.append((s_.t_in, "pop"))
        if kind == "stat":
            cues.append((.25, "ding"))
        if reaction == "shock":
            cues.append((react_t0, "boom"))
        if pun is not None:
            cues.append((punch_t, "hit"))
        json.dump(cues, open(os.environ.get("SCENE_CUES", "cues.json"), "w"))

        st = {"cap": -1, "amp": 0.0, "cap_t": 0.0}
        listener = None
        if layout == "duo":
            listener = "you" if speaker == "guide" else "guide"
        frame = self.camera.frame

        def camera_state(t):
            u = clamp(t / dur)
            z, px, py = 1.0, 0.0, 0.0
            if cam == "push":
                z = 1 + .11 * ease_io(u)
            elif cam == "pull":
                z = 1.11 - .11 * ease_io(u)
            elif cam == "pan":
                z = 1.08
            if pun is not None and kind == "scene":
                z += .07 * np.sin(PI * clamp((t - punch_t) / .45))
            if mood == "danger":
                px += .045 * np.sin(31 * t) * (.6 + .4 * np.sin(2.3 * t))
                py += .035 * np.cos(27 * t)
                z += .015 + .01 * np.sin(1.7 * t)
            elif mood == "tense":
                z += .03 * ease_io(u)
            if reaction == "shock" and react_t0 < t < react_t0 + .5:
                z += .1 * np.sin(PI * (t - react_t0) / .5)
                px, py = .06 * np.sin(60 * t), .05 * np.cos(55 * t)
            mx, my = FW / 2 * (1 - 1 / z), FH / 2 * (1 - 1 / z)
            if cam == "pan":
                px += mx * (-1 + 2 * ease_io(u)) * side
            else:
                px += clamp(fx / (FW / 2), -1, 1) * mx * .8
            return z, clamp(px, -mx, mx), clamp(py, -my, my)

        def tick(_m, dt):
            t = tick.t = getattr(tick, "t", 0.0) + dt
            update_ambient(amb, t)
            if rays is not None:
                rays.rotate(dt * .22, about_point=[0, .3, 0])
            e = float(env[min(len(env) - 1, int(t * fps))])
            st["amp"] = e if e > st["amp"] else .45 * st["amp"] + .55 * e   # snap open, release a little slower
            st["shp"] = .5 * st.get("shp", .5) + .5 * float(shp[min(len(shp) - 1, int(t * fps))])
            sx_ = cfg[speaker][0] if speaker in cfg else 0.0
            for k, ch in chars.items():
                x_t, gnd, scl = cfg[k]
                walking, x = False, x_t
                if layout == "walk":
                    x = -6.8 * side + 13.6 * side * clamp(t / dur)
                    walking = True
                elif enter and layout not in ("closeup", "prop_only"):
                    f = clamp(t / .9)
                    x = x_t - (1 - f) * (4.2 if x_t < 0 else -4.2)
                    walking = f < 1
                spk = (k == speaker)
                point = 0
                if spk and slots and 1.0 < t < min(dur - .3, 3.8) and layout in ("duo", "solo"):
                    point = 1 if cx > x_t else -1
                emote, ep = None, 0.0
                if reaction != "none":
                    tgt = listener if listener else speaker
                    if k == tgt and react_t0 < t < react_t0 + 1.5:
                        emote, ep = reaction, clamp((t - react_t0) / .45) * (1 - clamp((t - react_t0 - 1.1) / .4))
                        if reaction == "shock":
                            ep = clamp((t - react_t0) / .5) * (1 - clamp((t - react_t0 - 1.1) / .4))
                look = 0.0
                if layout == "duo" and not spk:
                    look = 1 if sx_ > x else -1
                elif slots and spk:
                    look = 1 if cx > x else -1
                ch.pose(t, x, gnd, scale=scl, speaking=spk, amp=st["amp"] if spk else 0.0, shape=st.get("shp", .5), point=point, emote=emote, ep=ep,
                        walking=walking, wave_hand=(kind == "title" and spk and t < 2.5), look=look)
            for s_ in slots:
                s_.update(t, dur)
                if s_.tag:
                    ts = ease_back((t - s_.t_in - .25) / .35) if t >= s_.t_in + .25 else 0.0
                    s_.tag.restore()
                    s_.tag.scale(max(ts, 1e-3))
            for m, t0 in pops:
                m.restore()
                m.scale(max(ease_back((t - t0) / .4), 1e-3))
            if pun is not None:
                pun.restore()
                punch_rays.restore()
                x = (t - punch_t) / .3
                vis = 0.0 if t < punch_t else (1.0 if t < punch_t + 1.5 else 0.0)
                pun.scale(max(ease_back(x), 1e-3) * (1 + .03 * np.sin(14 * t)) if vis else 1e-3)
                punch_rays.set_stroke(opacity=(1 - clamp((t - punch_t) / .45)) * vis)
                punch_rays.scale(1 + 1.2 * clamp((t - punch_t) / .45))
            # camera
            z, px, py = camera_state(t)
            frame.set(width=FW / z).move_to([px, py, 0])
            # HUD follows camera
            k = next((i for i, c in enumerate(cuts) if t < c), len(caps) - 1)
            if k != st["cap"]:
                st["cap"] = k
                st["cap_t"] = t
            w = max(.02, FW * (idx + clamp(t / dur)) / total)
            for m in hud:
                m.restore()
            if mood == "danger":
                tint.set_fill("#ff0000", .10 + .08 * abs(np.sin(3.2 * t)))
            elif mood == "tense":
                tint.set_fill("#000022", .16)
            elif mood == "relief":
                tint.set_fill("#ffd98a", .10 + .04 * np.sin(2 * t))
            bar.stretch_to_fit_width(w)
            bar.move_to([-FW / 2 + w / 2, 3.94, 0])
            for i, c in enumerate(caps):
                c.set_opacity(1 if i == k else 0)
            pop = 1 + .22 * max(0.0, 1 - (t - st["cap_t"]) / .18)
            caps[k].scale(pop)
            for m in hud:
                m.scale(1 / z, about_point=ORIGIN).shift([px, py, 0])
            if wipe is not None:
                wipe.restore()
                f = clamp(t / .38)
                wipe.shift([ease_io(f) * 19 * 1 / z + px, py, 0])
                wipe.set_opacity(1 if f < 1 else 0)

        clock = Mobject()
        clock.add_updater(tick)
        self.add(clock)
        for m in list(self.mobjects)[1:]:
            if m is not clock:
                m.add_updater(lambda _m: None)
        self.wait(dur)


# ---------------------------------------------------------------- thumbnail
THEMES = {
    "red": ("#3d0606", "#ff3b1f"), "blue": ("#041a40", "#1fa2ff"), "purple": ("#230a45", "#c04bff"),
    "green": ("#04301b", "#2ee66b"), "gold": ("#3d2400", "#ffb703"),
}


class ThumbScene(Scene):
    def construct(self):
        sp = json.load(open(os.environ["THUMB_JSON"], encoding="utf-8"))
        c1, c2 = THEMES.get(sp.get("theme") or "red", THEMES["red"])
        bg = Rectangle(width=FW + .2, height=FH + .2)
        bg.set_fill([c1, c2, c1], 1)
        bg.set_stroke(width=0)
        bg.set_sheen_direction(RIGHT)
        self.add(bg)
        ic_x, ic_y = 3.5, -1.65
        # sunburst from the icon
        for i in range(24):
            a = i * TAU / 24
            tri = Polygon([ic_x, ic_y, 0], [ic_x + 14 * np.cos(a), ic_y + 14 * np.sin(a), 0],
                          [ic_x + 14 * np.cos(a + TAU / 48), ic_y + 14 * np.sin(a + TAU / 48), 0])
            tri.set_fill(WHITE, .16 if i % 2 else .03).set_stroke(width=0)
            self.add(tri)
        for r, o in ((3.9, .10), (3.3, .16), (2.7, .24)):
            self.add(Circle(radius=r).move_to([ic_x, ic_y, 0]).set_fill("#ffffff", o).set_stroke(width=0))
        # main icon, huge, in "full effect" state
        g, spf = make_icon(sp.get("icon") or "warning")
        if spf:
            spf(1.0, 3.0)
        g.scale(1.3).move_to([ic_x, ic_y, 0]).rotate(.08)
        sh = g.copy()
        for m_ in sh.family_members_with_points():
            m_.set_fill(BLACK, .35 if m_.get_fill_opacity() > 0 else 0)
            m_.set_stroke(BLACK, opacity=.35 if m_.get_stroke_width() > 0 else 0)
        sh.shift([.14, -.14, 0])
        ring = Circle(radius=1.9).move_to([ic_x, ic_y, 0]).set_fill(opacity=0).set_stroke("#ff2d2d", 14)
        self.add(sh, g, ring)
        if sp.get("strike"):
            self.add(Line([ic_x - 1.7, ic_y + 1.7, 0], [ic_x + 1.7, ic_y - 1.7, 0]).set_stroke("#000000", 40),
                     Line([ic_x - 1.7, ic_y + 1.7, 0], [ic_x + 1.7, ic_y - 1.7, 0]).set_stroke("#ff1a1a", 28))
        # satellite icons, each crossed out
        sats = [i for i in (sp.get("icons") or []) if i in ICONS][:4]
        if not sats and sp.get("icon2") in ICONS:
            sats = [sp.get("icon2")]
        spots = [(-.1, -.8), (.5, -3.1), (6.2, -3.1), (6.2, -1.25)]
        for nm, (px, py) in zip(sats, spots):
            g2, sp2 = make_icon(nm)
            if sp2:
                sp2(1.0, 3.0)
            g2.scale(.62).move_to([px, py, 0])
            self.add(Circle(radius=.82).move_to([px, py, 0]).set_fill("#ffffff", .96).set_stroke("#111111", 6), g2,
                     Line([px - .6, py + .6, 0], [px + .6, py - .6, 0]).set_stroke("#ff1a1a", 9))
        # shocked character: hands clutching head, bottom-left
        ch = Char("guide")
        ch.pose(1.0, -4.9, -5.1, scale=2.05, speaking=True, amp=1.0, emote="shock", ep=1.0)
        for arm_, sg in ((ch.arm_l, -1), (ch.arm_r, 1)):
            arm_.rotate(sg * (2.83 - 2.4), about_point=arm_[0].get_center())
            ch.g.remove(arm_)
            ch.g.add(arm_)
        self.add(ch.g)
        # headline: lines separated by "|", first line small, others huge
        raw = str(sp.get("text") or "WOW").upper()
        lines = [x.strip() for x in raw.split("|") if x.strip()] or ["WOW"]
        lines = lines[:3]
        if len(lines) == 1:
            lines = [lines[0]]
        ys = {1: [2.2], 2: [2.85, 1.35], 3: [3.25, 2.0, .55]}[len(lines)]
        cols = ["#ffffff", "#ffd23f", "#ffffff"] if len(lines) == 3 else ["#ffffff", "#ffd23f"]
        for i, ln in enumerate(lines):
            t = T(ln, 150, cols[i % len(cols)], heavy=True)
            t.set_stroke(BLACK, 22, background=True)
            fit(t, 8.3)
            if len(lines) == 3 and i == 0:
                fit(t, 6.2)
            t.move_to([2.7, ys[i], 0]).rotate(-.03)
            self.add(t)
        # soft vignette for punch
        for i in range(8):
            self.add(Annulus(inner_radius=5.6 + .45 * i, outer_radius=15).set_fill(BLACK, .05).set_stroke(width=0))
