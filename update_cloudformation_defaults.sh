#!/bin/bash

if [[ "$#" == 0 ]] ; then
   PROFILE=default
elif [[ "$#" == 1 ]] ; then
   PROFILE=$1
fi

echo "Using AWS profile '$PROFILE'"

aws ec2 describe-vpcs --profile="$PROFILE"
vpc_json=$(aws ec2 describe-vpcs --profile="$PROFILE")
vpc=$(echo "$vpc_json" | jq '.Vpcs'[0]'.VpcId')
echo "$vpc"
subnet_json=$(aws ec2 describe-subnets --profile="$PROFILE")
subnet_len=$(echo "$subnet_json" | jq '.Subnets'[]'.AvailabilityZone' | wc -l)

#echo "$az"
#echo ${#az[*]}

for (( i=0; i<subnet_len; i++ ))
do
  echo "$subnet_json" | jq '.Subnets'[$i]'.AvailabilityZone'
  echo "$subnet_json" | jq '.Subnets'[$i]'.SubnetId'
done

#echo $subnet_json

