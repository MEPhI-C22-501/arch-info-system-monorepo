"""Initialize only synthetic product data on the local reports-pilot stand."""
import json
import os
from pathlib import Path
from db import Database
from product_fixture import business_fixture
from etl import load, now


def main():
    path=Path('/demo/subjects.json')
    subjects=json.loads(path.read_text())
    data=business_fixture(subjects);db=Database(os.environ['REPORTS_DATABASE_URL'])
    try:
        for source in ['planning','qa','reference']:
            value=now();load(db,source,lambda s=source,t=value:(data[s],t,t,None))
        with db.transaction():
            for link in data['links']:
                db.execute('INSERT INTO app.entity_link VALUES (?,?,?) ON CONFLICT(kind,source_id) DO UPDATE SET target_id=excluded.target_id',link)
            from star import refresh
            refresh(db,now())
        print('Synthetic Reports business data initialized')
    finally: db.close()


if __name__=='__main__': main()
