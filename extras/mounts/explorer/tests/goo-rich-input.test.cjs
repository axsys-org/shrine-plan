const {test}=require('node:test');
const assert=require('node:assert/strict');
const rich=require('../goo-rich-input.js');
const bold={'/sys/modifiers':{kind:'modifiers',value:['bold']}};
const link={'/sys/link':{kind:'path',value:'/notes/source'}};
const style={version:1,foreground:'#111111',textStyle:{family:'Goo Sans',fontSHA256:'a'.repeat(64),fontSize:15,lineHeight:24,letterSpacing:0,weight:400,style:'normal'}};
const contract={version:1,encoding:'goo-text-v1',maxBytes:65536,styles:[{myth:{},resolved:style},{myth:bold,resolved:style}]};
test('Enter and Backspace split and join without flattening descriptors',()=>{
 const before=[rich.run('left',bold),rich.run('right',link)];
 const split=rich.replace(before,4,4,[rich.run('\n')]);
 assert.equal(rich.text(split),'left\nright');
 assert.deepEqual(rich.replace(split,4,5,[]),before);
});
test('selection replacement retains formatting outside the selected range',()=>{
 const before=[rich.run('hello',bold),rich.run(' world',link)];
 const after=rich.replace(before,2,8,[rich.run('!')]);
 assert.deepEqual(after,[rich.run('he',bold),rich.run('!'),rich.run('rld',link)]);
});
test('empty paragraphs and trailing newline remain part of the value',()=>{
 assert.equal(rich.text(rich.normalize([rich.run('\n\n'),rich.run('last\n')])),'\n\nlast\n');
 assert.deepEqual(rich.normalize([]),[rich.run('')]);
});
test('rich admission rejects unsupported characters, metadata, versions and oversized payloads',()=>{
 assert.throws(()=>rich.validate([rich.run('caf\u00e9')],contract),/ASCII/);
 assert.throws(()=>rich.validate([rich.run('x',{'/unknown':{kind:'text',value:'x'}})],contract),/Formatting/);
 assert.throws(()=>rich.palette({...contract,version:2}),/Unsupported/);
 assert.throws(()=>rich.validate([rich.run('x'.repeat(65536))],contract),/limit/);
 assert.throws(()=>rich.validate([rich.run('x',{'/sys/link':{kind:'weblink',value:'javascript:alert(1)'}})],contract),/link/);
 assert.equal(rich.validate([rich.run('hello\nworld',link)],contract).length,1);
});
test('modifier order and absent versus empty modifiers select the same palette entry',()=>{
 assert.equal(rich.canonical({'/sys/modifiers':{kind:'modifiers',value:[]}}),'{}');
 assert.equal(rich.canonical({'/sys/modifiers':{kind:'modifiers',value:['bold','italic']}}),rich.canonical({'/sys/modifiers':{kind:'modifiers',value:['italic','bold']}}));
});
test('encoding or palette removal cannot silently replace a working editor',()=>{
 const element={gooEditor:{runs:[rich.run('draft',bold)],options:rich.palette(contract)}};
 assert.equal(rich.compatible(element,{editing:contract}),true);
 assert.equal(rich.compatible(element,{}),false);
 assert.equal(rich.compatible(element,{editing:{...contract,styles:contract.styles.slice(0,1)}}),false);
});
