"""Dump a synthetic Compose database and restore into a new temporary database.

Stops only the specified development worker for a consistent comparison.
The original database is never restored over or deleted. Temporary clone is removed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--compose',default='planning-system/compose.yaml')
    parser.add_argument('--output',default='planning-system/artifacts/restore-report.json')
    args=parser.parse_args()
    compose=['docker','compose','-p',args.project,'-f',args.compose]

    def run(parts,**kwargs):
        return subprocess.run(parts,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=120,**kwargs).stdout

    guard=run([*compose,'exec','-T','api','python','-c',
               "import os; print(os.getenv('APP_ENV')+':'+os.getenv('AUTH_MODE'))"]).decode().strip()
    if guard!='development:demo':raise RuntimeError('Only an isolated development/demo stand is allowed')
    postgres=[*compose,'exec','-T','postgres']
    clone='planning_restore_'+uuid4().hex[:12]
    was_running=bool(run([*compose,'ps','--status','running','-q','worker']).strip())
    created=False
    query="SELECT json_build_object('records',(SELECT md5(coalesce(string_agg(row_to_json(r)::text,'' ORDER BY kind,id),'')) FROM records r),'audit',(SELECT md5(coalesce(string_agg(row_to_json(a)::text,'' ORDER BY id),'')) FROM audit a),'requests',(SELECT md5(coalesce(string_agg(row_to_json(q)::text,'' ORDER BY id),'')) FROM request_results q),'migrations',(SELECT count(*) FROM schema_versions));"

    def fingerprint(database):
        return json.loads(run([*postgres,'psql','-U','planning','-d',database,'-Atc',query]))

    try:
        if was_running:run([*compose,'stop','worker'])
        original=fingerprint('planning')
        start=time.monotonic()
        backup=run([*postgres,'pg_dump','-U','planning','-Fc','planning'])
        backup_seconds=time.monotonic()-start
        if fingerprint('planning')!=original:raise RuntimeError('Database changed during backup; retry on an idle stand')
        run([*postgres,'createdb','-U','planning',clone]);created=True
        start=time.monotonic()
        run([*postgres,'pg_restore','-U','planning','--exit-on-error','-d',clone],input=backup)
        restore_seconds=time.monotonic()-start
        if fingerprint(clone)!=original:raise RuntimeError('Restored snapshots/audit/requests differ')
        has_baseline=run([*postgres,'psql','-U','planning','-d',clone,'-Atc',
                         "SELECT count(*) FROM records WHERE kind='plan' AND data->>'status'='ACTIVE';"]).strip()
        if int(has_baseline)==0:raise RuntimeError('Activate a synthetic baseline before running the restore check')
        protected=subprocess.run([*postgres,'psql','-U','planning','-d',clone,'-v','ON_ERROR_STOP=1','-c',
            "UPDATE records SET data=jsonb_set(data,'{name}','\"must be rejected\"') WHERE kind='plan' AND data->>'status'='ACTIVE';"],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if protected.returncode==0 or b'Approved plan content is immutable' not in protected.stderr:
            raise RuntimeError('Restored baseline trigger did not reject a direct mutation')
        if fingerprint(clone)!=original:raise RuntimeError('Rejected mutation changed restored data')
        report={'mode':'local synthetic Compose; not shared-stand RPO/RTO acceptance',
                'checks':{'dumpRestored':True,'sameSnapshotsAuditAndRequests':True,'baselineTriggerRestored':True},
                'backupSeconds':round(backup_seconds,3),'restoreSeconds':round(restore_seconds,3),
                'backupSha256':hashlib.sha256(backup).hexdigest(),'backupBytes':len(backup),'errors':[]}
        output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        if created:run([*postgres,'dropdb','-U','planning',clone])
        if was_running:run([*compose,'start','worker'])


if __name__=='__main__':main()
