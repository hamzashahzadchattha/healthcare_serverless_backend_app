import json
with open('.serverless/cloudformation-template-update-stack.json', 'r') as f:
    t = json.load(f)

# API Gateway V2 Authorizer IdentitySource can be very finicky
t['Resources']['HttpApiJwtAuthorizer']['Properties']['IdentitySource'] = ["$request.header.Authorization"]
# Try to make sure it's valid CF
with open('.serverless/cloudformation-template-update-stack-test.json', 'w') as f:
    json.dump(t, f, indent=2)
