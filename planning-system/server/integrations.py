"""Storage adapter. Local files are explicitly development fixtures."""
import os
from pathlib import Path
from fastapi import HTTPException
import boto3
from botocore.config import Config

def client():
    endpoint=os.environ['S3_ENDPOINT']
    if not endpoint.startswith('https://') and os.environ.get('APP_ENV')!='development':
        raise RuntimeError('S3 TLS required')
    return boto3.client('s3',endpoint_url=endpoint,region_name=os.environ.get('S3_REGION','us-east-1'),
        config=Config(signature_version='s3v4',retries={'max_attempts':3},connect_timeout=5,read_timeout=20))

def local_path(identifier):
    if os.environ.get('APP_ENV')!='development':raise RuntimeError('Local storage requires development')
    root=Path(os.environ.get('LOCAL_FILES','./planning-files'));root.mkdir(parents=True,exist_ok=True)
    return root/identifier

def write_file(identifier,data,mime):
    try:
        if os.environ.get('STORAGE_MODE','s3')=='local':local_path(identifier).write_bytes(data)
        else:client().put_object(Bucket=os.environ['S3_BUCKET'],Key=identifier,Body=data,ContentType=mime)
    except Exception:raise HTTPException(503,'Хранилище недоступно') from None

def read_file(identifier):
    try:
        if os.environ.get('STORAGE_MODE','s3')=='local':return local_path(identifier).read_bytes()
        return client().get_object(Bucket=os.environ['S3_BUCKET'],Key=identifier)['Body'].read()
    except Exception:raise HTTPException(503,'Хранилище недоступно') from None

def delete_file(identifier):
    try:
        if os.environ.get('STORAGE_MODE','s3')=='local':local_path(identifier).unlink(missing_ok=True)
        else:client().delete_object(Bucket=os.environ['S3_BUCKET'],Key=identifier)
    except Exception:raise HTTPException(503,'Хранилище недоступно') from None
