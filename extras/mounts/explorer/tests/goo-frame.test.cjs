// DOM-port unit checks. Browser document/composition coverage is separate.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function fixture() {
  class Element {
    constructor(tag='div',attrs={}) {this.tagName=tag.toUpperCase();this.attrs={...attrs};this.childNodes=[];this.dataset={};this.detaches=0;this.writes=[];}
    get children(){return this.childNodes;}
    get attributes(){return Object.entries(this.attrs).map(([name,value])=>({name,value}));}
    get isConnected(){return this.root || !!this.parentElement?.isConnected;}
    getAttribute(name){return this.attrs[name]??null;}
    hasAttribute(name){return Object.hasOwn(this.attrs,name);}
    setAttribute(name,value){this.writes.push(name);this.attrs[name]=value;}
    removeAttribute(name){delete this.attrs[name];}
    matches(){return this.tagName==='IFRAME' && this.hasAttribute('data-goo-presentation-frame');}
    contains(node){return node===this || this.childNodes.some(child=>child.contains(node));}
    querySelectorAll(){return [];}
    append(...nodes){for(const node of nodes)this.insertBefore(node,null);}
    insertBefore(node,before){node.remove();this.childNodes.splice(before?this.childNodes.indexOf(before):this.childNodes.length,0,node);node.parentElement=this;}
    remove(){if(this.parentElement){if(this.isConnected)this.detaches++;this.parentElement.childNodes=this.parentElement.childNodes.filter(child=>child!==this);this.parentElement=null;}}
    replaceChildren(...nodes){for(const node of [...this.childNodes])node.remove();this.append(...nodes);}
    set innerHTML(value){const {src='/goo-presentation?path=/a',title='Live'}=JSON.parse(value);const frame=new Element('iframe',{'data-goo-presentation-frame':'live',src,title});frame.dataset.gooPresentationFrame='live';this.append(new Element('h2'),frame,new Element('button'));}
  }
  const document={activeElement:null,querySelector:()=>null,createElement:tag=>new Element(tag)};
  const scope={document,console,URLSearchParams,AbortController};
  vm.runInNewContext(fs.readFileSync(require.resolve('../goo-actions.js'),'utf8'),scope);
  const container=new Element();container.root=true;
  const data=(src,title)=>({html:JSON.stringify({src,title}),controls:[],context:{width:352,textScale:1,direction:'ltr'}});
  const initial=data('/goo-presentation?path=/a','Original');
  scope.GooActions.prepareMount(container,initial,false,false).commit();
  return {container,actions:scope.GooActions,data,frame:container.children[1]};
}
test('staging a frame update leaves the installed document untouched',()=>{
  const {container,actions,data,frame}=fixture();
  const before=[...container.childNodes];
  actions.prepareMount(container,data('/goo-presentation?path=/a','Renamed'),true,false);
  assert.deepEqual(container.childNodes,before);assert.equal(frame.getAttribute('title'),'Original');assert.equal(frame.detaches,0);
});
test('admitted card title/body update does not detach or navigate continuing live frame',()=>{
  const {container,actions,data,frame}=fixture();
  const working={value:'unsubmitted',composing:true};frame.documentState=working;
  actions.prepareMount(container,data('/goo-presentation?path=/a','Renamed'),true,false).commit();
  assert.equal(container.children[1],frame);assert.equal(frame.documentState,working);
  assert.equal(frame.getAttribute('title'),'Renamed');assert.equal(frame.detaches,0);assert.equal(frame.writes.includes('src'),false);
});
test('subject change and retired occurrence replace their live document',()=>{
  for(const preserve of [true,false]) {
    const {container,actions,data,frame}=fixture();
    actions.prepareMount(container,data(preserve?'/goo-presentation?path=/b':'/goo-presentation?path=/a','Next'),preserve,false).commit();
    assert.notEqual(container.children[1],frame);assert.equal(frame.detaches,1);
  }
});
