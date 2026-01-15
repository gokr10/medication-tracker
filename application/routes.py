from __future__ import annotations

import datetime
from typing import Optional

from flask import Blueprint, Response, abort, make_response, request
from sqlalchemy.exc import IntegrityError

from application import db
from application.models import Medication, User, UserLog, UserMedication


bp = Blueprint('application', __name__)


def get_user(user_id, raises=True):
    # type: (int, bool) -> Optional[User]
    """
    Get the user specified by user_id and optionally raise if non-existent.
    """
    user = db.session.scalar(db.select(User).where(User.user_id == user_id))
    if not user and raises:
        abort(400, 'Invalid user_id - no user with id exists')
    return user



@bp.route('/medications', methods=['POST'])
def add_medication():
    # type: () -> Response
    """
    Accept: user_id, medication_name, dosage, unit, frequency, start_date, instructions

    Create the medication record and its schedule

    Return the created medication with ID
    """
    data = request.json

    user_id = data.get('user_id')
    # Validate that the specified user exists
    user = get_user(user_id)

    # Add Medication record or get existing one
    medication_name = data.get('medication_name')
    medication = Medication(medication_name=medication_name)
    db.session.add(medication)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        medication = db.session.scalar(db.select(Medication).where(
            Medication.medication_name == medication.medication_name))

    # Add UserMedication record
    dosage = data.get('dosage')
    unit = data.get('unit')
    frequency = data.get('frequency')
    start_date = data.get('start_date')
    instructions = data.get('instructions')
    user_medication = UserMedication(user_id=user.user_id,
                                     medication_id=medication.medication_id,
                                     dosage=dosage,
                                     unit=unit,
                                     frequency=frequency,
                                     instructions=instructions,
                                     date=start_date)
    db.session.add(user_medication)
    db.session.commit()

    return make_response({
        'message': f'Medication created successfully with medication_id: '
                   f'{user_medication.user_medication_id}',
        'medication': user_medication,
    }, 200)


@bp.route('/medications/<int:medication_id>/log', methods=['POST'])
def log_medication_dosage(medication_id):
    # type: (int) -> Response
    """
    Add a UserLog for taking medication. Check for any skipped doses between the
    last log and this one and input records for those that were skipped.

    Note - database results are ordered descending by id here to get the last
    input UserMedication and UserLog records. This can be relied upon due to
    SQL's auto-incrementing behavior on primary keys.

    Expected fields in json data:
        user_id
        actual_time (optional)
        dosage (optional)
        units (optional)
        notes (optional)
    """
    data = request.json

    user_id = data.get('user_id')
    # Validate the user exists
    get_user(user_id)

    # Get UserMedication record to compare dosage/frequency information to
    user_medication = db.session.scalars(db.select(UserMedication).where(
        UserMedication.medication_id == medication_id,
        UserMedication.user_id == user_id
    ).order_by(UserMedication.user_medication_id.desc())).first()

    actual_time = data.get('actual_time')
    if actual_time:
        try:
            actual_time = datetime.datetime.fromisoformat(actual_time)
        except ValueError:
            abort(400, 'actual_time value must be passed as an ISO format date'
                       'string')
    else:
        actual_time = datetime.datetime.now(datetime.timezone.utc)

    # Default to the medication dosage if other value isn't input
    dosage = data.get('dosage') or user_medication.dosage
    unit = data.get('unit') or user_medication.unit
    notes = data.get('notes')

    # Get last input UserLog for this medication to check for the expected time
    # of this dosage and any missed doses
    last_user_log = db.session.scalars(db.select(UserLog).where(
        UserLog.user_medication_id == user_medication.user_medication_id,
        UserLog.user_id == user_id,
        UserLog.dosage > 0,
    ).order_by(UserLog.user_log_id.desc())).first()
    if last_user_log:
        last_dosage_time = last_user_log.actual_time
        frequency_timedelta = datetime.timedelta(
            minutes=user_medication.frequency)
        # FIXME: if a user has multiple previous skipped doses, is the expected
        #  time after the last actual dose? Does it make sense to add these
        #  empty doses as log records? Benefit - quicker to query for skipped
        expected_time = last_dosage_time + frequency_timedelta

        minutes_elapsed = (actual_time - last_dosage_time).total_seconds() / 60
        # If full dose cycle(s) have passed between the last actual dose and
        # this dose, input records with dosage=0 for the skipped doses.
        if minutes_elapsed >= user_medication.frequency * 2:
            curr_dose_time = expected_time
            while curr_dose_time + frequency_timedelta < actual_time:
                skipped_log = UserLog(
                    user_id=user_id,
                    user_medication_id=user_medication.user_medication_id,
                    expected_time=curr_dose_time,
                    actual_time=curr_dose_time,
                    dosage=0,
                    unit=unit)
                db.session.add(skipped_log)
                curr_dose_time += frequency_timedelta
    else:
        # This is the first time the user has taken the medication. Log the
        # actual time as the expected time.
        expected_time = actual_time

    # Add UserLog record
    user_log = UserLog(user_id=user_id,
                       user_medication_id=user_medication.user_medication_id,
                       expected_time=expected_time,
                       actual_time=actual_time,
                       dosage=dosage,
                       unit=unit,
                       notes=notes)
    db.session.add(user_log)
    db.session.commit()
    return make_response(
        {'message': f'UserLog created successfully with user_log_id: '
                    f'{user_log.user_log_id}',
         'log': user_log,
    }, 200)


@bp.route('/users/<int:user_id>/medications', methods=['GET'])
def get_medications(user_id):
    # type: (int) -> Response
    """
    Get all active medications for a user and dosage schedule information.
    """
    # Validate the user exists
    get_user(user_id)

    # Get UserMedication records
    user_medications = db.session.scalars(db.select(UserMedication).where(
        UserMedication.user_id == user_id
    ).join(Medication).filter(Medication.active == True)).all()
    return make_response({'medications': user_medications}, 200)


@bp.route('/users/<int:user_id>/medication_logs', methods=['GET'])
def get_medication_logs(user_id):
    # type: (int) -> Response
    """
    Get medication logs for a user with additional filters:
    - date range - (start_date, end_date)
    - medication
    - skipped/late doses

    Optional filter by specific medication

    Pagination support

    Return with both scheduled and actual times

    Show which doses were taken, skipped, or taken late
    """
    # Validate the user exists
    get_user(user_id)

    data = request.json

    query = db.select(UserLog).filter(UserLog.user_id == user_id)

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    if start_date:
        try:
            start_date = datetime.datetime.fromisoformat(start_date)
        except ValueError:
            abort(400, 'start_date value must be passed as an ISO format date'
                       'string')
        query = query.filter(UserLog.actual_time >= start_date)
    if end_date:
        try:
            end_date = datetime.datetime.fromisoformat(end_date)
        except ValueError:
            abort(400, 'end_date value must be passed as an ISO format date'
                       'string')
        query = query.filter(UserLog.actual_time <= end_date)

    medication_name = data.get('medication_name')
    if medication_name:
        query = query.join(UserMedication).join(Medication).filter(
            Medication.medication_name == medication_name)

    # TODO: add pagination to help with large log history
    user_logs = db.session.scalars(query).all()
    return make_response({'logs': user_logs}, 200)


@bp.route('/users/<int:user_id>/adherence', methods=['GET'])
def get_adherence_history(user_id):
    """
    For a given date range and optionally specific medication:
    - Total scheduled doses
    - Total taken doses
    - Adherence percentage
    - On-time percentage (taken within 30 min of scheduled time)
    - Average delay for late doses
    """
    # TODO:
    #  - pull from UserLog records for taken doses
    #  - the 0 dose records could be useful here to more easily determine total
    #    scheduled doses, as well as for dose adherance stats
    #  - compare expected_time to actual_time for non-0 doses to get on-time %
    pass
