"""Procedural, labelled synthetic imagery for visual scenarios (Pillow + NumPy).

Every image is deterministic from (kind, seed, defect, severity, lighting) and comes with
ground-truth boxes. ``detect`` is a deliberately simple classical detector calibrated for
nominal lighting: it genuinely degrades when lighting shifts, which is what the visual
failure scenarios ask learners to diagnose. No model download or GPU is needed.
"""

import io
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

KINDS = {
    "surface": "Machined/stamped surface (factory visual QA)",
    "tower": "Power-line tower and insulators (drone inspection)",
    "turbine": "Wind-turbine blade close-up (drone inspection)",
    "traffic": "Junction camera, top-down (traffic enforcement)",
    "thermal": "Thermal camera of rotating/electrical equipment",
    "aerial": "Aerial orthophoto tile (disaster, drones, water, fleet)",
    "cells": "Microscopy field (genomics / drug discovery QC)",
}
DEFECTS = {
    "surface": ["scratch", "dent", "crack"],
    "tower": ["corrosion", "broken_insulator"],
    "turbine": ["erosion", "crack", "burn"],
    "traffic": ["red_light", "wrong_way"],
    "thermal": ["hotspot"],
    "aerial": ["flood", "damage"],
    "cells": ["abnormal_cell", "contamination"],
}


def _rng(kind, seed):
    return random.Random(f"{kind}:{seed}")


def _surface(d, img, rng, defect, severity, w, h):
    arr = np.asarray(img).astype(float)
    noise = np.random.default_rng(rng.randrange(10**9)).normal(0, 6, (h, w, 1))
    streak = np.sin(np.linspace(0, 40, h))[:, None, None] * 4
    arr = np.clip(arr + noise + streak, 0, 255)
    img.paste(Image.fromarray(arr.astype("uint8")))
    d = ImageDraw.Draw(img)
    boxes = []
    if defect:
        label = rng.choice(DEFECTS["surface"])
        x, y = rng.randint(40, w - 80), rng.randint(40, h - 60)
        size = int(20 + 50 * severity)
        if label == "scratch":
            x2, y2 = x + size, y + rng.randint(-size // 2, size // 2)
            d.line([(x, y), (x2, y2)], fill=(60, 60, 64), width=2)
            d.line([(x, y + 2), (x2, y2 + 2)], fill=(210, 210, 214), width=1)
            box = [min(x, x2) - 3, min(y, y2) - 3, max(x, x2) + 3, max(y, y2) + 5]
        elif label == "dent":
            r = size // 3
            for k in range(r, 0, -1):
                shade = int(95 + 60 * k / r)
                d.ellipse([x - k, y - k * 0.7, x + k, y + k * 0.7], fill=(shade, shade, shade + 4))
            box = [x - r, int(y - r * 0.7), x + r, int(y + r * 0.7)]
        else:
            pts, cx, cy = [], x, y
            for _ in range(10):
                cx += rng.randint(2, 7)
                cy += rng.randint(-5, 5)
                pts.append((cx, cy))
            d.line([(x, y)] + pts, fill=(35, 35, 38), width=2)
            xs, ys = [x] + [p[0] for p in pts], [y] + [p[1] for p in pts]
            box = [min(xs) - 3, min(ys) - 3, max(xs) + 3, max(ys) + 3]
        boxes.append(dict(label=label, box=box))
    return boxes


def _tower(d, img, rng, defect, severity, w, h):
    for y in range(h):
        c = int(150 + 70 * y / h)
        d.line([(0, y), (w, y)], fill=(c - 40, c - 10, c + 20))
    cx = w // 2 + rng.randint(-20, 20)
    base, top = h - 10, 30
    steel = (70, 74, 82)
    d.line([(cx - 45, base), (cx - 10, top)], fill=steel, width=3)
    d.line([(cx + 45, base), (cx + 10, top)], fill=steel, width=3)
    for k in range(8):
        y1 = top + (base - top) * k / 8
        y2 = top + (base - top) * (k + 1) / 8
        xl1, xr1 = cx - 10 - 35 * k / 8, cx + 10 + 35 * k / 8
        xl2, xr2 = cx - 10 - 35 * (k + 1) / 8, cx + 10 + 35 * (k + 1) / 8
        d.line([(xl1, y1), (xr2, y2)], fill=steel, width=1)
        d.line([(xr1, y1), (xl2, y2)], fill=steel, width=1)
    arm_y = top + 25
    d.rectangle([cx - 90, arm_y, cx + 90, arm_y + 6], fill=steel)
    boxes = []
    strings = [cx - 80, cx + 80, cx - 40]
    broken = rng.randrange(len(strings)) if defect else -1
    label = rng.choice(DEFECTS["tower"]) if defect else None
    for i, sx in enumerate(strings):
        for k in range(6):
            yy = arm_y + 8 + k * 7
            if label == "broken_insulator" and i == broken and k in (3, 4):
                continue
            d.ellipse([sx - 6, yy, sx + 6, yy + 5], fill=(196, 206, 220), outline=(90, 100, 120))
        d.line([(sx, arm_y + 50), (0 if sx < cx else w, arm_y + 70)], fill=(40, 40, 40), width=1)
        if label == "broken_insulator" and i == broken:
            boxes.append(dict(label=label, box=[sx - 10, arm_y + 26, sx + 10, arm_y + 44]))
    if label == "corrosion":
        x0 = cx + rng.randint(-80, 40)
        for _ in range(int(25 + 50 * severity)):
            px, py = x0 + rng.randint(0, 45), arm_y + rng.randint(-3, 9)
            d.ellipse([px, py, px + 3, py + 3], fill=(150 + rng.randint(0, 40), 80, 30))
        boxes.append(dict(label=label, box=[x0 - 2, arm_y - 5, x0 + 50, arm_y + 13]))
    return boxes


def _turbine(d, img, rng, defect, severity, w, h):
    for y in range(h):
        c = int(165 + 60 * y / h)
        d.line([(0, y), (w, y)], fill=(c - 55, c - 20, c + 25))
    angle = rng.uniform(-0.35, 0.35)
    length, width = w * 1.2, 46
    cx, cy = w * 0.1, h * 0.55

    def rot(px, py):
        return (
            cx + px * math.cos(angle) - py * math.sin(angle),
            cy + px * math.sin(angle) + py * math.cos(angle),
        )

    blade = [rot(0, -width / 2), rot(length, -width / 6), rot(length, width / 6), rot(0, width / 2)]
    d.polygon(blade, fill=(236, 238, 240), outline=(170, 172, 176))
    boxes = []
    if defect:
        label = rng.choice(DEFECTS["turbine"])
        t = rng.uniform(0.3, 0.7)
        px, py = rot(length * t, -width / 2 * (1 - t * 0.66))
        if label == "erosion":
            for _ in range(int(30 + 60 * severity)):
                ox, oy = rng.uniform(-30, 30), rng.uniform(0, 8)
                qx, qy = px + ox, py + oy
                d.point((qx, qy), fill=(120, 110, 100))
                d.ellipse([qx, qy, qx + 2, qy + 2], fill=(140, 128, 116))
            boxes.append(dict(label=label, box=[int(px - 32), int(py - 4), int(px + 32), int(py + 12)]))
        elif label == "crack":
            qx, qy = rot(length * t, 0)
            d.line([(qx - 20, qy - 6), (qx + 22, qy + 5)], fill=(60, 60, 60), width=2)
            boxes.append(dict(label=label, box=[int(qx - 24), int(qy - 10), int(qx + 26), int(qy + 9)]))
        else:
            qx, qy = rot(length * t, 4)
            for k in range(12, 0, -1):
                g = int(40 + 12 * k)
                d.ellipse([qx - k, qy - k, qx + k, qy + k], fill=(g, g - 10, g - 20))
            boxes.append(dict(label=label, box=[int(qx - 13), int(qy - 13), int(qx + 13), int(qy + 13)]))
    return boxes


def _traffic(d, img, rng, defect, severity, w, h):
    d.rectangle([0, 0, w, h], fill=(96, 120, 84))
    road = (78, 80, 86)
    d.rectangle([w // 2 - 40, 0, w // 2 + 40, h], fill=road)
    d.rectangle([0, h // 2 - 40, w, h // 2 + 40], fill=road)
    for x in range(0, w, 18):
        if not w // 2 - 40 < x < w // 2 + 40:
            d.line([(x, h // 2), (x + 9, h // 2)], fill=(230, 220, 120), width=1)
    for y in range(0, h, 18):
        if not h // 2 - 40 < y < h // 2 + 40:
            d.line([(w // 2, y), (w // 2, y + 9)], fill=(230, 220, 120), width=1)
    for k in range(6):
        d.rectangle([w // 2 - 38 + k * 13, h // 2 - 52, w // 2 - 32 + k * 13, h // 2 - 44], fill=(235, 235, 235))
    ns_green = rng.random() < 0.5
    lights = {"ns": (60, 200, 90) if ns_green else (220, 50, 50), "ew": (220, 50, 50) if ns_green else (60, 200, 90)}
    d.ellipse([w // 2 + 44, h // 2 - 56, w // 2 + 52, h // 2 - 48], fill=lights["ns"])
    d.ellipse([w // 2 - 58, h // 2 + 44, w // 2 - 50, h // 2 + 52], fill=lights["ew"])
    boxes = []
    colors = [(200, 40, 40), (40, 90, 200), (230, 200, 40), (235, 235, 235), (30, 30, 30), (40, 160, 90)]
    for _ in range(6):
        horizontal = rng.random() < 0.5
        c = rng.choice(colors)
        if horizontal:
            x, y = rng.choice([rng.randint(5, w // 2 - 75), rng.randint(w // 2 + 45, w - 35)]), h // 2 + rng.choice([-30, 10])
            box = [x, y, x + 26, y + 14]
        else:
            x, y = w // 2 + rng.choice([-30, 12]), rng.choice([rng.randint(5, h // 2 - 75), rng.randint(h // 2 + 45, h - 30)])
            box = [x, y, x + 14, y + 26]
        d.rectangle(box, fill=c, outline=(20, 20, 20))
        boxes.append(dict(label="vehicle", box=box))
    if defect:
        label = rng.choice(DEFECTS["traffic"])
        if label == "red_light":
            # A vehicle inside the junction on the axis whose light is red.
            if ns_green:
                box = [w // 2 - 20, h // 2 + 10, w // 2 + 6, h // 2 + 24]
            else:
                box = [w // 2 + 12, h // 2 - 20, w // 2 + 26, h // 2 + 6]
        else:
            box = [w - 60, h // 2 - 30, w - 34, h // 2 - 16]
            d.polygon([(w - 64, h // 2 - 23), (w - 58, h // 2 - 28), (w - 58, h // 2 - 18)], fill=(255, 255, 255))
        d.rectangle(box, fill=(250, 120, 20), outline=(20, 20, 20))
        boxes.append(dict(label=label, box=box))
    return boxes


def _thermal_lut(v):
    v = np.clip(v, 0, 1)
    r = np.clip(1.6 * v, 0, 1)
    g = np.clip(1.6 * v - 0.6, 0, 1)
    b = np.clip(np.where(v < 0.35, 0.3 + v, 1.2 - 2 * v), 0, 1)
    return (np.stack([r, g, b], -1) * 255).astype("uint8")


def _thermal(d, img, rng, defect, severity, w, h):
    yy, xx = np.mgrid[0:h, 0:w]
    field = 0.18 + 0.05 * np.sin(xx / 23.0) * np.cos(yy / 31.0)
    cx, cy = w // 2 + rng.randint(-30, 30), h // 2 + rng.randint(-15, 15)
    body = ((xx - cx) / 90.0) ** 2 + ((yy - cy) / 55.0) ** 2 < 1
    field = field + body * 0.32
    boxes = []
    if defect:
        hx, hy = cx + rng.randint(-50, 50), cy + rng.randint(-25, 25)
        spread = 8 + 10 * severity
        field = field + (0.35 + 0.35 * severity) * np.exp(-((xx - hx) ** 2 + (yy - hy) ** 2) / (2 * spread**2))
        r = int(spread * 2.2)
        boxes.append(dict(label="hotspot", box=[hx - r, hy - r, hx + r, hy + r]))
    img.paste(Image.fromarray(_thermal_lut(field)))
    d = ImageDraw.Draw(img)
    for k in range(h - 20):
        d.line([(w - 12, 10 + k), (w - 4, 10 + k)], fill=tuple(_thermal_lut(np.array([1 - k / (h - 20)]))[0]))
    return boxes


def _aerial(d, img, rng, defect, severity, w, h):
    palette = [(98, 140, 70), (120, 150, 80), (150, 130, 90), (86, 120, 60), (170, 160, 110)]
    for gx in range(0, w, 40):
        for gy in range(0, h, 40):
            d.rectangle([gx, gy, gx + 40, gy + 40], fill=rng.choice(palette))
    rx = rng.randint(60, w - 60)
    d.rectangle([rx - 5, 0, rx + 5, h], fill=(120, 120, 120))
    d.rectangle([0, h // 3 - 4, w, h // 3 + 4], fill=(120, 120, 120))
    river = [(0, int(h * 0.75))]
    for x in range(0, w + 20, 20):
        river.append((x, int(h * 0.75 + 12 * math.sin(x / 30))))
    d.line(river, fill=(70, 110, 170), width=10)
    buildings = []
    for _ in range(9):
        bx, by = rng.randint(10, w - 30), rng.randint(10, int(h * 0.62))
        d.rectangle([bx, by, bx + 16, by + 12], fill=(185, 180, 175), outline=(120, 115, 110))
        buildings.append((bx, by))
    boxes = []
    if defect:
        label = rng.choice(DEFECTS["aerial"])
        if label == "flood":
            fx, fy = rng.randint(40, w - 110), int(h * 0.5)
            pts = [(fx + 60 + 50 * math.cos(a) * rng.uniform(0.7, 1.2), fy + 30 * math.sin(a) * rng.uniform(0.7, 1.2)) for a in np.linspace(0, 2 * math.pi, 14)]
            d.polygon(pts, fill=(96, 110, 120))
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            boxes.append(dict(label=label, box=[int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]))
        else:
            for bx, by in buildings[: 2 + int(3 * severity)]:
                for _ in range(20):
                    px, py = bx + rng.randint(-3, 18), by + rng.randint(-3, 14)
                    d.point((px, py), fill=(60, 50, 45))
                d.rectangle([bx + 2, by + 2, bx + 14, by + 10], fill=(110, 95, 85))
                boxes.append(dict(label=label, box=[bx - 3, by - 3, bx + 19, by + 15]))
    return boxes


def _cells(d, img, rng, defect, severity, w, h):
    d.rectangle([0, 0, w, h], fill=(242, 222, 230))
    boxes = []
    for _ in range(26):
        x, y, r = rng.randint(8, w - 8), rng.randint(8, h - 8), rng.randint(7, 11)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(228, 170, 196), outline=(200, 140, 170))
        d.ellipse([x - r // 3, y - r // 3, x + r // 3, y + r // 3], fill=(120, 70, 150))
    if defect:
        label = rng.choice(DEFECTS["cells"])
        if label == "abnormal_cell":
            for _ in range(1 + int(2 * severity)):
                x, y, r = rng.randint(20, w - 20), rng.randint(20, h - 20), rng.randint(15, 20)
                d.polygon([(x + r * math.cos(a) * rng.uniform(0.8, 1.2), y + r * math.sin(a) * rng.uniform(0.8, 1.2)) for a in np.linspace(0, 2 * math.pi, 9)], fill=(210, 120, 170))
                d.ellipse([x - r // 2, y - r // 2, x + r // 2, y + r // 2], fill=(60, 20, 90))
                boxes.append(dict(label=label, box=[x - r - 3, y - r - 3, x + r + 3, y + r + 3]))
        else:
            x0, y0 = rng.randint(20, w - 70), rng.randint(20, h - 60)
            for _ in range(int(40 + 60 * severity)):
                px, py = x0 + rng.randint(0, 50), y0 + rng.randint(0, 40)
                d.ellipse([px, py, px + 2, py + 2], fill=(40, 60, 40))
            boxes.append(dict(label=label, box=[x0 - 2, y0 - 2, x0 + 54, y0 + 44]))
    return boxes


DRAW = dict(
    surface=_surface,
    tower=_tower,
    turbine=_turbine,
    traffic=_traffic,
    thermal=_thermal,
    aerial=_aerial,
    cells=_cells,
)


def render(kind, seed=0, defect=False, severity=0.7, lighting=1.0, size=(320, 240)):
    """Return (PIL image, annotations). ``lighting`` scales brightness and adds glare."""
    if kind not in DRAW:
        raise ValueError(f"Unknown visual kind '{kind}'. Choose from {', '.join(KINDS)}")
    w, h = size
    rng = _rng(kind, seed)
    base = (150, 152, 158) if kind == "surface" else (0, 0, 0)
    img = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(img)
    boxes = DRAW[kind](d, img, rng, defect, severity, w, h)
    if lighting != 1.0:
        arr = np.asarray(img).astype(float)
        yy, xx = np.mgrid[0:h, 0:w]
        glare = 40 * max(0.0, lighting - 1.0) * np.exp(-((xx - w * 0.7) ** 2 + (yy - h * 0.3) ** 2) / (2 * (w * 0.25) ** 2))
        arr = np.clip(arr * lighting + glare[..., None], 0, 255)
        img = Image.fromarray(arr.astype("uint8"))
    if kind in {"surface", "cells"}:
        img = img.filter(ImageFilter.GaussianBlur(0.4))
    return img, boxes


def png(img):
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def clip(kind, seed=0, defect=False, severity=0.7, frames=8, size=(320, 240)):
    """A short animated GIF 'video' clip: the scene shifts frame by frame."""
    w, h = size
    big, boxes = render(kind, seed, defect, severity, size=(w + 8 * frames, h))
    shots = []
    for f in range(frames):
        frame = big.crop((8 * f, 0, 8 * f + w, h))
        if kind == "traffic" and defect:
            d = ImageDraw.Draw(frame)
            d.text((6, 6), f"CAM-07  t+{f * 0.5:.1f}s", fill=(255, 255, 255))
        shots.append(frame.convert("P", palette=Image.ADAPTIVE, colors=96))
    out = io.BytesIO()
    shots[0].save(out, "GIF", save_all=True, append_images=shots[1:], duration=180, loop=0)
    return out.getvalue(), boxes


def features(img):
    """Hand-crafted image features used by the ML lab's visual defect models."""
    g = np.asarray(img.convert("L")).astype(float)
    blur = ndimage.uniform_filter(g, 9)
    residual = np.abs(g - blur)
    edges = np.hypot(ndimage.sobel(g, 0), ndimage.sobel(g, 1))
    return dict(
        brightness=round(float(g.mean()), 2),
        contrast=round(float(g.std()), 2),
        edge_density=round(float((edges > 60).mean()), 4),
        residual_peak=round(float(np.percentile(residual, 99.5)), 2),
        blob_area=round(float((residual > 18).mean()), 4),
    )


_REFERENCE = {}


def _reference_median(kind):
    """Median exposure of a nominal scene: the calibration the deployed detector assumes."""
    if kind not in _REFERENCE:
        img, _ = render(kind, seed=0, defect=False)
        _REFERENCE[kind] = float(np.median(np.asarray(img.convert("L"))))
    return _REFERENCE[kind]


def detect(img, kind, normalize=False, min_area=10):
    """Rule-based detector with absolute colour/intensity thresholds tuned for nominal exposure.

    Brighter or darker scenes shift pixel values past those thresholds, so defects are missed
    or false alarms appear: the 'new lighting' failure. ``normalize`` rescales exposure to
    the calibration reference first, which is the fix learners are expected to discover.
    """
    rgb = np.asarray(img.convert("RGB")).astype(float)
    if normalize:
        gray = np.asarray(img.convert("L")).astype(float)
        rgb = np.clip(rgb * (_reference_median(kind) / max(float(np.median(gray)), 1.0)), 0, 255)
    r, gch, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    g = 0.299 * r + 0.587 * gch + 0.114 * b
    sat = rgb.max(-1) - rgb.min(-1)
    if kind == "surface":
        mask = (g < 108) | (g > 240)
    elif kind == "tower":
        mask = (r - b > 80) & (r > 120) & (gch < 120)
    elif kind == "turbine":
        mask = (g < 132) & (sat < 30)
    elif kind == "traffic":
        mask = (sat > 70) & (rgb.min(-1) < 200)
    elif kind == "thermal":
        mask = g > 185
        mask[:, -18:] = False  # temperature scale bar
    elif kind == "aerial":
        total = np.maximum(r + gch + b, 1)
        flood = (np.abs(r / total - 0.295) < 0.018) & (np.abs(b / total - 0.368) < 0.018)
        mask = (flood & (g > 60)) | (g < 72)
    else:  # cells: abnormal nuclei are much darker than normal ones
        mask = g < 70
    mask = ndimage.binary_opening(mask, iterations=1)
    labels, count = ndimage.label(ndimage.binary_dilation(mask, iterations=2))
    found = []
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        if sl is None:
            continue
        area = int((labels[sl] == i).sum())
        if area < min_area:
            continue
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        found.append(dict(label="anomaly" if kind != "traffic" else "vehicle", box=[x0, y0, x1, y1], score=round(min(0.99, area / 400 + 0.3), 2)))
    return sorted(found, key=lambda b: -b["score"])[:12]


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def match(predicted, truth, threshold=0.1):
    """Recall-oriented matching of predicted boxes to labelled defects."""
    targets = [t for t in truth if t["label"] != "vehicle"]
    hits = sum(any(iou(p["box"], t["box"]) >= threshold for p in predicted) for t in targets)
    return dict(defects=len(targets), detected=hits, predictions=len(predicted))
