import React, { useState, useMemo } from 'react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  AreaChart, Area, ComposedChart,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  FunnelChart, Funnel, LabelList, Treemap,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine
} from 'recharts';

const C = ['#d4651a','#2563eb','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#ec4899','#84cc16','#64748b'];
const TT = { background:'#fff', border:'none', borderRadius:10, color:'#1a1a1a', fontSize:13, boxShadow:'0 8px 32px rgba(0,0,0,0.18)', padding:'12px 16px' };

// ── INDIA MAP ────────────────────────────────────────────────────
const INDIA_STATES = {
  'Maharashtra':[75.7,19.0],'Karnataka':[76.1,15.3],'Gujarat':[71.5,22.3],
  'Rajasthan':[74.2,27.0],'Tamil Nadu':[78.6,11.1],'Andhra Pradesh':[79.7,15.9],
  'Uttar Pradesh':[80.9,27.0],'West Bengal':[87.8,22.8],'Madhya Pradesh':[77.4,23.5],
  'Telangana':[79.0,17.9],'Bihar':[85.3,25.1],'Punjab':[75.3,31.1],
  'Haryana':[76.0,29.0],'Delhi':[77.1,28.7],'Kerala':[76.2,10.8],
  'Odisha':[84.8,20.4],'Jharkhand':[85.3,23.6],'Chhattisgarh':[81.8,21.3],
  'Assam':[92.9,26.2],'Himachal Pradesh':[77.2,31.9],'Uttarakhand':[79.0,30.1],
};
const IndiaMap = ({ data }) => {
  const [hov, setHov] = useState(null);
  if (!data?.length) return null;
  const dm = {}; data.forEach(d => { dm[d.name] = parseFloat(d.value)||0; });
  const maxV = Math.max(...Object.values(dm), 1);
  const minV = Math.min(...Object.values(dm).filter(v=>v>0), 0);
  const toX = lon => ((lon-68)/30)*380+10;
  const toY = lat => 340-((lat-8)/30)*330;
  const getC = v => { const t=(v-minV)/(maxV-minV||1); return `rgb(${Math.round(255-t*75)},${Math.round(220-t*140)},${Math.round(200-t*200)})`; };
  return (
    <div style={{width:'100%'}}>
      <svg viewBox="0 0 400 360" style={{width:'100%',maxHeight:280}}>
        <rect width={400} height={360} fill="#fdf6f0" rx={8}/>
        <text x={200} y={185} textAnchor="middle" fill="#e8c4a0" fontSize={90} fontWeight={700} opacity={0.1}>IN</text>
        {Object.entries(INDIA_STATES).map(([st,[lon,lat]])=>{
          const v=dm[st];
          if(v===undefined) return <circle key={st} cx={toX(lon)} cy={toY(lat)} r={3} fill="#e8c4a0" opacity={0.35}/>;
          const r=Math.max(9,Math.min(26,9+(v/maxV)*17)); const isH=hov===st;
          return (
            <g key={st} onMouseEnter={()=>setHov(st)} onMouseLeave={()=>setHov(null)} style={{cursor:'pointer'}}>
              <circle cx={toX(lon)} cy={toY(lat)} r={r+(isH?3:0)} fill={getC(v)} opacity={isH?1:0.82} stroke="#fff" strokeWidth={isH?2:1.5}/>
              {(r>13||isH)&&<text x={toX(lon)} y={toY(lat)+1} textAnchor="middle" dominantBaseline="middle" fontSize={isH?11:9} fontWeight={700} fill="#2d1a0e">{v.toLocaleString()}</text>}
              {isH&&<text x={toX(lon)} y={toY(lat)-r-6} textAnchor="middle" fontSize={11} fontWeight={600} fill="#2d1a0e" stroke="#fff" strokeWidth={3} paintOrder="stroke">{st}</text>}
            </g>
          );
        })}
      </svg>
      <div style={{display:'flex',flexWrap:'wrap',gap:4,marginTop:8}}>
        {[...data].sort((a,b)=>b.value-a.value).slice(0,8).map((d,i)=>(
          <span key={i} style={{fontSize:11,padding:'3px 9px',borderRadius:20,background:i===0?'#d4651a':'#fff3ea',color:i===0?'#fff':'#7a4f30',fontWeight:i===0?700:500}}>
            {d.name}: {parseFloat(d.value).toLocaleString()}
          </span>
        ))}
      </div>
    </div>
  );
};

// ── TOOLTIP ──────────────────────────────────────────────────────
const CTip = ({ active, payload, label }) => {
  if (!active||!payload?.length) return null;
  return (
    <div style={TT}>
      <div style={{fontWeight:700,color:'#1a1a1a',marginBottom:8,fontSize:13,borderBottom:'1px solid #f0d5be',paddingBottom:6}}>
        {payload[0]?.payload?.fullName||label}
      </div>
      {payload.map((p,i)=>(
        <div key={i} style={{color:p.color||C[i],margin:'3px 0',fontSize:13,display:'flex',justifyContent:'space-between',gap:20}}>
          <span>{p.name}</span><strong>{typeof p.value==='number'?p.value.toLocaleString():p.value}</strong>
        </div>
      ))}
    </div>
  );
};

// ── KPI CARD ─────────────────────────────────────────────────────
const KpiCard = ({ label, value, sub, color, delta, status }) => {
  const deltaPos = delta && !String(delta).startsWith('-');
  const sBg = status==='good'?'#dcfce7':status==='warn'?'#fef9c3':status==='bad'?'#fee2e2':'#f1f5f9';
  const sClr = status==='good'?'#166534':status==='warn'?'#854d0e':status==='bad'?'#991b1b':'#475569';
  const vStr = String(value);
  const vSize = vStr.length>12?15:vStr.length>9?18:vStr.length>6?22:vStr.length>4?26:30;
  return (
    <div style={{background:'#fff',border:'1px solid #f0d5be',borderRadius:12,padding:'14px 16px',borderTop:`3px solid ${color||'#d4651a'}`,minWidth:0,overflow:'hidden',boxSizing:'border-box'}}>
      {status&&<div style={{fontSize:9,fontWeight:700,padding:'2px 8px',borderRadius:20,background:sBg,color:sClr,marginBottom:8,letterSpacing:'0.06em',textTransform:'uppercase',display:'inline-block'}}>{status}</div>}
      <div style={{fontSize:10,color:'#b07a55',fontWeight:700,textTransform:'uppercase',letterSpacing:'0.07em',marginBottom:6,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{label}</div>
      <div style={{fontSize:vSize,fontWeight:800,color:'#1a1a1a',lineHeight:1.15,letterSpacing:'-0.02em',wordBreak:'break-word'}}>{value}</div>
      {delta&&<div style={{fontSize:11,color:deltaPos?'#16a34a':'#dc2626',marginTop:4,fontWeight:700}}>{deltaPos?'▲':'▼'} {delta}</div>}
      {sub&&<div style={{fontSize:11,color:'#7a4f30',marginTop:3,lineHeight:1.4,display:'-webkit-box',WebkitLineClamp:3,WebkitBoxOrient:'vertical',overflow:'hidden'}}>{sub}</div>}
    </div>
  );
};

// ── GANTT ─────────────────────────────────────────────────────────
const GanttChart = ({ tasks }) => {
  if (!tasks?.length) return null;
  const allD = tasks.flatMap(t=>[new Date(t.start),new Date(t.end)]);
  const minD=new Date(Math.min(...allD)), maxD=new Date(Math.max(...allD));
  const range=maxD-minD||1;
  const pct = d => Math.max(0,Math.min(100,((new Date(d)-minD)/range)*100));
  const SC = {done:'#10b981','in-progress':'#d4651a',upcoming:'#8b5cf6',delayed:'#ef4444','at-risk':'#f59e0b',planning:'#06b6d4'};
  const months=[]; const cur=new Date(minD); cur.setDate(1);
  while(cur<=maxD){months.push({label:cur.toLocaleString('default',{month:'short',year:'2-digit'}),left:pct(cur)});cur.setMonth(cur.getMonth()+1);}
  const todayP=pct(new Date());
  return (
    <div style={{overflowX:'auto',paddingBottom:4}}>
      <div style={{minWidth:500}}>
        <div style={{marginLeft:160,position:'relative',height:24,marginBottom:6,borderBottom:'1px solid #f0d5be'}}>
          {months.map((m,i)=><div key={i} style={{position:'absolute',left:`${m.left}%`,fontSize:10,color:'#b07a55',whiteSpace:'nowrap',paddingLeft:4,fontWeight:600}}>{m.label}</div>)}
          {todayP>=0&&todayP<=100&&<div style={{position:'absolute',left:`${todayP}%`,top:0,height:2000,width:2,background:'rgba(239,68,68,0.3)',zIndex:2}}>
            <span style={{position:'absolute',top:0,left:4,fontSize:9,color:'#ef4444',fontWeight:700,whiteSpace:'nowrap',background:'#fff7f0',padding:'1px 5px',borderRadius:4}}>Today</span>
          </div>}
        </div>
        {tasks.map((task,i)=>{
          const color=SC[task.status?.toLowerCase().replace(/\s/g,'-')]||C[i%C.length];
          const l=pct(task.start), w=Math.max(1,pct(task.end)-l);
          return (
            <div key={i} style={{display:'flex',alignItems:'center',marginBottom:5}}>
              <div style={{width:156,flexShrink:0,fontSize:11,color:'#2d1a0e',textAlign:'right',paddingRight:8,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',fontWeight:500}} title={task.name}>{task.name}</div>
              <div style={{flex:1,height:22,position:'relative',background:'#fff3ea',borderRadius:5}}>
                <div style={{position:'absolute',left:`${l}%`,width:`${w}%`,height:'100%',background:color,borderRadius:5,display:'flex',alignItems:'center',paddingLeft:6,fontSize:10,color:'#fff',fontWeight:700,overflow:'hidden',whiteSpace:'nowrap'}}>
                  {task.progress!==undefined&&<div style={{position:'absolute',left:0,top:0,bottom:0,width:`${task.progress}%`,background:'rgba(255,255,255,0.22)',borderRadius:5}}/>}
                  <span style={{position:'relative',zIndex:1}}>{w>8?task.name:''}{task.progress!==undefined?` ${task.progress}%`:''}</span>
                </div>
              </div>
            </div>
          );
        })}
        <div style={{display:'flex',gap:10,marginTop:10,marginLeft:160,flexWrap:'wrap'}}>
          {Object.entries(SC).map(([s,c])=><div key={s} style={{display:'flex',alignItems:'center',gap:4,fontSize:10,color:'#7a4f30'}}><div style={{width:10,height:10,borderRadius:2,background:c}}/>{s.charAt(0).toUpperCase()+s.slice(1).replace(/-/g,' ')}</div>)}
        </div>
      </div>
    </div>
  );
};

// ── WATERFALL ─────────────────────────────────────────────────────
const WaterfallChart = ({ items }) => {
  if (!items?.length) return null;
  let running=0;
  const data=items.map(d=>{const isT=d.total,v=parseFloat(d.value)||0,start=isT?0:running;if(!isT)running+=v;return{...d,start,end:isT?running:running,diff:v};});
  const vals=data.flatMap(d=>[d.start,d.end]);
  const minV=Math.min(0,...vals),maxV=Math.max(...vals),range=maxV-minV||1;
  const H=180,BW=44,CW=62;
  const toY=v=>H-((v-minV)/range)*H;
  return (
    <div style={{overflowX:'auto'}}>
      <svg width={Math.max(360,data.length*CW+20)} height={H+50}>
        <line x1={0} x2={data.length*CW} y1={toY(0)} y2={toY(0)} stroke="#e8c4a0" strokeDasharray="4 4"/>
        {data.map((d,i)=>{
          const x=i*CW+8, y1=toY(Math.max(d.start,d.end)), h=Math.max(2,Math.abs(toY(d.start)-toY(d.end)));
          const color=d.total?'#2563eb':d.diff>=0?'#10b981':'#ef4444';
          return (
            <g key={i}>
              <rect x={x} y={y1} width={BW} height={h} fill={color} rx={3} opacity={0.9}/>
              {!d.total&&i<data.length-1&&<line x1={x+BW} x2={x+CW} y1={toY(d.end)} y2={toY(d.end)} stroke="#ddd" strokeDasharray="3 3"/>}
              <text x={x+BW/2} y={y1-5} textAnchor="middle" fontSize={10} fill={color} fontWeight={700}>{d.diff>=0&&!d.total?'+':''}{d.diff.toLocaleString()}</text>
              <text x={x+BW/2} y={H+18} textAnchor="middle" fontSize={10} fill="#7a4f30">{String(d.name).length>9?d.name.slice(0,8)+'…':d.name}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const CTL = {bar:'Bar',stacked_bar:'Stacked',line:'Line',area:'Area',composed:'Mixed',pie:'Pie',radar:'Radar',funnel:'Funnel',treemap:'Map',waterfall:'Waterfall',gantt:'Gantt',india_map:'India'};

// ── PANEL ─────────────────────────────────────────────────────────
function Panel({ panel }) {
  const [type, setType] = useState(panel.chart_type||'bar');

  const rawData = useMemo(()=>{
    if(!panel.labels) return [];
    return panel.labels.map((lbl,i)=>{
      const row={name:String(lbl).length>12?String(lbl).slice(0,11)+'…':String(lbl),fullName:String(lbl)};
      if(panel.datasets) panel.datasets.forEach(ds=>{row[ds.label]=parseFloat(ds.values[i])||0;});
      else row.value=parseFloat(panel.values?.[i])||0;
      return row;
    });
  },[panel]);

  const keys = useMemo(()=>panel.datasets?panel.datasets.map(d=>d.label):['value'],[panel]);
  const total = useMemo(()=>panel.datasets
    ?panel.datasets.reduce((s,ds)=>s+ds.values.reduce((a,v)=>a+(parseFloat(v)||0),0),0)
    :(panel.values||[]).reduce((s,v)=>s+(parseFloat(v)||0),0),[panel]);

  const available = useMemo(()=>{
    if(panel.tasks||panel.chart_type==='gantt') return ['gantt'];
    if(panel.chart_type==='waterfall') return ['waterfall'];
    if(panel.chart_type==='india_map') return ['india_map','bar'];
    if(panel.chart_type==='funnel') return ['funnel','bar'];
    if(panel.chart_type==='radar') return ['radar','bar'];
    if(panel.chart_type==='treemap') return ['treemap','bar'];
    const multi=keys.length>1, many=rawData.length>8;
    if(multi) return ['bar','stacked_bar','line','area','composed'];
    if(many) return ['bar','line','area'];
    return ['bar','line','area','pie'];
  },[panel,keys,rawData]);

  const n=rawData.length;
  const many=n>5, vMany=n>9;

  // Chart height — generous, never clips
  const chartH = type==='pie'?280:panel.tasks?'auto':vMany?320:many?290:260;

  // X-axis — rotate early, truncate aggressively
  const xProps={
    dataKey:'name',
    tick:{fill:'#7a4f30',fontSize:vMany?9:many?10:12},
    axisLine:false, tickLine:false, interval:0,
    angle:many?-40:0,
    textAnchor:many?'end':'middle',
    height:many?72:36
  };
  const yProps={
    tick:{fill:'#7a4f30',fontSize:11}, axisLine:false, tickLine:false, width:50,
    tickFormatter:v=>v>=1000000?(v/1000000).toFixed(1)+'M':v>=1000?(v/1000).toFixed(1)+'k':v
  };

  const Grid=<>
    <CartesianGrid strokeDasharray="3 3" stroke="#f0e8de" vertical={false}/>
    <XAxis {...xProps}/>
    <YAxis {...yProps}/>
    <Tooltip content={<CTip/>}/>
    {keys.length>1&&<Legend iconType="circle" iconSize={9} wrapperStyle={{paddingTop:10,fontSize:11}} formatter={v=><span style={{color:'#7a4f30'}}>{v}</span>}/>}
    {panel.reference_line&&<ReferenceLine y={panel.reference_line.value} stroke="#ef4444" strokeDasharray="5 5" label={{value:panel.reference_line.label,fill:'#ef4444',fontSize:10,position:'right'}}/>}
  </>;

  const renderChart=()=>{
    if(type==='gantt'||panel.tasks) return <GanttChart tasks={panel.tasks}/>;
    if(type==='waterfall') return <WaterfallChart items={panel.waterfall_data}/>;

    if(type==='india_map'){
      const md=panel.map_data||rawData.map(d=>({name:d.fullName||d.name,value:d[keys[0]]||d.value||0}));
      return <IndiaMap data={md}/>;
    }

    if(type==='treemap') return (
      <ResponsiveContainer width="100%" height={chartH}>
        <Treemap data={panel.treemap_data||rawData.map(d=>({name:d.fullName||d.name,size:d[keys[0]]||d.value||0}))} dataKey="size" nameKey="name"
          content={({x,y,width,height,name,value})=>(
            <g>
              <rect x={x} y={y} width={width} height={height} fill={C[Math.abs((name||'').charCodeAt(0)||0)%C.length]} stroke="#fff" strokeWidth={2} rx={3}/>
              {width>50&&height>22&&<text x={x+width/2} y={y+height/2} textAnchor="middle" dominantBaseline="middle" fill="#fff" fontSize={11} fontWeight={700}>{name}</text>}
              {width>50&&height>38&&<text x={x+width/2} y={y+height/2+14} textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize={10}>{typeof value==='number'?value.toLocaleString():value}</text>}
            </g>
          )}/>
      </ResponsiveContainer>
    );

    if(type==='radar') return (
      <ResponsiveContainer width="100%" height={chartH}>
        <RadarChart data={rawData}>
          <PolarGrid stroke="#f0e8de"/>
          <PolarAngleAxis dataKey="name" tick={{fill:'#7a4f30',fontSize:11}}/>
          {keys.map((k,i)=><Radar key={k} name={k} dataKey={k} stroke={C[i]} fill={C[i]} fillOpacity={0.15} strokeWidth={2.5}/>)}
          <Legend iconType="circle" iconSize={9} formatter={v=><span style={{color:'#7a4f30',fontSize:11}}>{v}</span>}/>
          <Tooltip contentStyle={TT}/>
        </RadarChart>
      </ResponsiveContainer>
    );

    if(type==='funnel') return (
      <ResponsiveContainer width="100%" height={chartH}>
        <FunnelChart>
          <Tooltip contentStyle={TT}/>
          <Funnel dataKey="value" data={rawData} isAnimationActive>
            {rawData.map((_,i)=><Cell key={i} fill={C[i%C.length]}/>)}
            <LabelList position="right" fill="#7a4f30" stroke="none" dataKey="fullName" style={{fontSize:11,fontWeight:600}}/>
          </Funnel>
        </FunnelChart>
      </ResponsiveContainer>
    );

    if(type==='pie') return (
      <ResponsiveContainer width="100%" height={chartH}>
        <PieChart margin={{top:10,right:20,bottom:10,left:20}}>
          <Pie data={rawData} dataKey={keys[0]} nameKey="name"
            cx="50%" cy="42%" outerRadius={90} innerRadius={38}
            paddingAngle={2} label={false} labelLine={false}>
            {rawData.map((_,i)=><Cell key={i} fill={C[i%C.length]}/>)}
          </Pie>
          <Tooltip contentStyle={TT} formatter={(v,n)=>[typeof v==='number'?v.toLocaleString():v,n]}/>
          <Legend layout="horizontal" verticalAlign="bottom" align="center"
            iconType="circle" iconSize={9} wrapperStyle={{paddingTop:8,fontSize:11,lineHeight:'18px'}}
            formatter={(value,entry)=>(
              <span style={{color:'#7a4f30'}}>
                {String(value).length>16?String(value).slice(0,15)+'…':value}{' '}
                <strong style={{color:'#1a1a1a'}}>{entry.payload?.value?.toLocaleString()}</strong>
                {total>0&&<span style={{color:'#b07a55'}}>{' '}({((entry.payload?.value/total)*100).toFixed(0)}%)</span>}
              </span>
            )}/>
        </PieChart>
      </ResponsiveContainer>
    );

    if(type==='area') return (
      <ResponsiveContainer width="100%" height={chartH}>
        <AreaChart data={rawData} margin={{top:5,right:10,bottom:many?60:5,left:0}}>{Grid}
          {keys.map((k,i)=><Area key={k} type="monotone" dataKey={k} stroke={C[i]} fill={C[i]} fillOpacity={0.1} strokeWidth={2.5} dot={{fill:C[i],r:3,strokeWidth:2,stroke:'#fff'}} activeDot={{r:5}}/>)}
        </AreaChart>
      </ResponsiveContainer>
    );

    if(type==='line') return (
      <ResponsiveContainer width="100%" height={chartH}>
        <LineChart data={rawData} margin={{top:5,right:10,bottom:many?60:5,left:0}}>{Grid}
          {keys.map((k,i)=><Line key={k} type="monotone" dataKey={k} stroke={C[i]} strokeWidth={2.5} dot={{fill:C[i],r:3,strokeWidth:2,stroke:'#fff'}} activeDot={{r:5}}/>)}
        </LineChart>
      </ResponsiveContainer>
    );

    if(type==='composed') return (
      <ResponsiveContainer width="100%" height={chartH}>
        <ComposedChart data={rawData} margin={{top:5,right:10,bottom:many?60:5,left:0}}>{Grid}
          {keys.map((k,i)=>i===0
            ?<Bar key={k} dataKey={k} fill={C[i]} radius={[4,4,0,0]} barSize={18}/>
            :<Line key={k} type="monotone" dataKey={k} stroke={C[i]} strokeWidth={2.5} dot={{r:3}}/>
          )}
        </ComposedChart>
      </ResponsiveContainer>
    );

    // bar / stacked_bar
    const stacked=type==='stacked_bar';
    const barSz=keys.length>1?Math.max(8,20-keys.length*2):Math.min(26,Math.max(8,160/Math.max(n,1)));
    return (
      <ResponsiveContainer width="100%" height={chartH}>
        <BarChart data={rawData} barSize={barSz} barGap={2} barCategoryGap={many?'25%':'32%'}
          margin={{top:5,right:10,bottom:many?60:5,left:0}}>{Grid}
          {keys.map((k,i)=>(
            <Bar key={k} dataKey={k} fill={C[i]} radius={stacked&&i<keys.length-1?0:[4,4,0,0]} stackId={stacked?'s':undefined}>
              {!stacked&&keys.length===1&&rawData.map((_,j)=><Cell key={j} fill={C[j%C.length]}/>)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  };

  // Check if we have any renderable data
  const hasChartData = rawData.length > 0 || panel.tasks?.length > 0 || 
                       panel.waterfall_data?.length > 0 || panel.map_data?.length > 0 ||
                       panel.treemap_data?.length > 0;

  return (
    <div style={{
      background:'#fff', border:'1px solid #edd5be', borderRadius:14,
      padding:'18px 20px', display:'flex', flexDirection:'column', gap:12,
      boxSizing:'border-box'
    }}>
      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:10}}>
        <div style={{minWidth:0,flex:1}}>
          <div style={{fontSize:14,fontWeight:700,color:'#1a1a1a',letterSpacing:'-0.01em',lineHeight:1.3}}>{panel.title}</div>
          {panel.subtitle&&<div style={{fontSize:11,color:'#b07a55',marginTop:2,lineHeight:1.4}}>{panel.subtitle}</div>}
          {panel.show_total&&hasChartData&&<div style={{fontSize:11,color:'#7a4f30',marginTop:3}}>Total: <strong style={{color:'#1a1a1a',fontSize:13}}>{total.toLocaleString()}</strong>{panel.total_label?' '+panel.total_label:''}</div>}
        </div>
        {hasChartData&&!panel.tasks&&available.length>1&&(
          <div style={{display:'flex',gap:3,flexShrink:0,flexWrap:'nowrap'}}>
            {available.map(t=>(
              <button key={t} onClick={()=>setType(t)} style={{
                padding:'3px 9px',fontSize:10,borderRadius:20,border:'none',cursor:'pointer',
                background:type===t?'#d4651a':'#fff3ea',
                color:type===t?'#fff':'#b07a55',
                fontWeight:type===t?700:500,whiteSpace:'nowrap'
              }}>{CTL[t]||t}</button>
            ))}
          </div>
        )}
      </div>

      {/* Chart — only render if we have data */}
      {hasChartData ? (
        <div>{renderChart()}</div>
      ) : (
        /* No chart data — show insight/alert prominently as the content */
        <div style={{background:'#fff7f0',borderRadius:10,padding:'16px',textAlign:'center',border:'1px dashed #e8c4a0'}}>
          <div style={{fontSize:24,marginBottom:8}}>📊</div>
          <div style={{fontSize:12,color:'#b07a55',fontWeight:600}}>No chart data available</div>
          <div style={{fontSize:11,color:'#c4967a',marginTop:4}}>See insights below for analysis</div>
        </div>
      )}

      {panel.insight&&(
        <div style={{display:'flex',gap:8,alignItems:'flex-start',background:'#fff7f0',borderRadius:8,padding:'9px 12px',borderLeft:'3px solid #d4651a'}}>
          <span style={{fontSize:14,flexShrink:0}}>💡</span>
          <span style={{fontSize:12,color:'#7a4f30',lineHeight:1.5}}>{panel.insight}</span>
        </div>
      )}
      {panel.alert&&(
        <div style={{display:'flex',gap:8,alignItems:'flex-start',background:'#fef9c3',borderRadius:8,padding:'9px 12px',borderLeft:'3px solid #f59e0b'}}>
          <span style={{fontSize:14,flexShrink:0}}>⚠️</span>
          <span style={{fontSize:12,color:'#854d0e',lineHeight:1.5}}>{panel.alert}</span>
        </div>
      )}
    </div>
  );
}

// ── GRID LAYOUT ───────────────────────────────────────────────────
function getGridCols(panels) {
  const n = panels.length;
  if (n <= 1) return '1fr';
  const hasGantt = panels.some(p=>p.tasks||p.chart_type==='gantt');
  const hasMap   = panels.some(p=>p.chart_type==='india_map');
  if (hasGantt||hasMap) return '1fr';
  if (n === 2) return 'repeat(2,minmax(0,1fr))';
  if (n === 3) return 'repeat(3,minmax(0,1fr))';
  // 4 panels: 2×2 grid — each panel gets half the width, much better than 4 in a row
  if (n === 4) return 'repeat(2,minmax(0,1fr))';
  if (n === 5) return 'repeat(3,minmax(0,1fr))';
  if (n === 6) return 'repeat(3,minmax(0,1fr))';
  return 'repeat(2,minmax(0,1fr))';
}

// ── MAIN DASHBOARD ────────────────────────────────────────────────
export default function DashboardCard({ data }) {
  const [activeTab, setActiveTab] = useState(0);
  if (!data) return null;

  const tabs = data.tabs?.length ? data.tabs : [{label:'Overview',panels:data.panels||[]}];
  const currentPanels = tabs[activeTab]?.panels||[];

  const kpiCount = data.kpis?.length||0;
  const kpiCols = kpiCount===1?'1fr'
    :kpiCount===2?'repeat(2,minmax(0,1fr))'
    :kpiCount===3?'repeat(3,minmax(0,1fr))'
    :kpiCount===4?'repeat(4,minmax(0,1fr))'
    :kpiCount<=6?'repeat(3,minmax(0,1fr))'
    :'repeat(auto-fill,minmax(140px,1fr))';

  return (
    <div className="dashboard-card" style={{
      background:'#fdf6f0', border:'1px solid #e8c4a0',
      borderRadius:18, marginTop:12, width:'100%',
      // NO overflow:hidden — critical, this was clipping charts
    }}>
      {/* Header */}
      <div style={{background:'linear-gradient(135deg,#8c3a0c 0%,#c25514 45%,#d4651a 75%,#e07a1a 100%)',padding:'16px 22px',borderRadius:'18px 18px 0 0',display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:16}}>
        <div style={{minWidth:0,flex:1}}>
          <div style={{fontSize:17,fontWeight:800,color:'#fff',letterSpacing:'-0.02em',lineHeight:1.25}}>{data.title||'Analytics Dashboard'}</div>
          {data.subtitle&&<div style={{fontSize:12,color:'rgba(255,255,255,0.82)',marginTop:4,lineHeight:1.4}}>{data.subtitle}</div>}
        </div>
        <div style={{textAlign:'right',flexShrink:0}}>
          {data.source&&<div style={{fontSize:11,color:'rgba(255,255,255,0.75)',fontWeight:500}}>Source: {data.source}</div>}
          {data.as_of&&<div style={{fontSize:11,color:'rgba(255,255,255,0.6)',marginTop:2}}>As of: {data.as_of}</div>}
        </div>
      </div>

      <div style={{padding:'16px 20px',display:'flex',flexDirection:'column',gap:16}}>
        {/* KPI grid */}
        {kpiCount>0&&(
          <div style={{display:'grid',gridTemplateColumns:kpiCols,gap:10}}>
            {data.kpis.map((kpi,i)=><KpiCard key={i} {...kpi} color={C[i%C.length]}/>)}
          </div>
        )}

        {/* Tabs */}
        {tabs.length>1&&(
          <div style={{display:'flex',borderBottom:'2px solid #f0d5be'}}>
            {tabs.map((tab,i)=>(
              <button key={i} onClick={()=>setActiveTab(i)} style={{
                padding:'7px 18px',fontSize:13,border:'none',cursor:'pointer',background:'transparent',
                color:activeTab===i?'#d4651a':'#b07a55',fontWeight:activeTab===i?700:500,
                borderBottom:activeTab===i?'2px solid #d4651a':'2px solid transparent',
                marginBottom:-2,transition:'all 0.15s'
              }}>{tab.label}</button>
            ))}
          </div>
        )}

        {/* Panels — filter out completely empty ones before rendering */}
        {(() => {
          const validPanels = currentPanels.filter(p =>
            (p.labels && p.labels.length > 0) ||
            (p.tasks && p.tasks.length > 0) ||
            (p.waterfall_data && p.waterfall_data.length > 0) ||
            (p.map_data && p.map_data.length > 0) ||
            (p.treemap_data && p.treemap_data.length > 0) ||
            p.insight || p.alert
          );
          const gridCols = getGridCols(validPanels);
          return (
            <div style={{display:'grid',gridTemplateColumns:gridCols,gap:14,alignItems:'start'}}>
              {validPanels.map((panel,i)=><Panel key={i} panel={panel}/>)}
            </div>
          );
        })()}

        {data.note&&<div style={{fontSize:11,color:'#b07a55',borderTop:'1px solid #f0d5be',paddingTop:10,textAlign:'right',fontStyle:'italic'}}>{data.note}</div>}
      </div>
    </div>
  );
}