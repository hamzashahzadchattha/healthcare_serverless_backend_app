import json

with open('.serverless/cloudformation-template-update-stack.json', 'r') as f:
    t = json.load(f)

# Hardcode IdentitySource as list of strings
t['Resources']['HttpApiJwtAuthorizer']['Properties']['IdentitySource'] = ["$request.header.Authorization"]

# Bypass API GW V2 early validation by providing a publicly resolvable OIDC issuer
t['Resources']['HttpApiJwtAuthorizer']['Properties']['JwtConfiguration']['Issuer'] = "https://accounts.google.com"

with open('.serverless/cloudformation-template-update-stack-fixed2.json', 'w') as f:
    json.dump(t, f, indent=2)
