"""Real local Keycloak smoke. Never prints credentials or tokens."""
import json
import time
from pathlib import Path

import httpx


def main():
    with httpx.Client(timeout=15) as client:
        config=client.get('http://localhost:8080/auth/config')
        config.raise_for_status()
        assert config.json()['mode']=='oidc', 'Start compose.oidc.yaml first'

        def token(username):
            response=client.post('http://localhost:8081/realms/planning/protocol/openid-connect/token',data={
                'client_id':'planning-smoke','grant_type':'password',
                'username':username,'password':'local-planning-demo'})
            response.raise_for_status()
            return response.json()['access_token']

        def request(value):
            return client.get('http://localhost:8080/api/v1/projects',headers={'Authorization':'Bearer '+value})

        planner=token('planner')
        assert request(planner).status_code==200, 'Planner denied'
        assert request(token('outsider')).status_code==403, 'Missing role accepted'
        assert request('demo-R-02').status_code==401, 'Demo token accepted in OIDC mode'
        # planning-smoke has a five-second lifespan; use the same authentic JWT after expiry.
        time.sleep(6)
        assert request(planner).status_code==401, 'Expired token accepted'
    report={'issuer':'local Keycloak','checks':['planner:200','no-role:403','demo-token:401','expired:401'],'passed':True}
    output=Path(__file__).resolve().parents[1]/'artifacts/oidc-report.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print('Keycloak smoke: 4 checks passed')


if __name__=='__main__':
    main()
