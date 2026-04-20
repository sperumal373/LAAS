const fs=require('fs');
const src=fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx','utf8');
const idx=src.indexOf('id:\\\"manage\\\"');
if(idx>=0) console.log('manage ctx:', JSON.stringify(src.slice(idx,idx+250)));
const idx2=src.indexOf('function VMsPage(');
if(idx2>=0) console.log('close ctx:', JSON.stringify(src.slice(idx2-120,idx2)));
