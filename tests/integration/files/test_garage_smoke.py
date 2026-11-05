"""Garage starts, is bootstrapped, and answers S3 calls with the created key."""

import boto3
from botocore.config import Config


def test_garage_lists_buckets_with_the_created_key(garage) -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=garage.endpoint,
        aws_access_key_id=garage.key_id,
        aws_secret_access_key=garage.secret,
        region_name=garage.region,
        config=Config(s3={"addressing_style": "path"}),
    )
    assert s3.list_buckets()["ResponseMetadata"]["HTTPStatusCode"] == 200
