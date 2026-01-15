from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from application import db


# Database models ------

@dataclass
class User(db.Model):
    __tablename__ = 'users'

    user_id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(db.String, nullable=False)
    last_name: Mapped[str] = mapped_column(db.String, nullable=False)
    # TODO: add relationship to UserMedication table that allows access of
    #  user medications from the User model


@dataclass
class Medication(db.Model):
    __tablename__ = 'medications'

    medication_id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    medication_name: Mapped[str] = mapped_column(db.String, unique=True)
    active: Mapped[bool] = mapped_column(db.Boolean, default=True)


@dataclass
class UserMedication(db.Model):
    __tablename__ = 'user_medications'

    user_medication_id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.user_id'))
    medication_id: Mapped[int] = mapped_column(db.ForeignKey('medications.medication_id'))
    dosage: Mapped[int] = mapped_column(db.Integer)
    unit: Mapped[str] = mapped_column(db.String)
    frequency: Mapped[int] = mapped_column(db.Integer)
    instructions: Mapped[Optional[str]] = mapped_column(db.String, nullable=True)
    # Using `date` here instead of start_date as specified in the assessment - the user start date will be determined
    # instead by the first log of taking the medication in user_logs.
    date: Mapped[datetime.date] = mapped_column(db.Date, server_default=db.func.now())


@dataclass
class UserLog(db.Model):
    __tablename__ = 'user_logs'

    user_log_id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.user_id'))
    user_medication_id: Mapped[int] = mapped_column(db.ForeignKey('user_medications.user_medication_id'))
    expected_time: Mapped[datetime.datetime] = mapped_column(db.DateTime)
    actual_time: Mapped[datetime.datetime] = mapped_column(db.DateTime)
    dosage: Mapped[int] = mapped_column(db.Integer)
    unit: Mapped[str] = mapped_column(db.String)
    notes: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
