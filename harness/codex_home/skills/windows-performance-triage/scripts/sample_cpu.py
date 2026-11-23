"""Read-only CPU/Git sampler, promoted from the existing local diagnostic helper.
The original temporary file is retained as historical provenance, not a second
maintained implementation. No full process command lines are stored.
"""
import argparse, tempfile, struct
import ctypes as C,ctypes.wintypes as W,time,json,os,pathlib,datetime,collections,re,sys
parser=argparse.ArgumentParser(description='Bounded read-only Windows CPU and Git metadata sampling.')
parser.add_argument('samples',nargs='?',type=int,help='Legacy sample-count argument, 1..240.')
parser.add_argument('--seconds',type=float,help='Requested sampling duration, 1..60 seconds; default20.')
parser.add_argument('--output-dir',type=pathlib.Path,help='Local report directory; default system temporary directory.')
args=parser.parse_args()
if args.samples is not None and args.seconds is not None:parser.error('Use either samples or --seconds.')
if args.samples is not None and not 1<=args.samples<=240:parser.error('samples must be in1..240.')
if args.seconds is not None and not 1<=args.seconds<=60:parser.error('--seconds must be in1..60.')
if os.name!='nt' or struct.calcsize('P')!=8:parser.error('This sampler supports64-bit Windows Python only.')
sample_count=args.samples if args.samples is not None else int((args.seconds or 20)*4)
duration=args.samples*.25 if args.samples is not None else args.seconds or 20
output_dir=(args.output_dir or pathlib.Path(tempfile.gettempdir())).expanduser().resolve()
output_dir.mkdir(parents=True,exist_ok=True)
k=C.WinDLL('kernel32',use_last_error=True);n=C.WinDLL('ntdll');k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)];k.CloseHandle.argtypes=[W.HANDLE];k.GetSystemTimes.argtypes=[C.POINTER(W.FILETIME)]*3;n.NtQueryInformationProcess.argtypes=[W.HANDLE,W.ULONG,C.c_void_p,W.ULONG,C.POINTER(W.ULONG)]
class US(C.Structure):_fields_=[('Length',W.USHORT),('MaximumLength',W.USHORT),('Buffer',C.c_void_p)]
class SPI(C.Structure):_fields_=[('Next',W.ULONG),('Threads',W.ULONG),('PrivateWS',C.c_int64),('HardFaults',W.ULONG),('ThreadHighWater',W.ULONG),('Cycles',C.c_uint64),('Created',C.c_int64),('User',C.c_int64),('Kernel',C.c_int64),('Image',US),('Priority',W.LONG),('PID',C.c_void_p),('PPID',C.c_void_p)]
assert SPI.PID.offset==80
n.NtQuerySystemInformation.argtypes=[W.ULONG,C.c_void_p,W.ULONG,C.POINTER(W.ULONG)];n.NtQuerySystemInformation.restype=W.LONG

def snapshot():
 f=[W.FILETIME() for _ in range(3)];k.GetSystemTimes(*[C.byref(x) for x in f]);tot=[x.dwLowDateTime+(x.dwHighDateTime<<32) for x in f];size=4*1024*1024
 while True:
  b=C.create_string_buffer(size);r=W.ULONG();st=n.NtQuerySystemInformation(5,b,size,C.byref(r))
  if st>=0:break
  if st&0xffffffff!=0xc0000004 or size>=32*1024*1024:raise OSError(st)
  size=max(size*2,r.value+65536)
 base=C.addressof(b);off=0;rows={}
 for i in range(3000):
  p=SPI.from_buffer(b,off);name=''
  if p.Image.Buffer and base<=p.Image.Buffer<base+size and p.Image.Length<=1024:name=C.string_at(p.Image.Buffer,p.Image.Length).decode('utf-16le','replace')
  pid=int(p.PID or 0);rows[(pid,p.Created)]={'pid':pid,'parent':int(p.PPID or 0),'name':name,'cpu':p.User+p.Kernel,'kernel':p.Kernel,'threads':p.Threads}
  if not p.Next:break
  off+=p.Next
 return tot,rows

def read(h,a,l):
 b=C.create_string_buffer(l);r=C.c_size_t()
 if not k.ReadProcessMemory(h,a,b,l,C.byref(r)):raise OSError(C.get_last_error())
 return b.raw[:r.value]
def string(h,a):
 b=read(h,a,16);length=int.from_bytes(b[:2],'little');addr=int.from_bytes(b[8:16],'little')
 if length>32768:raise ValueError('oversize')
 return read(h,addr,length).decode('utf-16le','replace')
def git_info(p,by):
 chain=[];parent=p['parent']
 for i in range(6):
  if parent not in by:break
  q=by[parent];chain.append(q['name']);parent=q['parent']
 owner='Codex agent' if 'codex.exe' in chain else 'Codex desktop' if 'ChatGPT.exe' in chain and not any(x in chain[:chain.index('ChatGPT.exe')] for x in ['python.exe','pwsh.exe','powershell.exe']) else 'Antigravity' if any(x in chain for x in ['language_server.exe','Antigravity.exe','Antigravity-x64.exe']) else 'Other'
 d={'owner':owner,'ancestors':chain};h=k.OpenProcess(0x410,False,p['pid'])
 if not h:return d
 try:
  info=C.create_string_buffer(48);r=W.ULONG();assert n.NtQueryInformationProcess(h,0,info,48,C.byref(r))==0;peb=int.from_bytes(info.raw[8:16],'little');params=int.from_bytes(read(h,peb+0x20,8),'little');cwd=string(h,params+0x38);cmd=string(h,params+0x70);m=re.search(r'(?:^|\s)(status|diff|add|rev-parse|ls-files|hash-object|write-tree|fsmonitor--daemon)(?:\s|$)',cmd);fs=re.search(r'core\.fsmonitor=([^\s"]*)',cmd);d.update({'cwd':cwd,'operation':m.group(1) if m else 'metadata/other','fsmonitor_argument':(fs.group(1) if fs.group(1) in ('','true','false','0','1') else 'custom_hook') if fs else 'not_explicit'})
 except (OSError,ValueError,AssertionError):pass
 finally:k.CloseHandle(h)
 return d
start=datetime.datetime.now().astimezone().isoformat(timespec='seconds');a,prev=snapshot();cache={};samples=[];group_ticks=collections.Counter();all_ticks=0;count=sample_count;deadline=time.monotonic()+duration
for i in range(count):
 remaining=deadline-time.monotonic()
 if remaining<=0:break
 time.sleep(min(.25,remaining));b,cur=snapshot();total=(b[1]-a[1])+(b[2]-a[2]);all_ticks+=total;by={p['pid']:p for p in cur.values()};top=[]
 for key,p in cur.items():
  if p['name'].lower() in ['git.exe','git-lfs.exe'] and key not in cache:cache[key]={'pid':p['pid'],**git_info(p,by)}
  if key not in prev or p['pid']==0:continue
  ticks=p['cpu']-prev[key]['cpu'];group=p['name'];extra=cache.get(key)
  if extra:group+=' ['+extra['owner']+']'
  group_ticks[group]+=ticks;cpu=ticks/total*100
  if cpu>=1.5:
   row={x:p[x] for x in ['pid','name','threads']};row['cpu_pct']=round(cpu,2)
   if extra:row.update(extra)
   top.append(row)
 top.sort(key=lambda x:x['cpu_pct'],reverse=True);samples.append({'time':datetime.datetime.now().astimezone().isoformat(timespec='milliseconds'),'cpu_pct':round((total-(b[0]-a[0]))/total*100,2),'kernel_pct':round(((b[1]-a[1])-(b[0]-a[0]))/total*100,2),'top':top[:8]});a,prev=b,cur
summary={'started':start,'ended':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'average_cpu_pct':round(sum(x['cpu_pct'] for x in samples)/len(samples),2),'peak_cpu_pct':max(x['cpu_pct'] for x in samples),'samples_at_least_80_pct':sum(x['cpu_pct']>=80 for x in samples),'sample_count':len(samples),'observed_average_cpu_by_process_group':[{ 'process_group':g,'cpu_pct':round(t/all_ticks*100,2)} for g,t in group_ticks.most_common(12)],'limitations':'Short-lived processes born and exited between samples can be missed; parent-chain ownership is inferred; process and system timestamps differ slightly. Background workloads are uncontrolled.'};observations=list(cache.values());p=output_dir/('pc-live-load-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json');p.write_text(json.dumps({'summary':summary,'samples':samples,'git_observations':observations},ensure_ascii=False,indent=2),encoding='utf-8');(output_dir/'pc-live-load-latest.txt').write_text(str(p),encoding='utf-8');print(json.dumps({'report':str(p),'summary':summary,'git_observation_count':len(observations),'peak_sample':max(samples,key=lambda x:x['cpu_pct'])},ensure_ascii=False))
