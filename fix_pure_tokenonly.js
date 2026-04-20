const fs = require("fs");
const path = "C:\\caas-dashboard\\frontend\\src\\App.jsx";
const lines = fs.readFileSync(path, "utf8").split("\n");
let fixes = 0;

for (let i = 0; i < lines.length; i++) {
  // Fix 1: username required validation - make optional for Pure Storage
  if (lines[i].trim() === 'if(!form.user.trim()){setFormErr("Username is required.");return;}') {
    lines[i] = '    if(!form.user.trim()&&form.vendor!=="Pure Storage"){setFormErr("Username is required.");return;}';
    console.log("Fix 1: username optional for Pure Storage at line", i+1); fixes++;
  }

  // Fix 2: password required validation - make optional for Pure Storage
  if (lines[i].trim() === 'if(!form.pass.trim()){setFormErr("Password is required.");return;}') {
    lines[i] = '    if(!form.pass.trim()&&form.vendor!=="Pure Storage"){setFormErr("Password is required.");return;}';
    console.log("Fix 2: password optional for Pure Storage at line", i+1); fixes++;
  }

  // Fix 3: api_token validation - required for Pure Storage
  if (lines[i].includes('if(form.vendor==="Pure Storage"&&!form.api_token.trim())')) {
    lines[i] = '    if(form.vendor==="Pure Storage"&&!form.api_token.trim()){setFormErr("API Token is required for Pure Storage.");return;}';
    console.log("Fix 3: api_token required validation at line", i+1); fixes++;
  }
}

if (fixes === 0) {
  // api_token validation may not exist yet - insert it
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('setFormErr("");setStep("testing");')) {
      lines.splice(i, 0, '    if(form.vendor==="Pure Storage"&&!form.api_token.trim()){setFormErr("API Token is required for Pure Storage.");return;}');
      console.log("Fix 3 inserted: api_token required for Pure Storage at line", i+1); fixes++;
      break;
    }
  }
}

if (fixes < 2) { console.error("Some fixes not applied, only got:", fixes); process.exit(1); }
fs.writeFileSync(path, lines.join("\n"), "utf8");
console.log("Applied", fixes, "fixes. Saved.");
