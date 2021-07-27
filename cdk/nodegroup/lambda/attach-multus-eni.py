import boto3
import botocore
import os
from datetime import datetime

ec2_client = boto3.client('ec2')
asg_client = boto3.client('autoscaling')
ec2 = boto3.resource('ec2')

def lambda_handler(event, context):
    instance_id = event['detail']['EC2InstanceId']
    LifecycleHookName=event['detail']['LifecycleHookName']
    AutoScalingGroupName=event['detail']['AutoScalingGroupName']
    secgroup_ids = []
    subnet_ids = []

    count = 0
    while True:
      try:
        subnet_ids.append(os.environ['SubnetId' + str(count + 1)])
        secgroup_ids.append(os.environ['SecGroupId' + str(count + 1)])
        count = count + 1
      except KeyError:
        break

    if event["detail-type"] == "EC2 Instance-launch Lifecycle Action":
        index = 1
        for x in subnet_ids:
            interface_id = create_interface(x,secgroup_ids[index - 1])
            attachment = attach_interface(interface_id,instance_id,index)
            index = index+1
            if not interface_id:
                complete_lifecycle_action_failure(LifecycleHookName,AutoScalingGroupName,instance_id)
                return
            elif not attachment:
                complete_lifecycle_action_failure(LifecycleHookName,AutoScalingGroupName,instance_id)
                delete_interface(interface_id)
                return
        #complete_lifecycle_action_success(LifecycleHookName,AutoScalingGroupName,instance_id)

    if event["detail-type"] == "EC2 Instance-terminate Lifecycle Action":
        interface_ids = []
        attachment_ids = []

        # -* Further enhancement: K8s draining function should be added here -*#
        #complete_lifecycle_action_success(LifecycleHookName,AutoScalingGroupName,instance_id)


def create_interface(subnet_id,sg_id):
    network_interface_id = None
    if subnet_id:
        try:
            network_interface = ec2_client.create_network_interface(Groups=[sg_id],SubnetId=subnet_id)
            network_interface_id = network_interface['NetworkInterface']['NetworkInterfaceId']
            log("Created network interface: {}".format(network_interface_id))
        except botocore.exceptions.ClientError as e:
            log("Error creating network interface: {}".format(e.response['Error']))
    return network_interface_id


def attach_interface(network_interface_id, instance_id, index):
    attachment = None
    if network_interface_id and instance_id:
        try:
            attach_interface = ec2_client.attach_network_interface(
                NetworkInterfaceId=network_interface_id,
                InstanceId=instance_id,
                DeviceIndex=index
            )
            attachment = attach_interface['AttachmentId']
            log("Created network attachment: {}".format(attachment))
        except botocore.exceptions.ClientError as e:
            log("Error attaching network interface: {}".format(e.response['Error']))

    network_interface = ec2.NetworkInterface(network_interface_id)
    network_interface.create_tags(
        Tags=[
                {
                    'Key': 'node.k8s.amazonaws.com/no_manage',
                    'Value': 'true'
            }
        ]
    )

    #modify_attribute doesn't allow multiple parameter change at once..
    network_interface.modify_attribute(
        SourceDestCheck={
            'Value': False
        }
    )
    network_interface.modify_attribute(
        Attachment={
            'AttachmentId': attachment,
            'DeleteOnTermination': True
        },
    )

    return attachment


def delete_interface(network_interface_id):
    try:
        ec2_client.delete_network_interface(
            NetworkInterfaceId=network_interface_id
        )
        log("Deleted network interface: {}".format(network_interface_id))
        return True

    except botocore.exceptions.ClientError as e:
        log("Error deleting interface {}: {}".format(network_interface_id,e.response['Error']))


def complete_lifecycle_action_success(hookname,groupname,instance_id):
    try:
        asg_client.complete_lifecycle_action(
            LifecycleHookName=hookname,
            AutoScalingGroupName=groupname,
            InstanceId=instance_id,
            LifecycleActionResult='CONTINUE'
        )
        log("Lifecycle hook CONTINUEd for: {}".format(instance_id))
    except botocore.exceptions.ClientError as e:
            log("Error completing life cycle hook for instance {}: {}".format(instance_id, e.response['Error']))
            log('{"Error": "1"}')

def complete_lifecycle_action_failure(hookname,groupname,instance_id):
    try:
        asg_client.complete_lifecycle_action(
            LifecycleHookName=hookname,
            AutoScalingGroupName=groupname,
            InstanceId=instance_id,
            LifecycleActionResult='ABANDON'
        )
        log("Lifecycle hook ABANDONed for: {}".format(instance_id))
    except botocore.exceptions.ClientError as e:
            log("Error completing life cycle hook for instance {}: {}".format(instance_id, e.response['Error']))
            log('{"Error": "1"}')

def log(error):
    print('{}Z {}'.format(datetime.utcnow().isoformat(), error))

