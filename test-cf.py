import json

with open('.serverless/cloudformation-template-update-stack.json', 'r') as f:
    t = json.load(f)

# Hardcode IdentitySource as list of strings
t['Resources']['HttpApiJwtAuthorizer']['Properties']['IdentitySource'] = ["$request.header.Authorization"]

# Hardcode Issuer to avoid EarlyValidation evaluating the Ref to CognitoUserPool before it exists
# Sometimes EarlyValidation fails if Issuer is an unresolved string reference at creation
t['Resources']['HttpApiJwtAuthorizer']['Properties']['JwtConfiguration']['Issuer'] = {
    "Fn::Join": [
        "",
        [
            "https://cognito-idp.",
            {"Ref": "AWS::Region"},
            ".amazonaws.com/",
            {"Ref": "CognitoUserPool"}
        ]
    ]
}

with open('.serverless/cloudformation-template-update-stack-fixed.json', 'w') as f:
    json.dump(t, f, indent=2)
