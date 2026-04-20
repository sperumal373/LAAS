const fs=require("fs");
const f="C:\\caas-dashboard\\frontend\\src\\App.jsx";
const lines=fs.readFileSync(f,"utf8").split("\n");
let fixed=0;
for(let i=0;i<lines.length;i++){
  const noToken=!lines[i].includes("api_token");
  const hasPass=lines[i].includes("port:form.port.trim(), username:form.user.trim(), password:form.pass.trim()");
  const nextClose=lines[i+1]&&lines[i+1].trim()==="});";
  if(hasPass&&noToken&&nextClose){
    lines[i]=lines[i].replace("password:form.pass.trim()","password:form.pass.trim(), api_token:(form.api_token||\"\").trim()");
    console.log("Fixed testStorageConnection at line "+(i+1));
    fixed++;
  }
}
if(!fixed){console.error("Not found");process.exit(1);}
fs.writeFileSync(f,lines.join("\n"),"utf8");
console.log("Saved "+fixed+" fix(es)");
