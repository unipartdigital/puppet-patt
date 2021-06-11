#!/usr/bin/python3

import argparse
import boto3

parser = argparse.ArgumentParser()
parser.add_argument('--endpoint_url', help='endpoint url', required=True)
parser.add_argument('--bucket', help='bucket', required=True)
parser.add_argument('--aws_profile', help='profile in ~/.aws/credential', required=False, default="default")

args = parser.parse_args()
endpoint_url=args.endpoint_url
container=args.bucket
profile = args.aws_profile

session = boto3.Session(profile_name=profile)
s3 = session.client('s3', endpoint_url=endpoint_url)
s3.create_bucket(Bucket=container)

response = s3.list_buckets()
buckets = [bucket['Name'] for bucket in response['Buckets']]
result = [b for b in buckets if container in b]
if result:
    print (result[0])
else:
    print ("")
