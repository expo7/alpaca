#!/usr/bin/env python3
"""Direct Quantelle paper operations. Credentials stay in production."""
import sys,subprocess,json,re,shlex
SSH=['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','deploy@172.235.49.138']
def execute(command,body=None):
 return subprocess.run(SSH+[command],input=body,text=True).returncode
if len(sys.argv)>=2 and sys.argv[1]=='probe':
 contract=sys.argv[2] if len(sys.argv)>2 else 'QQQ261120P00720000'
 if not re.fullmatch(r'[A-Z]{1,6}[0-9]{6}[CP][0-9]{8}',contract): raise SystemExit('Invalid OCC contract')
 raise SystemExit(execute('cd /opt/alpaca && docker compose exec -T web python - '+shlex.quote(contract)+' < scripts/probe_market_data.py'))
if len(sys.argv)==4 and sys.argv[1]=='api':
 method,path=sys.argv[2:]
 allowed=r'/api/(operator/(option-strategies/|lifecycle-certifications/|incidents/|research-runs/|trade-signals/(publish/|[0-9]+/lifecycle/))|trade-signals/|option-strategies/)'
 if method not in ('GET','POST') or not re.fullmatch(allowed,path): raise SystemExit('Unsupported operation')
 body=sys.stdin.read() if method=='POST' else ''
 if body: json.loads(body)
 code="""import os,json,urllib.request,urllib.error
method,path,body=json.loads(INPUT)
token=os.environ.get('QUANTELLE_RESEARCH_OPERATOR_TOKEN','')
if not token: raise SystemExit('Production operator credential missing')
req=urllib.request.Request('http://127.0.0.1:8000'+path,data=body.encode() if method=='POST' else None,method=method,headers={'Host':'quantelle.io','Authorization':'Bearer '+token,'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(req,timeout=40) as r: print(json.dumps({'http':r.status,'data':json.load(r)}))
except urllib.error.HTTPError as e:
 print(json.dumps({'http':e.code,'error':e.read().decode()[:12000]}));raise SystemExit(1)
""".replace('INPUT',repr(json.dumps([method,path,body])))
 raise SystemExit(execute('cd /opt/alpaca && docker compose exec -T web python -',code))
raise SystemExit('Usage: quantelle-ops probe [OCC] | quantelle-ops api GET|POST /api/.../ (JSON stdin for POST)')
