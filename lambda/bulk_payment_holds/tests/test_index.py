"""Lambda test module."""
import json
from unittest.mock import Mock
from unittest.mock import patch

import boto3
from moto import mock_s3
from moto import mock_sns
import pytest

import index  # noqa


@pytest.fixture
def s3_create_event():
    """Create test event."""
    return {
        'Records': [
            {
                'eventVersion': '2.0',
                'eventTime': '1970-01-01T00:00:00.000Z',
                'requestParameters': {
                    'sourceIPAddress': '127.0.0.1'
                },
                's3': {
                    'configurationId': 'testConfigRule',
                    'object': {
                        'eTag': '0123456789abcdef0123456789abcdef',
                        'sequencer': '0A1B2C3D4E5F678901',
                        'key':
                            'bulk_payment_holds/template_20170802081510.csv',
                        'size': 14
                    },
                    'bucket': {
                        'arn': 'arn:aws:s3:::dev-cucumbers',
                        'name': 'dev-cucumbers',
                        'ownerIdentity': {
                            'principalId': 'EXAMPLE'
                        }
                    },
                    's3SchemaVersion': '1.0'
                },
                'responseElements': {
                    'x-amz-id-2': 'EXAMPLE123/5678abcdefghijklambdaisawesome',
                    'x-amz-request-id': 'EXAMPLE123456789'
                },
                'awsRegion': 'us-east-1',
                'eventName': 'ObjectCreated:Put',
                'userIdentity': {
                    ''
                    'principalId': 'EXAMPLE'
                },
                'eventSource': 'aws:s3'
            }
        ]
    }


@mock_s3
@patch('index.uuid')
@patch('index.send_sns')
@patch('index.send_put_request')
@patch('index.send_post_request')
@patch('index.get_active_vendor_holds')
@patch('index.partial')
@patch('index.logger')
def test_handler(
        mock_logger, mock_partial, mock_get_active, mock_send_post,
        mock_send_put, mock_send_sns, mock_uuid, s3_create_event):
    """Test handler."""
    request_obj = Mock()
    mock_partial.return_value = request_obj
    conn = boto3.resource('s3', region_name='us-east-1')
    # We need to create the bucket since this is all in Moto's 'virtual' aws.
    key = 'bulk_payment_holds/template_20170802081510.csv'
    conn.create_bucket(Bucket='dev-cucumbers')
    csv_raw = 'Vendor Id,Description\n123,desc\n456,desc2'.encode('utf-8')
    conn.Object(
        'dev-cucumbers', key).put(
        Body=csv_raw,
        Metadata={'creator_id': '123'})
    expected_result = Mock()
    expected_result.status_code = 200
    expected_result.json = Mock(return_value={'pagination': {
        'total_records': 5, 'type': 'none'}, 'items': [
        {'description': 'Returned Payment', 'creator_id': 'oa:179',
         'vendor_id': 84, 'hold_id': 1031}]})

    mock_get_active.return_value = expected_result
    mock_send_sns.return_value = None
    mock_uuid.uuid1.return_value = '12345.11'
    oa_user_id = 'oa:{}'.format('123')
    headers = {
        'Content-type': 'application/json', 'Orchard-User-Id': oa_user_id,
        'Grass-Account-Type': 'vendor'}
    result = index.handler(s3_create_event, None)

    assert result is None
    mock_get_active.assert_called_once_with(
        {'123': 'desc', '456': 'desc2'}, request_obj, '12345.11')
    mock_send_post.assert_any_call(
        '456', 'desc2', request_obj, headers, '12345.11')
    assert mock_send_post.call_count == 2
    mock_send_put.asset_not_called()


def test_get_active_vendor_holds():
    """Test get_active_vendor_holds."""
    mock_request = Mock()
    vendor_list = {'123': 'desc1', '456': 'desc2'}
    expected_result = [{
        'hold_id': '1', 'vendor_id': '456', 'description': 'desc2',
        'status': 'active'}]
    mock_request.return_value = expected_result

    result = index.get_active_vendor_holds(vendor_list, mock_request, '1')
    vendor_ids = ','.join(vendor_list)
    url = '/holds/active?vendor_ids={}'.format(vendor_ids)
    mock_request.assert_called_once_with(
        'GET', index.PAYMENT_HOLD_SERVICE, url, '1')
    assert result == expected_result


def test_send_post_request():
    """Test send_post_request."""
    mock_request = Mock()
    expected_result = {'status_code': '200'}
    mock_request.return_value = expected_result

    result = index.send_post_request('123', 'desc', mock_request, {}, '1')
    url = '/holds/vendor/123'
    data = {
        'status': 'active',
        'description': 'desc'
    }
    mock_request.assert_called_once_with(
        'POST', index.PAYMENT_HOLD_SERVICE, url, '1', headers={},
        data=json.dumps(data))
    assert result == expected_result


def test_send_put_request():
    """Test send_put_request."""
    mock_request = Mock()
    expected_result = {'status_code': '200'}
    mock_request.return_value = expected_result
    result = index.send_put_request('1', 'desc', mock_request, {}, '1')
    url = '/holds/1'
    data = {
        'status': 'active',
        'description': 'desc'
    }
    mock_request.assert_called_once_with(
        'PUT', index.PAYMENT_HOLD_SERVICE, url, '1', headers={},
        data=json.dumps(data))
    assert result == expected_result


@mock_sns
def test_send_sns():
    """Test send_sns."""
    sns = boto3.client('sns', region_name='us-east-1')
    topic_res = sns.create_topic(Name='some_topic')
    sns_topic_arn = topic_res['TopicArn']
    index.SNS_ARN = sns_topic_arn
    index.AWS_REGION_NAME = 'us-east-1'
    message = {'456': 'success'}
    result = index.send_sns(message, 'abdc', '1')
    assert result['ResponseMetadata']['HTTPStatusCode'] == 200
