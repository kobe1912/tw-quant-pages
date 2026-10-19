const fs=require('fs'),vm=require('vm'),assert=require('assert');
const report=JSON.parse(fs.readFileSync('docs/data/latest.json','utf8'));
const elements={};const element=id=>elements[id]??=({value:'',textContent:'',innerHTML:'',classList:{toggle(){}}});
const ctx={document:{getElementById:element,querySelectorAll:()=>[]},fetch:async()=>({ok:true,json:async()=>report}),Date,console};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('docs/app.js','utf8'),ctx);
setTimeout(()=>{assert(element('cards').innerHTML.includes('台積電'));assert(element('portfolio').innerHTML.includes('尚未開始'));assert(element('strategy').innerHTML.includes('S6'));
 element('strategy').value='S6';vm.runInContext('draw()',ctx);assert(element('cards').innerHTML.includes('沒有符合項目'));
 assert.strictEqual(vm.runInContext('esc("<script>")',ctx),'&lt;script&gt;');console.log('UI render, filtering and escaping passed');},0);
