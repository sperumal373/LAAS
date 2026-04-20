const fs = require('fs');
const path = 'C:\\caas-dashboard\\frontend\\src\\App.jsx';
let src = fs.readFileSync(path, 'utf8');

// 1. Add api_token to EMPTY form state
src = src.replace(
  'const EMPTY={vendor:"",name:"",ip:"",user:"",pass:"",port:"",site:"dc",capacity_tb:""};',
  'const EMPTY={vendor:"",name:"",ip:"",user:"",pass:"",api_token:"",port:"",site:"dc",capacity_tb:""};'
);

// 2. Add api_token validation + pass to testStorageConnection
src = src.replace(
  `    if(!form.pass.trim()){setFormErr("Password is required.");return;}
    setFormErr("");setStep("testing");
    const result=await testStorageConnection({
      vendor:form.vendor, ip:form.ip.trim(),
      port:form.port.trim(), username:form.user.trim(), password:form.pass.trim()
    });`,
  `    if(!form.pass.trim()){setFormErr("Password is required.");return;}
    if(form.vendor==="Pure Storage"&&!form.api_token.trim()){setFormErr("API Token is required for Pure Storage.");return;}
    setFormErr("");setStep("testing");
    const result=await testStorageConnection({
      vendor:form.vendor, ip:form.ip.trim(),
      port:form.port.trim(), username:form.user.trim(), password:form.pass.trim(),
      api_token:form.api_token.trim()||undefined
    });`
);

// 3. Pass api_token to createStorageArray
src = src.replace(
  `        username:form.user.trim(), password:form.pass.trim(),
        site:form.site, capacity_tb:form.capacity_tb?parseFloat(form.capacity_tb):0,`,
  `        username:form.user.trim(), password:form.pass.trim(),
        api_token:form.api_token.trim()||undefined,
        site:form.site, capacity_tb:form.capacity_tb?parseFloat(form.capacity_tb):0,`
);

// 4. Add the API Token field after the username/password grid using line-based approach
const lines2 = src.split('\n');
// Find the line with "borderTop" + "Optional" that comes after the password field section
let insertIdx = -1;
for (let i = 0; i < lines2.length; i++) {
  if (lines2[i].includes('borderTop') && lines2[i].includes('paddingTop:12') && lines2[i+1] && lines2[i+1].includes('Optional')) {
    insertIdx = i;
    break;
  }
}
if (insertIdx === -1) {
  console.error('Optional section divider not found');
  process.exit(1);
}
console.log('Inserting API Token field before line', insertIdx + 1);

const apiTokenBlock = [
  '                  {form.vendor==="Pure Storage"&&(',
  '                    <div>',
  '                      <label style={labelStyle}>API Token <span style={{color:"#f97316"}}>*</span></label>',
  '                      <input style={{...inputStyle,fontFamily:"monospace",borderColor:form.vendor==="Pure Storage"&&form.api_token?"#f97316":undefined}}',
  '                        placeholder="e.g.  T-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"',
  '                        value={form.api_token} onChange={e=>setF("api_token",e.target.value)}',
  '                        onFocus={e=>e.target.style.borderColor="#f97316"} onBlur={e=>e.target.style.borderColor=p.border}/>',
  '                      <div style={{fontSize:9,color:p.textMute,marginTop:4,lineHeight:1.5}}>',
  '                        Found in Pure Storage FlashArray UI \u2192 System \u2192 Users \u2192 API Tokens. Used for REST v2 authentication.',
  '                      </div>',
  '                    </div>',
  '                  )}',
];
lines2.splice(insertIdx, 0, ...apiTokenBlock);
src = lines2.join('\n');

fs.writeFileSync(path, src, 'utf8');
console.log('Pure Storage API Token field added to Register Storage Array modal.');
console.log('Saved.');
