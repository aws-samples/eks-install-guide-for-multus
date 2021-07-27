from __future__ import print_function
import boto3
import json
import urllib3

SUCCESS = "SUCCESS"
FAILED = "FAILED"

asg_client = boto3.client('autoscaling')
ec2_client = boto3.client('ec2')

http = urllib3.PoolManager()

def handler (event, context):
    AutoScalingGroupName = event['ResourceProperties']['AsgName']
    asg_response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[AutoScalingGroupName])
    instance_ids = []

    for i in asg_response['AutoScalingGroups']:
        for k in i['Instances']:
            instance_ids.append(k['InstanceId'])

    if instance_ids != []:
        ec2_client.terminate_instances(InstanceIds = instance_ids)

    responseValue = 1
    responseData = {}
    responseData['Data'] = responseValue
    send(event, context, SUCCESS, responseData, "CustomResourcePhysicalID")

def send(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None):
    responseUrl = event['ResponseURL']

    print(responseUrl)

    responseBody = {
        'Status' : responseStatus,
        'Reason' : reason or "See the details in CloudWatch Log Stream: {}".format(context.log_stream_name),
        'PhysicalResourceId' : physicalResourceId or context.log_stream_name,
        'StackId' : event['StackId'],
        'RequestId' : event['RequestId'],
        'LogicalResourceId' : event['LogicalResourceId'],
        'NoEcho' : noEcho,
        'Data' : responseData
    }

    json_responseBody = json.dumps(responseBody)

    print("Response body:")
    print(json_responseBody)

    headers = {
        'content-type' : '',
        'content-length' : str(len(json_responseBody))
    }

    try:
        response = http.request('PUT', responseUrl, headers=headers, body=json_responseBody)
        print("Status code:", response.status)


    except Exception as e:

        print("send(..) failed executing http.request(..):", e)
