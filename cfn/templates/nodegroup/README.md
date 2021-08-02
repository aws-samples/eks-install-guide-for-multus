# Multus CNI for Managed Node Groups

## Prerequisites
* Make sure EKS cluster is provisioned, if not please refer steps [here](../infra/README.md).
* Please use [cfn/templates/nodegroup/eks-nodegroup-multus.yaml](./eks-nodegroup-multus.yaml) and [cfn/templates/nodegroup/lambda_function.zip](./lambda_function.zip) containing lambda functions.

## Self-managed Node Group creation (with Multus CNI Plugin)
* Go to S3 and create bucket (folder/directory) with *Create bucket*.
* Bucket name to be unique like *multus-cluster* (recommend to use your name or unique keyword), and then *Create bucket*.
* Click the bucket you just created and drag & drop lambda_function.zip file (which you can find from /template directory of this GitHub). Then, click *Upload*.
* Please memorize bucket name you create (this is required in CloudFormation)
* Go to CloudFormation console by selecting CloudFormation from Services drop down or by search menu. 
    * Select *Create stack*, *with new resources(standard)*.
    * Click *Template is ready" (default), "Upload a template file", "Choose file". Select "eks-nodegroup-multus.yaml" file that you have downloaded from this GitHub. 
    * Stack name -> ng1
    * ClusterName -> eks-multus-cluster (your own name)
    * ClusterControlPlaneSecurityGroup -> "eks-multus-cluster-EksControlSecurityGroup-xxxx"
    * NodeGroupName -> ng1
    * Min/Desired/MaxSize -> 1/1/1
    * KeyName -> ee-default-keypair
    * VpcId -> vpc-eks-multus-cluster (that you created)
    * Subnets -> privateAz1-eks-multus-cluster (this is for main primary K8s networking network)
    * MultusSubnets -> multus1Az1 and Multus2Az1
    * MultusSecurityGroups -> multus-Sg-eks-multus-cluster
    * LambdaS3Bucket -> the one you created (eks-multus-cluster)
    * LambdaS3Key -> lambda_function.zip
    * *Next*, check "I acknowledge...", and then *Next*.

* Once CloudFormation stack creation is completed, check *Output* part in the menu and copy the value of NodeInstanceRole (e.g. arn:aws:iam::153318889914:role/ng1-NodeInstanceRole-1C77OUUUP6686 --> this is an example, you have to use your own)

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
      - rolearn: arn:aws:iam::153318889914:role/ng1-NodeInstanceRole-1C77OUUUP6686
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
        "mode": "l3",
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

## 6. Clean up environment
* Delete Node Group in EKS menu. 
* Go to CloudFormation and Delete ng1 stack. 
