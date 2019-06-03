#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test OnapService module."""
import mock
import pytest

from jinja2 import Environment
from requests import Response, Timeout, Session

from onapsdk.onap_service import OnapService

def test_init():
    """Test initialization."""
    svc = OnapService()
    assert svc.server == None
    assert svc.header == None
    assert svc.proxy == None
    assert isinstance(svc._jinja_env, Environment)

@mock.patch.object(Session, 'request')
def test_send_message_error_400_no_exception(mock_request):
    """Should give back None if issues on request."""
    svc = OnapService()
    mocked_response = Response()
    mocked_response.status_code = 400
    mock_request.return_value = mocked_response
    response = svc.send_message("GET", 'test get', 'http://my.url/')
    mock_request.assert_called_once_with('GET', 'http://my.url/', headers=None,
                                         verify=False, proxies=None)
    assert response == None

@mock.patch.object(Session, 'request')
def test_send_message_error_400_exception(mock_request):
    """Should raise Exception given if issues on request."""
    with pytest.raises(KeyError):
        svc = OnapService()
        mocked_response = Response()
        mocked_response.status_code = 400
        mock_request.return_value = mocked_response
        response = svc.send_message("GET", 'test get', 'http://my.url/',
                                    exception=KeyError)
        mock_request.assert_called_once_with('GET', 'http://my.url/',
                                             headers=None, verify=False,
                                             proxies=None)

@mock.patch.object(Session, 'request')
def test_send_message_error_timeout_no_exception(mock_request):
    svc = OnapService()
    mock_request.side_effect = Timeout()
    response = svc.send_message("GET", 'test get', 'http://my.url/')
    mock_request.assert_called_once_with('GET', 'http://my.url/', headers=None,
                                         verify=False, proxies=None)
    assert response == None

@mock.patch.object(Session, 'request')
def test_send_message_error_timeout_exception(mock_request):
    with pytest.raises(KeyError):
        svc = OnapService()
        mock_request.side_effect = Timeout()
        response = svc.send_message("GET", 'test get', 'http://my.url/',
                                    exception=KeyError)
        mock_request.assert_called_once_with('GET', 'http://my.url/', headers=None,
                                             verify=False, proxies=None)

@mock.patch.object(Session, 'request')
def test_send_message_OK(mock_request):
    svc = OnapService()
    mocked_response = Response()
    mocked_response.status_code = 200
    mock_request.return_value = mocked_response
    response = svc.send_message("GET", 'test get', 'http://my.url/')
    mock_request.assert_called_once_with('GET', 'http://my.url/', headers=None,
                                         verify=False, proxies=None)
    assert response == mocked_response
