"""Visual regression for real screenshots: compare a capture with its approved baseline.

Screenshots are captured by a browser tool (for example Playwright) from the
running application. This module only compares PNG files; it never draws,
generates or retouches an image. Standard library only, so the PNG decoder
supports the common case: 8-bit greyscale/RGB with or without alpha, non-interlaced.
"""
import json
import re
import shutil
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path

from . import evidence
from .evidence import git_commit, sha256_file

NAME_RX = re.compile(r"^[a-z0-9][a-z0-9._-]{0,60}$")
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def read_png(path):
    """(width, height, channels, rows) where rows is a list of bytes objects."""
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG file")
    pos, idat, header = 8, [], None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
        pos += 12 + length
    if not header:
        raise ValueError(f"{path}: PNG has no header")
    width, height, depth, ctype, _comp, _filt, interlace = header
    if depth != 8 or ctype not in CHANNELS or interlace:
        raise ValueError(f"{path}: unsupported PNG variant (bit depth {depth}, colour type {ctype}, interlace {interlace}); "
                         "capture as a standard 8-bit PNG")
    bpp = CHANNELS[ctype]
    stride = width * bpp
    raw = zlib.decompress(b"".join(idat))
    rows, prev = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        ftype, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif ftype != 0:
            raise ValueError(f"{path}: corrupt PNG (filter {ftype})")
        rows.append(bytes(line))
        prev = line
    return width, height, bpp, rows


def diff_ratio(a_path, b_path, tolerance=16):
    """Fraction of pixels whose colour differs by more than `tolerance` in any channel."""
    wa, ha, ca, ra = read_png(a_path)
    wb, hb, cb, rb = read_png(b_path)
    if (wa, ha) != (wb, hb):
        return None, f"size changed from {wa}x{ha} to {wb}x{hb}"
    if ca != cb:
        return None, "colour format changed (for example an alpha channel was added)"
    changed = 0
    for row_a, row_b in zip(ra, rb, strict=True):
        if row_a == row_b:
            continue
        for x in range(0, len(row_a), ca):
            if any(abs(row_a[x + k] - row_b[x + k]) > tolerance for k in range(ca)):
                changed += 1
    return changed / (wa * ha), None


def write_png(path, width, height, rows):
    """Write 8-bit RGB rows as a PNG (used for the difference image)."""
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    raw = b"".join(b"\x00" + r for r in rows)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def diff_image(a_path, b_path, out_path, tolerance=16):
    """A picture of where two same-sized captures differ: the baseline faded to grey, changed pixels in red."""
    w, h, ca, ra = read_png(a_path)
    _w, _h, cb, rb = read_png(b_path)
    rows = []
    for row_a, row_b in zip(ra, rb, strict=True):
        out = bytearray(w * 3)
        for x in range(w):
            pa, pb = row_a[x * ca:x * ca + ca], row_b[x * cb:x * cb + cb]
            if any(abs(pa[k] - pb[k]) > tolerance for k in range(min(ca, cb))):
                out[x * 3:x * 3 + 3] = b"\xe0\x10\x10"
            else:
                grey = 255 - (255 - (sum(pa[:3]) // min(ca, 3) if ca >= 3 else pa[0])) // 3
                out[x * 3:x * 3 + 3] = bytes((grey, grey, grey))
        rows.append(bytes(out))
    write_png(out_path, w, h, rows)


def _dirs(review_dir, baselines):
    review = Path(review_dir)
    return review, Path(baselines) if baselines else review.parent / "visual-baselines"


def compare(review_dir, name, image, baselines=None, threshold=0.1, tolerance=16, area=13):
    """Compare a fresh capture with the approved baseline. threshold is in percent of pixels.
    Every comparison is kept as its own evidence record, so a verdict can be cited by ID."""
    if not NAME_RX.match(name or ""):
        raise ValueError("screenshot name must be lowercase letters, digits, dot, dash or underscore")
    review, base_dir = _dirs(review_dir, baselines)
    image = Path(image)
    read_png(image)  # reject anything that is not a real, supported PNG before storing it
    shots = review / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    current = shots / f"{name}.png"
    if image.resolve() != current.resolve():
        shutil.copy2(image, current)
    result = {"name": name, "current": f"screenshots/{name}.png", "sha256": sha256_file(current),
              "threshold_pct": threshold, "compared_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    baseline = base_dir / f"{name}.png"
    if not baseline.exists():
        result.update(verdict="no_baseline", reason="no approved baseline yet: show this capture to the user and "
                                                    "record their approval with `visual approve`")
    else:
        ratio, problem = diff_ratio(baseline, current, tolerance)
        if problem:
            result.update(verdict="changed", changed_pct=None, reason=problem)
        else:
            pct = round(ratio * 100, 4)
            result.update(changed_pct=pct, verdict="match" if pct <= threshold else "changed",
                          reason=f"{pct}% of pixels differ" + ("" if pct <= threshold else f" (allowed: {threshold}%)"))
            if pct > threshold:
                diff_image(baseline, current, shots / f"{name}.diff.png", tolerance)
                result["diff_image"] = f"screenshots/{name}.diff.png"
        meta = base_dir / f"{name}.json"
        if meta.exists():
            result["baseline"] = json.loads(meta.read_text(encoding="utf-8"))
    (shots / f"{name}.compare.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    n = len(list(shots.glob(f"{name}.compare-*.json"))) + 1
    kept = shots / f"{name}.compare-{n:02d}.json"
    kept.write_text(json.dumps(result, indent=2), encoding="utf-8")
    rec = evidence.add_artifact(review, area, f"visual compare {name}: {result['verdict']}",
                                f"visual compare --name {name} (capture sha256 {result['sha256'][:12]})", kept,
                                exit_code=0 if result["verdict"] == "match" else 1)
    result["evidence"] = rec["id"]
    return result


def approve(review_dir, name, approved_by, baselines=None, project=None):
    """Make the current capture the approved baseline. Only the user can decide a look is correct."""
    if not approved_by or not str(approved_by).strip():
        raise ValueError("a baseline needs --by <who approved it>")
    review, base_dir = _dirs(review_dir, baselines)
    current = review / "screenshots" / f"{name}.png"
    if not current.exists():
        raise ValueError(f"no capture named {name} in this review; run `visual compare` first")
    base_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, base_dir / f"{name}.png")
    meta = {"name": name, "approved_by": approved_by.strip(), "sha256": sha256_file(current),
            "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": git_commit(project) if project else None}
    (base_dir / f"{name}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    note = evidence.add_note(review, 13, f"visual baseline approved: {name}", "inference",
                             f"approved by {meta['approved_by']}; baseline sha256 {meta['sha256'][:12]}")
    meta["evidence"] = note["id"]
    return meta
