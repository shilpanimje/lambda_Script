#!/bin/bash

# This is the build script that can be executed within a Lambda build Docker container.
# Usage from host OS:
#
# docker run -it \
# --volume <repo home>:/reporoot <Lambda image> \
# /home/jenkins/build.sh \
# <environment> \
# /reporoot/<path to Lambda root in repo> \
# <Lambda dir name>
#
# This script and the Docker process will exit with code 0 upon successful installation
# of dependencies, packaging of function, and execution of unit tests.

export ENVIRONMENT="$1"
export LAMBDA_HOME="$2"
export FUNC_NAME="$3"

# Fix for Google Protobuf issue in Kinesis Aggregation module
# https://github.com/awslabs/kinesis-aggregation/tree/master/python#important-build-note-for-aws-lambda-users
# You can disable it if you do not use Kinesis Aggregation.
export FIX_GOOGLE_PROTOBUF=1

if [ -z "$ENVIRONMENT" -o -z "$LAMBDA_HOME" -o -z "$FUNC_NAME" ]
then
    echo "Please provide environment, lambda home dir, and function name" >&2
    exit 1
fi

export VIRT_NAME="virt_$FUNC_NAME"
export VIRT_HOME="/home/jenkins/$VIRT_NAME"
export DEPLOY_ZIP="$LAMBDA_HOME/$FUNC_NAME/deploy.zip"

rm -rf "./$VIRT_NAME"
cd "/home/jenkins" || exit 1
virtualenv "$VIRT_NAME" -p "$(which python3)"
source "$VIRT_HOME/bin/activate"
cd "$VIRT_HOME" || exit 1
pip install -r "$LAMBDA_HOME/$FUNC_NAME/requirements.txt"
# Uninstall some packages that may conflict with those provided by Lambda runtime
pip uninstall -y boto3
pip uninstall -y botocore
deactivate

# Clean up previous deploy file if existed.
rm "$DEPLOY_ZIP"

# Zip up dependencies.
cd "$VIRT_HOME" || exit 1
cd "$VIRT_HOME/lib/python3.6/site-packages" || exit 1
zip -r "$DEPLOY_ZIP" *

# Fix Google Protobuf issue for Lambda
if [ -e "$VIRT_HOME/lib/python3.6/site-packages/google" ] &&
   [ $FIX_GOOGLE_PROTOBUF -eq 1 ]
then
    echo "Fixing google protobuf package issue"
    cd "$VIRT_HOME" || exit 1
    mkdir google
    touch google/__init__.py
    zip -ur "$DEPLOY_ZIP" google/
    rm -rf google/
fi

# If available, zip up shared Lambda modules.
if [ -e "$LAMBDA_HOME/common" ]
then
    export PYTHONPATH="$PYTHONPATH:$LAMBDA_HOME/common"
    cd "$LAMBDA_HOME/common" || exit 1
    find . -name '*.py' | xargs zip "$DEPLOY_ZIP"
fi

# Zip up Lambda function itself.
cd "$LAMBDA_HOME/$FUNC_NAME" || exit 1
find . -name '*.py' | xargs zip "$DEPLOY_ZIP"

# Now we run tests.

source "$VIRT_HOME/bin/activate"

if [ -e "$LAMBDA_HOME/common" ]
then
    cd "$LAMBDA_HOME/common"

    if [ -f "$LAMBDA_HOME/common/requirements.txt" ]
    then
        pip install -r "$LAMBDA_HOME/common/requirements.txt"
    fi

    pip install -r "$LAMBDA_HOME/common/requirements-dev.txt"
    python -V
    if [ -d tests ]; then
        python -m pytest tests/
    fi
    TEST_COMMON_EXIT_CODE="$?"
    # We need to ignore import order, because flake8 treats modules imported from
    # 'common' as external packages.
    flake8 --version
    flake8 --ignore=I100
    LINT_COMMON_EXIT_CODE="$?"
fi
cd "$LAMBDA_HOME/$FUNC_NAME" || exit 1
pip install -r "$LAMBDA_HOME/$FUNC_NAME/requirements-dev.txt"

if [ -d tests ]; then
    python -m pytest tests/
fi
TEST_EXIT_CODE="$?"
cd "$LAMBDA_HOME/$FUNC_NAME" || exit 1
# We need to ignore import order, because flake8 treats modules imported from
# 'common' as external packages.
flake8 --version
flake8 --ignore=I100
LINT_EXIT_CODE="$?"
deactivate
echo "Common tests exit code: $TEST_COMMON_EXIT_CODE"
echo "Common lint exit code: $LINT_COMMON_EXIT_CODE"
echo "Tests exit code: $TEST_EXIT_CODE"
echo "Lint exit code: $LINT_EXIT_CODE"

exit $[ $TEST_COMMON_EXIT_CODE + $LINT_COMMON_EXIT_CODE + $TEST_EXIT_CODE + $LINT_EXIT_CODE ]
