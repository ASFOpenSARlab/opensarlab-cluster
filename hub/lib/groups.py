
from typing import List, Dict
from sqlalchemy import Column, Unicode, Boolean

from jupyterhub import orm

"""
    db_url = ''
    groups = Groups(db_url)

    groups.get_all_groups()
"""

"""
ALTER TABLE groups ADD COLUMN description VARCHAR(255);
ALTER TABLE groups ADD COLUMN is_default INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN group_type VARCHAR(255) DEFAULT 'label';

CREATE TRIGGER IF NOT EXISTS add_new_user_to_groups_map
    AFTER INSERT
    ON users
BEGIN
    INSERT INTO user_group_map (user_id, group_id)
    SELECT
        new.id as user_id,
        id as group_id
    FROM groups
    WHERE is_default = 1;
END;
"""

class Group(orm.Group):
    description = Column(Unicode(255), default='')
    is_default = Column(Boolean, default=False)
    group_type = Column(Unicode(255), default='label')
    #is_active = Column(Boolean, default=True)

orm.Group = Group

class Groups():

    def __init__(self, db_url='sqlite:////srv/jupyterhub/jupyterhub.sqlite', db=None):

        if db is not None:
            self.session = db
        else:
            session_factory = orm.new_session_factory(db_url)
            self.session = session_factory()

    def get_all_groups(self) -> List[orm.Group]:
        return self.session.query(orm.Group).all()

    def add_group(self, group_name: str, description: str, is_default: Boolean, group_type: str, is_active: Boolean) -> None:

        """ TODO
        Still need to implement is_active
        """

        # Check if group exists already
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()
        if group is not None:
            print(f"Group '{group_name}' already exists. Aborting adding group.")
            raise Exception(f"Group '{group_name}' already exists. Aborting adding group.")

        group = orm.Group(name=group_name, description=description, is_default=is_default, group_type=group_type)
        self.session.add(group)
        self.session.commit()

    def update_group(self, group_name: str, description: str, is_default: Boolean, group_type: str, is_active: Boolean) -> None:

        """ TODO
        Still need to implement is_active
        """

        # Check if group does not exist already
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()
        if group is None:
            print(f"Group '{group_name}' doesn't exist. Aborting update group.")
            raise Exception(f"Group '{group_name}' doesn't exist. Aborting update group.")

        group = orm.Group(name=group_name, description=description, is_default=is_default, group_type=group_type)
        self.session.update(group)
        self.session.commit()

    def delete_group(self, group_name: str) -> None:
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group == None:
            print(f"Group {group_name} not found.")
            raise Exception(f"Group {group_name} not found.")

        self.session.delete(group)
        self.session.commit()

    def get_users_in_group(self, group_name: str) -> List[orm.User]:
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group is None:
            print(f"Group {group_name} not found.")
            raise Exception(f"Group {group_name} not found.")

        return group.users

    def get_user_names_in_group(self, group_name: str) -> List[str]:
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group is None:
            print(f"Group {group_name} not found.")
            raise Exception(f"Group {group_name} not found.")

        return [u.name for u in group.users]

    def get_group_names_for_user(self, user_name: str) -> List[str]:
        groups = self.get_all_groups()
        return [g.name for g in groups for u in g.users if u.name == user_name]

    def add_user_to_group(self, user_name: str, group_name: str) -> str:
        try:
            group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()
            user = self.session.query(orm.User).filter(orm.User.name == user_name).first()

            if group == None:
                print(f"Group {group_name} not found.")
                raise Exception(f"Group {group_name} not found.")
            if user == None:
                print(f"User {user_name} not found.")
                raise Exception(f"User {user_name} not found.")

            group.users.append(user)
            self.session.commit()

        except Exception as e:
            self.session.rollback()
            raise

    def remove_user_from_group(self, user_name: str, group_name: str) -> None:
        user = self.session.query(orm.User).filter(orm.User.name == user_name).first()
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group == None:
            print(f"Group {group_name} not found.")
            raise Exception(f"Group {group_name} not found.")
        if user == None:
            print(f"User {user_name} not found.")
            raise Exception(f"User {user_name} not found.")

        group.users.remove(user)
        self.session.commit()
