import fcntl,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
root=Path('/Users/ianchanner/.local/share/shrine')
names=['v5/native','development/recursive-binding/world-relay-live','codex/native']+[str(p.parent.parent.relative_to(root)) for p in sorted((root/'development').rglob('pins.pack')) if p.stat().st_blocks*512>80*1024**2 and p.stat().st_blocks*512>=p.stat().st_size*.9 and 'start-finish-v3' not in str(p) and all(n not in str(p) for n in ['grove-personal-v23','grove-native-material-v16','grove-self-construction-v4','grove-personal-v22','grove-personal-v25'])]
reports=[]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
for name in names:
 if shutil.disk_usage(root).free>6*1024**3:break
 world=root/name;source=world/'snap/pins.pack';temp=source.with_name('pins.compressed-check')
 with (world/'owner.lock').open('a+b') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:
   print('SKIP active owner',name,flush=True);continue
  opened=subprocess.run(['lsof','-t','--',str(source)],capture_output=True,text=True)
  if opened.stdout.strip():print('SKIP open file',name,flush=True);continue
  if temp.exists():raise RuntimeError('Unexpected recovery temporary file; preserve and inspect')
  before=source.stat();fingerprint=digest(source)
  print('Compressing inactive file',name,before.st_size,flush=True)
  try:
   subprocess.run(['ditto','--hfsCompression','--rsrc','--acl',str(source),str(temp)],check=True)
   after=temp.stat();current=source.stat()
   if digest(temp)!=fingerprint or (current.st_ino,current.st_size,current.st_mtime_ns)!=(before.st_ino,before.st_size,before.st_mtime_ns):raise RuntimeError('Content or source changed; refusing replacement')
   if after.st_blocks>=before.st_blocks:
    print('No physical saving',name,flush=True);temp.unlink();continue
   os.replace(temp,source)
   saved=(before.st_blocks-after.st_blocks)*512
   record={'world':name,'logical_bytes':before.st_size,'sha256':fingerprint,'physical_bytes_saved':saved,'same_path':str(source)};reports.append(record)
   Path('work/storage-recovery/verified-oct05-extra.json').write_text(json.dumps(reports,indent=2))
   print('Verified identical bytes; saved',round(saved/1024**2),'MiB; free',round(shutil.disk_usage(root).free/1024**2),'MiB',flush=True)
  finally:
   if temp.exists():temp.unlink()
print('Free MiB',round(shutil.disk_usage(root).free/1024**2),flush=True)
