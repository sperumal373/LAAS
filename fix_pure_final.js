const fs = require("fs");
const path = "C:\\caas-dashboard\\frontend\\src\\App.jsx";
const lines = fs.readFileSync(path, "utf8").split("\n");
let fixes = 0;

for (let i = 0; i < lines.length; i++) {

  // Insert api_token required check before setFormErr("")
  if (lines[i].includes('setFormErr("");setStep("testing");') && !lines[i-1].includes("Pure Storage")) {
    lines.splice(i, 0, '    if(form.vendor==="Pure Storage"&&!form.api_token.trim()){setFormErr("API Token is required for Pure Storage.");return;}');
    console.log("Fix 1: api_token required check inserted at line", i+1); fixes++; i++;
  }

  // Username label: show "(optional for Pure)" when Pure selected
  if (lines[i].includes('<label style={labelStyle}>Username') && lines[i].includes('required')) {
    lines[i] = lines[i].replace(
      '<label style={labelStyle}>Username <span style={{color:"#ef4444"}}>*</span></label>',
      '<label style={labelStyle}>Username {form.vendor==="Pure Storage"?<span style={{color:p.textMute,fontWeight:400}}>(optional  token auth)</span>:<span style={{color:"#ef4444"}}>*</span>}</label>'
    );
    console.log("Fix 2: username label updated at line", i+1); fixes++;
  }

  // Password label: show "(optional for Pure)" when Pure selected  
  if (lines[i].includes('<label style={labelStyle}>Password') && lines[i].includes('required')) {
    lines[i] = lines[i].replace(
      '<label style={labelStyle}>Password <span style={{color:"#ef4444"}}>*</span></label>',
      '<label style={labelStyle}>Password {form.vendor==="Pure Storage"?<span style={{color:p.textMute,fontWeight:400}}>(optional  token auth)</span>:<span style={{color:"#ef4444"}}>*</span>}</label>'
    );
    console.log("Fix 3: password label updated at line", i+1); fixes++;
  }
}

fs.writeFileSync(path, lines.join("\n"), "utf8");
console.log("Applied", fixes, "fixes. Saved.");
