#!/usr/bin/env python

import os
import sys
import argparse
import subprocess
import time
import re


parser = argparse.ArgumentParser(description='ec2-backup:The tool is will perfom a backup of a given directory into an aws ec2 to volume')
parser.add_argument("-v", default=0, help="pass the volume to perfom the backup into")
parser.add_argument("dir",help="pass directory to perform backup")
args = parser.parse_args()
volumeId = args.v
backupDir = args.dir


#Reading the Flags into variables
verbose = os.environ.get("EC2_BACKUP_VERBOSE")
InstanceType = os.environ.get("EC2_BACKUP_FLAGS_AWS")
SSHflag = os.environ.get("EC2_BACKUP_FLAGS_SSH")


#converts the value of "EC2_BACKUP_VERBOSE" flag to integer
if verbose == None:
	verbose = 0

verbose = int(verbose)
f = open('/dev/null', 'w')



# create an instance in the available zone of the volume provided, it also checks the for the EC2_BACKUP_FLAGS_AWS
def createInstance(volumeId):
        AvaZone = getAvaZone(volumeId)
	zone =  AvaZone[:-2]
	InstType = getInstType()
        imageId = getImageId(zone)
	if InstType == 0:
		createIst = "aws ec2 run-instances --image-id "+str(imageId)+ " --count 1 --availability-zone " +str(AvaZone)+"  --instance-type t2.micro  --key-name ec2-backup --output text | awk 'FNR == 2 {print$7}' "
	else :
		createIst = "aws ec2 run-instances --image-id "+str(imageId)+  " --count 1" +str(InstanceType)+ "--availability-zone " +str(AvaZone)+ "--key-name ec2-backup --output text | awk 'FNR == 2 {print$7}' "
	createInstance = subprocess.Popen(createIst,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = createInstance.communicate()
	InstanceId = out
	if verbose == 1 :
		print ("Creating an Instance "+str(InstanceId)+ " in Availability zone "+str(AvaZone))
	ec2wait(InstanceId)
	return InstanceId



# Create an instance in the current region
def create_Instance():
	zone = getRegion()
	imageId = getImageId(zone)
	InstType = getInstType()
	if InstType == 0 :
        	createIst = "aws ec2 run-instances --image-id "+str(imageId)+ " --instance-type t2.micro  --count 1  --key-name ec2-backup --output text | awk 'FNR == 2 {print$7}' "
        else:
		createIst = "aws ec2 run-instances --image-id "+str(imageId)+ "--count 1 " +str(InstanceType)+ " --key-name ec2-backup --output text | awk 'FNR == 2 {print$7}' "

	createInstance = subprocess.Popen(createIst,shell=True,stdout=subprocess.PIPE,stderr=f)
        out, err = createInstance.communicate()
	InstanceId = out
	InstanceId = InstanceId.strip()
	if verbose == 1 :
		print ("Creating an Instance "+str(InstanceId)+" in the Availability zone "+str(zone))
	ec2wait(InstanceId)
	return InstanceId



#The main objective is to validate the volume provided, and check if the size is enough to backup
#Throws an error if the given volume size is not enough to perform backup
def validateVolume(volumeId):
	validatedir() 
	validVol = "aws ec2 describe-volume-status --volume-ids "  +str(volumeId)+ " --query 'VolumeStatuses[*].VolumeStatus.Status'"
	volume = subprocess.Popen(validVol,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = volume.communicate()

	if verbose == 1:
		print ("Verifying volume...")
	if 'ok' in out:
		volstatus(volumeId)
		v = volsize(volumeId)
		d = dirSize()
		if v > d :
			InstanceId = createInstance(volumeId)
			isSudoUser(InstanceId)
			attachVol(InstanceId,volumeId)
		else:
			print("The given volume "+str(volumeId)+" size is not enough to perform backup")
			exit(1)
	else:
		print("Given an Invalid volume "+str(volumeId))
		exit(1)



#When volume is not provided, a new volume is created depending up on the zone of the instance spinned
#The size of the volume is defined depending upon size of backup directory.
#if size of backup is less than 1GB a volume of 2 GB is created by default else double the size of directory.
 
def createVolume():
	validatedir()
	d = dirSize()
	dirsize = int(d)
	if dirsize <= 1: 
		dirsize = 2
	else:
		dirsize = 2*dirsize
	
	InstanceId = create_Instance()
	isSudoUser(InstanceId)
	Region = getInstanceZone(InstanceId)	

	createvol = "aws ec2 create-volume --size 10 --availability-zone "+str(Region)+ " --size "+str(dirsize)+  "  --output text | awk 'FNR == 1 {print$7;exit}'"
    	volumeID = subprocess.Popen(createvol,shell=True,stdout=subprocess.PIPE,stderr=f)
        out, err = volumeID.communicate()
	volumeId = out.strip()
	print("Created volume : "+str(volumeId))    
	time.sleep(15)
	return (InstanceId,volumeId)



#This function is to handel EC2_BACKUP_FLAGS_AWS , prints an error message if the set flag is not available.
def getInstType():
	if InstanceType == None:
		return 0
	else:
		Itype = InstanceType.split(" ")
		Itype = Itype[-1]
		if Itype in ['t2.micro','t2.small','t2.medium','t3.micro','t3.small']:
			return 1
		else:
			print ("Given instance type is not available, available Instance types are t2.micro,t2.small,t2.medium,t3.micro,t3.small ")
			exit (1)	

	
# makes sure to wait till the instance got into running state	
def ec2wait(InstanceId):
	wait = "aws ec2 wait instance-running --instance-id "+(InstanceId)
	Wait = subprocess.Popen(wait,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = Wait.communicate()


#Attacht the given or created volume to the Instance created.
#After attaching calls SSH and terminate functions by passing the required paramenters
def attachVol(InstanceId,volumeId):
        InstanceId = InstanceId.strip()
        volumeId   = volumeId.strip()
	time.sleep(15)
        attachVol = "aws ec2 attach-volume --volume-id "+str(volumeId)+" --instance-id "+str(InstanceId)+" --device /dev/sde"
        AttachVol = subprocess.Popen(attachVol,shell=True,stdout=subprocess.PIPE,stderr=f)
        out, err = AttachVol.communicate()
	if verbose == 1:
		print("Attaching volume to the Instance....")
	SSH = SSHinstance(InstanceId)
	d = dirSize()
	terminate(InstanceId)
	print ("Back Complete, "+str(d)+"GB of data sent  to volume :"+str(volumeId))
	



#Will SSH it to the Instance depending upon the EC2_BACKUP_FLAGS_SSH
def SSHinstance(InstanceId):
	instIp = getInstDNS(InstanceId)
	time.sleep(60)
	if verbose == 1:
		print("Performing backup...")
	if SSHflag == None:
		ssh = "tar cf - " +str(backupDir)+  " | ssh ec2-user@" +str(instIp)+" -o StrictHostKeyChecking=no  'sudo dd of=/dev/xvde'"
	else:	
		ssh = "tar cf - " +str(backupDir)+  " | ssh -i ec2-backup.pem ec2-user@" +str(instIp)+" -o StrictHostKeyChecking=no  'sudo dd of=/dev/xvde'"	

	SSH = subprocess.Popen(ssh,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = SSH.communicate()
	return out

def isSudoUser(InstanceId):
	if str(backupDir) == "/":
		sudov = "sudo -v"
		sudoV = subprocess.Popen(sudov, shell=True, stdout=subprocess.PIPE, stderr=f)
		out, err = sudoV.communicate()
		if sudoV.returncode != 0:
			print("Couldn't backup the given root directory since user is not sudo user")
			terminate(InstanceId)
			exit(1)
	return

#query to get the availability zone of the volume passed to function 
def getAvaZone(volumeId):
	getZone = "aws ec2 describe-volumes --volume-ids " +str(volumeId)+  " --query 'Volumes[*].AvailabilityZone'"
	volZone = subprocess.Popen(getZone,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = volZone.communicate()
	return out


#query to get configured region
def getRegion():
	getReg = "aws ec2 describe-availability-zones --query 'AvailabilityZones[*].RegionName' | awk '{print$1}'"
	Region = subprocess.Popen(getReg,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = Region.communicate()
	return out.strip()


#query to get the availability zone of the Instance
def getInstanceZone(InstanceId):	
	getInstZone = "aws ec2 describe-instances --instance-id " +str(InstanceId)+"  --query 'Reservations[*].Instances[*].Placement.AvailabilityZone'"
	Instzone = subprocess.Popen(getInstZone,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = Instzone.communicate()
	return out.strip()	
  

#query to get DNS of the instance to perform SSH connection
def getInstDNS(InstanceId):
	getDns = "aws ec2 describe-instances --instance-id "+str(InstanceId)+" --filter Name=instance-state-name,Values=running  --query 'Reservations[*].Instances[*].{Instance:PublicDnsName}'"
	DNS = subprocess.Popen(getDns,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = DNS.communicate()
	return out.strip()



#query to get volume size of the provided VolumeId
def volsize(volId):	
	volsz = "aws ec2 describe-volumes --volume-ids " +str(volId)+  " --query Volumes[].Size"
	volSZ = subprocess.Popen(volsz,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = volSZ.communicate()
	out = out.strip()
	out = float(out)
	return out



#Query to check the status of the volume i.e; available or in-use
def volstatus(volId):
	volstatus = "aws ec2 describe-volumes --volume-ids " +str(volId)+ " --query 'Volumes[*].State'"
	volStatus = subprocess.Popen(volstatus,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = volStatus.communicate()
	if out.strip() == "available":
		pass
	else:
		print ("Given volume "+str(volId)+" is attached to aother instance")
		exit(1)
	

	
#Terminates the Instance
def terminate(InstanceId):
	terinst = "aws ec2 terminate-instances --instance-ids "+str(InstanceId)
	terInst = subprocess.Popen(terinst,shell=True,stdout=subprocess.PIPE)
	out, err = terInst.communicate()
	if verbose == 1:
		print ("Terminating the instance "+str(InstanceId))
	return out.strip()


#gets size of the backup directory
#throws an error if the size of the backup directory is null or no files in it.	
def dirSize():
	dirsize = "du -sh "+str(backupDir)+" | awk 'FNR ==1 {print$1}'"
	dirSize = subprocess.Popen(dirsize,shell=True,stdout=subprocess.PIPE,stderr=f)
	out, err = dirSize.communicate()
	out = str(out).strip()
	size = out[:-1]
	size = float(size[:-1])
	if out[-1] == "G":
		return size
	elif out[-1] == "M":
		return size/1000
	elif out[-1] == "K":
		return size/10000
	else:
		print ("The given directory does not contain any files to backup")	
		exit(1)



#Validate the given back directory, checks if it exists
def validatedir():
	a = os.path.expanduser(backupDir)
	A = os.path.exists(a)
	if A == True:
		return
	else:	
		print ("The given directory " +str(backupDir)+ " does not exist")
		exit(1)



#Image ID mapping depending upon the available regions
#Throws an error if mapping if not available for a region
def getImageId(zone):
	zoneID = zone
	AvaZoneMap = {
		"us-east-1"   :"ami-0c322300a1dd5dc79",
		"us-east-2"   :"ami-0520e698dd500b1d1",
		"us-west-1"   :"ami-00fc224d9834053d6",
		"us-west-2"   :"ami-087c2c50437d0b80d",
		"ca-central-1":"ami-0b85d4ff00de6a225",
		"sa-east-1"   :"ami-049d8bf763f81a55f",
		"eu-central-1":"ami-0badcc5b522737046",
		"eu-west-2"   :"ami-0a0cb6c7bcb2e4c51",
		"ap-south-1"  :"ami-0a74bfeb190bd404f"
	
		}
	if zoneID in AvaZoneMap:
		imageID = AvaZoneMap[zoneID]
		return(imageID)
	else:
		print("The tool does not support the current region "+(zoneID))
		exit (1)



#The Main condition where it starts with checking for volume ID.
if volumeId != 0:

        validateVolume(volumeId)
else:
	
	volumeId = createVolume()
	attachVol(volumeId[0],volumeId[1])



	






