# app/core/secrets_aws.py
import os
import json
import boto3

def get_secret_from_aws(key: str, secret_name="zoom-bot/secrets"):
    region = os.getenv("AWS_REGION", "us-east-1")

    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    secret_data = json.loads(response["SecretString"])

    if key not in secret_data:
        raise KeyError(f"Secret key '{key}' not found in '{secret_name}'")

    return secret_data[key]