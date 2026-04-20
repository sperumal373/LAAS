"""Fast fix: reverse cp1252-based double-encoding of UTF-8 in App.jsx"""
import re

fpath = r"C:\caas-dashboard\frontend\src\App.jsx"
with open(fpath, "rb") as f:
    raw = f.read()

# Strip BOM
if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]

text = raw.decode("utf-8")
print(f"Chars: {len(text)}")

# The damage: each original UTF-8 byte was treated as a cp1252 character
# and then re-encoded to UTF-8 by PowerShell.
# Fix: find runs of "high" chars (codepoints 0x80-0xFF plus cp1252 mapped chars)
# and reverse the transformation.

# cp1252 has special mappings for 0x80-0x9F that map to specific Unicode codepoints.
# Build reverse map: Unicode codepoint -> original byte value
CP1252_SPECIAL = {
    0x20AC: 0x80, 0x201A: 0x82, 0x0192: 0x83, 0x201E: 0x84, 0x2026: 0x85,
    0x2020: 0x86, 0x2021: 0x87, 0x02C6: 0x88, 0x2030: 0x89, 0x0160: 0x8A,
    0x2039: 0x8B, 0x0152: 0x8C, 0x017D: 0x8E, 0x2018: 0x91, 0x2019: 0x92,
    0x201C: 0x93, 0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97,
    0x02DC: 0x98, 0x2122: 0x99, 0x0161: 0x9A, 0x203A: 0x9B, 0x0153: 0x9C,
    0x017E: 0x9E, 0x0178: 0x9F,
}

def char_to_byte(ch):
    """Convert a Unicode char back to its cp1252 byte value, or None if not mappable."""
    cp = ord(ch)
    if cp < 0x80:
        return None  # ASCII - not part of mojibake
    if cp <= 0xFF:
        return cp  # Latin-1 range maps directly
    if cp in CP1252_SPECIAL:
        return CP1252_SPECIAL[cp]
    return None  # Not a cp1252 char

# Regex: find runs of chars that could be cp1252-expanded bytes
# These are chars in 0x80-0xFF range OR in CP1252_SPECIAL keys
cp1252_chars = set(chr(c) for c in range(0x80, 0x100)) | set(chr(c) for c in CP1252_SPECIAL)
pattern_chars = "".join(re.escape(c) for c in sorted(cp1252_chars))
moji_run = re.compile(f"[{re.escape(''.join(sorted(cp1252_chars)))}]{{2,}}")

def fix_run(m):
    """Given a run of mojibake chars, reverse the cp1252 encoding."""
    run = m.group(0)
    raw_bytes = bytearray()
    for ch in run:
        b = char_to_byte(ch)
        if b is not None:
            raw_bytes.append(b)
        else:
            # Shouldn't happen but fallback
            raw_bytes.extend(ch.encode("utf-8"))
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Not valid UTF-8 - return original
        return run

fixed = moji_run.sub(fix_run, text)

# Verify
has_moji = len(moji_run.findall(fixed))
print(f"Remaining mojibake runs after fix: {has_moji}")

# Check key symbols
checks = {"✅": "checkmark", "—": "em dash", "…": "ellipsis", "─": "box dash",
           "🟠": "orange", "🔷": "blue diamond", "💾": "floppy", "🖥": "monitor",
           "⚙": "gear", "📊": "chart", "✗": "cross", "·": "middot", "＋": "plus"}
for sym, label in checks.items():
    print(f"  {label}: {'YES' if sym in fixed else 'NO'}")

# Write
with open(fpath, "w", encoding="utf-8", newline="") as f:
    f.write(fixed)
print("DONE — file written.")
