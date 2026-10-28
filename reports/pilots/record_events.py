"""Run and record the isolated real Kafka test through the redacting launcher."""
import hashlib,json,subprocess,sys
from pathlib import Path


def main():
    base=Path(__file__).resolve().parent;root=base.parents[1];artifact=base/'artifacts/event-verification.json'
    artifact.write_text(json.dumps({'passed':False,'state':'running'})+'\n')
    result=subprocess.run([sys.executable,str(base/'launch.py'),'run','--rm','-T','--no-deps','events','python','check_events.py'],capture_output=True,text=True,cwd=root)
    (base/'artifacts/events.log').write_text(result.stdout+result.stderr)
    lines=[json.loads(s) for s in result.stdout.splitlines() if s.startswith('{')]
    output=lines[-1] if lines else {'passed':False,'reason':'See sanitized events.log'}
    output['passed']=bool(result.returncode==0 and output.get('passed'))
    from datetime import datetime,timezone
    output['checked_at_utc']=datetime.now(timezone.utc).isoformat()
    names=['events.py','ops.py','event_runner.py','event_outbox.py','maintenance.py','star.py','db.py','etl.py','check_events.py','record_events.py','compose.yaml','Dockerfile','requirements.txt']
    output['source_sha256']={str((base/n).relative_to(root)):hashlib.sha256((base/n).read_bytes()).hexdigest() for n in names}
    artifact.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output));return 0 if output['passed'] else 1


if __name__=='__main__':sys.exit(main())
