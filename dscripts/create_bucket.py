#!/usr/bin/python3

import argparse
import boto3
from botocore.client import Config

# import logging
# logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser()
parser.add_argument('-e', '--endpoint_url', help='endpoint url', required=True)
parser.add_argument('-b', '--bucket', help='bucket', required=True)
parser.add_argument('-p', '--aws_profile', help='profile in ~/.aws/credential', required=False, default="default")
parser.add_argument('-r', '--aws_region', help='aws region', required=False, default="Default")
parser.add_argument('-f', '--aws_force_path', help='aws foce path style', required=False, type=bool, default=True)

args = parser.parse_args()
endpoint_url=args.endpoint_url
container=args.bucket
profile = args.aws_profile
region = args.aws_region

session = boto3.Session(profile_name=profile, region_name=region)

if args.aws_force_path:
    s3 = session.client('s3', endpoint_url=endpoint_url, config=Config(s3={'addressing_style': 'path'}))
else:
    s3 = session.client('s3', endpoint_url=endpoint_url)

try:
    s3.create_bucket(Bucket=container)
except s3.exceptions.BucketAlreadyOwnedByYou:
    pass
except Exception as e:
    raise

response = s3.list_buckets()
buckets = [bucket['Name'] for bucket in response['Buckets']]
result = [b for b in buckets if container in b]
if result:
    print (result[0])
else:
    print ("")
