# email_service/client.py
import boto3
import os


def get_ses_client():
    return boto3.client("ses", region_name="eu-central-1")
