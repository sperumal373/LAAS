const fs=require('fs');
const src=fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx','utf8');
// Find manage tab
const mIdx=src.indexOf('id:\\"manage\\"');
if(mIdx>=0){
  const chunk=src.slice(mIdx,mIdx+300);
  console.log('manage:', JSON.stringify(chunk));
}
