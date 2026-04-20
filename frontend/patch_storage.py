# -*- coding: utf-8 -*-
"""
Patch App.jsx:
  Replace the Storage body block with:
    1. Full-width 5-donut row (Overall multi-arc + 4 per-OEM)
       - Each donut: center used/total/%, OEM label + array count below
       - Hover on any arc => tooltip with per-array breakdown
    2. Existing 2x2 OEM grid (unchanged) below the donuts
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\caas-dashboard\frontend\src\App.jsx'
content = open(path, encoding='utf-8').read()

body_marker   = '            {/* \u2500\u2500 Body \u2500\u2500 */}'
footer_marker = '            {/* \u2500\u2500 Footer KPIs \u2500\u2500 */}'

b = content.find(body_marker)
close = '\n            )}\n\n' + footer_marker
body_end = content.find(close, b)
if b == -1 or body_end == -1:
    sys.exit('markers not found')

old_block = content[b : body_end + len('\n            )}')]

# ─────────────────────────────────────────────────────────────────────
# NEW BODY  (use concatenation to avoid raw-string escape issues)
# ─────────────────────────────────────────────────────────────────────
NB = []
NB.append(r"""            {/* ── Body ── */}
            {extArrays.length>0&&(
              <div style={{padding:"10px 14px 0 14px"}}>

                {/* ════════════════════════════════════════
                    5-Donut Row: Overall + per-OEM
                    ════════════════════════════════════════ */}
                {(()=>{
                  /* ── single-OEM donut helper ─────────────── */
                  const _oemDonut=(g,sz,sw)=>{
                    const r=(sz-sw)/2, cx=sz/2, cy=sz/2;
                    const pct=g.totalTB>0?Math.min(100,Math.round((g.usedTB/g.totalTB)*100)):0;
                    const usedSweep=pct/100*Math.PI*2;
                    const mkArc=(sweep)=>{
                      if(sweep<=0||sweep>Math.PI*2-0.001) return null;
                      const sa=-Math.PI/2, ea=sa+sweep;
                      const sx=cx+r*Math.cos(sa),sy=cy+r*Math.sin(sa);
                      const ex=cx+r*Math.cos(ea),ey=cy+r*Math.sin(ea);
                      return 'M'+sx.toFixed(2)+','+sy.toFixed(2)+'A'+r+','+r+',0,'+(sweep>Math.PI?1:0)+',1,'+ex.toFixed(2)+','+ey.toFixed(2);
                    };
                    const pctClr=pct<70?g.accentFrom:pct<85?"#f59e0b":"#ef4444";
                    const tipId='stg-oem-tip-'+g.id;
                    return(
                      <div key={g.id} style={{display:"flex",flexDirection:"column",alignItems:"center",
                        gap:5,flex:1,minWidth:90,position:"relative"}}>
                        <div style={{position:"relative",width:sz,height:sz,flexShrink:0}}>
                          <svg width={sz} height={sz} style={{display:"block",overflow:"visible"}}>
                            <defs>
                              <linearGradient id={"stg-oem-"+g.id} x1="0" y1="0" x2="1" y2="1">
                                <stop offset="0%" stopColor={g.accentFrom}/>
                                <stop offset="100%" stopColor={g.accentTo}/>
                              </linearGradient>
                            </defs>
                            {/* track ring */}
                            <circle cx={cx} cy={cy} r={r} fill="none" stroke={g.accentFrom+"22"} strokeWidth={sw}/>
                            {/* used arc */}
                            {mkArc(usedSweep)&&<path d={mkArc(usedSweep)} fill="none"
                              stroke={"url(#stg-oem-"+g.id+")"}
                              strokeWidth={sw} strokeLinecap="round"
                              style={{filter:"drop-shadow(0 0 6px "+g.accentFrom+"88)"}}/>}
                            {/* hit area */}
                            <circle cx={cx} cy={cy} r={r} fill="none" stroke="transparent" strokeWidth={sw+16}
                              style={{cursor:"pointer"}}
                              onMouseEnter={()=>{const t=document.getElementById(tipId);if(t)t.style.display="block";}}
                              onMouseLeave={()=>{const t=document.getElementById(tipId);if(t)t.style.display="none";}}/>
                            {/* center text */}
                            <text x={cx} y={cy-7} textAnchor="middle"
                              style={{fontSize:12,fontWeight:900,fill:"#f1f5f9",fontFamily:"'Geist Mono',monospace"}}>
                              {fmtTB(g.usedTB)}
                            </text>
                            <text x={cx} y={cy+5} textAnchor="middle"
                              style={{fontSize:7,fill:"#475569",fontWeight:700,letterSpacing:".3px"}}>
                              {"of "+fmtTB(g.totalTB)}
                            </text>
                            <text x={cx} y={cy+17} textAnchor="middle"
                              style={{fontSize:12,fontWeight:900,fill:pctClr}}>
                              {pct+"%"}
                            </text>
                          </svg>
                          {/* per-array tooltip */}
                          <div id={tipId} style={{display:"none",position:"absolute",
                            bottom:"calc(100% + 8px)",left:"50%",transform:"translateX(-50%)",
                            pointerEvents:"none",zIndex:70,
                            background:"linear-gradient(135deg,#0d1829f5,#0a1628f5)",
                            border:"1px solid "+g.accentFrom+"55",borderRadius:10,
                            padding:"8px 10px",minWidth:164,maxWidth:220,
                            boxShadow:"0 8px 28px rgba(0,0,0,0.75),0 0 12px "+g.accentFrom+"30"}}>
                            {/* tooltip header */}
                            <div style={{display:"flex",alignItems:"center",gap:6,
                              marginBottom:6,paddingBottom:5,borderBottom:"1px solid "+g.accentFrom+"30"}}>
                              <div style={{width:8,height:8,borderRadius:"50%",
                                background:g.accentFrom,boxShadow:"0 0 6px "+g.accentFrom}}/>
                              <span style={{fontSize:11,fontWeight:800,color:"#fff",
                                textTransform:"uppercase",letterSpacing:".5px"}}>{g.label}</span>
                              <span style={{marginLeft:"auto",fontSize:11,fontWeight:900,
                                color:pctClr,fontFamily:"'Geist Mono',monospace"}}>{pct+"%"}</span>
                            </div>
                            {/* per-array rows */}
                            {g.arrays.map((a,ai)=>{
                              const c=extCapMap[a.id];
                              if(!c||c.status==="error") return(
                                <div key={a.id} style={{display:"flex",alignItems:"center",
                                  gap:5,padding:"3px 0",opacity:.55}}>
                                  <span style={{fontSize:10,color:"#94a3b8",flex:1,
                                    overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{a.name}</span>
                                  <span style={{fontSize:9,color:"#ef4444",fontWeight:700}}>ERR</span>
                                </div>
                              );
                              const ap=c.totalTB>0?Math.min(100,Math.round((c.usedTB/c.totalTB)*100)):0;
                              const ac=ap<70?g.accentFrom:ap<85?"#f59e0b":"#ef4444";
                              return(
                                <div key={a.id} style={{
                                  padding:"4px 0",
                                  borderBottom:ai<g.arrays.length-1?"1px solid #1e293b":"none"}}>
                                  <div style={{display:"flex",alignItems:"center",gap:4,marginBottom:2}}>
                                    <span style={{fontSize:10,color:"#e2e8f0",fontWeight:600,flex:1,
                                      overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{a.name}</span>
                                    <span style={{fontSize:10,fontWeight:800,color:ac,
                                      fontFamily:"'Geist Mono',monospace",flexShrink:0}}>{ap+"%"}</span>
                                  </div>
                                  <div style={{height:3,borderRadius:2,background:"#1e293b",
                                    overflow:"hidden",marginBottom:2}}>
                                    <div style={{height:"100%",width:ap+"%",borderRadius:2,
                                      background:"linear-gradient(90deg,"+g.accentFrom+","+g.accentTo+")"}}/>
                                  </div>
                                  <div style={{fontSize:9,color:"#475569",
                                    fontFamily:"'Geist Mono',monospace"}}>
                                    {fmtTB(c.usedTB)+" / "+fmtTB(c.totalTB)}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                        {/* label below donut */}
                        <div style={{textAlign:"center",lineHeight:1.3}}>
                          <div style={{fontSize:11,fontWeight:800,color:g.accentFrom,
                            textTransform:"uppercase",letterSpacing:".6px"}}>{g.shortLabel}</div>
                          <div style={{fontSize:9,color:"#475569",marginTop:1}}>
                            {g.arrays.length+(g.arrays.length===1?" array":" arrays")}
                          </div>
                        </div>
                      </div>
                    );
                  };

                  /* ── Overall multi-arc donut ──────────────── */
                  const sz=110, sw=12;
                  const _r=(sz-sw)/2, _cx=sz/2, _cy=sz/2;
                  let _ang=-Math.PI/2;
                  const _gap=groupedArrays.length>1?0.05:0;
                  const ovSegs=groupedArrays.filter(g=>g.totalTB>0).map((g,i)=>{
                    const share=g.totalTB/Math.max(extTotalTB,0.001);
                    const tSweep=share*Math.PI*2-_gap;
                    const uSweep=Math.max(0,tSweep*(g.pct/100));
                    const sa=_ang, tEa=sa+tSweep, uEa=sa+uSweep;
                    _ang=tEa+_gap;
                    const mkP=(ea)=>{
                      if(Math.abs(ea-sa)<0.001) return null;
                      const sx=_cx+_r*Math.cos(sa),sy=_cy+_r*Math.sin(sa);
                      const ex=_cx+_r*Math.cos(ea),ey=_cy+_r*Math.sin(ea);
                      return 'M'+sx.toFixed(2)+','+sy.toFixed(2)+'A'+_r+','+_r+',0,'+(ea-sa>Math.PI?1:0)+',1,'+ex.toFixed(2)+','+ey.toFixed(2);
                    };
                    return{g,i,trackD:mkP(tEa),usedD:mkP(uEa)};
                  });

                  return(
                    <div style={{display:"flex",gap:10,alignItems:"flex-start",
                      padding:"8px 0 14px 0",borderBottom:"1px solid #1a2f4a",
                      overflowX:"auto"}}>

                      {/* Donut 0 — Overall */}
                      <div style={{display:"flex",flexDirection:"column",alignItems:"center",
                        gap:5,flex:1,minWidth:90,position:"relative"}}>
                        <div style={{position:"relative",width:sz,height:sz,flexShrink:0}}>
                          <svg width={sz} height={sz} style={{display:"block",overflow:"visible"}}>
                            <defs>
                              {groupedArrays.map(g=>(
                                <linearGradient key={g.id} id={"stg-ov-"+g.id} x1="0" y1="0" x2="1" y2="1">
                                  <stop offset="0%" stopColor={g.accentFrom}/>
                                  <stop offset="100%" stopColor={g.accentTo}/>
                                </linearGradient>
                              ))}
                            </defs>
                            {ovSegs.map((s,i)=>s.trackD&&(
                              <path key={"ot"+i} d={s.trackD} fill="none"
                                stroke={s.g.accentFrom+"22"} strokeWidth={sw} strokeLinecap="round"/>
                            ))}
                            {ovSegs.map((s,i)=>s.usedD&&(
                              <path key={"ou"+i} d={s.usedD} fill="none"
                                stroke={"url(#stg-ov-"+s.g.id+")"} strokeWidth={sw} strokeLinecap="round"
                                style={{filter:"drop-shadow(0 0 5px "+s.g.accentFrom+"88)"}}/>
                            ))}
                            {ovSegs.map((s,i)=>s.trackD&&(
                              <path key={"oh"+i} d={s.trackD} fill="none" stroke="transparent"
                                strokeWidth={sw+16} strokeLinecap="round" style={{cursor:"pointer"}}
                                onMouseEnter={()=>{const t=document.getElementById("stg-ov-tip-"+i);if(t)t.style.display="block";}}
                                onMouseLeave={()=>{const t=document.getElementById("stg-ov-tip-"+i);if(t)t.style.display="none";}}/>
                            ))}
                            <text x={_cx} y={_cy-7} textAnchor="middle"
                              style={{fontSize:12,fontWeight:900,fill:"#f1f5f9",fontFamily:"'Geist Mono',monospace"}}>
                              {fmtTB(extUsedTB)}
                            </text>
                            <text x={_cx} y={_cy+5} textAnchor="middle"
                              style={{fontSize:7,fill:"#475569",fontWeight:700,letterSpacing:".3px"}}>
                              {"of "+fmtTB(extTotalTB)}
                            </text>
                            <text x={_cx} y={_cy+17} textAnchor="middle"
                              style={{fontSize:12,fontWeight:900,fill:extColor}}>
                              {extPct+"%"}
                            </text>
                          </svg>
                          {/* overall tooltips — one per OEM arc */}
                          {ovSegs.map((s,i)=>{
                            const pc=s.g.pct<70?s.g.accentFrom:s.g.pct<85?"#f59e0b":"#ef4444";
                            return(
                              <div key={i} id={"stg-ov-tip-"+i}
                                style={{display:"none",position:"absolute",
                                  bottom:"calc(100% + 8px)",left:"50%",transform:"translateX(-50%)",
                                  pointerEvents:"none",zIndex:70,
                                  background:"linear-gradient(135deg,#0d1829f5,#0a1628f5)",
                                  border:"1px solid "+s.g.accentFrom+"55",borderRadius:9,
                                  padding:"7px 10px",minWidth:142,
                                  boxShadow:"0 6px 24px rgba(0,0,0,0.7),0 0 10px "+s.g.accentFrom+"30"}}>
                                <div style={{display:"flex",alignItems:"center",gap:5,marginBottom:5}}>
                                  <div style={{width:8,height:8,borderRadius:"50%",
                                    background:s.g.accentFrom,boxShadow:"0 0 6px "+s.g.accentFrom}}/>
                                  <span style={{fontSize:11,fontWeight:800,color:"#fff",
                                    textTransform:"uppercase",letterSpacing:".5px"}}>{s.g.label}</span>
                                </div>
                                <div style={{display:"grid",gridTemplateColumns:"auto auto",gap:"2px 8px"}}>
                                  <span style={{fontSize:10,color:"#64748b"}}>Used</span>
                                  <span style={{fontSize:10,fontWeight:700,color:pc,
                                    fontFamily:"'Geist Mono',monospace"}}>{fmtTB(s.g.usedTB)}</span>
                                  <span style={{fontSize:10,color:"#64748b"}}>Total</span>
                                  <span style={{fontSize:10,fontWeight:700,color:"#94a3b8",
                                    fontFamily:"'Geist Mono',monospace"}}>{fmtTB(s.g.totalTB)}</span>
                                  <span style={{fontSize:10,color:"#64748b"}}>Util</span>
                                  <span style={{fontSize:10,fontWeight:900,color:pc,
                                    fontFamily:"'Geist Mono',monospace"}}>{s.g.pct+"%"}</span>
                                  <span style={{fontSize:10,color:"#64748b"}}>Arrays</span>
                                  <span style={{fontSize:10,fontWeight:700,color:"#818cf8",
                                    fontFamily:"'Geist Mono',monospace"}}>{s.g.arrays.length}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        <div style={{textAlign:"center",lineHeight:1.3}}>
                          <div style={{fontSize:11,fontWeight:800,color:"#94a3b8",
                            textTransform:"uppercase",letterSpacing:".6px"}}>Overall</div>
                          <div style={{fontSize:9,color:"#475569",marginTop:1}}>
                            {extArrays.length+" arrays \u00b7 "+groupedArrays.length+" OEMs"}
                          </div>
                        </div>
                      </div>

                      {/* Donuts 1-4 — per OEM */}
                      {groupedArrays.map(g=>_oemDonut(g,sz,sw))}

                    </div>
                  );
                })()}

                {/* ════════════════════════════════════════
                    2×2 OEM Grid (per-array detail)
                    ════════════════════════════════════════ */}
                <div style={{padding:"10px 0"}}>
                <div style={{flex:1,minWidth:280,display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>""")

# Now append the existing 2x2 grid body (from the old content)
# Find start and end of the 2x2 grid content in old_block
old_block = content[b : body_end + len('\n            )}')]

# The 2x2 grid starts with the extTotalTB>0?groupedArrays... line
# and ends with the closing of the outer flex div
grid_inner_start = old_block.find('                  {extTotalTB>0?groupedArrays.map')
grid_inner_end   = old_block.find('\n              </div>\n            )}')
if grid_inner_start == -1 or grid_inner_end == -1:
    print('ERROR finding grid inner')
    print(repr(old_block[:500]))
    sys.exit(1)

grid_inner = old_block[grid_inner_start : grid_inner_end]
print(f'grid_inner len={len(grid_inner)}')

NB.append(grid_inner)
NB.append("""
                </div>
                </div>

              </div>
            )}""")

new_block = ''.join(NB)

# Replace
if old_block not in content:
    print('ERROR: old_block not found in content')
    sys.exit(1)

new_content = content.replace(old_block, new_block, 1)
open(path, 'w', encoding='utf-8').write(new_content)
print('DONE. File written.')
print(f'old_block len={len(old_block)}, new_block len={len(new_block)}')
