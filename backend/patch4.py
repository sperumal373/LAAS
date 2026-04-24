f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()

marker = b'</div>\r\n                            )}\r\n                            {actions.length > 0 && ('
assert marker in raw, 'marker not found'

q = b'\x22'  # double quote
lines = [
    b'</div>',
    b'                            )}',
    b'                            {/* MTV Pipeline Stages */}',
    b'                            {plan.target_platform === ' + q + b'openshift' + q + b' && isLive && liveMtvStatus && liveMtvStatus.vms && liveMtvStatus.vms.length > 0 && (',
    b'                              <div style={{ marginBottom: 14, padding: 14, borderRadius: 8, background: `${p.surface}`, border: `1px solid ${p.border}` }}>',
    b'                                <div style={{ fontSize: 13, fontWeight: 800, color: p.text, marginBottom: 10, textTransform: ' + q + b'uppercase' + q + b', letterSpacing: ' + q + b'.5px' + q + b' }}>{' + q + b'\xf0\x9f\x94\x84' + q + b'} MTV Migration Stages</div>',
    b'                                {liveMtvStatus.vms.map((vm, vi) => {',
    b'                                  const MTV_STAGES = [' + q + b'Initialize' + q + b',' + q + b'PreflightInspection' + q + b',' + q + b'DiskTransfer' + q + b',' + q + b'Cutover' + q + b',' + q + b'ImageConversion' + q + b',' + q + b'VirtualMachineCreation' + q + b'];',
    b'                                  const stageMap = {};',
    b'                                  (vm.pipeline || []).forEach(s => { stageMap[s.name] = s; });',
    b'                                  return (',
    b'                                    <div key={vi} style={{ marginBottom: vi < liveMtvStatus.vms.length - 1 ? 12 : 0 }}>',
    b'                                      <div style={{ fontSize: 12.5, fontWeight: 700, color: p.text, marginBottom: 8 }}>{' + q + b'\xf0\x9f\x96\xa5\xef\xb8\x8f' + q + b'} {vm.name || ' + q + b'VM' + q + b'} <span style={{ fontSize: 11, fontWeight: 500, color: p.textMute, marginLeft: 6 }}>Phase: {vm.phase || ' + q + b'Pending' + q + b'}</span></div>',
    b'                                      <div style={{ display: ' + q + b'flex' + q + b', alignItems: ' + q + b'center' + q + b', gap: 0 }}>',
    b'                                        {MTV_STAGES.map((stg, si) => {',
    b'                                          const info = stageMap[stg] || (stg === ' + q + b'DiskTransfer' + q + b' ? stageMap[' + q + b'DiskTransferV2v' + q + b'] || stageMap[' + q + b'DiskAllocation' + q + b'] : null) || {};',
    b'                                          const ph = info.phase || ' + q + b'Pending' + q + b';',
    b'                                          const done = ph === ' + q + b'Completed' + q + b';',
    b'                                          const run = ph === ' + q + b'Running' + q + b' || ph === ' + q + b'InProgress' + q + b';',
    b'                                          const fail = ph === ' + q + b'Failed' + q + b' || ph === ' + q + b'Error' + q + b';',
    b'                                          const clr = done ? ' + q + b'#22c55e' + q + b' : run ? ' + q + b'#3b82f6' + q + b' : fail ? ' + q + b'#ef4444' + q + b' : `${p.textMute}55`;',
    b'                                          const ico = done ? ' + q + b'\\u2714' + q + b' : run ? ' + q + b'\\u23F3' + q + b' : fail ? ' + q + b'\\u2718' + q + b' : ' + q + b'\\u25CB' + q + b';',
    b'                                          const pct = info.total > 0 ? Math.round(info.completed / info.total * 100) : null;',
    b'                                          const lbl = stg.replace(/([A-Z])/g, ' + q + b' $1' + q + b').trim();',
    b'                                          return <Fragment key={stg}>',
    b'                                            <div style={{ display: ' + q + b'flex' + q + b', flexDirection: ' + q + b'column' + q + b', alignItems: ' + q + b'center' + q + b', flex: 1, minWidth: 0 }}>',
    b'                                              <div style={{ width: 30, height: 30, borderRadius: ' + q + b'50%' + q + b', background: !done && !run && !fail ? `${p.textMute}15` : `${clr}18`, display: ' + q + b'flex' + q + b', alignItems: ' + q + b'center' + q + b', justifyContent: ' + q + b'center' + q + b', fontSize: 14, border: `2px solid ${clr}`, boxShadow: run ? `0 0 10px ${clr}44` : ' + q + b'none' + q + b', transition: ' + q + b'all .3s' + q + b', animation: run ? ' + q + b'pulse 2s infinite' + q + b' : ' + q + b'none' + q + b' }}>',
    b'                                                <span style={{ color: clr, fontWeight: 700 }}>{ico}</span>',
    b'                                              </div>',
    b'                                              <div style={{ fontSize: 10, marginTop: 3, color: !done && !run && !fail ? p.textMute : clr, fontWeight: run ? 800 : 600, textAlign: ' + q + b'center' + q + b', lineHeight: 1.2, maxWidth: 80 }}>{lbl}</div>',
    b'                                              {pct !== null && <div style={{ fontSize: 9, color: clr, fontWeight: 700, marginTop: 1 }}>{pct}%</div>}',
    b'                                            </div>',
    b'                                            {si < MTV_STAGES.length - 1 && <div style={{ flex: 0.6, height: 2, borderRadius: 1, background: done ? ' + q + b'#22c55e' + q + b' : `${p.textMute}22`, transition: ' + q + b'background .5s' + q + b', marginBottom: 20 }} />}',
    b'                                          </Fragment>;',
    b'                                        })}',
    b'                                      </div>',
    b'                                    </div>',
    b'                                  );',
    b'                                })}',
    b'                              </div>',
    b'                            )}',
    b'                            {actions.length > 0 && (',
]
comp = b'\r\n'.join(lines)
raw = raw.replace(marker, comp, 1)
open(f, 'wb').write(raw)
print('4 OK - MTV pipeline stages added. Size:', len(raw))