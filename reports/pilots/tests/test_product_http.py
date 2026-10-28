"""The public contract over real HTTP, including exported bytes and audit."""
import io
import json
import os
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from test_acceptance import report_server
from acceptance_data import source_server,dataset
from db import Database
from demo import MEMBER_1
from product_service import tick
from test_product import seed,claims,QUERY,ADMIN,AN,AD,MB


class ProductHTTP(unittest.TestCase):
    def test_catalog_reports_views_exports_subscriptions_notifications_and_audit(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        public=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));public.update(kid='product',alg='RS256',use='sig')
        with tempfile.TemporaryDirectory() as directory,source_server(dataset(),public) as (base,_,_):
            dsn='sqlite:'+str(Path(directory)/'product.sqlite');db=Database(dsn);db.initialize();seed(db)
            def bearer(c): return jwt.encode(dict(c,iat=int(time.time()),iss=base,aud='reports'),key,algorithm='RS256',headers={'kid':'product'})
            admin=bearer(claims());member=bearer(claims(MEMBER_1,[MB]))
            with report_server(dsn,base,base+'/jwks') as api:
                def call(path,method='GET',body=None,token=admin,headers=None):
                    head={'Content-Type':'application/json',**(headers or {})}
                    if token: head['Authorization']='Bearer '+token
                    req=urllib.request.Request(api+'/api/v1/'+path,data=json.dumps(body).encode() if body is not None else None,headers=head,method=method)
                    try: response=urllib.request.urlopen(req,timeout=10)
                    except urllib.error.HTTPError as error: response=error
                    with response:
                        raw=response.read();value=None if response.status==204 else json.loads(raw) if 'json' in response.headers.get('Content-Type','') else raw
                        return response.status,value,dict(response.headers)
                status,catalog,_=call('reports');self.assertEqual(status,200);self.assertEqual(len(catalog['items']),11)
                self.assertEqual(call('reports',token=None)[0],401)
                admin_only=bearer(claims(ADMIN,[AD]))
                request=urllib.request.Request(api+'/pilot/reports/time-logs',headers={'Authorization':'Bearer '+admin_only})
                with self.assertRaises(urllib.error.HTTPError) as forbidden: urllib.request.urlopen(request)
                self.assertEqual(forbidden.exception.code,403)
                for n in range(1,12):
                    status,result,headers=call(f'reports/R-{n:02d}/query','POST',QUERY)
                    self.assertEqual(status,200,(n,result));self.assertIn('X-Correlation-Id',headers)
                    self.assertEqual(result['reportId'],f'R-{n:02d}')
                self.assertEqual(call('reports/R-02/query','POST',QUERY,member)[0],403)
                status,view,_=call('views','POST',{'reportId':'R-01','name':'<img src=x>','query':QUERY});self.assertEqual(status,201)
                self.assertEqual(call('views/'+view['viewId'],token=member)[0],404)
                status,job,_=call('exports','POST',{'reportId':'R-01','query':QUERY,'format':'xlsx'});self.assertEqual(status,202)
                tick(db)
                status,file,headers=call('exports/'+job['exportId']+'/file');self.assertEqual(status,200)
                with zipfile.ZipFile(io.BytesIO(file)) as z: self.assertIn('xl/workbook.xml',z.namelist())
                self.assertEqual(call('exports/'+job['exportId']+'/file',token=member)[0],404)
                status,printed,headers=call('reports/R-01/print','POST',QUERY);self.assertEqual(status,200)
                self.assertIn("default-src 'none'",headers['Content-Security-Policy'])
                payload={'reportId':'R-01','query':QUERY,'schedule':'0 9 * * 1','format':'csv','recipients':[MEMBER_1]}
                status,subscription,_=call('subscriptions','POST',payload);self.assertEqual(status,201)
                self.assertEqual(call('subscriptions/'+subscription['subscriptionId'],'PATCH',{'status':'PAUSED'},headers={'If-Match':'0'})[0],409)
                self.assertEqual(call('subscriptions/'+subscription['subscriptionId'],'PATCH',{'status':'ACTIVE'},headers={'if-match':'1'})[0],200)
                with db.transaction(): db.execute("UPDATE app.subscription SET next_run_at='2026-10-01T00:00:00+00:00'")
                tick(db)
                status,notifications,_=call('notifications',token=member);self.assertEqual(status,200);self.assertTrue(notifications['items'])
                notification=notifications['items'][0]
                self.assertEqual(call('notifications/'+notification['notificationId'],'PATCH',{'read':True},member)[0],200)
                self.assertEqual(call('notifications/'+notification['notificationId'],'PATCH',{'read':True})[0],404)
                self.assertEqual(call('audit',token=member)[0],403)
                status,events,_=call('audit');self.assertEqual(status,200);self.assertGreaterEqual(events['total'],11)
                self.assertFalse(any('Bearer ' in json.dumps(event) for event in events['items']))
                self.assertEqual(call('views/'+view['viewId'],'DELETE')[0],204)
                self.assertEqual(call('subscriptions/'+subscription['subscriptionId'],'DELETE')[0],204)
            db.close()
