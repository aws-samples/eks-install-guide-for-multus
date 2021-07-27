# Multus CNI for Managed Node Groups

## MultusNodeGroupStack
* CDK creates 2 Lambda (1> attach multus eni, 2> auto reboot) to attach multus ENIs to EKS managed NodeGroup.
* Basically, logic is identical to the one, [CFN version](../cfn/templates/nodegroup/README.md).
* CFN version is only available with Self-Managed NodeGroup (because of constraints of CFN, lack of interactability - In CFN, it is not possible to find AutoScaling Group armed to EKS NodeGroup while we need this for CloudWatch Event Rule configuration).
* CDK version makes this to be available using AwsCustomResource SDK API call.

## Prerequisites
* You have to install nodejs and CDK. (unless you are using Cloud9) <br>
`sudo yum install nodejs`  <br>
`curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash` <br>
`. ~/.nvm/nvm.sh` <br>
`nvm install 10.23.0` <br>
`sudo npm install -g npm@latest` (to install 6.14.8) <br>
`sudo npm install -g aws-cdk` <br>

## How To
After `git clone https://github.com/aws-samples/eks-install-guide-for-multus`, please do..

* `cd eks-install-guide-for-multus/cdk/nodegroup`
* `npm install` 
* `cdk bootstrap aws://AWS_ACCOUNT_ID/AWS_DEFAULT_REGION`
* Setting environmental variables according to your environment.
    * `cdk.json` → configure variables such as vpc-id, eks cluster name, multus subnetId, security group Id and so on.
* `cdk synth -j` 
* `cdk deploy -j` 

*Note that because of MIME userdata, we have to use JSON format*

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


## Install Multus

* Install multus CNI, if not already deployed.
  ````
  git clone https://github.com/intel/multus-cni.git
  kubectl apply -f ~/multus-cni/images/multus-daemonset.yml
  ````

## Create NetworkAttachmentDefinition
* Create below [networkAttachementDefinition](../examples/multus-ipvlan-cdk.yaml) and apply it to the cluster.

  ````
  apiVersion: "k8s.cni.cncf.io/v1"
  kind: NetworkAttachmentDefinition
  metadata:
    name: ipvlan-conf-cdk
  spec:
    config: '{
        "cniVersion": "0.3.0",
        "type": "ipvlan",
        "master": "eth1",
        "mode": "l3",
        "ipam": {
          "type": "host-local",
          "subnet": "10.0.6.0/24",
          "rangeStart": "10.0.6.20",
          "rangeEnd": "10.0.6.40",
          "gateway": "10.0.6.1"
        }
      }'
  ````

  ````
  kubectl apply -f multus-ipvlan-cdk.yaml
  ````

## Deploy Sample App

* Deploy [dummy app](../examples/app-ipvlan-cdk.yaml) using above network attachment. 
  ````
  apiVersion: v1
  kind: Pod
  metadata:
    name: samplepod-cdk
    annotations:
      k8s.v1.cni.cncf.io/networks: ipvlan-conf-cdk
  spec:
    containers:
    - name: samplepod
      command: ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
      image: praqma/network-multitool
  ````

  ````
  kubectl apply -f app-ipvlan-cdk.yaml
  kubectl describe pod samplepod-cdk
  kubectl exec -it samplepod-cdk -- /bin/bash
  root@samplepod:/# ip a
  ````

## Cleanup
* `cd eks-install-guide-for-multus/cdk/nodegroup/`
* `cdk destroy`
* If you see any error, please clean up via console by deleting CDK stack
