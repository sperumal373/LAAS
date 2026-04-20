import sys, uuid
sys.stdout.reconfigure(encoding='utf-8')
path = r'c:\caas-dashboard\frontend\src\App.jsx'
lines = open(path, encoding='utf-8').readlines()

# Replace the entire STORAGE OVERVIEW IIFE: lines 1647-1880 (1-indexed) = indices 1646-1879

print('START:', repr(lines[1646][:60]))
print('END:  ', repr(lines[1879][:60]))

new_section = r"""      {/* ────── STORAGE OVERVIEW ────── */}
      {(()=>{
        const extArrays  = ovStorArrays||[];
        const extCapMap  = ovStorCapMap||{};
        const extFetched = ovStorArrays!==null;
        if(!extFetched && extArrays.length===0) return null;

        const extTotalTB=extArrays.reduce((s,a)=>s+(extCapMap[a.id]?.totalTB||0),0);
        const extUsedTB =extArrays.reduce((s,a)=>s+(extCapMap[a.id]?.usedTB||0),0);
        const extFreeTB =extArrays.reduce((s,a)=>s+(extCapMap[a.id]?.freeTB||0),0);
        const extPct    =extTotalTB>0?Math.round((extUsedTB/extTotalTB)*100):0;
        const extColor  =extPct<70?"#10b981":extPct<85?"#f59e0b":"#ef4444";
        const fmtTB=v=>v>=1?v.toFixed(1)+" TB":(v*1024).toFixed(0)+" GB";

        const _oemGroups=[
          {id:"dell",  label:"Dell Technologies",shortLabel:"Dell",  accentFrom:"#0076CE",accentTo:"#00A3E0",gradient:"linear-gradient(135deg,#0076CE,#00457C)",icon:"\uD83D\uDFE6",vendors:["Dell-EMC","Dell PowerFlex","Dell PowerScale"]},
          {id:"pure",  label:"Pure Storage",      shortLabel:"Pure",  accentFrom:"#FE5000",accentTo:"#FF8C00",gradient:"linear-gradient(135deg,#FE5000,#FF8C00)",icon:"\uD83D\uDFE0",vendors:["Pure Storage","Pure FlashArray"]},
          {id:"netapp",label:"NetApp",             shortLabel:"NetApp",accentFrom:"#0067C5",accentTo:"#5AABE3",gradient:"linear-gradient(135deg,#0067C5,#034078)",icon:"\uD83D\uDFE3",vendors:["NetApp"]},
          {id:"hpe",   label:"HPE",                shortLabel:"HPE",   accentFrom:"#01A982",accentTo:"#2AD2C9",gradient:"linear-gradient(135deg,#01A982,#00684A)",icon:"\uD83D\uDFE2",vendors:["HPE","HPE Nimble","HPE Alletra"]},
          {id:"other", label:"Other",              shortLabel:"Other", accentFrom:"#64748b",accentTo:"#94a3b8",gradient:"linear-gradient(135deg,#64748b,#334155)",icon:"\u2B1C",vendors:[]},
        ];
        const _vendorColor=v=>{const m={"NetApp":"#0067C5","Pure FlashArray":"#FE5000","Pure Storage":"#f97316","HPE":"#01A982","HPE Nimble":"#01A982","HPE Alletra":"#01A982","Dell-EMC":"#007DB8","Dell PowerFlex":"#0076CE","Dell PowerScale":"#00857C"};return m[v]||"#64748b";};
        const _tag=v=>{const m={"Dell-EMC":"PowerStore","Dell PowerFlex":"PowerFlex","Dell PowerScale":"PowerScale","Pure Storage":"FlashBlade","Pure FlashArray":"FlashArray","NetApp":"ONTAP","HPE":"Alletra","HPE Nimble":"Nimble","HPE Alletra":"Alletra"};return m[v]||v;};

        const groupedArrays=_oemGroups.map(g=>{
          const arrays=extArrays.filter(a=>g.vendors.includes(a.vendor)||(g.id==="other"&&!_oemGroups.slice(0,4).some(og=>og.vendors.includes(a.vendor))));
          const totalTB=arrays.reduce((s,a)=>s+(extCapMap[a.id]?.totalTB||0),0);
          const usedTB =arrays.reduce((s,a)=>s+(extCapMap[a.id]?.usedTB||0),0);
          const pct=totalTB>0?Math.round((usedTB/totalTB)*100):0;
          return{...g,arrays,totalTB,usedTB,pct};
        }).filter(g=>g.arrays.length>0);

        // ── Interactive donut with hover tooltip ──
        // Uses a unique prefix per render to avoid gradient ID clashes
        const _gid=`stg`;
        const _multiDonut=(sz=120,sw=13)=>{
          const r=(sz-sw)/2,cx=sz/2,cy=sz/2;
          let angle=-Math.PI/2;
          const gap=groupedArrays.length>1?0.05:0;
          // Build arc segments with angle metadata for tooltip hit-testing
          const segments=groupedArrays.filter(g=>g.totalTB>0).map(g=>{
            const share=g.totalTB/Math.max(extTotalTB,0.001);
            const totalSweep=share*Math.PI*2-gap;
            const usedSweep=Math.max(0,totalSweep*(g.pct/100));
            const sa=angle, trackEa=sa+totalSweep, usedEa=sa+usedSweep;
            angle=trackEa+gap;
            const mkPath=(ea)=>{
              if(Math.abs(ea-sa)<0.001) return null;
              const sx=cx+r*Math.cos(sa),sy=cy+r*Math.sin(sa);
              const ex=cx+r*Math.cos(ea),ey=cy+r*Math.sin(ea);
              return`M${sx},${sy}A${r},${r},0,${ea-sa>Math.PI?1:0},1,${ex},${ey}`;
            };
            // midpoint angle for tooltip anchor
            const midA=sa+totalSweep/2;
            const tipX=cx+(r+sw)*Math.cos(midA);
            const tipY=cy+(r+sw)*Math.sin(midA);
            return{g,trackD:mkPath(trackEa),usedD:mkPath(usedEa),midA,tipX,tipY};
          });
          return(
            <div style={{position:"relative",width:sz,height:sz,flexShrink:0}}>
              <svg width={sz} height={sz} style={{display:"block",overflow:"visible"}}>
                <defs>
                  {groupedArrays.map(g=>(
                    <linearGradient key={g.id} id={`${_gid}-${g.id}`} x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stopColor={g.accentFrom}/><stop offset="100%" stopColor={g.accentTo}/>
                    </linearGradient>
                  ))}
                </defs>
                {/* track arcs */}
                {segments.map((s,i)=>s.trackD&&<path key={`t${i}`} d={s.trackD} fill="none" stroke={s.g.accentFrom+"20"} strokeWidth={sw} strokeLinecap="round"/>)}
                {/* used arcs */}
                {segments.map((s,i)=>s.usedD&&<path key={`u${i}`} d={s.usedD} fill="none" stroke={`url(#${_gid}-${s.g.id})`} strokeWidth={sw} strokeLinecap="round"
                  style={{filter:`drop-shadow(0 0 6px ${s.g.accentFrom}88)`}}/>)}
                {/* invisible wide hit areas for hover tooltip */}
                {segments.map((s,i)=>s.trackD&&(
                  <path key={`h${i}`} d={s.trackD} fill="none" stroke="transparent" strokeWidth={sw+14} strokeLinecap="round"
                    style={{cursor:"pointer"}}
                    onMouseEnter={e=>{
                      const tip=document.getElementById(`${_gid}-tip-${i}`);
                      if(tip){tip.style.display="block";}
                    }}
                    onMouseLeave={e=>{
                      const tip=document.getElementById(`${_gid}-tip-${i}`);
                      if(tip){tip.style.display="none";}
                    }}/>
                ))}
                {/* center text */}
                <text x={cx} y={cy-10} textAnchor="middle" style={{fontSize:14,fontWeight:900,fill:"#f1f5f9",fontFamily:"'Geist Mono',monospace"}}>{fmtTB(extUsedTB)}</text>
                <text x={cx} y={cy+4}  textAnchor="middle" style={{fontSize:8,fill:"#475569",fontWeight:700,textTransform:"uppercase",letterSpacing:".5px"}}>used of</text>
                <text x={cx} y={cy+17} textAnchor="middle" style={{fontSize:12,fontWeight:800,fill:"#475569",fontFamily:"'Geist Mono',monospace"}}>{fmtTB(extTotalTB)}</text>
                <text x={cx} y={cy+31} textAnchor="middle" style={{fontSize:11,fontWeight:900,fill:extColor}}>{extPct}%</text>
              </svg>
              {/* hover tooltips — positioned absolutely over svg */}
              {segments.map((s,i)=>{
                const left=Math.round(s.tipX);
                const top=Math.round(s.tipY);
                const pctClr=s.g.pct<70?s.g.accentFrom:s.g.pct<85?"#f59e0b":"#ef4444";
                return(
                  <div key={`tip${i}`} id={`${_gid}-tip-${i}`} style={{display:"none",position:"absolute",
                    left:left,top:top,transform:"translate(-50%,-110%)",
                    pointerEvents:"none",zIndex:50,
                    background:"linear-gradient(135deg,#0d1829ee,#0a1628ee)",
                    border:`1px solid ${s.g.accentFrom}60`,borderRadius:8,
                    padding:"6px 10px",minWidth:130,
                    boxShadow:`0 4px 20px rgba(0,0,0,0.6),0 0 10px ${s.g.accentFrom}33`}}>
                    <div style={{display:"flex",alignItems:"center",gap:5,marginBottom:4}}>
                      <div style={{width:8,height:8,borderRadius:"50%",background:s.g.accentFrom,boxShadow:`0 0 6px ${s.g.accentFrom}`}}/>
                      <span style={{fontSize:11,fontWeight:800,color:"#fff",textTransform:"uppercase",letterSpacing:".5px"}}>{s.g.label}</span>
                    </div>
                    <div style={{display:"grid",gridTemplateColumns:"auto auto",gap:"2px 8px"}}>
                      <span style={{fontSize:10,color:"#64748b"}}>Used</span>
                      <span style={{fontSize:10,fontWeight:700,color:pctClr,fontFamily:"'Geist Mono',monospace"}}>{fmtTB(s.g.usedTB)}</span>
                      <span style={{fontSize:10,color:"#64748b"}}>Total</span>
                      <span style={{fontSize:10,fontWeight:700,color:"#94a3b8",fontFamily:"'Geist Mono',monospace"}}>{fmtTB(s.g.totalTB)}</span>
                      <span style={{fontSize:10,color:"#64748b"}}>Util</span>
                      <span style={{fontSize:10,fontWeight:900,color:pctClr,fontFamily:"'Geist Mono',monospace"}}>{s.g.pct}%</span>
                      <span style={{fontSize:10,color:"#64748b"}}>Arrays</span>
                      <span style={{fontSize:10,fontWeight:700,color:"#818cf8",fontFamily:"'Geist Mono',monospace"}}>{s.g.arrays.length}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        };

        return(
          <div style={{background:"linear-gradient(135deg,#080f1c,#0d1829,#0a1628)",
            border:"1px solid #1a2f4a",borderRadius:16,overflow:"hidden",
            boxShadow:"0 8px 40px rgba(0,0,0,0.45)"}}>

            {/* ── Header ── */}
            <div style={{padding:"11px 16px",background:"linear-gradient(135deg,#0076CE0d,#FE50000a,#0a1628)",
              borderBottom:"1px solid #1a2f4a",display:"flex",alignItems:"center",gap:12,flexWrap:"wrap"}}>
              <div style={{width:34,height:34,borderRadius:9,flexShrink:0,
                background:"linear-gradient(135deg,#0076CE,#FE5000,#01A982)",
                display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,
                boxShadow:"0 4px 12px #0076CE40"}}>{"\uD83D\uDDC2\uFE0F"}</div>
              <div style={{flex:1,minWidth:120}}>
                <div style={{fontWeight:900,fontSize:14,letterSpacing:"1.2px",textTransform:"uppercase",
                  background:"linear-gradient(90deg,#0076CE,#FE5000,#01A982,#0067C5)",
                  WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>Enterprise Storage Arrays</div>
                <div style={{fontSize:10,color:"#475569",marginTop:1}}>
                  {extArrays.length} arrays · {groupedArrays.length} OEM vendors · hover donut for details</div>
              </div>
              <div style={{display:"flex",gap:5,alignItems:"center",flexWrap:"wrap"}}>
                {groupedArrays.map(g=>(
                  <div key={g.id} style={{display:"flex",alignItems:"center",gap:4,padding:"2px 7px",borderRadius:5,
                    background:g.accentFrom+"18",border:`1px solid ${g.accentFrom}35`}}>
                    <div style={{width:6,height:6,borderRadius:"50%",background:g.accentFrom,boxShadow:`0 0 5px ${g.accentFrom}`}}/>
                    <span style={{fontSize:10,fontWeight:800,color:g.accentFrom,textTransform:"uppercase",letterSpacing:".4px"}}>{g.shortLabel}</span>
                    <span style={{fontSize:10,color:"#64748b",fontFamily:"'Geist Mono',monospace"}}>{g.pct}%</span>
                  </div>
                ))}
              </div>
              <div style={{padding:"3px 10px",borderRadius:8,background:extColor+"20",border:`1px solid ${extColor}40`,fontSize:11,fontWeight:800,color:extColor,flexShrink:0}}>
                {extPct===0&&extTotalTB===0?"LOADING":extPct<70?"HEALTHY":extPct<85?"WARNING":"CRITICAL"}
              </div>
              <button onClick={()=>onNavigate("storage")} style={{padding:"3px 10px",borderRadius:6,
                border:"1px solid #0076CE50",background:"#0076CE15",color:"#60a5fa",
                fontSize:11,fontWeight:700,cursor:"pointer",whiteSpace:"nowrap",transition:"all .2s",flexShrink:0}}
                onMouseEnter={e=>{e.currentTarget.style.background="#0076CE30";}}
                onMouseLeave={e=>{e.currentTarget.style.background="#0076CE15";}}>Manage \u2192</button>
            </div>

            {/* ── Body ── */}
            {extArrays.length>0&&(
              <div style={{padding:"12px 14px",display:"flex",gap:14,alignItems:"flex-start",flexWrap:"wrap"}}>

                {/* Left: interactive donut + 4 stats */}
                <div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:8,flexShrink:0,width:120}}>
                  {_multiDonut(120,13)}
                  <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"2px 6px",width:"100%"}}>
                    {[{l:"Used",v:fmtTB(extUsedTB),c:extColor},{l:"Free",v:fmtTB(extFreeTB),c:"#10b981"},{l:"Total",v:fmtTB(extTotalTB),c:"#94a3b8"},{l:"Arrays",v:extArrays.length,c:"#818cf8"}].map(s=>(
                      <div key={s.l} style={{textAlign:"center",padding:"2px 0"}}>
                        <div style={{fontWeight:900,fontSize:12,color:s.c,fontFamily:"'Geist Mono',monospace",lineHeight:1}}>{s.v}</div>
                        <div style={{fontSize:8,color:"#334155",fontWeight:700,textTransform:"uppercase",letterSpacing:".3px",marginTop:1}}>{s.l}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Right: 2x2 OEM grid — compact per-array rows */}
                <div style={{flex:1,minWidth:280,display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
                  {extTotalTB>0?groupedArrays.map(g=>(
                    <div key={g.id} style={{borderRadius:10,overflow:"hidden",border:`1px solid ${g.accentFrom}30`,
                      display:"flex",flexDirection:"column",boxShadow:`0 2px 12px ${g.accentFrom}10`}}>
                      {/* OEM header */}
                      <div style={{padding:"7px 10px",background:g.gradient,display:"flex",alignItems:"center",gap:7}}>
                        <span style={{fontSize:14}}>{g.icon}</span>
                        <div style={{flex:1,minWidth:0}}>
                          <div style={{fontSize:11,fontWeight:900,color:"#fff",textTransform:"uppercase",letterSpacing:".8px",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{g.label}</div>
                          <div style={{fontSize:9,color:"#ffffffaa",fontFamily:"'Geist Mono',monospace",marginTop:1}}>{fmtTB(g.usedTB)} / {fmtTB(g.totalTB)}</div>
                        </div>
                        <div style={{padding:"2px 6px",borderRadius:5,background:"rgba(0,0,0,0.3)",border:"1px solid #ffffff30",fontSize:11,fontWeight:900,color:"#fff",flexShrink:0}}>{g.pct}%</div>
                      </div>
                      {/* OEM progress bar */}
                      <div style={{height:3,background:"rgba(0,0,0,0.5)",overflow:"hidden"}}>
                        <div style={{height:"100%",width:`${g.pct}%`,transition:"width 1.2s ease",
                          background:`linear-gradient(90deg,${g.accentFrom},${g.accentTo})`,boxShadow:`0 0 6px ${g.accentFrom}88`}}/>
                      </div>
                      {/* per-array compact rows */}
                      <div style={{padding:"6px 8px",background:"#060d1a",display:"flex",flexDirection:"column",gap:4,flex:1}}>
                        {g.arrays.map(a=>{
                          const c=extCapMap[a.id];
                          const vc=_vendorColor(a.vendor);
                          if(!c||c.status==="error") return(
                            <div key={a.id} style={{display:"flex",alignItems:"center",gap:6,padding:"4px 6px",borderRadius:6,background:"#0d182988",border:`1px solid ${vc}20`}}>
                              <div style={{width:3,height:"100%",minHeight:16,borderRadius:2,background:vc,flexShrink:0}}/>
                              <span style={{fontSize:11,color:"#64748b",flex:1,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontWeight:600}}>{a.name}</span>
                              <span style={{fontSize:9,color:vc,fontWeight:700,padding:"1px 4px",borderRadius:3,background:vc+"18",flexShrink:0}}>{_tag(a.vendor)}</span>
                              <span style={{fontSize:9,color:c?"#ef4444":"#f59e0b",fontWeight:800,flexShrink:0}}>{c?"ERR":"\u2026"}</span>
                            </div>
                          );
                          const pct=c.totalTB>0?Math.min(100,Math.round((c.usedTB/c.totalTB)*100)):0;
                          const barClr=pct<70?vc:pct<85?"#f59e0b":"#ef4444";
                          return(
                            <div key={a.id} style={{padding:"5px 6px",borderRadius:6,background:"#0d182988",
                              border:`1px solid ${vc}22`,transition:"border-color .2s,background .2s"}}
                              onMouseEnter={e=>{e.currentTarget.style.borderColor=vc+"55";e.currentTarget.style.background="#0d1829dd";}}
                              onMouseLeave={e=>{e.currentTarget.style.borderColor=vc+"22";e.currentTarget.style.background="#0d182988";}}>
                              <div style={{display:"flex",alignItems:"center",gap:5,marginBottom:4}}>
                                <div style={{width:3,alignSelf:"stretch",borderRadius:2,background:barClr,flexShrink:0,boxShadow:`0 0 5px ${barClr}88`}}/>
                                <div style={{flex:1,minWidth:0}}>
                                  <div style={{fontSize:12,color:"#e2e8f0",fontWeight:700,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",lineHeight:1.3}}>{a.name}</div>
                                </div>
                                <span style={{fontSize:9,color:vc,fontWeight:700,padding:"1px 4px",borderRadius:3,background:vc+"18",flexShrink:0,border:`1px solid ${vc}30`}}>{_tag(a.vendor)}</span>
                                <span style={{fontSize:11,fontWeight:900,color:barClr,fontFamily:"'Geist Mono',monospace",minWidth:28,textAlign:"right"}}>{pct}%</span>
                              </div>
                              <div style={{display:"flex",alignItems:"center",gap:6,marginLeft:8}}>
                                <div style={{flex:1,height:5,borderRadius:3,background:"#1e293b",overflow:"hidden"}}>
                                  <div style={{height:"100%",width:`${pct}%`,borderRadius:3,transition:"width 1.1s ease",
                                    background:`linear-gradient(90deg,${barClr},${g.accentTo})`,boxShadow:`0 0 6px ${barClr}66`}}/>
                                </div>
                                <span style={{fontSize:9,color:"#334155",fontFamily:"'Geist Mono',monospace",flexShrink:0,whiteSpace:"nowrap"}}>{fmtTB(c.usedTB)}/{fmtTB(c.totalTB)}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )):(
                    <div style={{gridColumn:"1/-1",textAlign:"center",padding:"20px 0",color:"#475569",fontSize:13}}>
                      <div style={{fontSize:26,marginBottom:5,opacity:.4}}>{"\uD83D\uDDC2\uFE0F"}</div>
                      <div style={{fontWeight:600}}>Fetching array capacity\u2026</div>
                    </div>
                  )}
                </div>

              </div>
            )}

            {/* ── Footer KPIs ── */}
            <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",borderTop:"1px solid #1a2f4a18"}}>
              {[
                {icon:"\uD83D\uDCE6",label:"Total",  value:fmtTB(extTotalTB),color:"#94a3b8"},
                {icon:"\uD83D\uDD34",label:"Used",   value:fmtTB(extUsedTB), color:extColor},
                {icon:"\uD83D\uDFE2",label:"Free",   value:fmtTB(extFreeTB), color:"#10b981"},
                {icon:"\uD83D\uDCCA",label:"Used %", value:extPct+"%",        color:extColor},
              ].map((k,i)=>(
                <div key={k.label} style={{padding:"8px 8px",textAlign:"center",
                  borderRight:i<3?"1px solid #1a2f4a18":"none",cursor:"pointer",transition:"background .2s"}}
                  onClick={()=>onNavigate("storage")}
                  onMouseEnter={e=>{e.currentTarget.style.background=k.color+"08";}}
                  onMouseLeave={e=>{e.currentTarget.style.background="transparent";}}>
                  <div style={{fontSize:13,marginBottom:1}}>{k.icon}</div>
                  <div style={{fontWeight:900,fontSize:15,color:k.color,fontFamily:"'Geist Mono',monospace",lineHeight:1}}>{k.value}</div>
                  <div style={{fontSize:8,fontWeight:700,color:"#334155",marginTop:1,textTransform:"uppercase",letterSpacing:".5px"}}>{k.label}</div>
                </div>
              ))}
            </div>
          </div>
        );
      })()}
"""

# indices 1646..1879 inclusive => replace with new_section
new_lines = lines[:1646] + [new_section] + lines[1880:]
open(path, 'w', encoding='utf-8').writelines(new_lines)

nl = open(path, encoding='utf-8').readlines()
print('Done. Total lines:', len(nl))
for i,l in enumerate(nl):
    if 'STORAGE OVERVIEW' in l or 'BACKUP & DATA PROTECTION' in l or 'IPAM OVERVIEW' in l:
        print(f'{i+1}: {l.rstrip()}')
