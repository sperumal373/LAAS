const fs = require("fs");
const path = "C:\\caas-dashboard\\frontend\\src\\App.jsx";
const lines = fs.readFileSync(path, "utf8").split("\n");
let fixed = 0;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes("port:form.port.trim(), username:form.user.trim(), password:form.pass.trim()")) {
    const next = lines[i+1] ? lines[i+1].trim() : "";
    const prev = lines[i-1] ? lines[i-1] : "";
    if (next === "});" && prev.includes("testStorageConnection")) {
      lines[i] = lines[i].replace("password:form.pass.trim()", "password:form.pass.trim(), api_token:(form.api_token||\"\").trim()");
      console.log("Fix 1 testStorageConnection line " + (i+1));
      fixed++;
    } else if (lines[i+1] && lines[i+1].includes("site:form.site")) {
      lines[i] = lines[i].replace("password:form.pass.trim()", "password:form.pass.trim(), api_token:(form.api_token||\"\").trim()");
      console.log("Fix 2 createStorageArray line " + (i+1));
      fixed++;
    }
  }
}
if (!fixed) { console.error("No matches found"); process.exit(1); }
fs.writeFileSync(path, lines.join("\n"), "utf8");
console.log("Applied " + fixed + " fix(es). Saved.");
