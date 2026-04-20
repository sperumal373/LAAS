// fix_3features.js — #1 Tag selector, #7 vCenter count, #11 Better overview graphics
const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
let content = raw;

function replace(search, replacement, label) {
  if (!content.includes(search)) {
    console.error('FAILED [' + label + ']: not found\n  Search: ' + JSON.stringify(search.substring(0,80)));
    return false;
  }
  const count = content.split(search).length - 1;
  if (count > 1) { console.error('FAILED [' + label + ']: '+count+' matches'); return false; }
  content = content.replace(search, replacement);
  console.log('OK [' + label + ']');
  return true;
}

// ── #7: Real connected count ──────────────────────────────────────────────────
replace(
  'const vcErrorCount = vcSums.filter(s=>s.status==="error").length;',
  '// A vCenter is "disconnected" if: API failed OR all ESXi hosts are offline\r\n        const vcErrorCount = vcSums.filter(s=>\r\n          s.status==="error" || (s.total_hosts>0 && (s.connected_hosts||0)===0)\r\n        ).length;',
  '#7 vcErrorCount'
);

// ── #1a: Tag state declarations ───────────────────────────────────────────────
replace(
  '  const [includeLicense, setIncludeLicense] = useState(false);  // OS license\r\n  const [includeInternet, setIncludeInternet] = useState(false); // internet access',
  '  const [includeLicense, setIncludeLicense] = useState(false);  // OS license\r\n  const [includeInternet, setIncludeInternet] = useState(false); // internet access\r\n  const [availTags,   setAvailTags]  = useState([]);\r\n  const [selTags,     setSelTags]    = useState([]);\r\n  const [tagsLoading, setTagsLoading]= useState(false);',
  '#1a tag state'
);

// ── #1b: useEffect to fetch tags when vcId changes ───────────────────────────
replace(
  '  // Step 3 — Network & IP\r\n  const [network,   setNetwork]  = useState("");',
  '  // Load VMware tags from project utilization for selected vCenter\r\n  useEffect(()=>{\r\n    if(!vcId) return;\r\n    let cancelled=false;\r\n    setTagsLoading(true); setAvailTags([]);\r\n    fetchProjectUtilization(vcId)\r\n      .then(d=>{\r\n        if(cancelled) return;\r\n        const tags=(d?.projects||[]).map(pr=>pr.tag||pr.name).filter(t=>t&&t!=="Untagged").sort();\r\n        setAvailTags([...new Set(tags)]);\r\n      })\r\n      .catch(()=>{})\r\n      .finally(()=>{ if(!cancelled) setTagsLoading(false); });\r\n    return()=>{ cancelled=true; };\r\n  },[vcId]);\r\n\r\n  // Step 3 — Network & IP\r\n  const [network,   setNetwork]  = useState("");',
  '#1b tag useEffect'
);

// ── #1c: Tag chips UI in Step 1 (between license section and duration/notes) ──
replace(
  '              )}\r\n            </div>\r\n\r\n            <div className="g2">\r\n              <div><label>Duration</label>',
  [
    '              )}',
    '            </div>',
    '',
    '            {/* Tag selector — VMware tags for this vCenter */}',
    '            {(availTags.length>0||tagsLoading)&&(',
    '              <div>',
    '                <label style={{display:"flex",alignItems:"center",gap:6,marginBottom:5}}>',
    '                  \ud83c\udff7\ufe0f VM Tags',
    '                  {tagsLoading&&<span style={{fontSize:10,color:p.yellow,marginLeft:5}}>\u23f3 Loading\u2026</span>}',
    '                  <span style={{fontSize:10,color:p.textMute,fontWeight:400,marginLeft:4}}>optional — select tags to apply on this VM</span>',
    '                </label>',
    '                {!tagsLoading&&(',
    '                  <div style={{display:"flex",flexWrap:"wrap",gap:6}}>',
    '                    {availTags.map(tag=>{',
    '                      const on=selTags.includes(tag);',
    '                      return(',
    '                        <button key={tag} type="button"',
    '                          onClick={()=>setSelTags(prev=>on?prev.filter(t=>t!==tag):[...prev,tag])}',
    '                          style={{padding:"4px 11px",borderRadius:20,fontSize:12,fontWeight:on?700:400,',
    '                            cursor:"pointer",transition:"all .12s",',
    '                            background:on?`${p.accent}22`:p.panelAlt,',
    '                            border:`1.5px solid ${on?p.accent:p.border}`,',
    '                            color:on?p.accent:p.textMute}}>',
    '                          {on?"\u2713 ":""}{tag}',
    '                        </button>',
    '                      );',
    '                    })}',
    '                  </div>',
    '                )}',
    '                {selTags.length>0&&(',
    '                  <div style={{fontSize:11,color:p.green,marginTop:5,padding:"4px 8px",',
    '                    borderRadius:5,background:`${p.green}10`,border:`1px solid ${p.green}20`}}>',
    '                    \u2705 Tags to apply: <b>{selTags.join(", ")}</b>',
    '                  </div>',
    '                )}',
    '              </div>',
    '            )}',
    '',
    '            <div className="g2">',
    '              <div><label>Duration</label>',
  ].join('\r\n'),
  '#1c tag chips UI'
);

// ── #1d: Tags in submission payload ──────────────────────────────────────────
replace(
  '        include_license:includeLicense,\r\n        license_type:includeLicense?detectedLicType:"",',
  '        include_license:includeLicense,\r\n        license_type:includeLicense?detectedLicType:"",\r\n        tags:selTags,',
  '#1d tags in payload'
);

// ── #11: Cross-platform heatmap row at bottom of EnvironmentChartsPanel ───────
replace(
  '      </div>\r\n    </div>\r\n  );\r\n}\r\n\r\n// \u2500\u2500\u2500 OVERVIEW \u2500\u2500\u2500',
  [
    '      </div>',
    '      {/* Cross-Platform Resource Heatmap */}',
    '      <div style={{padding:"14px 20px 16px",borderTop:`1px solid ${p.border}`,',
    '        background:`linear-gradient(90deg,${p.accent}06,${p.cyan}04,transparent)`}}>',
    '        <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.4px",textTransform:"uppercase",',
    '          color:p.textMute,marginBottom:10}}>',
    '          \ud83d\udcca Cross-Platform Resource Heatmap',
    '        </div>',
    '        <div style={{display:"flex",flexDirection:"column",gap:7}}>',
    '          {(()=>{',
    '            const rows=[',
    '              {label:"VMware \u2022 CPU",     pct:cpuPct,  color:"#3b82f6",detail:`${Math.round((summary?.cpu?.used_mhz||0)/1000)}/${Math.round((summary?.cpu?.total_mhz||0)/1000)} GHz`},',
    '              {label:"VMware \u2022 RAM",     pct:ramPct,  color:"#8b5cf6",detail:`${fmtGB(summary?.ram?.used_gb||0)} / ${fmtGB(summary?.ram?.total_gb||0)}`},',
    '              {label:"VMware \u2022 Storage", pct:diskPct, color:"#06b6d4",detail:`${fmtGB(summary?.storage?.used_gb||0)} / ${fmtGB(summary?.storage?.total_gb||0)}`},',
    '              ...(ocpClusters>0&&ocpPodsTot>0?[{label:"OCP \u2022 Pods",  pct:Math.round(ocpPodsRun/ocpPodsTot*100),  color:"#ef4444",detail:`${ocpPodsRun}/${ocpPodsTot} running`,inv:true}]:[]),',
    '              ...(ocpNodesTot>0?[{label:"OCP \u2022 Nodes", pct:Math.round(ocpNodesRdy/ocpNodesTot*100), color:"#f97316",detail:`${ocpNodesRdy}/${ocpNodesTot} ready`,  inv:true}]:[]),',
    '              ...(nutPCs>0&&nutVMsTot>0?[{label:"Nutanix \u2022 VMs",pct:Math.round(nutVMsRun/nutVMsTot*100), color:"#22c55e",detail:`${nutVMsRun}/${nutVMsTot} running`,inv:true}]:[]),',
    '            ];',
    '            return rows.map(({label,pct,color,detail,inv})=>{',
    '              const sp=Math.min(100,Math.max(0,pct||0));',
    '              const bc=inv?(sp>=80?"#10b981":sp>=50?"#f59e0b":"#ef4444"):(sp>=85?"#ef4444":sp>=65?"#f59e0b":color);',
    '              return(',
    '                <div key={label} style={{display:"flex",alignItems:"center",gap:8}}>',
    '                  <div style={{minWidth:140,fontSize:11,fontWeight:600,color:p.textSub,textAlign:"right"}}>{label}</div>',
    '                  <div style={{flex:1,height:10,borderRadius:5,background:`${p.border}70`,overflow:"hidden"}}>',
    '                    <div style={{width:`${sp}%`,height:"100%",borderRadius:5,',
    '                      background:`linear-gradient(90deg,${bc}99,${bc})`,',
    '                      boxShadow:`0 0 6px ${bc}50`,transition:"width .6s ease"}}/>',
    '                  </div>',
    '                  <div style={{minWidth:40,fontSize:11,fontWeight:800,color:bc,fontFamily:"monospace",textAlign:"right"}}>{sp}%</div>',
    '                  <div style={{minWidth:170,fontSize:10,color:p.textMute,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{detail}</div>',
    '                </div>',
    '              );',
    '            });',
    '          })()}',
    '        </div>',
    '      </div>',
    '    </div>',
    '  );',
    '}',
    '',
    '// \u2500\u2500\u2500 OVERVIEW \u2500\u2500\u2500',
  ].join('\r\n'),
  '#11 heatmap row'
);

// Mini connectivity bar inside each platform pill
replace(
  '                    <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:2}}>\r\n                      <div style={{width:8,height:8,borderRadius:"50%",background:sc,boxShadow:`0 0 6px ${sc}70`,animation:pl.status==="healthy"?"pulse 2s infinite":"none"}}/>',
  [
    '                    <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:3}}>',
    '                      {pl.connCount!=null&&pl.totalCount>0&&(',
    '                        <div title={`${pl.connCount}/${pl.totalCount} connected`}',
    '                          style={{width:50,height:4,borderRadius:2,background:`${p.border}60`,overflow:"hidden"}}>',
    '                          <div style={{width:`${Math.round((pl.connCount/pl.totalCount)*100)}%`,height:"100%",borderRadius:2,background:sc,transition:"width .5s"}}/>',
    '                        </div>',
    '                      )}',
    '                      <div style={{width:8,height:8,borderRadius:"50%",background:sc,boxShadow:`0 0 6px ${sc}70`,animation:pl.status==="healthy"?"pulse 2s infinite":"none"}}/>',
  ].join('\r\n'),
  '#11 platform pill mini-bar'
);

// Write
fs.writeFileSync(filePath + '.bak_3feat', raw, 'utf8');
fs.writeFileSync(filePath, content, 'utf8');

const vLines = content.split('\r\n');
console.log('\n--- Verification ---');
console.log('Lines:', vLines.length);
console.log('#7:', content.includes('s.status==="error" || (s.total_hosts>0'));
console.log('#1a:', content.includes('const [availTags'));
console.log('#1b:', content.includes('fetchProjectUtilization(vcId)'));
console.log('#1c:', content.includes('VM Tags'));
console.log('#1d:', content.includes('tags:selTags'));
console.log('#11 heatmap:', content.includes('Cross-Platform Resource Heatmap'));
console.log('#11 mini-bar:', content.includes('pl.connCount/pl.totalCount'));
console.log('DONE');
