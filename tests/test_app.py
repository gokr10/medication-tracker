from __future__ import annotations

import datetime
import uuid
from http import HTTPStatus

import pytest

from application import create_app, db
from application.models import Medication, User, UserLog, UserMedication

"""
TODO:
- testing config that points to a test db
- more parametrized arg inputs for edge cases
"""

# FIXME: set to True or remove condition completely to run db cleanup after
#  fixture use. Setting to False for now for visibility of test data since I
#  didn't include seed data
DO_DB_CLEANUP = False


# Default parameters for creating test UserMedication instance. Note - need to
# provide user_id and medication_id for fully valid parameters.
DEFAULT_USER_MEDICATION = {
    'dosage': 200,
    'unit': 'mg',
    'frequency': 24 * 60,  # Every 24 hours
}

UTC_NOW = datetime.datetime.now(datetime.timezone.utc)


# Utils ------

def get_unique_name(prefix=''):
    suffix = uuid.uuid4()
    return f'{prefix}{suffix}'


def rfc_date_to_datetime(rfc_date):
    # type: (str) -> datetime.datetime
    """
    Helper to convert RFC 1123 format date string (that is returned with json
    responses) to a datetime object.
    FIXME: is there a better way to get flask/json to use ISO format when it
      serializes dates within the flask app code?
    """
    return datetime.datetime.strptime(
        rfc_date, '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=datetime.timezone.utc)


# Fixtures ------

@pytest.fixture()
def app():
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture()
def client(app):
    yield app.test_client()


@pytest.fixture()
def user(app):
    """
    user fixture that creates records for a test user that has associated
    medications and medication schedule information.
    Delete the records on fixture closure
    """
    user = User(first_name=get_unique_name(prefix='Jane'),
                          last_name=get_unique_name(prefix='Doe'))

    with app.app_context():
        db.session.add(user)
        db.session.commit()

    yield user

    if DO_DB_CLEANUP:
        db.session.delete(user)


@pytest.fixture()
def medications(app, user):
    medication_foo = Medication(
        medication_name=get_unique_name(prefix='foo'))
    medication_bar = Medication(
        medication_name=get_unique_name(prefix='bar'))

    # medication_id is needed to create below associated records, commit now
    with app.app_context():
        db.session.add_all((medication_foo, medication_bar))
        db.session.commit()

    yield medication_foo, medication_bar

    if DO_DB_CLEANUP:
        db.session.delete(medication_foo)
        db.session.delete(medication_bar)


@pytest.fixture()
def user_medications(app, user, medications):
    medication_foo, medication_bar = medications

    user_medication_foo_args = DEFAULT_USER_MEDICATION.copy()
    user_medication_foo_args.update({'user_id': user.user_id,
                                     'medication_id': medication_foo.medication_id})
    user_medication_foo = UserMedication(**user_medication_foo_args)
    user_medication_bar_args = DEFAULT_USER_MEDICATION.copy()
    user_medication_bar_args.update({'user_id': user.user_id,
                                     'medication_id': medication_bar.medication_id})
    user_medication_bar = UserMedication(**user_medication_bar_args)

    with app.app_context():
        db.session.add_all((user_medication_foo, user_medication_bar))
        db.session.commit()

    yield user_medication_foo, user_medication_bar

    if DO_DB_CLEANUP:
        db.session.delete(user_medication_foo)
        db.session.delete(user_medication_bar)


@pytest.fixture()
def user_logs(app, user, medications, user_medications):
    user_medication1, user_medication2 = user_medications
    
    user_log1 = UserLog(user_id=user.user_id,
                                  user_medication_id=user_medication1.user_medication_id,
                                  expected_time=UTC_NOW,
                                  actual_time=UTC_NOW,
                                  dosage=200,
                                  unit='mg',
                                  notes='user log 1')

    user_log2 = UserLog(user_id=user.user_id,
                                  user_medication_id=user_medication2.user_medication_id,
                                  expected_time=UTC_NOW,
                                  actual_time=UTC_NOW,
                                  dosage=400,
                                  unit='mg',
                                  notes='user log 2')

    with app.app_context():
        db.session.add_all((user_log1, user_log2))
        db.session.commit()

    yield user_log1, user_log2

    if DO_DB_CLEANUP:
        db.session.delete(user_log1)
        db.session.delete(user_log2)


# Tests ------

# FIXME: add more arg_overrides for different edge cases
@pytest.mark.parametrize(
    'arg_overrides, expected_response',
    [({'user_id': None}, HTTPStatus.BAD_REQUEST),
     ({}, HTTPStatus.OK)],
    ids=('invalid_user',
         'valid_parameters')
)
def test_add_medication(arg_overrides, expected_response, client, user):
    """
    Test Medication record creation via the /medications endpoint
    """
    medication_data = DEFAULT_USER_MEDICATION.copy()
    medication_data['medication_name'] = get_unique_name()
    if 'user_id' not in arg_overrides:
        arg_overrides['user_id'] = user.user_id
    medication_data.update(arg_overrides)

    response = client.post('/medications',
                           json=medication_data)
    assert response.status_code == expected_response
    if response.status_code == HTTPStatus.OK:
        assert response.json['medication']['user_id'] == user.user_id
        medication_id = response.json['medication']['medication_id']
        assert medication_id
        # TODO: check db for created medication record? This is asserting the
        #  UserMedication was created successfully

        # Ensure submitting an additional request with the same name/info
        # returns the existing record instead of erroring
        response = client.post('/medications',
                               json=medication_data)
        assert response.json['medication']['medication_id'] == medication_id


# TODO: test more thoroughly here - add parametrization for testing missed doses
#  and expected vs scheduled
def test_log_medication_dosage(client, user, user_medications):
    """
    Test UserLog creation
    """
    # Just use one medication for the purpose of this test
    user_medication = user_medications[0]
    medication_id = user_medication.medication_id
    response = client.post(f'/medications/{medication_id}/log',
                           json={'user_id': user.user_id})

    assert response.status_code == HTTPStatus.OK
    assert response.json['log']['user_id'] == user.user_id
    assert response.json['log']['user_medication_id'] == user_medication.user_medication_id
    assert response.json['log']['actual_time'] is not None


@pytest.mark.parametrize(
    'user_id_override, expected_response',
    [(True, HTTPStatus.NOT_FOUND),
     (False, HTTPStatus.OK)],
    ids=('invalid_user',
         'valid_user')
)
def test_get_medications(user_id_override, expected_response, client, user_medications):
    """
    Test gathering UserMedication records
    """
    user_id = None if user_id_override else user_medications[0].user_id
    response = client.get(f'/users/{user_id}/medications')
    assert response.status_code == expected_response
    if response.status_code == HTTPStatus.OK:
        assert response.json['medications']
        assert all(user_med['user_id'] == user_id for user_med in
                   response.json['medications'])


@pytest.mark.parametrize(
    'start_date, end_date, specify_medication_name',
    [(UTC_NOW - datetime.timedelta(days=14),
      UTC_NOW + datetime.timedelta(days=14), False),
     (None, None, True),
     (UTC_NOW - datetime.timedelta(days=14),
      UTC_NOW + datetime.timedelta(days=14), True)],
    ids=('date_range',
         'medication_name',
         'date_range_and_medication_name')
)
def test_get_medication_logs(start_date, end_date, specify_medication_name, client, user, medications, user_logs):
    """
    Test gathering UserLog records
    """
    json_data = {}
    if start_date:
        json_data['start_date'] = start_date.isoformat()
    if end_date:
        json_data['end_date'] = end_date.isoformat()
    medication_name = None
    if specify_medication_name:
        # Just use one of the medication fixtures since its already in the db
        medication_name = medications[0].medication_name
        json_data['medication_name'] = medication_name

    response = client.get(f'/users/{user.user_id}/medication_logs',
                          json=json_data)
    assert response.status_code == HTTPStatus.OK

    logs = response.json['logs']
    assert logs
    if start_date:
        assert all(rfc_date_to_datetime(user_log['actual_time']) >= start_date
                   for user_log in logs)
    if end_date:
        assert all(rfc_date_to_datetime(user_log['actual_time']) <= end_date
                   for user_log in logs)
    if medication_name:
        # TODO: we have the logs here, so need to check that the log's
        #  associated medication has the same name
        pass
