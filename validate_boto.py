import boto3
import json
import botocore.exceptions

cf = boto3.client('cloudformation', region_name='us-east-1')
with open('.serverless/cloudformation-template-update-stack.json', 'r') as f:
    template = f.read()

try:
    response = cf.validate_template(TemplateBody=template)
    print("Success:")
    print(json.dumps(response, indent=2))
except botocore.exceptions.ClientError as e:
    print("Validation Error:")
    print(e)
