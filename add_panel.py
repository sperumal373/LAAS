PATH = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
with open(PATH, 'rb') as f:
    text = f.read().decode('utf-8')

marker = '      {/* ======================== PLANS TAB ========================= */}'
if marker not in text:
    print('PLANS TAB marker not found!')
    import sys; sys.exit(1)

panel = r'''      {/* POST-MIGRATION TASKS PANEL */}
      {ptGroupId && (
        <div style={{ position: 'fixed', top: 0, right: 0, width: 520, height: '100vh', background: p.surface, boxShadow: '-4px 0 30px rgba(0,0,0,.25)', zIndex: 1000, display: 'flex', flexDirection: 'column', borderLeft: '3px solid ' + p.accent }}>
          <div style={{ padding: '18px 22px', borderBottom: '1px solid ' + p.border, display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 22 }}>{'\u2699\ufe0f'}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 16, color: p.text }}>Post-Migration Tasks</div>
              <div style={{ fontSize: 11.5, color: p.textMute }}>Group #{ptGroupId}</div>
            </div>
            <button onClick={() => setPtGroupId(null)} style={{ background: 'none', border: 'none', color: p.textMute, fontSize: 22, cursor: 'pointer', fontWeight: 700 }}>&times;</button>
          </div>
          {ptLoading ? <div style={{ padding: 40, textAlign: 'center' }}><LoadDots p={p} /></div> : (
            <div style={{ flex: 1, overflow: 'auto', padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                {[['playbook', 'Ansible Playbook'], ['custom', 'Custom Script']].map(([val, label]) => (
                  <button key={val} onClick={() => setPtTaskType(val)}
                    style={{ flex: 1, padding: '10px 14px', borderRadius: 8, border: '1px solid ' + (ptTaskType === val ? p.accent : p.border), background: ptTaskType === val ? p.accent + '18' : 'transparent', color: ptTaskType === val ? p.accent : p.textMute, fontWeight: 700, fontSize: 12.5, cursor: 'pointer' }}>
                    {label}
                  </button>
                ))}
              </div>
              <input value={ptTaskName} onChange={e => setPtTaskName(e.target.value)} placeholder="Task name (e.g. Install Monitoring Agent)"
                style={{ padding: '10px 14px', borderRadius: 8, border: '1px solid ' + p.border, background: p.bg, color: p.text, fontSize: 13, width: '100%', boxSizing: 'border-box' }} />
              {ptTaskType === 'playbook' && (
                <div>
                  <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: 'block' }}>Select Playbook / Job Template</label>
                  <select value={ptSelTemplate} onChange={e => setPtSelTemplate(e.target.value)}
                    style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid ' + p.border, background: p.bg, color: p.text, fontSize: 13 }}>
                    <option value="">-- Select a playbook --</option>
                    {ptPlaybooks.map(pb => (
                      <option key={pb.aap_instance_id + ':' + pb.id} value={pb.aap_instance_id + ':' + pb.id}>
                        {pb.name} ({pb.aap_instance_name || 'AAP'})
                      </option>
                    ))}
                  </select>
                  {ptPlaybooks.length === 0 && <div style={{ fontSize: 11.5, color: '#f59e0b', marginTop: 6 }}>No AAP instances configured.</div>}
                </div>
              )}
              {ptTaskType === 'custom' && (
                <div>
                  <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: 'block' }}>Script (runs on each VM via SSH/WinRM)</label>
                  <textarea value={ptCustomScript} onChange={e => setPtCustomScript(e.target.value)} rows={6}
                    placeholder="# Example: install agent\napt-get update && apt-get install -y agent"
                    style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid ' + p.border, background: p.bg, color: p.text, fontSize: 12, fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box' }} />
                </div>
              )}
              {ptTaskType === 'playbook' && (
                <div>
                  <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: 'block' }}>Extra Variables (JSON, optional)</label>
                  <textarea value={ptExtraVars} onChange={e => setPtExtraVars(e.target.value)} rows={3}
                    placeholder='{"env": "production"}'
                    style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid ' + p.border, background: p.bg, color: p.text, fontSize: 12, fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box' }} />
                </div>
              )}
              <button onClick={runPostTask} disabled={ptRunning}
                style={{ padding: '12px 20px', borderRadius: 8, border: 'none', background: ptRunning ? p.border : '#10b981', color: '#fff', fontWeight: 800, fontSize: 14, cursor: ptRunning ? 'default' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                {ptRunning ? 'Running...' : '\u25b6 Execute on All VMs'}
              </button>
              {ptTasks.length > 0 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: p.text, marginBottom: 10, borderTop: '1px solid ' + p.border, paddingTop: 14 }}>Task History</div>
                  {ptTasks.map(t => {
                    const sc = { running: '#3b82f6', successful: '#10b981', failed: '#ef4444', partial: '#f59e0b', pending: '#6b7280', timeout: '#f59e0b' };
                    const isE = ptExpandedTask === t.id;
                    let res = t.results;
                    if (typeof res === 'string') try { res = JSON.parse(res); } catch { res = {}; }
                    return (
                      <div key={t.id} style={{ background: p.bg, borderRadius: 8, border: '1px solid ' + p.border, marginBottom: 8, overflow: 'hidden' }}>
                        <div onClick={() => { setPtExpandedTask(isE ? null : t.id); if (t.status === 'running') refreshPostTaskStatus(t.id); }}
                          style={{ padding: '10px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: sc[t.status] || '#6b7280', display: 'inline-block' }}></span>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 700, fontSize: 12.5, color: p.text }}>{t.task_name}</div>
                            <div style={{ fontSize: 10.5, color: p.textMute }}>{t.task_type} &middot; {t.triggered_by} &middot; {(t.started_at || '').slice(0,16)}</div>
                          </div>
                          <span style={{ fontSize: 11, fontWeight: 700, color: sc[t.status] || '#6b7280', textTransform: 'uppercase' }}>{t.status}</span>
                        </div>
                        {isE && res && (
                          <div style={{ padding: '8px 14px 12px', borderTop: '1px solid ' + p.border, fontSize: 11.5, color: p.textMute }}>
                            {res.error && <div style={{ color: '#ef4444', marginBottom: 6 }}>Error: {res.error}</div>}
                            {res.aap_job_id && <div>AAP Job ID: {res.aap_job_id}</div>}
                            {(res.vms || []).map((v, i) => (
                              <div key={i} style={{ display: 'flex', gap: 8, padding: '3px 0' }}>
                                <span style={{ fontWeight: 600 }}>{v.name}</span>
                                <span style={{ color: sc[v.status] || '#6b7280' }}>{v.status}</span>
                              </div>
                            ))}
                            {res.output && typeof res.output === 'string' && (
                              <pre style={{ marginTop: 6, padding: 8, background: '#1e1e2e', color: '#a6e3a1', borderRadius: 6, fontSize: 10.5, maxHeight: 150, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{res.output.slice(0, 2000)}</pre>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

'''

text = text.replace(marker, panel + '      ' + marker.lstrip())
print('Panel added!')

with open(PATH, 'wb') as f:
    f.write(text.encode('utf-8'))
print('Saved!')