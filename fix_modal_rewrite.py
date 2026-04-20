"""
Complete rewrite of VolumeTopologyModal in App.jsx:
- Fix remaining ?? symbols (error icon, Arrow double, comment)
- Better header (vendor badge doesn't overlap text)
- Show only relevant fields per vendor
- Add vCenter/ESXi mapping section
- Clean, readable layout
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

app_path = r'c:\caas-dashboard\frontend\src\App.jsx'
with open(app_path, encoding='utf-8', errors='replace') as f:
    app = f.read()

# Find function boundaries
fn_start = app.find('function VolumeTopologyModal')
fn_end   = app.find('\nfunction ', fn_start + 10)
if fn_end == -1:
    fn_end = app.find('\n// ', fn_start + 10)

print(f"Modal function: chars {fn_start} to {fn_end}")

NEW_MODAL = r"""function VolumeTopologyModal({arrId, arrName, vendor, volume, p, onClose}){
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [err,     setErr]     = useState('');

  useEffect(()=>{
    setLoading(true); setErr(''); setData(null);
    fetchStorageTopology(arrId, volume.name||volume)
      .then(d=>{ setData(d); setLoading(false); })
      .catch(e=>{ setErr(e.message||'Failed to load topology'); setLoading(false); });
  },[arrId, volume]);

  function handlePrint(){
    const el = document.getElementById('vol-topo-print-root');
    if(el) el.style.display='block';
    window.print();
    if(el) el.style.removeProperty('display');
  }

  const vendorColor = {
    'Pure FlashArray':'#FE5000','NetApp':'#8b5cf6','HPE':'#01A982',
    'Dell-EMC':'#007DB8','Dell PowerFlex':'#0076CE','HPE Nimble':'#01A982',
    'Dell PowerScale':'#00857C','Pure Storage':'#f97316'
  }[vendor]||'#3b82f6';

  const hostOsIcon = (os)=>{
    const o=(os||'').toLowerCase();
    if(o.includes('windows')||o.includes('win')) return '[Win]';
    if(o.includes('vmware')||o.includes('esxi')||o.includes('esx')) return '[ESX]';
    if(o.includes('linux')||o.includes('rhel')||o.includes('ubuntu')) return '[Lin]';
    if(o.includes('aix')) return '[AIX]';
    if(o.includes('solaris')) return '[Sol]';
    return '[SRV]';
  };
  const protoColor=(proto)=>{
    const p2=(proto||'').toLowerCase();
    if(p2.includes('fc')||p2.includes('fibre')) return '#f97316';
    if(p2.includes('iscsi')||p2.includes('iqn')) return '#3b82f6';
    if(p2.includes('nvme')) return '#a855f7';
    if(p2.includes('nfs')||p2.includes('smb')||p2.includes('cifs')) return '#10b981';
    return '#6b7280';
  };

  const Card = ({children, style={}})=>(
    <div className="topo-card" style={{borderRadius:10,border:`1px solid ${p.border}`,background:p.panel,padding:'12px 14px',flexShrink:0,...style}}>
      {children}
    </div>
  );
  const SectionTitle = ({t})=>(
    <div style={{fontSize:9,fontWeight:700,textTransform:'uppercase',letterSpacing:'.7px',
      color:p.textMute,marginBottom:8,marginTop:4,paddingBottom:4,borderBottom:`1px solid ${p.border}`}}>
      {t}
    </div>
  );
  const Label = ({t,c})=>(
    <div style={{fontSize:8,fontWeight:700,textTransform:'uppercase',letterSpacing:'.6px',color:c||p.textMute,marginBottom:4}}>{t}</div>
  );
  const KV = ({k,v,mono,color,small})=>(v!=null&&v!==''?
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',fontSize:small?9:10,marginBottom:2,gap:8}}>
      <span style={{color:p.textMute,flexShrink:0}}>{k}</span>
      <span style={{fontWeight:600,color:color||p.text,fontFamily:mono?'monospace':undefined,textAlign:'right',wordBreak:'break-all',maxWidth:'65%'}}>{v}</span>
    </div>:null
  );
  const Badge = ({t,color,bg})=>(
    <span style={{fontSize:9,padding:'2px 7px',borderRadius:5,background:bg||`${color||p.border}15`,
      border:`1px solid ${color||p.border}40`,color:color||p.textMute,whiteSpace:'nowrap'}}>{t}</span>
  );
  const Mono = ({v,color,bg})=>(
    <div style={{display:'flex',alignItems:'center',gap:5,marginBottom:3}}>
      <span style={{fontFamily:'monospace',fontSize:10,color:color||p.text,wordBreak:'break-all',
        background:bg||`${color||p.border}10`,padding:'2px 6px',borderRadius:4,border:`1px solid ${color||p.border}30`}}>{v}</span>
    </div>
  );
  const FlowLine = ({color})=>(
    <div style={{width:2,height:16,background:color||p.border,margin:'0 auto'}}/>
  );
  const FlowArrow = ({label,color})=>(
    <div style={{display:'flex',flexDirection:'column',alignItems:'center'}}>
      <FlowLine color={color}/>
      <div style={{padding:'2px 10px',borderRadius:5,border:`1px solid ${color||p.border}50`,
        background:`${color||p.border}10`,fontSize:8,fontWeight:700,color:color||p.textMute,whiteSpace:'nowrap'}}>
        {label}
      </div>
      <FlowLine color={color}/>
    </div>
  );

  const volName = data?.volume_name || volume?.name || volume || '-';
  const topo    = data?.topology || [];
  const vcmap   = data?.vcenter_mapping || [];

  // Vendor-relevant volume fields
  const showSerial   = !!data?.serial;
  const showWwn      = !!data?.wwn;
  const showNaa      = !!data?.naa_id;
  const showSvm      = !!data?.svm;
  const showPool     = !!data?.pool;
  const showPod      = !!data?.pod;
  const showJunction = !!data?.junction_path;
  const showDr       = data?.data_reduction!=null;
  const showThin     = data?.thin!=null;

  return(
    <div id="vol-topo-print-root" style={{position:'fixed',inset:0,zIndex:10500,background:'rgba(0,0,0,.72)',
      display:'flex',flexDirection:'column',fontFamily:'system-ui,sans-serif'}}>

      {/* ── Header ── */}
      <div className="topo-no-print" style={{background:p.card,borderBottom:`1px solid ${p.border}`,
        padding:'12px 18px',display:'flex',alignItems:'center',gap:12,flexShrink:0,flexWrap:'nowrap',minHeight:56}}>
        {/* Vendor dot */}
        <div style={{width:10,height:10,borderRadius:'50%',background:vendorColor,flexShrink:0,
          boxShadow:`0 0 6px ${vendorColor}80`}}/>
        {/* Title block */}
        <div style={{flex:1,minWidth:0,overflow:'hidden'}}>
          <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',lineHeight:1.4}}>
            <span style={{fontWeight:800,fontSize:14,color:p.text,whiteSpace:'nowrap'}}>Volume Topology</span>
            <span style={{fontFamily:'monospace',fontWeight:700,fontSize:13,color:vendorColor,
              wordBreak:'break-all',maxWidth:320}}>{volName}</span>
            <Badge t={vendor} color={vendorColor}/>
          </div>
          <div style={{fontSize:10,color:p.textMute,marginTop:2,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
            {loading?'Loading topology...' : err?'Error loading topology' :
              `${arrName} \u00b7 ${topo.length} host${topo.length!==1?'s':''} connected${data?.protocol?' \u00b7 '+data.protocol:''}`}
          </div>
        </div>
        {/* Buttons */}
        <div style={{display:'flex',gap:8,flexShrink:0}}>
          {!loading&&!err&&data&&(
            <button onClick={handlePrint} style={{padding:'5px 12px',borderRadius:6,
              border:`1px solid ${vendorColor}60`,background:`${vendorColor}15`,color:vendorColor,
              fontSize:11,fontWeight:600,cursor:'pointer'}}>
              Export PDF
            </button>
          )}
          <button onClick={onClose} style={{padding:'5px 12px',borderRadius:6,
            border:`1px solid ${p.border}`,background:'none',color:p.textMute,
            fontSize:11,cursor:'pointer'}}>
            Close
          </button>
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{flex:1,overflowY:'auto',overflowX:'auto',padding:'20px 24px',background:p.bg}}>

        {loading&&(
          <div style={{textAlign:'center',padding:80,color:p.textMute,fontSize:13}}>
            Building topology map...
          </div>
        )}
        {err&&(
          <div style={{textAlign:'center',padding:60}}>
            <div style={{fontSize:13,color:'#ef4444',padding:'12px 20px',borderRadius:8,
              background:'#ef444415',border:'1px solid #ef444440',display:'inline-block'}}>
              Error: {err}
            </div>
          </div>
        )}

        {!loading&&!err&&data&&(
          <>
            {/* ── Volume Source Card ── */}
            <div style={{display:'flex',justifyContent:'center',marginBottom:12}}>
              <Card style={{minWidth:300,maxWidth:480,border:`2px solid ${vendorColor}60`,
                boxShadow:`0 0 20px ${vendorColor}25`}}>
                <SectionTitle t="Storage Array - Source Volume"/>
                <div style={{fontWeight:900,fontSize:15,color:p.text,fontFamily:'monospace',
                  marginBottom:10,wordBreak:'break-all',color:vendorColor}}>{volName}</div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'2px 16px'}}>
                  <KV k="Array"    v={arrName}/>
                  <KV k="Vendor"   v={vendor}/>
                  <KV k="Size"     v={data.size}/>
                  <KV k="Used"     v={data.used}/>
                  <KV k="Protocol" v={data.protocol} color={protoColor(data.protocol)}/>
                  <KV k="State"    v={data.state}
                    color={data.state==='online'||data.state==='normal'||data.state==='available'?'#10b981':'#f59e0b'}/>
                  {showSerial   && <KV k="Serial"      v={data.serial}       mono/>}
                  {showWwn      && <KV k="WWN"          v={data.wwn}          mono/>}
                  {showPool     && <KV k="Pool / CPG"   v={data.pool}/>}
                  {showSvm      && <KV k="SVM"          v={data.svm}/>}
                  {showPod      && <KV k="Pod"          v={data.pod}/>}
                  {showJunction && <KV k="Junction Path" v={data.junction_path} mono/>}
                  {showDr       && <KV k="Data Reduction" v={data.data_reduction?data.data_reduction+'x':null}/>}
                  {showThin     && <KV k="Thin Prov"   v={data.thin!=null?(data.thin?'Yes':'No'):null}/>}
                </div>
                {showNaa&&(
                  <div style={{marginTop:10,padding:'6px 9px',borderRadius:6,
                    background:`${vendorColor}10`,border:`1px solid ${vendorColor}30`}}>
                    <Label t="ESXi Canonical Name (NAA ID)" c={vendorColor}/>
                    <div style={{fontFamily:'monospace',fontSize:10,color:p.text,wordBreak:'break-all'}}>{data.naa_id}</div>
                  </div>
                )}
              </Card>
            </div>

            {/* ── Replication ── */}
            {data.replication&&data.replication.length>0&&(
              <div style={{marginBottom:16}}>
                <SectionTitle t={`SnapMirror / Replication (${data.replication.length})`}/>
                <div style={{display:'flex',flexWrap:'wrap',gap:12,justifyContent:'center'}}>
                  {data.replication.map((r,ri)=>{
                    const isOut=r.direction==='outbound';
                    const sc=r.state==='snapmirrored'||r.state==='in_sync'?'#10b981':r.state==='uninitialized'?'#f59e0b':'#3b82f6';
                    const peer = r.remote_volume||r.dest_vol||r.source_vol||'-';
                    const peerSvm = r.remote_svm||r.dest_svm||r.source_svm||r.peer_svm||'';
                    return(
                      <div key={ri} style={{display:'flex',alignItems:'center',gap:6}}>
                        {!isOut&&<Card style={{minWidth:160,border:`1px solid #f59e0b50`}}>
                          <Label t="Source" c="#f59e0b"/>
                          <div style={{fontWeight:700,fontSize:10,fontFamily:'monospace',color:p.text,wordBreak:'break-all'}}>{peer}</div>
                          {peerSvm&&<div style={{fontSize:9,color:p.textMute,marginTop:2}}>SVM: {peerSvm}</div>}
                        </Card>}
                        <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:3,minWidth:100}}>
                          <div style={{fontSize:8,fontWeight:700,color:sc,textTransform:'uppercase'}}>
                            {isOut?'Replicates to >>':'<< Replicates from'}
                          </div>
                          <div style={{padding:'4px 10px',borderRadius:7,border:`1px solid ${sc}40`,
                            background:`${sc}08`,textAlign:'center'}}>
                            <div style={{fontSize:8,fontWeight:800,color:sc,textTransform:'uppercase',marginBottom:1}}>
                              {r.policy||'SnapMirror'}
                            </div>
                            <div style={{fontSize:9,color:p.textMute}}>
                              State: <span style={{color:sc,fontWeight:700}}>{r.state||'-'}</span>
                            </div>
                            {r.lag_time&&<div style={{fontSize:9,color:p.textMute}}>Lag: {r.lag_time}</div>}
                            <div style={{fontSize:9,fontWeight:700,
                              color:r.healthy===true?'#10b981':r.healthy===false?'#ef4444':'#f59e0b'}}>
                              {r.healthy===true?'Healthy':r.healthy===false?'Unhealthy':'Unknown'}
                            </div>
                          </div>
                          <div style={{fontSize:12,color:sc}}>{isOut?'>>':'<<'}</div>
                        </div>
                        {isOut&&<Card style={{minWidth:160,border:`1px solid #06b6d450`}}>
                          <Label t="Destination" c="#06b6d4"/>
                          <div style={{fontWeight:700,fontSize:10,fontFamily:'monospace',color:p.text,wordBreak:'break-all'}}>{peer}</div>
                          {peerSvm&&<div style={{fontSize:9,color:p.textMute,marginTop:2}}>SVM: {peerSvm}</div>}
                        </Card>}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Connected Hosts ── */}
            {topo.length===0&&(
              <div style={{textAlign:'center',padding:40,color:p.textMute,fontSize:12,
                border:`1px dashed ${p.border}`,borderRadius:10,marginBottom:16}}>
                No host connections found for this volume.
              </div>
            )}
            {topo.length>0&&(
              <div style={{marginBottom:16}}>
                <SectionTitle t={`Connected Hosts / Initiators (${topo.length})`}/>
                <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:0}}>
                  {topo.map((h,hi)=>{
                    const pc = protoColor(h.protocol||data.protocol);
                    const osIcon = hostOsIcon(h.os_type||h.host_type||'');
                    const iqns = h.iqns||[];
                    const wwns = h.wwns||[];
                    const nqns = h.nqns||[];
                    const hname = h.host_name||h.name||'Unknown Host';
                    const proto = h.protocol||data.protocol||'SAN';
                    const isFC    = proto.toLowerCase().includes('fc')||proto.toLowerCase().includes('fibre')||wwns.length>0;
                    const isISCSI = proto.toLowerCase().includes('iscsi')||iqns.length>0;
                    const isNVMe  = proto.toLowerCase().includes('nvme')||nqns.length>0;
                    const isNFS   = proto.toLowerCase().includes('nfs')||proto.toLowerCase().includes('smb');
                    const isSdc   = !!h.sdc_ip;
                    return(
                      <div key={hi} style={{display:'flex',flexDirection:'column',alignItems:'center',width:'100%'}}>
                        <FlowArrow label={`${proto}${h.lun_id!=null?' \u00b7 LUN '+h.lun_id:''}`} color={pc}/>
                        <Card style={{width:'100%',maxWidth:720,border:`1px solid ${pc}40`,marginBottom:0}}>
                          <div style={{display:'flex',alignItems:'flex-start',gap:12}}>
                            {/* OS badge */}
                            <div style={{width:44,height:44,borderRadius:8,background:`${pc}15`,
                              border:`1px solid ${pc}30`,display:'flex',alignItems:'center',justifyContent:'center',
                              fontSize:10,fontWeight:700,color:pc,flexShrink:0}}>{osIcon}</div>
                            <div style={{flex:1,minWidth:0}}>
                              {/* Host name + badges */}
                              <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:6,flexWrap:'wrap'}}>
                                <span style={{fontWeight:800,fontSize:13,color:p.text}}>{hname}</span>
                                {h.host_group&&<Badge t={h.host_group} color="#6366f1"/>}
                                {h.host_set&&<Badge t={'Set: '+h.host_set} color="#6366f1"/>}
                                {(h.os_type||h.host_type)&&<Badge t={h.os_type||h.host_type} color={pc}/>}
                                {h.protocol&&<Badge t={h.protocol} color={pc}/>}
                                {h.active!=null&&<Badge t={h.active?'Active':'Inactive'}
                                  color={h.active?'#10b981':'#ef4444'}/>}
                              </div>
                              {/* Relevant KV fields — only show non-empty */}
                              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))',gap:'2px 16px'}}>
                                {h.lun_id!=null&&<KV k="LUN ID"     v={String(h.lun_id)} mono color={pc}/>}
                                {h.volume_wwn&&  <KV k="Volume WWN" v={h.volume_wwn}     mono/>}
                                {h.port&&        <KV k="Array Port" v={h.port}           mono/>}
                                {isSdc&&h.sdc_ip&&<KV k="SDC IP"   v={h.sdc_ip}/>}
                                {isSdc&&h.sdc_os&&<KV k="SDC OS"   v={h.sdc_os}/>}
                                {h.chap_enabled&&<KV k="CHAP"      v="Enabled"/>}
                              </div>
                              {/* iSCSI IQNs */}
                              {isISCSI&&iqns.length>0&&(
                                <div style={{marginTop:8}}>
                                  <Label t={`iSCSI IQN${iqns.length>1?'s':''} (${iqns.length})`} c="#3b82f6"/>
                                  <div style={{display:'flex',flexDirection:'column',gap:3}}>
                                    {iqns.map((iqn,ii)=><Mono key={ii} v={iqn} color="#3b82f6"/>)}
                                  </div>
                                </div>
                              )}
                              {/* FC WWNs */}
                              {isFC&&wwns.length>0&&(
                                <div style={{marginTop:8}}>
                                  <Label t={`FC WWN${wwns.length>1?'s':''} (${wwns.length})`} c="#f97316"/>
                                  <div style={{display:'flex',flexWrap:'wrap',gap:4}}>
                                    {wwns.map((wwn,wi)=>(
                                      <span key={wi} style={{fontFamily:'monospace',fontSize:10,padding:'2px 7px',
                                        borderRadius:5,background:'#f9731615',border:'1px solid #f9731640',color:p.text}}>
                                        <span style={{fontSize:8,fontWeight:800,color:'#f97316',marginRight:4}}>WWN</span>{wwn}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {/* NVMe NQNs */}
                              {isNVMe&&nqns.length>0&&(
                                <div style={{marginTop:8}}>
                                  <Label t={`NVMe NQN${nqns.length>1?'s':''} (${nqns.length})`} c="#a855f7"/>
                                  <div style={{display:'flex',flexDirection:'column',gap:3}}>
                                    {nqns.map((nqn,ni)=><Mono key={ni} v={nqn} color="#a855f7"/>)}
                                  </div>
                                </div>
                              )}
                              {/* iGroup initiators (NetApp) */}
                              {(h.initiators||[]).length>0&&(
                                <div style={{marginTop:8}}>
                                  <Label t={`Initiators in iGroup (${h.initiators.length})`} c="#8b5cf6"/>
                                  <div style={{display:'flex',flexDirection:'column',gap:2}}>
                                    {h.initiators.map((ini,ii)=><Mono key={ii} v={ini} color="#8b5cf6"/>)}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </Card>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── vCenter / ESXi Mapping ── */}
            {vcmap.length>0&&(
              <div style={{marginBottom:16}}>
                <SectionTitle t={`vCenter / ESXi Mapping (${vcmap.length} host${vcmap.length!==1?'s':''})`}/>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))',gap:10}}>
                  {vcmap.map((vm,vi)=>(
                    <Card key={vi} style={{border:'1px solid #01A98240'}}>
                      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                        <div style={{width:8,height:8,borderRadius:'50%',background:'#01A982'}}/>
                        <span style={{fontWeight:700,fontSize:11,color:p.text}}>{vm.esxi_host}</span>
                        <Badge t="ESXi" color="#01A982"/>
                        <Badge t={vm.vcenter} color="#6b7280"/>
                      </div>
                      {vm.datastores&&vm.datastores.length>0&&(
                        <div style={{marginBottom:6}}>
                          <Label t={`Datastores (${vm.datastores.length})`} c="#01A982"/>
                          {vm.datastores.map((ds,di)=>(
                            <div key={di} style={{display:'flex',justifyContent:'space-between',
                              alignItems:'center',padding:'3px 7px',borderRadius:5,marginBottom:2,
                              background:p.bg,border:`1px solid ${p.border}`}}>
                              <span style={{fontSize:10,fontWeight:600,color:p.text}}>{ds.name}</span>
                              <span style={{fontSize:9,color:p.textMute}}>{ds.type} &nbsp;
                                <span style={{color:p.text}}>{ds.total_gb}GB</span>
                                &nbsp;free: <span style={{color:'#10b981'}}>{ds.free_gb}GB</span>
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {vm.hba_wwpns&&vm.hba_wwpns.length>0&&(
                        <div>
                          <Label t={`HBA WWPNs (${vm.hba_wwpns.length})`} c="#f97316"/>
                          <div style={{display:'flex',flexWrap:'wrap',gap:3}}>
                            {vm.hba_wwpns.slice(0,4).map((wp,wi)=>(
                              <span key={wi} style={{fontFamily:'monospace',fontSize:9,padding:'1px 5px',
                                borderRadius:4,background:'#f9731610',border:'1px solid #f9731630',color:p.text}}>{wp}</span>
                            ))}
                            {vm.hba_wwpns.length>4&&<span style={{fontSize:9,color:p.textMute}}>+{vm.hba_wwpns.length-4} more</span>}
                          </div>
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* ── Storage Ports ── */}
            {data.storage_ports&&data.storage_ports.length>0&&(
              <div style={{marginBottom:16}}>
                <SectionTitle t={`Storage Array Ports (${data.storage_ports.length})`}/>
                <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
                  {data.storage_ports.map((pt,pi)=>{
                    const pc2=protoColor(pt.protocol||'');
                    const isUp=pt.link_state==='up'||pt.link_state==='ready'||pt.link_state==='online';
                    return(
                      <div key={pi} style={{padding:'5px 10px',borderRadius:7,
                        border:`1px solid ${pc2}40`,background:`${pc2}08`,
                        display:'flex',flexDirection:'column',gap:2,minWidth:140}}>
                        <div style={{fontWeight:700,fontSize:10,color:p.text}}>{pt.name}</div>
                        {pt.wwn&&<div style={{fontFamily:'monospace',fontSize:9,color:p.textMute}}>{pt.wwn}</div>}
                        {pt.ip &&<div style={{fontFamily:'monospace',fontSize:9,color:p.textMute}}>{pt.ip}</div>}
                        <div style={{display:'flex',gap:4,marginTop:2}}>
                          <Badge t={pt.protocol||'?'} color={pc2}/>
                          <Badge t={pt.link_state||'?'} color={isUp?'#10b981':'#ef4444'}/>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Legend ── */}
            <div style={{marginTop:16,display:'flex',flexWrap:'wrap',gap:6,justifyContent:'center',fontSize:9,color:p.textMute}}
              className="topo-no-print">
              {[['#3b82f6','iSCSI (IQN)'],['#f97316','Fibre Channel (WWN)'],['#a855f7','NVMe (NQN)'],
                ['#10b981','NFS / SMB'],['#FE5000','Pure FlashArray'],['#8b5cf6','NetApp ONTAP'],
                ['#01A982','HPE Alletra/Nimble'],['#007DB8','Dell PowerStore']].map(([c2,l])=>(
                <span key={l} style={{padding:'2px 8px',borderRadius:5,border:`1px solid ${c2}40`,background:`${c2}10`,color:c2}}>{l}</span>
              ))}
            </div>

            {/* Print header */}
            <div style={{display:'none'}} className="topo-print-only">
              <div style={{marginBottom:8,fontSize:10,color:'#555'}}>
                <strong>LAAS Storage Topology Report</strong> &nbsp; Array: {arrName} &nbsp; Volume: {volName} &nbsp; Vendor: {vendor} &nbsp; Generated: {new Date().toLocaleString()}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
"""

# Verify we found the function
if fn_start == -1:
    print("ERROR: VolumeTopologyModal function not found")
    sys.exit(1)

new_app = app[:fn_start] + NEW_MODAL + app[fn_end:]
with open(app_path, 'w', encoding='utf-8') as f:
    f.write(new_app)
print(f"OK: VolumeTopologyModal rewritten ({len(NEW_MODAL)} chars, replaces {fn_end-fn_start} chars)")
print(f"File length: {len(new_app)} chars (was {len(app)})")
