// Pure production byte contracts; no hand-built legacy DOM or live namespace.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source = await readFile(new URL('./values.js', import.meta.url));
const {parseValueMetadata, valueWindowURL, parseValueChunk, renderValueWindow} =
  await import('data:text/javascript;base64,' + source.toString('base64'));
const epoch = '900719925474099312345', path = '/demo', slot = '/text';
const url = '/debug-read/value?path=/demo&slot=/text&epoch=' + epoch + '&offset=0&limit=4096';
const data = {valueState:'preview',previewReason:'byte-limit',valueBytes:'8200',valuePreviewBytes:'2048',
  valueEpoch:epoch,valueRepresentation:'utf8-bytes',valueUrl:url};
const metadata = (overrides = {}, target = path) => parseValueMetadata({dataset:{...data,...overrides}},target,slot);
assert.equal(parseValueMetadata({dataset:{}},path,slot).state,'unknown');
assert.equal(metadata().epoch,epoch);
assert.equal(metadata({valueState:'complete',previewReason:'',valueBytes:'0',valuePreviewBytes:'0'}).bytes,'0');
for (const invalid of [
  {valueState:'invented'}, {valueState:'complete'}, {previewReason:'invented'},
  {valueBytes:'01'}, {valueBytes:8200}, {valueEpoch:'1e20'}, {valuePreviewBytes:'8201'},
  {valueRepresentation:'json'}, {valueState:'opaque',previewReason:'semantic-summary'},
  {valueUrl:'https://foreign.invalid' + url}, {valueUrl:url + '&epoch=2'},
  {valueUrl:url + '&extra=1'}, {valueUrl:url + '#fragment'},
  {valueUrl:url.replace('offset=0','offset=1')}, {valueUrl:url.replace('/demo','/other')},
  {valueUrl:url.replace('limit=4096','limit=65537')}, {valueUrl:url.replace('limit=4096','limit=0')},
]) assert.throws(() => metadata(invalid),JSON.stringify(invalid));
for (const target of ['/h/z/1/0/demo','/x/demo','/o/demo'])
  assert.throws(() => metadata({valueUrl:url.replace('/demo',target)},target));
for (const target of ['demo','/demo/','//demo','/demo/../other']) assert.throws(() => metadata({},target));
for (const start of ['-1','01','1e3','8201']) assert.throws(() => valueWindowURL(metadata(),start));
const first = valueWindowURL(metadata()), second = valueWindowURL(metadata(),'4096');
assert.deepEqual([first.offset,first.limit,first.end],['0',4099,'4096']);
assert.deepEqual([second.offset,second.limit,second.end],['4093',4102,'8192']);
assert.equal(new URL(second.url,'http://inert.invalid').searchParams.get('epoch'),epoch);

function response(bytes, request) {
  const offset = Number(request.offset), end = Math.min(bytes.length,offset + request.limit);
  return {version:1,path:request.path,slot:request.slot,epoch:request.epoch,recordEpoch:'7',
    type:request.representation === 'utf8-bytes' ? 'text' : 'natural',
    representation:request.representation,encoding:'hex',total:String(bytes.length),offset:request.offset,
    next:end === bytes.length ? null : String(end),complete:end === bytes.length,
    hex:bytes.subarray(offset,end).toString('hex')};
}
// Each scalar belongs to the window containing its leading byte.
for (const scalar of ['é','λ','日','😀']) for (let lead = 4093; lead < 4097; lead++) {
  const text = 'a'.repeat(lead) + scalar + 'b'.repeat(4200);
  const bytes = Buffer.from(text), meta = metadata({valueBytes:String(bytes.length)});
  let reconstructed = '', raw = [];
  for (let start = 0; start < bytes.length; start += 4096) {
    const request = valueWindowURL(meta,String(start));
    const window = renderValueWindow(parseValueChunk(response(bytes,request),request),request);
    assert.equal(window.format,'utf8'); reconstructed += window.text; raw.push(window.bytes);
  }
  assert.equal(reconstructed,text); assert.deepEqual(Buffer.concat(raw),bytes);
}
for (const bytes of [Buffer.from([0,1,255]),Buffer.from([0xc0,0xaf]),Buffer.from([0xe2,0x82])]) {
  const request = valueWindowURL(metadata({valueBytes:String(bytes.length),valuePreviewBytes:''}));
  const window = renderValueWindow(parseValueChunk(response(bytes,request),request),request);
  assert.equal(window.format,'hex'); assert.deepEqual(Buffer.from(window.bytes),bytes);
}
const bytes = Buffer.from('exact'), request = valueWindowURL(metadata({valueBytes:'5',valuePreviewBytes:'5'}));
const valid = response(bytes,request);
assert.deepEqual(Buffer.from(parseValueChunk(valid,request).bytes),bytes);
for (const invalid of [null,[],{...valid,extra:true},...[
  ['version',2],['epoch','1'],['recordEpoch',epoch + '0'],['path','/other'],['slot','/other'],
  ['representation','natural-le-bytes'],['total','05'],['offset','1'],['encoding','base64'],
  ['hex','65'],['hex','GG'],['hex','657861637'],['next','5'],['complete',false],['type','natural'],
].map(([key,value])=>({...valid,[key]:value}))]) assert.throws(() => parseValueChunk(invalid,request));
const natural = valueWindowURL(metadata({valueRepresentation:'natural-le-bytes',valueBytes:'5',valuePreviewBytes:'5'}));
const window = renderValueWindow(parseValueChunk(response(bytes,natural),natural),natural);
assert.equal(window.format,'hex'); assert.equal(window.text,'65 78 61 63 74');
console.log('PASS: exact metadata, endpoint identity, epochs, strict chunks, UTF-8 boundaries, and lossless byte fallback.');
