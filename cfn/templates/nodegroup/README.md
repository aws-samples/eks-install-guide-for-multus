# Multus CNI for Managed Node Groups

## Prerequisites
* Make sure EKS cluster is provisioned, if not please refer steps [here](../infra/README.md).
* Please use [cfn/templates/nodegroup/eks-nodegroup-multus.yaml](./eks-nodegroup-multus.yaml) and [cfn/templates/nodegroup/lambda_function.zip](./lambda_function.zip) containing lambda functions.

## Self-managed Node Group IP management strategy 

### Option 1 Allocate Worker IPs statically via a custom lambda-based solution
This solution works on the logical subnet sharing model, between the workers and pods. In this model, worker nodes always start taking the free IPs from the beginning of the subnet and the pods start taking the IPs from end of the subnet. With this allocation strategy the IPs wont clash between workers and Pods. To make this model work, worker ENIs must get IPs statically from the first free available IPs from the subnet and not use DHCP allocation. 

![Worker IPs statically assigned from begining of the subnet](https://github.com/aws-samples/eks-install-guide-for-multus/blob/main/images/useIPsFromStartOfSubnet.png)


For this Strategy use ```useIPsFromStartOfSubnet: true``` settings while creating the [Self managed Node Group]( ##-Self-managed-Node-Group-creation ) section.

#### Pros
1.  No need of CIDR reservation on subnets or additional management, works for any subnet without additional overhead.
2.  As the worker nodes always pick the first available IP address, scaling for the worker nodes is seamless (no need to readjust subnet cidr reservation).

#### Cons
1.  Custom solution, in comparison to Subnet CIDR reservation (Option 2), which is a VPC feature.
2.  Doesn’t protect the pod IP addresses from accidental use cases, i.e. if an EC2 instance is created without lambda function (manual EC2 creation or useIPsFromStartOfSubnet as False).
3.  Slight complex logic of lambda function, to assign the ip addresses statically for the worker nodes.
4.  increase the lambda execution time a little bit (10-60 secs), depending on the number of interfaces, so slightly increased instantiation time.


### Option 2: Use VPC subnet cidr reservation (static) for pods IP addresses  
This solution works on the subnet CIDR separation model, between the workers and pods. In this model, we would create a reservation of the pod IP addresses chunks (you can go as granualar as /32 CIDRs) for explicit (static) allocation only. The unreserved chunk of the subnet CIDR would be available for the DHCP (default) allocation for the worker nodes behind the autoscaling group. Please refer to VPC subnet CIDR reservation for more details. This would ensure that worker would never encroach in the reserved CIDRs for pod.

![Worker IPs from CIDR reservation](https://github.com/aws-samples/eks-install-guide-for-multus/blob/main/images/useCidrReservation.png)


Below is an example of creating a subnet CIDR reservation. This needs to be done for each multus based subnets, for desired multus pod IP ranges.

```
$ aws ec2 create-subnet-cidr-reservation --subnet-id  subnet-04b92f3c451542e6a --cidr 10.10.10.128/25 --reservation-type explicit
{
    "SubnetCidrReservation": {
        "SubnetCidrReservationId": "scr-0d919a0ece72fd48b",
        "SubnetId": "subnet-04b92f3c451542e6a",
        "Cidr": "10.10.10.128/25",
        "ReservationType": "explicit",
        "OwnerId": "xxxxxxx"
    }
}
```
For this Strategy use ```useIPsFromStartOfSubnet: false``` settings while creating the [Self managed Node Group]( ##-Self-managed-Node-Group-creation ) section.

#### Pros
1.  Custom code or lambda and its maintenace is not needed, as subnet CIDR reservation is VPC feature.
2.  You can reserve multiple subnet CIDR blocks.
3.  POD IP address space is protected from accidental DHCP usage.

#### Cons
1.  Additional overhead/management to define CIDR reservation for each Multus subnet
2.  Existing subnet cidr reservation cant be modified, you would have to delete the reservation and create it, however it doesnt impact already assigned IPs, so its a safe operation

## Self managed Node Group creation

* Go to S3 and create bucket (folder/directory) with *Create bucket*.
* Bucket name to be unique like *multus-cluster* (recommend to use your name or unique keyword), and then *Create bucket*.
* Click the bucket you just created and drag & drop lambda_function.zip file (which you can find from /template directory of this GitHub). Then, click *Upload*.
* Please memorize bucket name you create (this is required in CloudFormation)
* Go to CloudFormation console by selecting CloudFormation from Services drop down or by search menu. 
    * Select *Create stack*, *with new resources(standard)*.
    * Click *Template is ready" (default), "Upload a template file", "Choose file". Select "eks-nodegroup-multus.yaml" file that you have downloaded from this GitHub. 
    * Stack name -> ng1
    * ClusterName -> eks-multus-cluster (your own cluster name)
    * ClusterControlPlaneSecurityGroup -> "eks-multus-cluster-EksControlSecurityGroup-xxxx"
    * NodeGroupName -> ng1
    * AutoScalingGroup Min/Desired/MaxSize -> 1/2/3
    * NodeInstanceType -> select EC2 flavor, based on the requirement (or choose default)
    * NodeImageIdSSMParam --> EKS optimized linux2 AMI release (default 1.21, change the release value, if needed)
    * NodeImageId --> (if using custome AMI then use AMIID, this option will override NodeImageIdSSMParam)
    * NodeVolumeSize --> configure Root Volume size (default 50 gb)
    * KeyName -> ee-default-keypair (or any ssh key you have)
    * BootstrapArguments -> configure your k8 node labels, (leave default if not sure)
    * useIPsFromStartOfSubnet -> use true (to use option 1 mentioned above) or false (to use option 2 i.e. cidr reservation)
    * VpcId -> vpc-eks-multus-cluster (that you created)
    * Subnets -> privateAz1-eks-multus-cluster (this is for main primary K8s networking network)
    * MultusSubnets -> multus1Az1 and Multus2Az1 (subnets are attached in same order as provided, so multus1Az1 as eth1 and Multus2Az1 as eth2 )
    * MultusSecurityGroups -> multus-Sg-eks-multus-cluster
    * LambdaS3Bucket -> the one you created (eks-multus-cluster)
    * LambdaS3Key -> lambda_function.zip
    * InterfaceTags --> (optional , leave it blank or put a key-value pair as Tags on the i/f)
    * *Next*, check "I acknowledge...", and then *Next*.

* Once CloudFormation stack creation is completed, check *Output* part in the menu and copy the value of NodeInstanceRole (e.g. arn:aws:iam::XXXXXXXXXXXXX:role/ng1-NodeInstanceRole-1C77OUUUP6686 --> this is an example, you have to use your own)

## Login to Bastion Host
* Usually in eksworkshop, we guide customer to experience Cloud9 (AWS IDE environment). But in this workshop, plan is to provide a general environment with your own Bastion Host EC2, where you have to install kubectl tools and other tools as needed.
* (General)
    * We can use EC2 Instance Connect to login to EC2 instance.
    * EC2->Instances->"connect" (right top corner of screen).
    * click "connect"

* (MAC user) Log in from your laptop
    * Let's use key pair we downloaded to access to the instance.

  ````
  chmod 600 ee-default-keypair.pem
  ssh-add ee-default-keypair.pem
  ssh -A ec2-user@54.208.182.244
  ````

    * Copy AWS credentials; be mindful that you have to use your own not below one.

  ````
  export AWS_DEFAULT_REGION=us-west-2
  export AWS_ACCESS_KEY_ID=ASIA..
  export AWS_SECRET_ACCESS_KEY=4wyDA..
  export AWS_SESSION_TOKEN=IQo...
  ````

    * Try whether AWS confidential is already configured well

    ````
    aws sts get-caller-identity
    {
      "Account": "XXXXXXXX",
      "UserId": "AROAV2K6K7CXSDASDAA:MasterKey",
      "Arn": "arn:aws:sts::XXXXXXXXXXXXX:assumed-role/TeamRole/MasterKey"
    }
    ````

* (Window user) Log in from your laptop
    * Please use PuTTy and refer to the guide, https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/putty.html


## Apply AWS Auth Configmap
* Go to the bastion host where we can run kubectl command. 
* Download aws-auth-cm file.
  ````
  curl -o aws-auth-cm.yaml https://s3.us-west-2.amazonaws.com/amazon-eks/cloudformation/2020-10-29/aws-auth-cm.yaml
  ````

* Open aws-auth-cm.yaml file downloaded using vi or any text editor. And place above copied NodeInstanceRole value to the place of "*<ARN of instance role (not instance profile)>*", and then apply this through kubectl.
  ````
  kind: ConfigMap
  metadata:
    name: aws-auth
    namespace: kube-system
  data:
    mapRoles: |
      - rolearn: arn:aws:iam::XXXXXXXXXXXXX:role/ng1-NodeInstanceRole-1C77OUUUP6686
        username: system:node:{{EC2PrivateDNSName}}
        groups:
          - system:bootstrappers
          - system:nodes
  ````
  ````
  kubectl apply -f aws-auth-cm.yaml
  ````

## Install Multus

* Let's go to Bastion host where we can run kubectl. 
* Install multus CNI.
  ````
  kubectl apply -f https://raw.githubusercontent.com/aws/amazon-vpc-cni-k8s/master/config/multus/v3.7.2-eksbuild.1/aws-k8s-multus.yaml
  ````
* Change the multus container image address inside multus-daemonset.yml before applying it to the cluster.
  ````
      containers:
      - name: kube-multus
        image: 940911992744.dkr.ecr.us-west-2.amazonaws.com/eks/multus-cni:v3.7.2-eksbuild.1
  ````
* Go to this [page](https://docs.aws.amazon.com/eks/latest/userguide/add-ons-images.html) and find the container image address for your region.


## Create NetworkAttachmentDefinition
* Create below [networkAttachementDefinition](../../examples/multus-ipvlan-1.yaml) and apply it to the cluster.

  ````
  apiVersion: "k8s.cni.cncf.io/v1"
  kind: NetworkAttachmentDefinition
  metadata:
    name: ipvlan-conf-1
  spec:
    config: '{
        "cniVersion": "0.3.0",
        "type": "ipvlan",
        "master": "eth1",
        "mode": "l2",
        "ipam": {
          "type": "host-local",
          "subnet": "10.0.4.0/24",
          "rangeStart": "10.0.4.70",
          "rangeEnd": "10.0.4.80",
          "gateway": "10.0.4.1"
        }
      }'
  ````

  ````
  kubectl apply -f multus-ipvlan-1.yaml
  ````

## Deploy Sample App

* Deploy [dummy app](../../examples/app-ipvlan.yaml) using above network attachment.
  ````
  apiVersion: v1
  kind: Pod
  metadata:
    name: sampleapp-1
    annotations:
      k8s.v1.cni.cncf.io/networks: ipvlan-conf-1
  spec:
    containers:
    - name: sampleapp
      command: ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
      image: praqma/network-multitool
  ````

  ````
  kubectl apply -f app-ipvlan.yaml
  kubectl describe pod sampleapp-1
  kubectl exec -it sampleapp-1 -- /bin/bash
  root@sampleapp:/# ip a
  ````
 ## Automated Multus pod IP management on EKS

Since, Multus pods are using ipvlan CNI, which means that the macaddress of the pod remains same as the master interface. However, vpc will not be aware of the assumed IP address of the pod, since the IP allocations to these pods hasn’t happened via VPC. VPC is only aware of the IP addresses allocated on the ENI on EC2 worker nodes. To make these IPs routable in VPC network, please refer to [Automated Multus pod IP management on EKS](https://github.com/aws-samples/eks-automated-ipmgmt-multus-pods). to automate the pod IP assignment seamlessly, without any change in application code.

## 6. Clean up environment
* Delete Node Group in EKS menu. 
* Go to CloudFormation and Delete ng1 stack. 
