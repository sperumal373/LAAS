"""
Fix double/triple-encoded UTF-8 mojibake in App.jsx.
PowerShell Set-Content -Encoding UTF8 re-encoded the file causing all
multi-byte UTF-8 sequences to be expanded again.

Strategy: replace known bad byte sequences with their correct UTF-8 equivalents.
"""

fpath = r"C:\caas-dashboard\frontend\src\App.jsx"
with open(fpath, "rb") as f:
    raw = f.read()

# Strip BOM if present
had_bom = raw[:3] == b"\xef\xbb\xbf"
if had_bom:
    raw = raw[3:]

print(f"File size: {len(raw)} bytes")

# Build replacement table: damaged_bytes -> correct_bytes
# Each damaged sequence is the UTF-8 encoding of the Windows-1252 interpretation
# of the original UTF-8 bytes.
# Pattern: original UTF-8 multi-byte -> each byte interpreted as cp1252 char -> 
#          those chars encoded as UTF-8 again
#
# We enumerate all 2-byte and 3-byte UTF-8 starting sequences and their mojibake forms

def cp1252_to_utf8_moji(original_utf8_bytes):
    """Given original UTF-8 bytes, return the mojibake bytes that result from
    treating each byte as cp1252 and re-encoding as UTF-8."""
    result = bytearray()
    for byte in original_utf8_bytes:
        char = bytes([byte]).decode("cp1252", errors="replace")
        result.extend(char.encode("utf-8"))
    return bytes(result)

# Generate the full repair table for all Unicode chars that appear in the file
# We'll do this by scanning the current file for all multibyte sequences,
# treating them as mojibake, and building the reverse map

replacements = []

# First pass: collect all unique non-ASCII "runs" in the file as UTF-8 decoded chars
text = raw.decode("utf-8")

# Collect all chars > 0x7F
import re
# Find all runs of high Unicode chars (potential mojibake blocks)
# We look for chars in 0x80-0x2FFF range that form mojibake patterns
# Key insight: mojibake chars are ALWAYS in cp1252 range (0x80-0xFF mapped to cp1252)
# The cp1252 chars that are multibyte UTF-8: 0xC0-0xFF -> 2-byte UTF-8
#                                             0x80-0xBF -> shows as weird chars

# Build complete mapping: for every possible 2-byte original UTF-8 sequence (0xC2-0xDF + 0x80-0xBF)
# and every 3-byte sequence, generate the mojibake and add to replacement table
repair_map = {}

# 2-byte UTF-8: 0xC2-0xDF followed by 0x80-0xBF
for b1 in range(0xC2, 0xE0):
    for b2 in range(0x80, 0xC0):
        orig = bytes([b1, b2])
        try:
            char = orig.decode("utf-8")
            moji = cp1252_to_utf8_moji(orig)
            if moji != orig:
                repair_map[moji] = orig
        except:
            pass

# 3-byte UTF-8: 0xE0-0xEF + continuation bytes
for b1 in range(0xE0, 0xF0):
    for b2 in range(0x80, 0xC0):
        for b3 in range(0x80, 0xC0):
            orig = bytes([b1, b2, b3])
            try:
                orig.decode("utf-8")  # validate
                moji = cp1252_to_utf8_moji(orig)
                if moji != orig:
                    repair_map[moji] = orig
            except:
                pass

# 4-byte UTF-8 (emoji): 0xF0-0xF4
for b1 in range(0xF0, 0xF5):
    for b2 in range(0x80, 0xC0):
        for b3 in range(0x80, 0xC0):
            for b4 in range(0x80, 0xC0):
                orig = bytes([b1, b2, b3, b4])
                try:
                    orig.decode("utf-8")
                    moji = cp1252_to_utf8_moji(orig)
                    if moji != orig:
                        repair_map[moji] = orig
                except:
                    pass

print(f"Repair map entries: {len(repair_map)}")

# Sort by length descending so longer sequences are replaced first
sorted_keys = sorted(repair_map.keys(), key=lambda x: -len(x))

# Apply replacements
repaired = raw
total_replacements = 0
for moji_bytes in sorted_keys:
    correct_bytes = repair_map[moji_bytes]
    count = repaired.count(moji_bytes)
    if count > 0:
        repaired = repaired.replace(moji_bytes, correct_bytes)
        total_replacements += count

print(f"Total replacements made: {total_replacements}")

# Verify the result is valid UTF-8
try:
    result_text = repaired.decode("utf-8")
    print(f"Result is valid UTF-8, {len(result_text)} chars")
    
    # Check key characters
    print(f"  ✅ checkmark: {'✅' in result_text}")
    print(f"  — em dash: {'—' in result_text}")
    print(f"  … ellipsis: {'…' in result_text}")
    print(f"  ─ box dash: {'─' in result_text}")
    print(f"  🟠 orange circle: {'🟠' in result_text}")
    print(f"  ＋ fullwidth plus: {'＋' in result_text}")
    
    # Count remaining high chars
    high = sum(1 for c in result_text if 0x80 <= ord(c) <= 0xFF)
    print(f"  Remaining 0x80-0xFF chars (should be ~0): {high}")
    
    # Write repaired file
    with open(fpath, "wb") as f:
        f.write(repaired)  # no BOM
    print("WRITTEN successfully.")
    
except Exception as e:
    print(f"ERROR: result is not valid UTF-8: {e}")
    # Find bad position
    for pos in range(len(repaired)):
        try:
            repaired[:pos+1].decode("utf-8")
        except:
            print(f"  Bad at byte {pos}: {hex(repaired[pos])}")
            print(f"  Context: {repaired[max(0,pos-20):pos+20].hex()}")
            break
