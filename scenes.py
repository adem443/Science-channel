import json, os
from manim import *

YELLOW, RED, LIGHT = "#f2b63d", "#ff5a47", "#f4f1ea"

def fit(m, w=12.5):
    if m.width > w: m.scale_to_fit_width(w)
    return m

class SceneRenderer(Scene):
    def construct(self):
        spec = json.load(open(os.environ["SCENE_JSON"], encoding="utf-8"))
        dur = float(os.environ["SCENE_DUR"])
        self.camera.background_color = "#14161a"
        self.used = 0.0
        t = spec.get("type", "title")
        getattr(self, "s_" + t, self.s_title)(spec, dur)
        self.wait(max(0.1, dur - self.used))

    def p(self, *anims, rt=0.8):
        self.play(*anims, run_time=rt); self.used += rt

    def w(self, s):
        if s > 0: self.wait(s); self.used += s

    def s_title(self, s, dur):
        a = fit(Text(s.get("text", ""), font_size=64, color=LIGHT, weight=BOLD))
        b = fit(Text(s.get("subtitle", ""), font_size=34, color=YELLOW)).next_to(a, DOWN, buff=0.5)
        self.p(FadeIn(a, shift=UP * 0.3), rt=1); self.p(FadeIn(b), rt=1)

    def s_bullets(self, s, dur):
        h = fit(Text(s.get("heading", ""), font_size=48, color=YELLOW, weight=BOLD)).to_edge(UP, buff=0.7)
        self.p(FadeIn(h), rt=0.7)
        items = s.get("items", [])[:4]
        gap = max(0.3, (dur - 1.5) / (len(items) + 1))
        prev = h
        for it in items:
            self.w(gap)
            m = fit(Text("•  " + it, font_size=36, color=LIGHT), 11.5)
            m.next_to(prev, DOWN, buff=0.6, aligned_edge=LEFT) if prev is not h else m.next_to(h, DOWN, buff=0.9).to_edge(LEFT, buff=1.0)
            self.p(FadeIn(m, shift=RIGHT * 0.3), rt=0.6); prev = m

    def s_stat(self, s, dur):
        v = fit(Text(str(s.get("value", "")), font_size=130, color=YELLOW, weight=BOLD), 11)
        l = fit(Text(s.get("label", ""), font_size=38, color=LIGHT)).next_to(v, DOWN, buff=0.5)
        self.p(FadeIn(v, scale=0.7), rt=1); self.p(FadeIn(l), rt=0.8)

    def s_diagram(self, s, dur):
        h = fit(Text(s.get("heading", ""), font_size=46, color=YELLOW, weight=BOLD)).to_edge(UP, buff=0.7)
        self.p(FadeIn(h), rt=0.7)
        nodes = s.get("nodes", [])[:4]
        boxes = VGroup()
        for n in nodes:
            tx = Text(n, font_size=28, color=LIGHT)
            if tx.width > 2.6: tx.scale_to_fit_width(2.6)
            boxes.add(VGroup(RoundedRectangle(corner_radius=0.2, width=3.0, height=1.6, color=RED), tx))
        boxes.arrange(RIGHT, buff=0.7); fit(boxes, 12.5).move_to(ORIGIN)
        gap = max(0.3, (dur - 2) / (len(nodes) + 1))
        for i, b in enumerate(boxes):
            self.w(gap)
            anims = [FadeIn(b, shift=UP * 0.2)]
            if i: anims.append(GrowArrow(Arrow(boxes[i-1].get_right(), b.get_left(), buff=0.1, color=YELLOW)))
            self.p(*anims, rt=0.6)
