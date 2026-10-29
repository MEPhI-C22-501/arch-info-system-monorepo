"""All Cube measure families against real PostgreSQL and signed local JWTs."""
import hashlib,json,os,subprocess,sys,tempfile,threading,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import fasteners,jwt,pgserver
from cryptography.hazmat.primitives.asymmetric import rsa
from db import Database
from check_cube import free_port
sys.path.insert(0,str(Path(__file__).with_name('tests')))
from test_product import seed,claims,QUERY,MEMBER_1,MEMBER_2,ADMIN
from report_engine import Engine,AN,MB,PM,TL,QA


def main():
    artifact=Path(__file__).with_name('artifacts')/'semantic-verification.json'
    artifact.write_text(json.dumps({'passed':False,'state':'running'})+'\n')
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));jwk.update(kid='semantic-ephemeral',use='sig',alg='RS256')
    class Keys(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'keys':[jwk]}).encode())
    keys=ThreadingHTTPServer(('127.0.0.1',0),Keys);threading.Thread(target=keys.serve_forever,daemon=True).start()
    issuer=f'http://127.0.0.1:{keys.server_port}';checks=[]
    with tempfile.TemporaryDirectory(prefix='rs-',dir='/tmp') as tmp:
        pgserver.PostgresServer.runtime_path=Path(tmp)/'run';pgserver.PostgresServer._lock=fasteners.InterProcessLock(Path(tmp)/'lock')
        server=pgserver.get_server(Path(tmp)/'data',cleanup_mode='delete');cube=None;db=None
        try:
            uri=server.get_uri();db=Database(uri);db.initialize();data=seed(db)
            project=data['tracker']['work-items'][0]['projectId']
            with db.transaction():
                for role in [PM,TL,QA]:db.execute('INSERT INTO app.user_scope VALUES (?,?,?,?)',(ADMIN,role,project,''))
            expected={f'R-{i:02d}':Engine(db).query(f'R-{i:02d}',claims(),QUERY)['totals'] for i in range(1,12)};db.connection.commit()
            host=urllib.parse.parse_qs(urllib.parse.urlsplit(uri).query)['host'][0];port=free_port()
            env=dict(os.environ,CUBEJS_DB_TYPE='postgres',CUBEJS_DB_HOST=host,CUBEJS_DB_NAME='postgres',CUBEJS_DB_USER='postgres',CUBEJS_DEV_MODE='false',CUBEJS_CACHE_AND_QUEUE_DRIVER='memory',CUBEJS_TELEMETRY='false',CUBEJS_PRE_AGGREGATIONS_SCHEMA='reports_preaggregations',CUBEJS_PRE_AGGREGATIONS_BUILDER='true',CUBEJS_LOG_LEVEL='error',REPORTS_OIDC_ISSUER=issuer,REPORTS_OIDC_JWKS_URL=issuer,REPORTS_CUBE_CONFIG=str(Path(__file__).with_name('cube')/'cube.js'),PORT=str(port),CUBEJS_PG_SQL_PORT=str(free_port()))
            script="const S=require('@cubejs-backend/server');const c=require(process.env.REPORTS_CUBE_CONFIG);c.logger=()=>{};new S(c).listen().catch(()=>process.exit(1));"
            cube=subprocess.Popen([os.getenv('NODE','node'),'-e',script],cwd=Path(__file__).with_name('cube'),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            def token(role=AN,subject=ADMIN,scope=''):
                return jwt.encode(dict(iss=issuer,aud='reports',sub=subject,iat=int(time.time()),exp=int(time.time())+600,scope=scope,resource_access={'reports':{'roles':[role]}}),key,algorithm='RS256',headers={'kid':'semantic-ephemeral'})
            def request(route,q=None,access=None):
                url=f'http://127.0.0.1:{port}/cubejs-api/v1/'+route
                if q:url+='?'+urllib.parse.urlencode({'query':json.dumps(q)})
                req=urllib.request.Request(url,headers={'Authorization':access or token()})
                try:
                    with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
                except urllib.error.HTTPError as e:
                    body=json.load(e)
                    # Cube messages for these synthetic queries contain no DSN/token.
                    raise RuntimeError('Cube HTTP '+str(e.code)+': '+str(body.get('error','query failed'))) from None
            for _ in range(90):
                if cube.poll() is not None:raise RuntimeError('Cube semantic server failed')
                try:request('meta');break
                except (urllib.error.URLError,TimeoutError):time.sleep(1)
            else:raise RuntimeError('Cube semantic readiness failed')
            def query(measures,dimensions=None,access=None,**extra):
                q=dict(measures=measures,**extra)
                if dimensions:q['dimensions']=dimensions
                for _ in range(90):
                    result=request('load',q,access)
                    if result.get('error')=='Continue wait':time.sleep(.5);continue
                    if result.get('error'):raise RuntimeError('Cube semantic query failed')
                    return result['data']
                raise RuntimeError('Cube semantic timeout')
            def equal(measure,wanted,**kwargs):
                rows=query([measure],**kwargs);actual=rows[0].get(measure) if rows else None
                if actual is not None:
                    try:actual=float(actual)
                    except (ValueError,TypeError):pass
                if isinstance(wanted,(int,float)):
                    if actual is None or abs(actual-wanted)>0.0001:raise AssertionError(f'{measure}: {actual} != {wanted}')
                elif actual!=wanted:raise AssertionError(f'{measure}: unexpected null/value')
                checks.append(measure)
            equal('TimeLogs.hours',expected['R-01']['M-01'])
            equal('PlanFact.overrun',1.25,timeDimensions=[{'dimension':'PlanFact.period','dateRange':['2026-10-01','2026-10-31']}])
            equal('PlanFact.overrun',0,timeDimensions=[{'dimension':'PlanFact.period','dateRange':['2026-10-01','2026-10-03']}])
            equal('TimeLogs.velocity',expected['R-06']['M-07'],timeDimensions=[{'dimension':'TimeLogs.loggedDate','dateRange':['2026-10-04','2026-10-31']}])
            for member,wanted in [('plannedHours',10),('remainingHours',-1.25),('overrun',1.25),('overdue',0),('completionPercent',100),('cycleMedian',3),('cycleP85',3),('leadMedian',3),('leadP85',3),('throughput',1),('estimateErrorPercent',12.5),('correctionCoefficient',1.125)]:equal('WorkItems.'+member,wanted)
            for member,wanted in [('opened',1),('remaining',1),('closeMedian',2)]:equal('Defects.'+member,wanted)
            for member,wanted in [('closed',1),('reopened',1),('reopenPercent',100)]:equal('DefectFlow.'+member,wanted)
            equal('TestResults.passPercent',100);equal('TestRuns.passPercent',100);equal('TestRuns.executionPercent',100)
            equal('Resources.deficitHours',12);equal('Resources.utilizationPercent',None)
            equal('Resources.utilizationPercent',46.875,filters=[{'member':'Resources.userId','operator':'equals','values':[MEMBER_1]}])
            equal('Resources.deficitHours',None,timeDimensions=[{'dimension':'Resources.day','dateRange':['2026-10-01','2026-10-07']}])
            equal('StatusFlow.averageWip',3/7,timeDimensions=[{'dimension':'StatusFlow.day','dateRange':['2026-10-01','2026-10-07']}])
            equal('Quality.defectDensity',None);equal('Quality.candidateDefectDensity',10);equal('Forecasts.forecastFinish',None)
            forecast=data['planning']['forecast'][0];forecast['data'].update(budgetAdjustment=100,estimatedTotalCost=500,currencyCode='RUB')
            from etl import load,now
            at=now();assert load(db,'planning',lambda:({'forecast':[forecast]},at,at,None))['status']=='LOADED'
            equal('Forecasts.budgetAdjustment',100,dimensions=['Forecasts.currency'],access=token(scope='cost.read'))
            equal('TimeLogs.hours',3.75,access=token(MB,MEMBER_1))
            for role in [PM,TL]:equal('WorkItems.plannedHours',10,access=token(role))
            equal('TestRuns.executionPercent',100,access=token(QA));equal('WorkItems.plannedHours',None,access=token(MB,MEMBER_2))
            for q,access in [({'measures':['Resources.hours']},token(MB,MEMBER_1)),({'measures':['Forecasts.budgetAdjustment'],'dimensions':['Forecasts.currency']},token()),({'measures':['WorkItems.plannedHours']},token(PM,MEMBER_2))]:
                try:request('load',q,access)
                except RuntimeError:checks.append('permission-denied')
                else:raise AssertionError('Unauthorized Cube query succeeded')
            result={'passed':True,'checks':checks,'real_cube':True,'real_postgres':True,'m16_approved':False,'source_integrations_verified':False}
            root=Path(__file__).resolve().parents[2];sources=[Path(__file__),Path(__file__).with_name('star.py'),*(p for p in Path(__file__).with_name('cube').rglob('*.js') if p.is_file() and 'node_modules' not in p.parts)]
            result['source_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
            artifact.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0
        finally:
            if cube:
                cube.terminate()
                try:cube.wait(timeout=15)
                except subprocess.TimeoutExpired:cube.kill();cube.wait()
            if db:db.close()
            server.cleanup();keys.shutdown();keys.server_close()


if __name__=='__main__':sys.exit(main())
