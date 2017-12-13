"""Lambda to read csv file from s3 bucket."""

import csv
from functools import partial
import json
import logging
import os
import tempfile
import urllib.parse
import uuid

import boto3
from owsrequest import request as owsrequest


logger = logging.getLogger()
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
AWS_REGION_NAME = os.environ.get('AWS_REGION_NAME', 'us-east-1')
SNS_ARN = os.environ.get('SNS_ARN')
SNS_ARN_SUBJECT = 'Result For Bulk Accounting Payment Holds.'
LAMBDA_NAME = 'lambda-payment-holds'
PAYMENT_HOLD_SERVICE = 'ows-accounting'


def handler(event, context):
    """Lambda starting point."""
    print('Event=', json.dumps(event))
    # check if all required keys exists
    if not event.get('Records') or not event.get('Records')[0]['s3'] \
            or not event.get('Records')[0]['s3'].get('bucket') or \
            not event.get('Records')[0]['s3'].get('bucket').get('name'):
        return logger.error('Invalid event message parameters.')

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    s3 = boto3.resource('s3')

    obj = s3.Object(bucket, urllib.parse.unquote(key))

    # check creator id
    if 'creator_id' not in obj.get()['Metadata']:
        return logger.error(
            'S3 File {} did not have creator_id. '
            'It might not be uploaded from OA.'.format(key))

    creator_id = obj.get()['Metadata']['creator_id']
    correlation_id = str(uuid.uuid1())
    print('correlation_id=', correlation_id)

    # list of vendor_ids from csv file
    vendor_list = {}
    # create temp dir
    with tempfile.TemporaryFile() as temp:
        s3.Bucket(bucket).download_fileobj(key, temp)
        temp.seek(0)
        file_contents = csv.reader(temp.read().decode('utf8').splitlines())
        next(file_contents)  # skip first header row
        for row in file_contents:
            vendor_list[str(row[0])] = str(row[1])

    request = partial(owsrequest.process, LAMBDA_NAME, ENVIRONMENT)

    # make /holds/active call with all vendor_ids
    response = get_active_vendor_holds(vendor_list, request, correlation_id)
    if response.status_code != 200:
        return logger.error(
            'Failed to get active holds for vendor. Actual error: {}'.format(
                response.text))

    active_hold_id_list = {}
    for vendor_data in response.json()['items']:
        active_hold_id_list[str(vendor_data['vendor_id'])] = str(
            vendor_data['hold_id'])

    oa_user_id = 'oa:{}'.format(creator_id)
    headers = {
        'Content-type': 'application/json',
        'Orchard-User-Id': oa_user_id,
        'Grass-Account-Type': 'vendor'}

    sns_response = {}

    for vendor_id in vendor_list:
        # check vendor id in csv file is exist in active vendor id list,
        # if present then do put call else post call.
        if vendor_id in active_hold_id_list:
            response = send_put_request(
                active_hold_id_list[vendor_id], vendor_list[vendor_id],
                request, headers, correlation_id)
        else:
            response = send_post_request(
                vendor_id, vendor_list[vendor_id], request, headers,
                correlation_id)

        if response.status_code == 200:
            sns_response[vendor_id] = 'active hold successfully created.'
        else:
            sns_response[vendor_id] = response.text

    send_sns(sns_response, key, correlation_id)


def get_active_vendor_holds(vendor_list, request, correlation_id):
    """Get active vendor list.

    Args:
        vendor_list (list): vendor ids list.
        request (owsrequest): partial request object.
        correlation_id (int): correlation id.

    Return:
        Response: response obj with status and response text.
    """
    vendor_ids = ','.join(vendor_list)
    url = '/holds/active?vendor_ids={}'.format(vendor_ids)

    response = request('GET', PAYMENT_HOLD_SERVICE, url, correlation_id)

    return response


def send_post_request(vendor_id, description, request, header, correlation_id):
    """Save status active.

    Args:
        vendor_id (int): vendor id.
        description (string): description for vendor id.
        request (owsrequest): partial request object.
        header (dict): header params.
        correlation_id (int): correlation id.

    Return:
        Response: response obj with status and response text.
    """
    url = '/holds/vendor/{0}'.format(vendor_id)
    data = {
        'status': 'active',
        'description': description
    }
    response = request(
        'POST', PAYMENT_HOLD_SERVICE, url, correlation_id, headers=header,
        data=json.dumps(data))
    return response


def send_put_request(hold_id, description, request, header, correlation_id):
    """Update status active.

    Args:
        hold_id (int): hold id.
        description (string): description for vendor id.
        request (owsrequest): partial request object.
        header (dict): header params.
        correlation_id (int): correlation id.

    Return:
        Response: response obj with status and response text.
    """
    url = '/holds/{0}'.format(hold_id)
    data = {
        'status': 'active',
        'description': description
    }

    response = request(
        'PUT', PAYMENT_HOLD_SERVICE, url, correlation_id, headers=header,
        data=json.dumps(data))
    return response


def send_sns(message, file, correlation_id):
    """Publish message using AWS SNS.

    Args:
        message (dict): {vendor_id: result of api call}.
        file (string): csv filename.
        correlation_id (int): correlation id.
    """
    response_list = []
    for (key, value) in message.items():
        response_list.append('Vendor %s :: %s' % (key, value))
    response_str = '\n'.join(response_list)

    filename_msg = 'Bulk Payment Hold Filename: {}'.format(
        os.path.basename(file))
    run_id_msg = 'Run id: {}'.format(correlation_id)
    result_msg = 'For holds data in this csv: \n\n{}'.format(response_str)
    footer_msg = 'You can view/edit these holds from OA > View vendor page' \
        ' > Payment holds panel.'

    formatted_msg = '{filename}\n\n{run_id}\n\n{result}\n\n{footer}'.format(
        filename=filename_msg, run_id=run_id_msg, result=result_msg,
        footer=footer_msg)

    sns = boto3.client(service_name='sns', region_name=AWS_REGION_NAME)

    return sns.publish(
        TopicArn=SNS_ARN,
        Message=formatted_msg,
        Subject=SNS_ARN_SUBJECT)
