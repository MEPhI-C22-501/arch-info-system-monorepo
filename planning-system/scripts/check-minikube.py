"""Verify a deployed development module, optionally restarting its own pods.

KUBECONFIG=/path/to/config python planning-system/scripts/check-minikube.py \
    --context planning-review --restart
Uses only synthetic development data. Never prints Secret values.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
from uuid import uuid4

import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True)
    parser.add_argument('--restart',action='store_true',help='Restart only this module API and PostgreSQL')
    parser.add_argument('--ingress',action='store_true',help='Verify planning.local through the ingress-nginx addon')
    parser.add_argument('--output',default='planning-system/artifacts/minikube-report.json')
    args=parser.parse_args()
    namespace='arch-planning-system'
    command=['kubectl','--context',args.context,'--namespace',namespace]

    def kube(*parts):
        return subprocess.check_output([*command,*parts],text=True,timeout=180).strip()

    config=json.loads(kube('get','configmap','planning-config','-o','json'))['data']
    if config.get('APP_ENV')!='development' or config.get('AUTH_MODE')!='demo':
        raise RuntimeError('This smoke test requires the isolated development/demo namespace')
    claims=json.loads(kube('get','pvc','-o','json'))['items']
    if not claims or any(x['status'].get('phase')!='Bound' for x in claims):
        raise RuntimeError('All module PVCs must be Bound')
    pvc_ids={x['metadata']['name']:x['metadata']['uid'] for x in claims}

    @contextmanager
    def connect(service='planning-api',remote_port=8000,target_namespace=namespace,host=None):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        proc=subprocess.Popen(['kubectl','--context',args.context,'--namespace',target_namespace,
                               'port-forward','--address=127.0.0.1',
                               'service/'+service,f'{port}:{remote_port}'],
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15,
                              headers={'Host':host} if host else {}) as client:
                deadline=time.monotonic()+60
                while True:
                    if proc.poll() is not None:raise RuntimeError('port-forward exited')
                    try:
                        response=client.get('/readyz')
                        if response.status_code==200:break
                    except httpx.TransportError:pass
                    if time.monotonic()>deadline:raise RuntimeError('API readiness timeout')
                    time.sleep(.5)
                yield client
        finally:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)

    def headers(role='R-02'):
        return {'Authorization':'Bearer demo-'+role,'Idempotency-Key':str(uuid4())}

    def checked(response,code=200):
        if response.status_code!=code:raise RuntimeError(f'HTTP {response.status_code}: {response.text[:200]}')
        return response

    with connect() as client:
        workspace=checked(client.get('/api/v1/workspace',headers=headers())).json()
        marker=checked(client.post('/api/v1/projects',headers=headers(),json={
            'portfolioId':workspace['portfolioId'],'programId':None,'code':'SMOKE-'+uuid4().hex[:8],
            'name':'Проверка сохранности PVC','goal':'Синтетический smoke test','managerSubject':'demo-R-03'}),201).json()
        content=b'Planning System PVC persistence fixture\n'
        attachment=checked(client.post('/api/v1/attachments',headers=headers(),
            data={'ownerType':'PROJECT','ownerId':marker['id']},
            files={'file':('pvc-smoke.txt',content,'text/plain')}),201).json()

    # The seed must preserve the marker and leave row counts unchanged.
    count_code="from sqlalchemy import select,func; from server import storage as d; c=d.engine.connect(); print(c.execute(select(func.count()).select_from(d.records)).scalar())"
    before_count=kube('exec','deployment/planning-api','--','python','-c',count_code)
    kube('exec','deployment/planning-api','--','python','-m','server.manage','seed')
    if before_count!=kube('exec','deployment/planning-api','--','python','-c',count_code):
        raise RuntimeError('Seed changed an existing dataset')

    if args.restart:
        kube('delete','pod','postgres-0','--wait=true')
        kube('rollout','status','statefulset/postgres','--timeout=120s')
        kube('rollout','restart','deployment/planning-api')
        kube('rollout','status','deployment/planning-api','--timeout=120s')
    with connect() as client:
        saved=checked(client.get('/api/v1/projects/'+marker['id'],headers=headers())).json()
        if saved!=marker:raise RuntimeError('Project changed after seed/restart')
        downloaded=checked(client.get('/api/v1/attachments/'+attachment['id']+'/content',headers=headers())).content
        if downloaded!=content:raise RuntimeError('File content changed after seed/restart')
    after_claims=json.loads(kube('get','pvc','-o','json'))['items']
    if pvc_ids!={x['metadata']['name']:x['metadata']['uid'] for x in after_claims}:
        raise RuntimeError('PVCs were replaced')
    if args.ingress:
        with connect('ingress-nginx-controller',80,'ingress-nginx','planning.local') as client:
            checked(client.get('/readyz'))
            if 'Planning System' not in checked(client.get('/')).text:
                raise RuntimeError('Ingress did not return the Planning System UI')
    report={'context':args.context,'namespace':namespace,'mode':'development / synthetic / mock',
            'checks':{'readiness':True,'pvcBound':True,'seedIdempotent':True,
                      'postgresAndApiRestart':args.restart,'projectPersisted':True,'filePersisted':True,
                      'samePvcIds':True,'ingressRouting':args.ingress},'fileSha256':hashlib.sha256(content).hexdigest(),
            'pvcNames':sorted(pvc_ids),'errors':[]}
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
