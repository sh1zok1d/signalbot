"""Scan every blob reachable from any ref for secret / PII / infrastructure patterns.  Reports counts and paths only, never values."""
import subprocess, re, sys, collections, json, os
REPO=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); OUT=os.path.join(REPO,'docs','closure')
def run(cmd, inp=None): return subprocess.run(cmd, cwd=REPO, input=inp, capture_output=True, text=False).stdout
objs=run(['git','rev-list','--all','--objects']).decode('utf-8','replace').splitlines()
blobs={}  # sha -> path
for line in objs:
    parts=line.split(' ',1)
    if len(parts)==2 and parts[1]: blobs.setdefault(parts[0],parts[1])
shas=list(blobs)
info=run(['git','cat-file','--batch-check'], inp='\n'.join(shas).encode()).decode().splitlines()
blob_shas=[l.split()[0] for l in info if len(l.split())==3 and l.split()[1]=='blob' and int(l.split()[2])<5_000_000]
PAT={
 'telegram_bot_token': re.compile(rb'\b[0-9]{8,10}:[A-Za-z0-9_-]{35}\b'),
 'openai_key': re.compile(rb'\bsk-(proj-)?[A-Za-z0-9_-]{20,}\b'),
 'anthropic_key': re.compile(rb'\bsk-ant-[A-Za-z0-9_-]{20,}\b'),
 'aws_key': re.compile(rb'\bAKIA[0-9A-Z]{16}\b'),
 'github_token': re.compile(rb'\b(ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b'),
 'private_key_block': re.compile(rb'-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
 'generic_assignment': re.compile(rb'(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*["\'][^"\'\s]{12,}["\']'),
 'postgres_url_with_password': re.compile(rb'postgres(ql)?://[^:\s]+:[^@\s]{3,}@'),
 'redis_url_with_password': re.compile(rb'redis://[^:\s]*:[^@\s]{3,}@'),
 'public_ipv4': re.compile(rb'\b(?!10\.)(?!127\.)(?!192\.168\.)(?!172\.(1[6-9]|2[0-9]|3[01])\.)(?!0\.)(?!255\.)(\d{1,3}\.){3}\d{1,3}\b'),
 'email': re.compile(rb'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
 'telegram_chat_or_user_id_assignment': re.compile(rb'(?i)\b(chat_id|user_id|telegram_id|owner_id|tg_id|admin_id|allowed_users?)\b\s*[:=]\s*-?[0-9]{6,}'),
 'ssh_target': re.compile(rb'\bssh\s+(-\S+\s+)*[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+'),
 'hostname_assignment': re.compile(rb'(?i)\b(host|hostname|server|vps)\b\s*[:=]\s*["\']?[A-Za-z0-9-]+\.[A-Za-z0-9.-]+'),
 'dotenv_file': None,
}
SKIP_EXT=('.png','.jpg','.jpeg','.gif','.pdf','.pkl','.parquet','.gz','.zip','.npy','.npz','.woff','.ttf')
hits=collections.defaultdict(lambda: collections.defaultdict(int)); files_by_cat=collections.defaultdict(set); n=0
for sha in blob_shas:
    path=blobs[sha]
    if path.lower().endswith(SKIP_EXT): continue
    if os.path.basename(path)=='.env' or path.endswith('/.env') or re.search(r'(^|/)\.env(\.[A-Za-z0-9]+)?$',path) and not path.endswith('.example'):
        files_by_cat['dotenv_file'].add(path)
    data=run(['git','cat-file','-p',sha]); n+=1
    if b'\0' in data[:4096]: continue
    for cat,rx in PAT.items():
        if rx is None: continue
        m=rx.findall(data)
        if m:
            hits[cat][path]+=len(m); files_by_cat[cat].add(path)
rep={'blobs_scanned':n,'refs':len(run(['git','for-each-ref']).splitlines()),'by_category':{c:{'files':len(files_by_cat[c]),'matches':sum(hits[c].values()),'top_paths':sorted(hits[c].items(),key=lambda kv:-kv[1])[:40]} for c in PAT},'dotenv_files':sorted(files_by_cat['dotenv_file'])}
json.dump(rep,open(os.path.join(OUT,'GIT_HISTORY_SCAN_2026-10-15.json'),'w'),indent=1)
print(json.dumps({c:(v['files'],v['matches']) for c,v in rep['by_category'].items()},indent=0)); print('blobs',n)
