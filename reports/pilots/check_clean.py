"""Check a fresh Reports stack while preserving all existing pilot volumes.

The normal pilot is briefly stopped to free its localhost ports. A unique test
project gets empty volumes. Only these new volumes are removed; the original
project is restarted in finally. No secret-bearing configs/backups are written.
"""
import hashlib
import json
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[1]
    artifact = directory/'artifacts/clean-stack-verification.json'
    artifact.write_text(json.dumps({'passed': False, 'state': 'running'})+'\n')
    project = 'reports-check-'+secrets.token_hex(6)
    logs = []
    def run(label, args, check=True):
        print(label, flush=True)
        result = subprocess.run([sys.executable, *args], cwd=root, capture_output=True, text=True)
        # Every Compose line has already passed launch.py's redaction.
        logs.append(label+'\n'+result.stdout+result.stderr)
        if check and result.returncode:
            raise RuntimeError(label+' failed')
        return result
    def compose(label, args, isolated=False, check=True):
        prefix = ['--project', project] if isolated else []
        return run(label, ['reports/pilots/launch.py', *prefix, *args], check)
    fresh, restored = None, False
    try:
        compose('Preserving original volumes and stopping pilot', ['down'])
        compose('Starting isolated project with empty volumes',
                ['up', '--build', '-d', '--wait', '--wait-timeout', '240'], isolated=True)
        roles = run('Checking API/Cube/Superset key rotation and role lifecycle on fresh stack',
                    ['reports/pilots/check_roles.py'], check=False)
        if roles.returncode:
            compose('Collecting sanitized failure diagnostics', ['logs', '--tail', '40', 'api', 'cube', 'keycloak', 'superset'],
                    isolated=True, check=False)
            raise RuntimeError('Fresh role/key rotation check failed')
        acl = compose('Checking restricted Cube database reader', ['exec', '-T', 'postgres', 'psql',
            '-U', 'reports_owner', '-d', 'reports', '-Atc',
            "SELECT has_table_privilege('reports_cube','dwh.report_time_log','SELECT'),"
            "has_table_privilege('reports_cube','dwh.fact_time_log','SELECT'),"
            "has_table_privilege('reports_cube','dwh.source_record','SELECT'),"
            "has_table_privilege('reports_cube','dwh.dimension_version','SELECT'),"
            "has_table_privilege('reports_cube','dwh.source_snapshot','SELECT'),"
            "has_table_privilege('reports_cube','app.subject_binding','SELECT')"], isolated=True)
        if acl.stdout.strip() != 't|f|f|f|f|f':
            raise RuntimeError('Cube database role has excessive read access')
        fresh = run('Checking real OIDC and RLS on fresh stack', ['reports/pilots/check_bi.py'])
        fresh = json.loads(fresh.stdout)
        if not fresh.get('passed'): raise RuntimeError('Fresh BI verification failed')
        run('Checking full Reports API and jobs on fresh stack', ['reports/pilots/check_product.py'])
        compose('Checking real Kafka, redelivery and outbox in an isolated database',
                ['run','--rm','-T','--no-deps','events','python','check_events.py'],isolated=True)
    finally:
        try:
            cleanup = compose('Removing only isolated test project and its new volumes', ['down', '-v'], isolated=True, check=False)
        finally:
            recovery = compose('Restoring original pilot with its original volumes',
                               ['up', '--build', '-d', '--wait', '--wait-timeout', '240'], check=False)
            restored = recovery.returncode == 0
            (directory/'artifacts/clean-stack.log').write_text('\n'.join(logs))
            if not restored: raise RuntimeError('Original pilot restart failed; original volumes retained')
    if cleanup.returncode: raise RuntimeError('Isolated test cleanup failed')
    names = ['reports/pilots/check_clean.py', 'reports/pilots/launch.py', 'reports/pilots/compose.yaml',
             'reports/pilots/provision.py', 'reports/pilots/db.py', 'reports/pilots/etl.py',
             'reports/pilots/api.py', 'reports/pilots/check_bi.py', 'reports/pilots/check_roles.py',
             'reports/pilots/cube/cube.js', 'reports/pilots/superset/setup_bi.py',
             'reports/pilots/superset/superset_config.py', 'reports/pilots/superset/session_policy.py',
             'reports/pilots/superset/Dockerfile', 'reports/pilots/superset/cube_driver/pyproject.toml',
             'reports/pilots/superset/cube_driver/reports_cube/dialect.py',
             'reports/pilots/superset/cube_driver/reports_cube/engine.py']
    names += ['reports/pilots/'+name for name in ['product_store.py','report_engine.py','product_service.py','product_http.py','product_jobs.py','product_ui.py','product_fixture.py','product_demo.py','delivery.py','check_product.py','ui/index.html','ui/app.js','ui/styles.css']]
    names += ['reports/pilots/'+name for name in ['star.py','ops.py','events.py','event_runner.py','event_outbox.py','maintenance.py','check_events.py','requirements.txt','cube/access.js']]
    names += [str(p.relative_to(root)) for p in (directory/'cube/model').glob('*.js')]
    result = {'fresh_product_verified': True, 'fresh_kafka_verified':True, 'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': True,
              'empty_volumes': True, 'fresh_oidc_and_rls_checks': len(fresh['checks']),
              'test_volumes_removed': True, 'original_volumes_preserved': True, 'original_stack_restarted': restored,
              'cube_reader_only_prepared_view': True,
              'source_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}}
    artifact.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result)); return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'error_type': type(error).__name__, 'check': 'See sanitized clean-stack.log'}))
        sys.exit(1)
