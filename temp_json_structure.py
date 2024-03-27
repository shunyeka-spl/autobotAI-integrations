# I created this file to understand the structue of json string
# In case if we use regex
st = """
"task_id='e682a00305e3439aa660f7f408efc8b0' 
creds=SDKCreds(
    creds=None, 
    envs={
        'AWS_ACCESS_KEY_ID': 'jhklhlhgk', 
        'AWS_SECRET_ACCESS_KEY': 'ghkhghlh', 
        'AWS_SESSION_TOKEN': 'hdfaksdf'
    }
) 
connection_interface=<ConnectionInterfaces.PYTHON_SDK: 'python_sdk'> 
executable='\\ndef executor(context):\\n    clients = context[\\'clients\\']\\n    exec_details = context[\\'execution_details\\']\\n    resources = context[\\'resources\\']\\n    integration_details = context[\\'integration\\']  ### AccountId, ProjectName, SubscriptionId etc\\n    s3_client = context[\\'clients\\'][\"s3\"]\\n    buckets = s3_client.list_buckets()[\"Buckets\"]\\n    for bucket in buckets:\\n        bucket[\"name\"] = bucket.pop(\"Name\")\\n        bucket[\"id\"] = bucket[\"name\"]\\n    return buckets\\n' 
clients=['s3'] 
params={} 
node_details={
    'filter_resources': False
}
context=PayloadTaskContext(
    integration=AWSIntegration(
        userId='amit@shunyeka.com*', 
        accountId='175c0fa813244bc5a1aa6264e7ba20cc', 
        integrationState=<IntegrationStates.INACTIVE: 'INACTIVE'>, 
        cspName='aws', 
        alias='test-aws-integrationsv2', 
        connection_type=<ConnectionTypes.DIRECT: 'DIRECT'>, 
        groups=[
            'aws', 
            'shunyeka', 
            'integrations-v2'
        ], 
        agent_ids=[], 
        accessToken='', 
        createdAt='2024-02-26T13:38:59.978056', 
        updatedAt='2024-02-26T13:38:59.978056',
        indexFailures=0, 
        isUnauthorized=False, 
        lastUsed=None, 
        resource_type='integration', 
        name=None, 
        description=None, 
        logo=None, 
        access_key='jhgvhbkg', 
        secret_key='mnbmbk', 
        session_token='hdfaksdf', 
        account_id='175c0fa813244bc5a1aa6264e7ba20cc', 
        role_arn=None, 
        activeRegions=[
            'us-east-1', 
            'ap-south-1'
        ]
    ), 
    global_variables={
        'default_aws_region': 'us-east-1'
    }, 
    integration_variables={}, 
    integration_group_vars={}, 
    execution_details=ExecutionDetails(
        execution_id='660275c610755f71b634e572', 
        bot_id='660274d5fa724e7537a4c0c5', 
        bot_name='AWS Integrations-V2 Test', 
        node_name='Python-Code-Executor', 
        caller=Caller(
            user_id='amit@shunyeka.com', 
            root_user_id='amit@shunyeka.com'
        )
    ), 
    node_steps={}
) 
resources=[]
"""
