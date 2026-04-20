import sys
sys.stdout.reconfigure(encoding='utf-8')
path = r'c:\caas-dashboard\frontend\src\App.jsx'
lines = open(path, encoding='utf-8').readlines()

# Replace lines 1797..1857 (0-indexed) = the 2x2 OEM grid + stray )} 
# i.e. from "Right: 2x2 OEM grid" comment through the stray )}
print('START:', repr(lines[1796][:80]))
print('END:  ', repr(lines[1856][:80]))

new_grid = """\
                {/* Right: 2\xd72 OEM grid \u2014 each array as a mini card */}
                <div style={{flex:1,minWidth:280,display:"grid",gridTemplateColumns:"1fr 1fr",gap:10}}>
                  {extTotalTB>0?groupedArrays.map(g=>(
                    <div key={g.id} style={{borderRadius:12,overflow:"hidden",border:`1px solid ${g.accentFrom}35`,display:"flex",flexDirection:"column",
                      boxShadow:`0 4px 20px ${g.accentFrom}15`}}>
                      {/* OEM gradient header */}
                      <div style={{padding:"8px 12px",background:g.gradient,display:"flex",alignItems:"center",gap:8,
                        boxShadow:`inset 0 -2px 8px rgba(0,0,0,0.3)`}}>
                        <span style={{fontSize:16}}>{g.icon}</span>
                        <div style={{flex:1}}>
                          <div style={{fontSize:11,fontWeight:900,color:"#fff",textTransform:"uppercase",letterSpacing:"1px"}}>{g.label}</div>
                          <div style={{fontSize:10,color:"#ffffffbb",fontFamily:"'Geist Mono',monospace",marginTop:1}}>{fmtTB(g.usedTB)} / {fmtTB(g.totalTB)}</div>
                        </div>
                        <div style={{width:36,height:36,borderRadius:"50%",background:"rgba(0,0,0,0.3)",border:"2px solid #ffffff40",
                          display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
                          <span style={{fontSize:11,fontWeight:900,color:"#fff"}}>{g.pct}%</span>
                        </div>
                      </div>
                      {/* OEM thick progress bar */}
                      <div style={{height:4,background:"rgba(0,0,0,0.4)",overflow:"hidden"}}>
                        <div style={{height:"100%",width:`${g.pct}%`,transition:"width 1.2s ease",
                          background:`linear-gradient(90deg,${g.accentFrom},${g.accentTo})`,
                          boxShadow:`0 0 8px ${g.accentFrom}88`}}/>
                      </div>
                      {/* per-array mini cards */}
                      <div style={{padding:"8px 10px",background:"#060d1a",display:"flex",flexDirection:"column",gap:6,flex:1}}>
                        {g.arrays.map(a=>{
                          const c=extCapMap[a.id];
                          const vc=_vendorColor(a.vendor);
                          if(!c||c.status==="error") return(
                            <div key={a.id} style={{padding:"7px 10px",borderRadius:8,background:"#0d1829",
                              border:`1px solid ${vc}25`,display:"flex",alignItems:"center",gap:8}}>
                              <div style={{width:4,height:"100%",minHeight:28,borderRadius:2,background:vc,flexShrink:0}}/>
                              <div style={{flex:1,minWidth:0}}>
                                <div style={{fontSize:12,color:"#94a3b8",fontWeight:700,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{a.name}</div>
                                <div style={{fontSize:10,color:"#475569",marginTop:1}}>{_tag(a.vendor)}</div>
                              </div>
                              <div style={{padding:"3px 8px",borderRadius:6,background:"#ef444420",border:"1px solid #ef444440",
                                fontSize:11,fontWeight:800,color:"#ef4444",flexShrink:0}}>{c?"ERR":"\u2026"}</div>
                            </div>
                          );
                          const pct=c.totalTB>0?Math.min(100,Math.round((c.usedTB/c.totalTB)*100)):0;
                          const barClr=pct<70?vc:pct<85?"#f59e0b":"#ef4444";
                          return(
                            <div key={a.id} style={{padding:"8px 10px",borderRadius:8,background:"#0d1829",
                              border:`1px solid ${vc}28`,transition:"border-color .2s"}}
                              onMouseEnter={e=>{e.currentTarget.style.borderColor=vc+"60";}}
                              onMouseLeave={e=>{e.currentTarget.style.borderColor=vc+"28";}}>
                              {/* array name + vendor tag + pct badge */}
                              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
                                <div style={{width:4,borderRadius:2,alignSelf:"stretch",background:barClr,flexShrink:0,
                                  boxShadow:`0 0 6px ${barClr}88`}}/>
                                <div style={{flex:1,minWidth:0}}>
                                  <div style={{fontSize:13,color:"#e2e8f0",fontWeight:700,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",lineHeight:1.2}}>{a.name}</div>
                                  <div style={{fontSize:10,color:vc,fontWeight:700,marginTop:2,opacity:.9}}>{_tag(a.vendor)}</div>
                                </div>
                                <div style={{width:34,height:34,borderRadius:"50%",flexShrink:0,
                                  background:`conic-gradient(${barClr} ${pct*3.6}deg, #1e293b ${pct*3.6}deg)`,
                                  display:"flex",alignItems:"center",justifyContent:"center",
                                  boxShadow:`0 0 8px ${barClr}44`}}>
                                  <div style={{width:24,height:24,borderRadius:"50%",background:"#0d1829",
                                    display:"flex",alignItems:"center",justifyContent:"center"}}>
                                    <span style={{fontSize:9,fontWeight:900,color:barClr}}>{pct}%</span>
                                  </div>
                                </div>
                              </div>
                              {/* capacity bar */}
                              <div style={{height:6,borderRadius:3,background:"#1e293b",overflow:"hidden",marginLeft:12}}>
                                <div style={{height:"100%",width:`${pct}%`,borderRadius:3,transition:"width 1.1s ease",
                                  background:`linear-gradient(90deg,${barClr},${g.accentTo})`,
                                  boxShadow:`0 0 8px ${barClr}66`}}/>
                              </div>
                              {/* used / total labels */}
                              <div style={{display:"flex",justifyContent:"space-between",marginTop:4,marginLeft:12}}>
                                <span style={{fontSize:10,color:"#64748b",fontFamily:"'Geist Mono',monospace",fontWeight:600}}>{fmtTB(c.usedTB)} used</span>
                                <span style={{fontSize:10,color:"#334155",fontFamily:"'Geist Mono',monospace"}}>{fmtTB(c.totalTB)} total</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )):(
                    <div style={{gridColumn:"1/-1",textAlign:"center",padding:"24px 0",color:"#475569",fontSize:13}}>
                      <div style={{fontSize:28,marginBottom:6,opacity:.4}}>\U0001f5c2\ufe0f</div>
                      <div style={{fontWeight:600}}>Fetching array capacity\u2026</div>
                      <div style={{marginTop:3,color:"#334155",fontSize:11}}>{extArrays.length} array{extArrays.length!==1?"s":""} registered</div>
                    </div>
                  )}
                </div>

              </div>
            )}
"""

# Replace indices 1796..1856 (0-indexed), which is lines 1797-1857 (1-indexed)
new_lines = lines[:1796] + [new_grid] + lines[1857:]
open(path, 'w', encoding='utf-8').writelines(new_lines)

nl = open(path, encoding='utf-8').readlines()
print('Done. Total lines:', len(nl))
# verify
for i,l in enumerate(nl[1793:1802], start=1793):
    print(f'{i+1}: {l.rstrip()[:90]}')
