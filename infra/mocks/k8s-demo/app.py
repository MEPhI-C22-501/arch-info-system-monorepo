"""Infrastructure demo only: mock UI/API, real PostgreSQL/S3/Kafka/Keycloak calls."""
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TEAMS = ['planning-system', 'task-tracker', 'reference-manager', 'qa', 'reports']
TEAM = os.getenv('TEAM', 'gateway')
ROLE = os.getenv('ROLE', 'api')
TOPIC = 'dev.infra.examples.v1'


def http(url, data=None, headers=None):
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def database():
    import psycopg
    return psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=5)


def migrate():
    for attempt in range(60):
        try:
            with database() as db:
                db.execute('CREATE TABLE IF NOT EXISTS infra_demo_record '
                           '(id uuid PRIMARY KEY, message text NOT NULL, created_at timestamptz DEFAULT now())')
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(2)
    print('Demo migration completed', flush=True)


def etl():
    rows = json.loads(http('http://backend.arch-task-tracker.svc.cluster.local:8080/api/records'))['rows']
    with database() as db:
        for row in rows:
            db.execute('INSERT INTO infra_demo_record(id,message) VALUES(%s,%s) ON CONFLICT(id) '
                       'DO UPDATE SET message=excluded.message', (row['id'], 'ETL from tracker: ' + row['message']))
    print(json.dumps({'source': 'task-tracker REST API', 'target': 'reports PostgreSQL',
                      'loaded': len(rows), 'mock': True}), flush=True)


def kafka_config():
    return {
        'bootstrap.servers': 'kafka.arch-infra.svc.cluster.local:9092',
        'security.protocol': 'SASL_SSL', 'sasl.mechanism': 'PLAIN',
        'sasl.username': 'example', 'sasl.password': os.environ['KAFKA_EXAMPLE_PASSWORD'],
        'ssl.ca.location': '/kafka/kafka.crt',
        'ssl.endpoint.identification.algorithm': 'https',
        'socket.timeout.ms': 10000, 'log_level': 0,
    }


def token():
    body = urllib.parse.urlencode({
        'grant_type': 'client_credentials', 'client_id': 'example-caller',
        'client_secret': os.environ['KC_EXAMPLE_CALLER_SECRET'],
    }).encode()
    return json.loads(http(os.environ['KEYCLOAK_URL'] +
                           '/realms/arch-info-system/protocol/openid-connect/token', body))['access_token']


def verify_token(value):
    import jwt
    client = jwt.PyJWKClient(os.environ['KEYCLOAK_URL'] +
                            '/realms/arch-info-system/protocol/openid-connect/certs')
    key = client.get_signing_key_from_jwt(value).key
    return jwt.decode(value, key, algorithms=['RS256'], audience='example-api',
                      issuer='http://localhost:18081/realms/arch-info-system')


def check_services():
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    result = {}
    with database() as db:
        db.execute('SELECT 1 FROM infra_demo_record LIMIT 1')
    result['postgres'] = 'ok'
    claims = verify_token(token())
    result['keycloak'] = {'status': 'ok', 'subject': claims['sub'], 'audience': claims['aud']}
    client = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT'],
                          aws_access_key_id=os.environ['S3_ACCESS_KEY'],
                          aws_secret_access_key=os.environ['S3_SECRET_KEY'],
                          region_name='us-east-1', config=Config(s3={'addressing_style': 'path'}))
    key = 'infra-demo/' + str(uuid.uuid4())
    client.put_object(Bucket=os.environ['S3_BUCKET'], Key=key, Body=TEAM.encode())
    assert client.get_object(Bucket=os.environ['S3_BUCKET'], Key=key)['Body'].read() == TEAM.encode()
    client.delete_object(Bucket=os.environ['S3_BUCKET'], Key=key)
    foreign = 'arch-dev-qa' if TEAM == 'reports' else 'arch-dev-reports'
    try:
        client.head_bucket(Bucket=foreign)
    except ClientError as error:
        if error.response['ResponseMetadata']['HTTPStatusCode'] != 403:
            raise
    else:
        raise RuntimeError('Foreign bucket unexpectedly accessible')
    result['s3'] = {'status': 'ok', 'bucket': os.environ['S3_BUCKET'], 'foreignBucket': 'denied'}
    # A real OTLP/HTTP request; visible in the Collector file/debug exporter.
    now = str(time.time_ns())
    payload = {'resourceLogs': [{'resource': {'attributes': [
        {'key': 'service.name', 'value': {'stringValue': 'demo-' + TEAM}}]},
        'scopeLogs': [{'logRecords': [{'timeUnixNano': now,
            'severityText': 'INFO', 'body': {'stringValue': 'Kubernetes infrastructure demo'}}]}]}]}
    http('http://otel-collector.arch-infra.svc.cluster.local:4318/v1/logs',
         json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    result['otlp'] = 'accepted'
    return result


def publish(message):
    from confluent_kafka import Producer
    event = {'eventId': str(uuid.uuid4()), 'source': TEAM, 'message': message}
    producer = Producer(kafka_config())
    errors = []
    producer.produce(TOPIC, key=event['eventId'], value=json.dumps(event),
                     on_delivery=lambda error, _: errors.append(str(error)) if error else None)
    if producer.flush(15) or errors:
        raise RuntimeError('Kafka delivery failed')
    return event


def consume(event_id):
    from confluent_kafka import Consumer, KafkaError
    config = {**kafka_config(), 'group.id': 'example-workers-demo-' + str(uuid.uuid4()),
              'auto.offset.reset': 'earliest', 'enable.auto.commit': False}
    consumer = Consumer(config)
    try:
        consumer.subscribe([TOPIC])
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            item = consumer.poll(1)
            if item is None:
                continue
            if item.error():
                if item.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise RuntimeError('Kafka read failed')
            event = json.loads(item.value())
            if event['eventId'] == event_id:
                return {'consumer': TEAM, 'topic': TOPIC, 'event': event}
        raise TimeoutError('Event not found')
    finally:
        consumer.close()


PAGE = '''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Infrastructure demo</title>
<style>body{font:16px system-ui;max-width:960px;margin:40px auto;padding:0 20px;
background:#f5f6f8;color:#20242b}h1{font-size:26px}button,a{margin:6px;padding:9px;
display:inline-block}pre{background:white;padding:20px;white-space:pre-wrap;
border:1px solid #ddd}small{color:#555}</style>
<a href="/">Все команды</a><h1>__TEAM__</h1>
<p>MOCK приложения. PostgreSQL, Keycloak, MinIO, Kafka и Kubernetes — реальные.</p>
<small>Проверка инфраструктуры; бизнес-контракты команды не реализованы.</small><p>
<button data-path="info">Pod и БД</button>
<button data-path="checks" data-method="POST">Keycloak / S3 / OTLP</button>
<button data-path="records" data-method="POST">Сохранить запись</button>
<button data-path="records">Прочитать записи</button>
<button data-path="peer">HTTP в соседний сервис</button>
<button data-path="events" data-method="POST">Отправить событие Kafka</button></p>
<pre id="out">Выберите проверку</pre><script>
document.querySelectorAll('button').forEach(b=>b.onclick=async()=>{
const out=document.getElementById('out');out.textContent='Выполняется…';
try{const r=await fetch('api/'+b.dataset.path,{method:b.dataset.method||'GET',
headers:{'Content-Type':'application/json'},body:b.dataset.method?
JSON.stringify({message:'demo '+new Date().toISOString()}):undefined});
out.textContent=JSON.stringify({status:r.status,result:await r.json()},null,2);
}catch(e){out.textContent=String(e);}});</script></html>'''


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type='application/json'):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def proxy(self, target):
        size = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(size) if size else None
        headers = {'Content-Type': 'application/json'}
        if self.headers.get('Authorization'):
            headers['Authorization'] = self.headers['Authorization']
        request = urllib.request.Request(target, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, timeout=50) as response:
                self.send(response.status, response.read(), response.headers.get('Content-Type', '').split(';')[0])
        except urllib.error.HTTPError as error:
            self.send(error.code, error.read())

    def handle_request(self):
        try:
            if self.path == '/livez':
                return self.send(200, {'status': 'alive'})
            if ROLE == 'gateway':
                team, _, path = self.path.lstrip('/').partition('/')
                if team in TEAMS:
                    if self.path == '/' + team:
                        self.send_response(302); self.send_header('Location', '/' + team + '/'); self.end_headers()
                        return
                    return self.proxy(f'http://frontend.arch-{team}.svc.cluster.local:8080/' + path)
                links = ''.join(f'<li><a href="/{x}/">{x}</a></li>' for x in TEAMS)
                return self.send(200, ('<!doctype html><meta charset="utf-8"><title>Kubernetes demo</title>'
                    '<body style="font:18px system-ui;max-width:850px;margin:50px auto">'
                    '<h1>Общий стенд в Kubernetes</h1><p>5 команд: отдельные frontend, mock backend и PostgreSQL.</p>'
                    '<p>Общие Keycloak, Kafka, MinIO, Collector. Данные синтетические.</p><ul>' + links +
                    '</ul><a href="http://localhost:18081/admin/">Keycloak</a> · '
                    '<a href="http://localhost:19001">MinIO Console</a></body>').encode(), 'text/html')
            if ROLE == 'frontend':
                if self.path.startswith('/api/') or self.path == '/readyz':
                    return self.proxy('http://backend:8080' + self.path)
                return self.send(200, PAGE.replace('__TEAM__', TEAM).encode(), 'text/html')
            if self.path in ('/readyz', '/api/info'):
                with database() as db:
                    count = db.execute('SELECT count(*) FROM infra_demo_record').fetchone()[0]
                return self.send(200, {'team': TEAM, 'mock': True, 'pod': os.environ['HOSTNAME'],
                                      'namespace': os.environ['NAMESPACE'], 'records': count, 'database': 'ok'})
            if self.path == '/api/protected':
                try:
                    claims = verify_token(self.headers.get('Authorization', '').removeprefix('Bearer '))
                except Exception:
                    return self.send(401, {'error': 'invalid or missing bearer token'})
                return self.send(200, {'subject': claims['sub'], 'audience': claims['aud']})
            if self.path == '/api/peer':
                peer = 'task-tracker' if TEAM == 'reference-manager' else 'reference-manager'
                return self.send(200, {'caller': TEAM, 'response': json.loads(http(
                    f'http://backend.arch-{peer}.svc.cluster.local:8080/api/info'))})
            size = int(self.headers.get('Content-Length', 0))
            if size > 8192:
                return self.send(413, {'error': 'request too large'})
            body = json.loads(self.rfile.read(size)) if size else {}
            if self.path == '/api/records':
                with database() as db:
                    if self.command == 'POST':
                        identifier = str(uuid.uuid4())
                        db.execute('INSERT INTO infra_demo_record(id,message) VALUES(%s,%s)',
                                   (identifier, str(body.get('message', 'demo'))[:1000]))
                    else:
                        rows = db.execute('SELECT id::text,message,created_at::text FROM infra_demo_record '
                                          'ORDER BY created_at DESC LIMIT 50').fetchall()
                if self.command == 'POST':
                    return self.send(201, {'id': identifier, 'team': TEAM})
                return self.send(200, {'team': TEAM, 'rows': [dict(zip(['id', 'message', 'createdAt'], x)) for x in rows]})
            if self.command == 'POST' and self.path == '/api/checks':
                return self.send(200, check_services())
            if self.command == 'POST' and self.path == '/api/events':
                return self.send(201, publish(str(body.get('message', 'demo'))[:1000]))
            if self.command == 'POST' and self.path == '/api/consume':
                return self.send(200, consume(body['eventId']))
            self.send(404, {'error': 'unknown demo endpoint'})
        except Exception as error:
            print(f'{self.path}: {type(error).__name__}', flush=True)
            self.send(503, {'error': type(error).__name__, 'team': TEAM})

    do_GET = handle_request
    do_POST = handle_request


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'migrate':
        migrate()
    elif len(sys.argv) > 1 and sys.argv[1] == 'etl':
        etl()
    else:
        ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
