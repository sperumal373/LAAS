const fs = require("fs");
const path = "C:\\caas-dashboard\\frontend\\src\\App.jsx";
const lines = fs.readFileSync(path, "utf8").split("\n");

// ── Fix 1: EMPTY defaults vendor to Pure Storage ──────────────────────────
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('const EMPTY={vendor:"",name:"",ip:""')) {
    lines[i] = '  const EMPTY={vendor:"Pure Storage",name:"",ip:"",user:"",pass:"",api_token:"",port:"",site:"dc",capacity_tb:""};';
    console.log("Fix 1: EMPTY vendor defaulted to Pure Storage at line", i+1); break;
  }
}

// ── Fix 2: Simplify handleTest validation ────────────────────────────────
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('if(!form.vendor){setFormErr("Please select a vendor.")')) {
    // Remove vendor check, replace with clean validation block
    lines[i] = '    if(!form.name.trim()){setFormErr("Array name is required.");return;}';
    // Remove next stale lines (name check, ip check, user check, pass check, pure check)
    let j = i + 1;
    let removed = 0;
    while (removed < 5 && j < lines.length) {
      const l = lines[j].trim();
      if (l.startsWith('if(!form.name') || l.startsWith('if(!form.ip') ||
          l.startsWith('if(!form.user') || l.startsWith('if(!form.pass') ||
          l.startsWith('if(form.vendor==="Pure Storage"')) {
        lines.splice(j, 1); removed++;
      } else { break; }
    }
    // Insert clean replacements after name check
    lines.splice(i+1, 0,
      '    if(!form.ip.trim()){setFormErr("Management IP is required.");return;}',
      '    if(!form.api_token.trim()){setFormErr("API Token is required.");return;}'
    );
    console.log("Fix 2: Simplified validation at line", i+1); break;
  }
}

// ── Fix 3: Replace entire form section ───────────────────────────────────
// Find {step==="form"&&( start and the matching )} to replace with clean form
let formStart = -1, braceDepth = 0, formEnd = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('{step==="form"&&(') && lines[i].includes('{/*') === false) {
    formStart = i; break;
  }
}
if (formStart === -1) {
  // try alternate
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === '{step==="form"&&(' || lines[i].includes('{step==="form"&&(')) {
      formStart = i; break;
    }
  }
}
console.log("Form section starts at line", formStart + 1);

// Find the closing )} that ends the form block by tracking JSX parens
if (formStart !== -1) {
  let depth = 0;
  for (let i = formStart; i < formStart + 300; i++) {
    for (const ch of lines[i]) {
      if (ch === '(') depth++;
      if (ch === ')') { depth--; if (depth === 0 && i > formStart) { formEnd = i; break; } }
    }
    if (formEnd !== -1) break;
  }
}
console.log("Form section ends at line", formEnd + 1);

if (formStart !== -1 && formEnd !== -1) {
  const newForm = [
    `              {/* ── FORM ── */}`,
    `              {step==="form"&&(`,
    `                <div style={{display:"flex",flexDirection:"column",gap:16}}>`,
    `                  {/* Pure Storage badge */}`,
    `                  <div style={{display:"flex",alignItems:"center",gap:10,padding:"10px 14px",borderRadius:9,background:"#f9731610",border:"1px solid #f9731630"}}>`,
    `                    <span style={{fontSize:22}}>🟠</span>`,
    `                    <div>`,
    `                      <div style={{fontWeight:800,fontSize:12,color:"#f97316"}}>Pure Storage FlashArray</div>`,
    `                      <div style={{fontSize:10,color:p.textMute,marginTop:1}}>REST API v2 — token authentication</div>`,
    `                    </div>`,
    `                  </div>`,
    `                  <div>`,
    `                    <label style={labelStyle}>Array Name <span style={{color:"#ef4444"}}>*</span></label>`,
    `                    <input style={inputStyle} placeholder="e.g.  FlashArray-Prod-01" value={form.name} onChange={e=>setF("name",e.target.value)}`,
    `                      onFocus={e=>e.target.style.borderColor="#f97316"} onBlur={e=>e.target.style.borderColor=p.border}/>`,
    `                  </div>`,
    `                  <div>`,
    `                    <label style={labelStyle}>Management IP / Hostname <span style={{color:"#ef4444"}}>*</span></label>`,
    `                    <input style={inputStyle} placeholder="e.g.  192.168.10.50  or  flasharray.mgmt.local" value={form.ip}`,
    `                      onChange={e=>setF("ip",e.target.value.replace(/^https?:\\/\\//i,"").replace(/\\/+$/,""))}`,
    `                      onFocus={e=>e.target.style.borderColor="#f97316"} onBlur={e=>e.target.style.borderColor=p.border}/>`,
    `                  </div>`,
    `                  <div>`,
    `                    <label style={labelStyle}>API Token <span style={{color:"#ef4444"}}>*</span></label>`,
    `                    <input style={{...inputStyle,fontFamily:"monospace",letterSpacing:"0.3px"}}`,
    `                      placeholder="T-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"`,
    `                      value={form.api_token} onChange={e=>setF("api_token",e.target.value.trim())}`,
    `                      onFocus={e=>e.target.style.borderColor="#f97316"} onBlur={e=>e.target.style.borderColor=p.border}/>`,
    `                    <div style={{fontSize:9,color:p.textMute,marginTop:4,lineHeight:1.6}}>`,
    `                      FlashArray GUI → top-right username → <strong style={{color:p.text}}>API Tokens</strong> → Create API Token`,
    `                    </div>`,
    `                  </div>`,
    `                  <div style={{borderTop:\`1px solid \${p.border}\`,paddingTop:12}}>`,
    `                    <div style={{fontSize:9,color:p.textMute,fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:10}}>Optional</div>`,
    `                    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>`,
    `                      <div>`,
    `                        <label style={labelStyle}>Port</label>`,
    `                        <input style={inputStyle} placeholder="443" value={form.port} onChange={e=>setF("port",e.target.value)}`,
    `                          onFocus={e=>e.target.style.borderColor="#f97316"} onBlur={e=>e.target.style.borderColor=p.border}/>`,
    `                      </div>`,
    `                      <div>`,
    `                        <label style={labelStyle}>Site</label>`,
    `                        <select style={{...inputStyle,cursor:"pointer"}} value={form.site} onChange={e=>setF("site",e.target.value)}>`,
    `                          <option value="dc">Primary DC</option>`,
    `                          <option value="dr">DR Site</option>`,
    `                          <option value="other">Other</option>`,
    `                        </select>`,
    `                      </div>`,
    `                      <div>`,
    `                        <label style={labelStyle}>Capacity (TB)</label>`,
    `                        <input style={inputStyle} type="number" placeholder="e.g. 500" value={form.capacity_tb} onChange={e=>setF("capacity_tb",e.target.value)}`,
    `                          onFocus={e=>e.target.style.borderColor="#f97316"} onBlur={e=>e.target.style.borderColor=p.border}/>`,
    `                      </div>`,
    `                    </div>`,
    `                  </div>`,
    `                  {formErr&&<div style={{padding:"8px 12px",borderRadius:7,background:"#ef444412",border:"1px solid #ef444430",fontSize:11,color:"#ef4444"}}>{formErr}</div>}`,
    `                  <div style={{display:"flex",gap:10}}>`,
    `                    <button onClick={closeModal} style={{flex:1,padding:"9px",borderRadius:8,border:\`1px solid \${p.border}\`,background:"none",color:p.textMute,fontSize:12,cursor:"pointer",fontWeight:600}}>Cancel</button>`,
    `                    <button onClick={handleTest} style={{flex:2,padding:"9px",borderRadius:8,border:"none",background:"linear-gradient(90deg,#f97316,#ea580c)",color:"#fff",fontSize:12,cursor:"pointer",fontWeight:700}}>Test Connection</button>`,
    `                  </div>`,
    `                </div>`,
    `              )}`,
  ];

  // Replace lines from formStart comment line (one before) to formEnd
  const commentLine = formStart > 0 && lines[formStart-1].includes('FORM') ? formStart-1 : formStart;
  lines.splice(commentLine, formEnd - commentLine + 1, ...newForm);
  console.log("Fix 3: Form section replaced with Pure Storage-only form");
}

fs.writeFileSync(path, lines.join("\n"), "utf8");
console.log("All fixes applied. Saved.");
