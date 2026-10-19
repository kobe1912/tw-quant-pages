const fs=require('fs'),vm=require('vm'),assert=require('assert');
const report=JSON.parse(fs.readFileSync('docs/data/latest.json','utf8'));const elements={};
const el=id=>elements[id]??=({value:'',textContent:'',innerHTML:'',disabled:false,classList:{toggle(){}}});
const ctx={document:{getElementById:el,querySelectorAll:()=>[]},fetch:async()=>({ok:true,json:async()=>report}),Date,console};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('docs/app.js','utf8'),ctx);
setTimeout(()=>{
 assert(el('meta').textContent.includes('永豐'));assert(el('sector').innerHTML.includes('餐飲'));assert(el('strategy').innerHTML.includes('S6'));
 el('search').value='2330';vm.runInContext('draw()',ctx);assert(el('cards').innerHTML.includes('台積電'));
 el('search').value='';el('sector').value='餐飲';vm.runInContext('draw()',ctx);assert(!el('cards').innerHTML.includes('台積電'));
 assert(el('sectors').innerHTML.includes('族群'));assert(el('portfolio').innerHTML.includes('尚未開始'));
 assert.strictEqual(vm.runInContext('esc("<script>")',ctx),'&lt;script&gt;');
 console.log('Provider display, sectors, stock search, filters and escaping passed');
},0);
