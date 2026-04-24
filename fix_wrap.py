path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
raw = open(path, "rb").read()

# Add back the missing wrapper before thead
old = b"            </div>\r\n                    <thead"
new = (
    b"            </div>\r\n"
    b"\r\n"
    b"            {loadingVMs ? <LoadDots p={p} /> : selVC && (\r\n"
    b"              <>\r\n"
    b"                {/* Selection stat bar */}\r\n"
    b"                {selCount > 0 && (\r\n"
    b"                  <div style={{\r\n"
    b"                    display: \"flex\", gap: 20, flexWrap: \"wrap\", padding: \"10px 16px\", marginBottom: 14,\r\n"
    b"                    borderRadius: 10, background: `${p.accent}10`, border: `1px solid ${p.accent}25`,\r\n"
    b"                  }}>\r\n"
)

c = raw.count(old)
print(f"Found {c}")
if c == 1:
    # Actually let me check what was there before - need the stat bar and table wrapper
    # The stat bar lines should still exist after thead. Let me just add the missing wrappers
    pass

# Better approach: find what's missing by checking lines around 616-617
lines = raw.split(b"\r\n")
# Line 616 is </div>, line 617 is <thead> - we need the wrapper between them
# Insert the missing lines
missing = b"\r\n".join([
    b"",
    b"            {loadingVMs ? <LoadDots p={p} /> : selVC && (",
    b"              <>",
    b"                {/* Selection stat bar */}",
    b"                {selCount > 0 && (",
    b"                  <div style={{",
    b'                    display: "flex", gap: 20, flexWrap: "wrap", padding: "10px 16px", marginBottom: 14,',
    b"                    borderRadius: 10, background: `${p.accent}10`, border: `1px solid ${p.accent}25`,",
    b"                  }}>",
    b'                    <span style={{ fontSize: 12, fontWeight: 700, color: p.accent }}>{selCount} VM{selCount !== 1 ? "s" : ""} selected</span>',
    b"                    <span style={{ fontSize: 12, color: p.textSub }}>{totalCPU} vCPUs</span>",
    b"                    <span style={{ fontSize: 12, color: p.textSub }}>{totalRAM.toFixed(1)} GB RAM</span>",
    b"                    <span style={{ fontSize: 12, color: p.textSub }}>{totalDisk.toFixed(1)} GB Storage</span>",
    b"                  </div>",
    b"                )}",
    b"",
    b'                <div style={{ maxHeight: 420, overflowY: "auto", borderRadius: 10, border: `1px solid ${p.border}` }}>',
    b'                  <table style={{ width: "100%", borderCollapse: "collapse" }}>',
])

raw = raw.replace(
    b"            </div>\r\n                    <thead",
    b"            </div>\r\n" + missing + b"\r\n                    <thead",
    1
)

open(path, "wb").write(raw)
print("Restored missing wrapper")