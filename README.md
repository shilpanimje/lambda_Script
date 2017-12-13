# lambda-payment-holds


### Getting started

Prepare your Docker image (we will call it `ci-lambda`):

```
$ docker build -t ci-lambda /var/www/html/lambda-payment-holds/build/
```

### Development

It may not be possible to run your Lambda function outside of the Lambda environment.  It should be
possible, however, to use the build script provided by this Docker container to ensure all
dependencies are satisfied and unit tests pass.

To prepare a deploy file and run tests:

```
$ docker run -it --volume /var/www/html/lambda-payment-holds/:/reporoot ci-lambda /reporoot/build/build.sh dev /reporoot/lambda bulk_payment_holds
```

### Deployment

During development, it would be possible to deploy the function within dev
AWS account using the following command:

```
$ /var/www/html/lambda-payment-holds/lambda/build/deploy.sh dev /var/www/html/lambda-payment-holds/lambda/ bulk_payment_holds
```

This assumes that `dev` matches your AWS config profile pointing at Orchard's dev account.  You can
verify your AWS configuration as follows:

```
$ aws --profile dev configure list
      Name                    Value             Type    Location
      ----                    -----             ----    --------
   profile                      dev           manual    --profile
access_key     ****************IDJA shared-credentials-file    
secret_key     ****************osO9 shared-credentials-file    
    region                <not set>             None    None
```

The following would indicate a missing `dev` profile:

```
$ aws --profile dev configure list
      Name                    Value             Type    Location
      ----                    -----             ----    --------
   profile                      dev           manual    --profile

The config profile (dev) could not be found
```

Continuous integration
----------------------

Jenkins will be serve an interface for automatic building and deploying of Lambda functions outside
a local development environment.  A Jenkins job can be created with the following parameters:

- repo
- relative path to lambda dir (including lambda dir itself)
- Lambda function name (must match subdirectory)
- environment (dev, prod)

This job will perform the following steps:

1. clone the repo
2. install dependencies as per `requirements.txt`
3. create a zip file containing function's source code and its dependencies
4. install dependencies as per `requirements-dev.txt`
5. run pytests and flake8, halt on failure
6. deploy zip file into appropriate AWS account
