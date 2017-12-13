#!/bin/bash

# This is the deploy script that can be executed on the host environment to send Lambda
# function zip file to appropriate AWS account/environment.  Prerequisites are the following:
# - active AWS account
# - pre-provisioned Python 3.6 Lambda function named <environment>-<function name>
# - existing Lambda zip file on host OS (obtained from executing build.sh)
# - not technically required, but highly recommended: successful exit code from executing build.sh

# Example:
# $ cd project_root/
# $ ./build/deploy.sh dev accounting/lambda consumer accounting_consumer

ENVIRONMENT="$1"
LAMBDA_HOME="$2"
FUNC_NAME="$3"
AWS_LAMBDA_NAME="$4"

if [ -z "$ENVIRONMENT" -o -z "$LAMBDA_HOME" -o -z "$FUNC_NAME" -o -z "$AWS_LAMBDA_NAME" ]
then
    echo "Please provide environment, lambda home dir, function name, and aws function name" >&2
    exit 1
fi

DEPLOY_ZIP="$LAMBDA_HOME/$FUNC_NAME/deploy.zip"

# Upload function code if function exists
if $(aws lambda get-function --function-name ${ENVIRONMENT}-${AWS_LAMBDA_NAME} --region us-east-1 --query 'Configuration.[FunctionName]' | grep -q ${ENVIRONMENT}-${AWS_LAMBDA_NAME}); then
    aws lambda update-function-code --function-name ${ENVIRONMENT}-${AWS_LAMBDA_NAME} --zip-file fileb://${DEPLOY_ZIP} --region us-east-1
    exit "$?"
else 
    echo "${ENVIRONMENT}-${AWS_LAMBDA_NAME} not found. This may mean that the function does not exist, the name is wrong, or another error occurred." >&2
    exit 1
fi
