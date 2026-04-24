path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

marker = b'placeholder="Filter by name or OS..."'
idx = data.find(marker)
if idx < 0:
    print("Not found")
    exit()
close = data.find(b'/>', idx)
insert_pos = close + 2
clear_btn = (
    b'\r\n                {hasFilters && <button onClick={() => {setFPower("");setFOS("");setFTag("");setFApp("");}} '
    b'style={{marginLeft:8,padding:"6px 14px",borderRadius:8,border:"1px solid "+p.accent,background:"transparent",color:p.accent,fontSize:11.5,fontWeight:700,cursor:"pointer",letterSpacing:".5px"}}'
    b'>Clear Filters</button>}'
)
data = data[:insert_pos] + clear_btn + data[insert_pos:]
open(path, 'wb').write(data)
print("Added clear filters button")
