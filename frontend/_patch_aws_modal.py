"""
Patch AWSPage in App.jsx:
1. Add SSO state variables + functions after existing ones
2. Replace the credentials modal with a tabbed version (Manual | SSO)
3. Import the 4 new SSO api functions at the top of the file
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

APP = 'frontend/src/App.jsx'
content = open(APP, encoding='utf-8').read()

# ── Guard ──────────────────────────────────────────────────────────────────
if 'ssoTab' in content:
    print("Already patched — skipping")
    exit(0)

# ── 1. Add SSO imports to api.js import line in App.jsx ───────────────────
content = content.replace(
    'fetchAWSSubnets,',
    'fetchAWSSubnets,\n  fetchAWSSSOStatus, initAWSSSO, pollAWSSSO, refreshAWSSSO,',
    1
)

# ── 2. Add new state vars + SSO functions right after `actionMsg` state ────
OLD_STATE_END = '  const [actionMsg,   setActionMsg]   = useState(null);\n\n  useEffect(() => { loadStatus(); }, []);'
NEW_STATE_END = '''  const [actionMsg,   setActionMsg]   = useState(null);

  // SSO state
  const [ssoTab,       setSsoTab]       = useState("manual"); // "manual" | "sso"
  const [ssoStatus,    setSsoStatus]    = useState(null);
  const [ssoStartUrl,  setSsoStartUrl]  = useState("https://d-9f6719d514.awsapps.com/start/#");
  const [ssoRegion,    setSsoRegion]    = useState("ap-south-1");
  const [ssoAccountId, setSsoAccountId] = useState("986182225774");
  const [ssoRoleName,  setSsoRoleName]  = useState("");
  const [ssoInitResult,setSsoInitResult]= useState(null);  // {verification_uri_complete, user_code, expires_in}
  const [ssoPolling,   setSsoPolling]   = useState(false);
  const [ssoPollTimer, setSsoPollTimer] = useState(null);
  const [ssoMsg,       setSsoMsg]       = useState(null);

  useEffect(() => { loadStatus(); loadSSOStatus(); }, []);

  async function loadSSOStatus() {
    try { const s = await fetchAWSSSOStatus(); setSsoStatus(s); } catch(e) {}
  }

  async function handleSSOInit() {
    setSsoMsg(null); setSsoInitResult(null);
    try {
      const r = await initAWSSSO({ start_url: ssoStartUrl, sso_region: ssoRegion, account_id: ssoAccountId, role_name: ssoRoleName });
      if (r.success) {
        setSsoInitResult(r);
        setSsoMsg({ ok: true, text: "✅ Open the link below in your browser and approve the login." });
        setSsoPolling(true);
        // Start polling every 5 seconds
        const t = setInterval(async () => {
          try {
            const pr = await pollAWSSSO();
            if (pr.success) {
              clearInterval(t); setSsoPollTimer(null); setSsoPolling(false);
              setSsoMsg({ ok: true, text: "✅ SSO connected! Credentials refreshed automatically every 20 minutes." });
              setSsoInitResult(null);
              await loadSSOStatus(); await loadStatus();
            } else if (!pr.pending) {
              clearInterval(t); setSsoPollTimer(null); setSsoPolling(false);
              setSsoMsg({ ok: false, text: pr.error || "Authorization failed." });
            }
          } catch(e) { /* keep polling */ }
        }, 5000);
        setSsoPollTimer(t);
      } else {
        setSsoMsg({ ok: false, text: r.error || "Failed to initiate SSO." });
      }
    } catch(e) { setSsoMsg({ ok: false, text: String(e) }); }
  }

  function cancelSSO() {
    if (ssoPollTimer) { clearInterval(ssoPollTimer); setSsoPollTimer(null); }
    setSsoPolling(false); setSsoInitResult(null); setSsoMsg(null);
  }

  async function handleManualSSORefresh() {
    setSsoMsg(null);
    try {
      const r = await refreshAWSSSO();
      setSsoMsg(r.success ? { ok: true, text: `✅ Refreshed — key ${r.access_key}, expires ${r.expiry||"unknown"}` } : { ok: false, text: r.error });
      await loadSSOStatus(); await loadStatus();
    } catch(e) { setSsoMsg({ ok: false, text: String(e) }); }
  }'''

if OLD_STATE_END not in content:
    print("ERROR: could not find state end anchor")
    exit(1)
content = content.replace(OLD_STATE_END, NEW_STATE_END, 1)
print("Step 2: state vars inserted")

# ── 3. Replace the credentials modal with the tabbed version ──────────────
OLD_MODAL_START = '      {/* Credentials Modal */}\n      {credModal && ('
OLD_MODAL_END   = '      )}\n\n      {/* Not configured yet */}'

start_idx = content.find(OLD_MODAL_START)
end_marker = '      )}\n\n      {/* Not configured yet */}'
end_idx   = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"ERROR: modal markers not found  start={start_idx} end={end_idx}")
    exit(1)

NEW_MODAL = '''      {/* Credentials Modal — Manual keys OR SSO */}
      {credModal && (
        <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.65)",zIndex:9999,display:"flex",alignItems:"center",justifyContent:"center"}}>
          <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:14,padding:28,width:500,boxShadow:"0 20px 60px #0008",maxHeight:"90vh",overflowY:"auto"}}>
            <div style={{fontSize:16,fontWeight:700,color:p.text,marginBottom:14}}>🔑 AWS Credentials</div>

            {/* Mode tabs */}
            <div style={{display:"flex",gap:0,marginBottom:18,borderRadius:8,overflow:"hidden",border:`1px solid ${p.border}`}}>
              {[{id:"manual",label:"🔑 Manual Keys"},{id:"sso",label:"☁️ IAM Identity Center (SSO)"}].map(t=>(
                <button key={t.id} onClick={()=>{setSsoTab(t.id);setSsoMsg(null);}}
                  style={{flex:1,padding:"7px 0",border:"none",cursor:"pointer",fontSize:12,fontWeight:ssoTab===t.id?700:400,
                    background:ssoTab===t.id?AWS_ORANGE:"transparent",color:ssoTab===t.id?"#000":p.textMute}}>
                  {t.label}
                </button>
              ))}
            </div>

            {/* ── Manual tab ── */}
            {ssoTab==="manual" && (<>
              <div style={{fontSize:12,color:p.textMute,marginBottom:14}}>
                Enter your AWS Access Key ID and Secret Access Key.<br/>
                For temporary/SSO keys, paste the Session Token too.
              </div>
              {[
                {label:"Access Key ID",           val:accessKey,    set:setAccessKey,    ph:"AKIA…",                  type:"text"},
                {label:"Secret Access Key",        val:secretKey,    set:setSecretKey,    ph:"Your secret key",        type:"password"},
                {label:"Session Token (optional)", val:sessionToken, set:setSessionToken, ph:"IQoJb3JpZ2… (leave blank for permanent keys)", type:"password"},
                {label:"Default Region",           val:region,       set:setRegion,       ph:"ap-south-1",             type:"text"},
              ].map(f=>(
                <div key={f.label} style={{marginBottom:12}}>
                  <div style={{fontSize:11,fontWeight:600,color:p.textMute,marginBottom:4}}>{f.label}</div>
                  <input type={f.type} value={f.val} onChange={e=>f.set(e.target.value)} placeholder={f.ph}
                    style={{width:"100%",padding:"7px 10px",borderRadius:6,border:`1px solid ${p.border}`,background:p.card,color:p.text,fontSize:12,boxSizing:"border-box"}}/>
                </div>
              ))}
              {saveMsg && <div style={{padding:"8px 12px",borderRadius:6,background:saveMsg.ok?"#10b98122":"#ef444422",border:`1px solid ${saveMsg.ok?"#10b981":"#ef4444"}`,fontSize:12,color:saveMsg.ok?"#10b981":"#ef4444",marginBottom:10}}>{saveMsg.text}</div>}
              <div style={{display:"flex",gap:8,justifyContent:"flex-end",marginTop:6}}>
                <button onClick={()=>{setCredModal(false);setSaveMsg(null);}} style={{background:"transparent",border:`1px solid ${p.border}`,color:p.textMute,borderRadius:6,padding:"6px 14px",fontSize:12,cursor:"pointer"}}>Cancel</button>
                <button onClick={handleSaveCreds} disabled={saving||!accessKey||!secretKey}
                  style={{background:AWS_ORANGE,border:"none",color:"#000",borderRadius:6,padding:"6px 16px",fontSize:12,fontWeight:700,cursor:"pointer",opacity:saving||!accessKey||!secretKey?0.5:1}}>
                  {saving?"Saving…":"Save & Connect"}
                </button>
              </div>
            </>)}

            {/* ── SSO tab ── */}
            {ssoTab==="sso" && (<>
              <div style={{fontSize:12,color:p.textMute,marginBottom:14}}>
                Connect via <b>AWS IAM Identity Center</b>. Credentials auto-refresh every 20 minutes —
                no more manual token copy-paste.
              </div>

              {/* SSO current status pill */}
              {ssoStatus?.sso_configured && (
                <div style={{marginBottom:14,padding:"8px 12px",borderRadius:8,background:ssoStatus.token_valid?"#10b98118":"#f59e0b18",border:`1px solid ${ssoStatus.token_valid?"#10b981":"#f59e0b"}`,fontSize:12}}>
                  <div style={{fontWeight:700,color:ssoStatus.token_valid?"#10b981":"#f59e0b"}}>
                    {ssoStatus.token_valid?"✅ SSO Active":"⚠ SSO Configured — Token may need renewal"}
                  </div>
                  <div style={{color:p.textMute,marginTop:4}}>
                    Account: {ssoStatus.account_id} · Role: {ssoStatus.role_name}
                    {ssoStatus.cred_expires_in_sec!=null && (
                      <span style={{marginLeft:8,color:ssoStatus.cred_expires_in_sec<300?"#ef4444":"#10b981"}}>
                        · Creds expire in {Math.max(0,Math.round(ssoStatus.cred_expires_in_sec/60))} min
                      </span>
                    )}
                    {ssoStatus.last_refresh && <span style={{marginLeft:8}}>· Last refresh: {ssoStatus.last_refresh.slice(11,19)} UTC</span>}
                  </div>
                  <button onClick={handleManualSSORefresh} style={{marginTop:8,background:"transparent",border:`1px solid ${p.border}`,color:p.textMute,borderRadius:4,padding:"3px 10px",fontSize:11,cursor:"pointer"}}>
                    ⟳ Force Refresh Now
                  </button>
                </div>
              )}

              {[
                {label:"SSO Start URL",  val:ssoStartUrl,  set:setSsoStartUrl,  ph:"https://d-xxxxxxxxxx.awsapps.com/start/#"},
                {label:"SSO Region",     val:ssoRegion,    set:setSsoRegion,    ph:"ap-south-1"},
                {label:"Account ID",     val:ssoAccountId, set:setSsoAccountId, ph:"123456789012"},
                {label:"Role / Permission Set Name", val:ssoRoleName, set:setSsoRoleName, ph:"AdministratorAccess"},
              ].map(f=>(
                <div key={f.label} style={{marginBottom:12}}>
                  <div style={{fontSize:11,fontWeight:600,color:p.textMute,marginBottom:4}}>{f.label}</div>
                  <input value={f.val} onChange={e=>f.set(e.target.value)} placeholder={f.ph}
                    style={{width:"100%",padding:"7px 10px",borderRadius:6,border:`1px solid ${p.border}`,background:p.card,color:p.text,fontSize:12,boxSizing:"border-box"}}/>
                </div>
              ))}

              {/* Verification link block */}
              {ssoInitResult && (
                <div style={{marginBottom:14,padding:"12px 14px",borderRadius:8,background:"#3b82f618",border:"1px solid #3b82f6"}}>
                  <div style={{fontWeight:700,color:"#60a5fa",marginBottom:6,fontSize:12}}>
                    🌐 Step 2 — Open this link in your browser and approve:
                  </div>
                  <a href={ssoInitResult.verification_uri_complete} target="_blank" rel="noreferrer"
                    style={{color:"#60a5fa",fontSize:11,wordBreak:"break-all",display:"block",marginBottom:8}}>
                    {ssoInitResult.verification_uri_complete}
                  </a>
                  {ssoInitResult.user_code && (
                    <div style={{fontSize:13,fontWeight:800,color:"#f59e0b",letterSpacing:2}}>
                      Code: {ssoInitResult.user_code}
                    </div>
                  )}
                  <div style={{fontSize:11,color:p.textMute,marginTop:6}}>
                    {ssoPolling ? "⟳ Waiting for your browser approval…" : ""}
                    {" "}Expires in ~{Math.round((ssoInitResult.expires_in||600)/60)} min.
                  </div>
                </div>
              )}

              {ssoMsg && <div style={{padding:"8px 12px",borderRadius:6,background:ssoMsg.ok?"#10b98122":"#ef444422",border:`1px solid ${ssoMsg.ok?"#10b981":"#ef4444"}`,fontSize:12,color:ssoMsg.ok?"#10b981":"#ef4444",marginBottom:10}}>{ssoMsg.text}</div>}

              <div style={{display:"flex",gap:8,justifyContent:"flex-end",marginTop:6,flexWrap:"wrap"}}>
                {ssoPolling && <button onClick={cancelSSO} style={{background:"transparent",border:`1px solid #ef4444`,color:"#ef4444",borderRadius:6,padding:"6px 14px",fontSize:12,cursor:"pointer"}}>✕ Cancel</button>}
                <button onClick={()=>{setCredModal(false);setSsoMsg(null);cancelSSO();}} style={{background:"transparent",border:`1px solid ${p.border}`,color:p.textMute,borderRadius:6,padding:"6px 14px",fontSize:12,cursor:"pointer"}}>Close</button>
                {!ssoPolling && (
                  <button onClick={handleSSOInit} disabled={!ssoStartUrl||!ssoAccountId||!ssoRoleName}
                    style={{background:AWS_ORANGE,border:"none",color:"#000",borderRadius:6,padding:"6px 16px",fontSize:12,fontWeight:700,cursor:"pointer",opacity:!ssoStartUrl||!ssoAccountId||!ssoRoleName?0.5:1}}>
                    ☁️ Connect via SSO
                  </button>
                )}
              </div>
            </>)}
          </div>
        </div>
      )}

      {/* Not configured yet */}'''

content = content[:start_idx] + NEW_MODAL + content[end_idx + len(end_marker):]
print("Step 3: modal replaced")

# ── 4. Add ssoStatus indicator to header row (next to refresh/configure btns) ─
# Update the header "not configured" empty state to also mention SSO option
OLD_NOT_CFG_TEXT = 'Enter your AWS Access Key ID and Secret Access Key to discover EC2 instances, S3 buckets, RDS databases, VPCs, and cos'
if OLD_NOT_CFG_TEXT in content:
    # find full text node line and extend it
    pass  # ok, already handled by modal

# ── 5. Write file ──────────────────────────────────────────────────────────
open(APP, 'w', encoding='utf-8').write(content)
print("App.jsx written successfully")

# Verify key strings
check_content = open(APP, encoding='utf-8').read()
for key in ['ssoTab', 'ssoStatus', 'handleSSOInit', 'pollAWSSSO', 'fetchAWSSSOStatus', 'initAWSSSO']:
    print(f"  {key}: {'OK' if key in check_content else 'MISSING'}")
