const assert = require('node:assert/strict');

async function exerciseActionsMount(page) {
  const result=await page.evaluate(()=>{
    const container=document.createElement('section');document.body.append(container);
    const context={width:520,textScale:1.25,direction:'rtl'};
    const data=(id,value)=>({view:'/edit',kind:'view',slot:'/content',role:'/record',context,
      profile:{id:'mash-goo',version:1,revision:'browser-mount-fixture'},
      html:`<fieldset class="goo-preview"><input data-node="${id}" value="${value}" aria-label="Draft"><button data-node="save">Save</button></fieldset>`,
      controls:[{id,kind:'input',slot:'/draft'}],display:{nodes:[]}});
    const oldData=data('input-1','original server text');
    let localInputEvents=0, reboundInputEvents=0, actionEvents=0;
    const bind=()=>GooActions.bind(container,{controls:[{id:container.querySelector('input').dataset.node,kind:'input',slot:'/draft'}],
      input:(_slot,input,signal)=>input.addEventListener('input',()=>reboundInputEvents++,{signal})});
    GooActions.mount(container,oldData);bind();
    const retained=container.querySelector('input');
    retained.addEventListener('input',()=>localInputEvents++);
    container.addEventListener('click',()=>actionEvents++);
    retained.focus();retained.value='unsaved draft';retained.setSelectionRange(2,7,'backward');
    const next=data('input-2','new server text');GooActions.mount(container,next,true);bind();
    const after={same:retained===container.querySelector('input'),active:document.activeElement===retained,
      value:retained.value,start:retained.selectionStart,end:retained.selectionEnd,direction:retained.selectionDirection,
      node:retained.dataset.node,slot:retained.dataset.inputSlot,localInputEvents,reboundInputEvents,actionEvents,
      context:JSON.parse(container.dataset.renderContext),display:container.gooDisplay===next.display};
    retained.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:'x'}));
    const listeners={localInputEvents,reboundInputEvents};
    GooActions.mount(container,data('replacement','fresh lifetime'),false);
    const replacement={replaced:container.querySelector('input')!==retained,oldDetached:!retained.isConnected,value:container.querySelector('input').value};
    container.remove();return {after,listeners,replacement};
  });
  assert.deepEqual(result.after,{same:true,active:true,value:'unsaved draft',start:2,end:7,direction:'backward',node:'input-2',slot:'/draft',
    localInputEvents:0,reboundInputEvents:0,actionEvents:0,context:{width:520,textScale:1.25,direction:'rtl'},display:true});
  assert.deepEqual(result.listeners,{localInputEvents:1,reboundInputEvents:1});
  assert.deepEqual(result.replacement,{replaced:true,oldDetached:true,value:'fresh lifetime'});
  return {cases:3};
}

module.exports={exerciseActionsMount};
