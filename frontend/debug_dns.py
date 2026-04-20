f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

# The approach: precompute fRecs right before the dns records table
# Instead of computing inline, compute it just before using it

# Current broken pattern (two separate .filter calls)
old_broken = (
    '                          {records.filter(r=>!dnsQ||[r.hostname,r.type,r.data]'
    '.some(v=>String(v||"").toLowerCase().includes(dnsQ.toLowerCase())))'
    '.length===0&&<tr><td colSpan={5} style={{padding:24,textAlign:"center",color:p.textMute}}>No matching records</td></tr>}\n'
    '                          {records.filter(r=>!dnsQ||[r.hostname,r.type,r.data]'
    '.some(v=>String(v||"").toLowerCase().includes(dnsQ.toLowerCase())))'
    '.map((r,i)=>('
)

# New approach: use a simple variable via useMemo-like const declared inline BEFORE the tbody,
# but we need to move the filter logic before JSX. 
# Best approach: wrap tbody content in a fragment and use a non-arrow expression

# Actually the simplest fix: use Array.from + filter but computed differently
# Let's replace with a global const computed just before the table header
# We'll inject it right before the <table> opening

# Find the table wrapper and inject the const before it
table_anchor = '                    <div style={{overflowX:"auto",borderRadius:8,border:`1px solid ${p.border}`,background:p.panel}}>\n                      <table style={{width:"100%",borderCollapse:"collapse"}}>\n                        <thead><tr style={{background:p.surface}}>\n                          <TH>Hostname</TH><TH w="70px">Type</TH><TH>Data</TH><TH w="90px">TTL</TH>{canWrite&&<TH w="80px">Delete</TH>}'

if table_anchor in content:
    print('Table anchor found')
    idx = content.find(table_anchor)
    # Find what comes before - the rLoad ternary
    segment = content[max(0,idx-300):idx+100]
    print(repr(segment))
else:
    print('Table anchor NOT found')
    # Try shorter
    short = '<TH>Hostname</TH><TH w="70px">Type</TH>'
    idx = content.find(short)
    print('Short found at:', idx)
    print(repr(content[max(0,idx-200):idx+100]))
