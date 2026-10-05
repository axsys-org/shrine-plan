// Real browser input and real-time video. No fake clock or application fixtures.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/Users/ianchanner/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=process.env.CANVAS_EVIDENCE||'/Users/ianchanner/.local/share/shrine/reviews/canvas-reset-20261004';
const url=process.env.CANVAS_URL||'http://127.0.0.1:8193/';
const mode=process.argv[2]||'interaction';
async function run(){
  const dir=path.join(root,mode+'-'+new Date().toISOString().replaceAll(':','-'));await fs.mkdir(dir,{recursive:true});
  const browser=await chromium.launch({headless:process.env.HEADLESS==='1'});
  const context=await browser.newContext({viewport:{width:1440,height:900},recordVideo:{dir,size:{width:1440,height:900}}});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let result={mode,url,passed:false,coverage:'Local physical interaction only; native semantic acceptance remains separate.'};
  try{
    await page.goto(url);await page.bringToFront();
    await page.getByRole('button',{name:'Network delay off',exact:true}).click();
    // Overlay follows actual mouse events solely to make the recorded input visible.
    await page.evaluate(()=>{const cursor=document.createElement('div');cursor.style.cssText='position:fixed;width:12px;height:12px;border:2px solid #536f9a;border-radius:50%;pointer-events:none;z-index:99;transform:translate(-50%,-50%)';document.body.append(cursor);document.addEventListener('pointermove',e=>{cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';});});
    await page.getByRole('button',{name:'Refresh native material',exact:true}).click();
    const b=await page.locator('#sheet').boundingBox();
    async function drag(x,y,dx,dy,steps=45){await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,{steps});await page.mouse.up();}
    await page.getByRole('button',{name:'▭ Region',exact:true}).click();
    await drag(b.x+55,b.y+65,420,270);
    const label=page.getByRole('textbox',{name:'Sketch label'}).first();
    await label.click();await page.keyboard.type('A place to build',{delay:45});
    await page.getByRole('button',{name:'▤ Input',exact:true}).click();
    await drag(b.x+95,b.y+150,320,95);
    const input=page.getByRole('textbox',{name:'Sketch input'});
    await input.click();await page.keyboard.type('Typing while the native response is delayed',{delay:30});
    for(let i=0;i<4;i++){
      const r=await page.locator('.sketch[data-kind=input]').boundingBox();
      await drag(r.x+35,r.y+5,30*(i%2?-1:1),22*(i%2?-1:1));
      const handle=await page.getByRole('button',{name:'Resize region'}).last().boundingBox();
      await drag(handle.x+5,handle.y+5,35*(i%2?-1:1),15*(i%2?-1:1),25);
    }
    await page.getByRole('button',{name:'Duplicate',exact:true}).click();
    await page.getByRole('button',{name:'Undo',exact:true}).click();
    assert.equal(await page.locator('.sketch').count(),2);
    await page.mouse.move(b.x+550,b.y+400);await page.mouse.wheel(0,400);await page.mouse.wheel(0,-400);
    await page.getByRole('button',{name:'Activity',exact:true}).click();await page.getByRole('button',{name:'Activity',exact:true}).click();
    await page.waitForTimeout(2200); // Actual response delay, not a virtual/fake clock.
    result.evidence=await page.evaluate(()=>window.groveEvidence());
    result.errors=errors;
    assert.equal(errors.length,0);
    assert.ok(result.evidence.summary.local.count>=100,'Need an actual distribution');
    assert.ok(result.evidence.samples.roundTrip.some(s=>s.delayMs===2000&&s.ms>=2000),'Delayed response must actually arrive');
    assert.ok(result.evidence.summary.local.p95<=16,'Local p95 exceeds 16 ms');
    const draft=await input.inputValue();
    await page.reload();await page.getByRole('textbox',{name:'Sketch input'}).waitFor();
    assert.equal(await page.getByRole('textbox',{name:'Sketch input'}).inputValue(),draft);
    await page.getByRole('button',{name:'Network delay off',exact:true}).click();
    result.passed=true;
    await page.screenshot({path:path.join(dir,'actual.png')});
  }catch(error){result.failure=error.stack;await page.screenshot({path:path.join(dir,'failure.png')}).catch(()=>{});}
  finally{
    const video=page.video();await context.close();await video.saveAs(path.join(dir,'proof.webm'));await browser.close();
    await fs.writeFile(path.join(dir,'evidence.json'),JSON.stringify(result,null,2));
    const relative=path.relative(root,dir),preview=result.passed?'actual.png':'failure.png';
    const title='Interaction gate · '+(result.passed?'physical gate passed':'failed — retained evidence');
    const html='<!doctype html><meta charset="utf-8"><title>Grove reset evidence</title><style>body{font:15px system-ui;background:#f5f6f2;color:#253025;margin:25px}section{display:grid;grid-template-columns:1fr 1fr;gap:20px}video,img{width:100%}pre{white-space:pre-wrap}a{color:#37599b}</style><h1>'+title+'</h1><p>Recorded real browser interactions; no reference animation was ported. This clip covers physical input and draft reload only. Native publication, contract refinement and failure-path gates remain pending.</p><section><div><h2>Actual browser</h2><video controls src="'+relative+'/proof.webm"></video><img src="'+relative+'/'+preview+'"></div><div><h2>Reference target — step 1</h2><img src="reference/stills/01-sketch-to-real-ui.png"><p>The reference includes model refinement, which this physical gate does not claim.</p></div></section><p><a href="'+relative+'/evidence.json">Raw timings and assertions</a></p><pre>'+JSON.stringify(result.evidence?.summary||result.failure,null,2)+'</pre>';
    await fs.writeFile(path.join(root,'index.html'),html);
    console.log(JSON.stringify({directory:dir,passed:result.passed,summary:result.evidence?.summary,failure:result.failure},null,2));
    if(!result.passed)process.exitCode=1;
  }
}
run().catch(e=>{console.error(e);process.exitCode=1;});
