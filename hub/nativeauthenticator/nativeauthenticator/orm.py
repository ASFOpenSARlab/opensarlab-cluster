import base64
import bcrypt
import os
import re
from jupyterhub.orm import Base

import onetimepass
from sqlalchemy import Boolean, Column, Integer, String, LargeBinary
from sqlalchemy.orm import validates


class UserGroupMapInfo(Base):
    """
    CREATE TABLE user_group_map (
    	user_id INTEGER NOT NULL,
    	group_id INTEGER NOT NULL,
    	PRIMARY KEY (user_id, group_id),
    	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    	FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE
    );
    """
    __tablename__ = 'user_group_map'
    user_id = Column(Integer, primary_key=True)
    group_id = Column(Integer, primary_key=True)
    # Foreign Constraints?

    def __init__(self, **kwargs):
        super(UserGroupMapInfo, self).__init__(**kwargs)

    @classmethod
    def find_all_user_ids_by_group_id(cls, db, group_id):
        """Find all user ids by group id.
        Returns None if not found"""
        return db.query(cls).filter(cls.group_id == group_id).first()

    @classmethod
    def find_all_group_ids_by_user_id(cls, db, user_id):
        """Find all groups by user id.
        Returns None if not found"""
        return db.query(cls).filter(cls.user_id == user_id).first()


class GroupInfo(Base):
    """
    CREATE TABLE groups (
    	id INTEGER NOT NULL,
    	name VARCHAR(255),
    	PRIMARY KEY (id),
    	UNIQUE (name)
    );
    """
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)

    def __init__(self, **kwargs):
        super(GroupInfo, self).__init__(**kwargs)

    @classmethod
    def find_group_id_by_group_name(cls, db, group_name):
        """Find a group id by group name.
        Returns None if not found"""
        return db.query(cls).filter(cls.name == group_name).first()

    @classmethod
    def find_group_name_by_group_id(cls, db, group_id):
        """Find a group name by group id.
        Returns None if not found"""
        return db.query(cls).filter(cls.id == group_id).first()


class UserInfo(Base):
    """
    CREATE TABLE users_info (
    	id INTEGER NOT NULL,
    	username VARCHAR NOT NULL,
    	password BLOB NOT NULL,
    	is_authorized BOOLEAN,
    	email VARCHAR,
    	has_2fa BOOLEAN,
    	otp_secret VARCHAR(16),
    	PRIMARY KEY (id),
    	CHECK (is_authorized IN (0, 1)),
    	CHECK (has_2fa IN (0, 1))
    );
    """
    __tablename__ = 'users_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    password = Column(LargeBinary, nullable=False)
    is_authorized = Column(Boolean, default=False)
    email = Column(String)
    has_2fa = Column(Boolean, default=False)
    otp_secret = Column(String(16))

    def __init__(self, **kwargs):
        super(UserInfo, self).__init__(**kwargs)
        if not self.otp_secret:
            self.otp_secret = base64.b32encode(os.urandom(10)).decode('utf-8')

    @classmethod
    def find_by_user_id(cls, db, user_id):
        """Find a user info record by user_id.
        Returns None if not found"""
        return db.query(cls).filter(cls.user_id == user_id).first()

    @classmethod
    def find(cls, db, username):
        """Find a user info record by name.
        Returns None if not found"""
        return db.query(cls).filter(cls.username == username).first()

    def is_valid_password(self, password):
        """Checks if a password passed matches the
        password stored"""
        encoded_pw = bcrypt.hashpw(password.encode(), self.password)
        return encoded_pw == self.password

    @classmethod
    def change_authorization(cls, db, username):
        user = db.query(cls).filter(cls.username == username).first()
        user.is_authorized = not user.is_authorized
        db.commit()
        return user

    @validates('email')
    def validate_email(self, key, address):
        if not address:
            return
        assert re.match(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$",
                        address)
        return address

    def is_valid_token(self, token):
        return onetimepass.valid_totp(token, self.otp_secret)
