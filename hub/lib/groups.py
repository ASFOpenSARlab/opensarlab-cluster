
from typing import List, Dict
from sqlalchemy import Column, Unicode, Boolean, Integer, ForeignKey

from jupyterhub import orm

"""
    Usage:

    from jupyterhub import Groups
    g = Groups()

    g.get_all_groups()

    ------------
    During Jupyterhub helm upgrade, the DB might need an update.
    If the build fails die to DB conflicts, the custom parts of the DB will need to be taken apart briefly.

    1. Within `hub` pod (via `kubectl exec`), run
        $ cd /srv/jupyterhub/
        $ sqlite3 jupyterhub.sqlite

    2. As needed, export current data
        > 


    CREATE TABLE groups_meta (
       id INTEGER NOT NULL,
       group_name VARCHAR(255) NOT NULL,
       description VARCHAR(255),
       group_type VARCHAR(255),
       is_default INTEGER,
       is_active INTEGER,
       PRIMARY KEY (id),
       FOREIGN KEY(group_name) REFERENCES groups (name) ON DELETE CASCADE
    );


"""

class GroupMeta(orm.Base):
    """Group Meta"""

    __tablename__ = 'groups_meta'
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(Unicode(255), ForeignKey('groups.name', ondelete='CASCADE'))
    description = Column(Unicode(255), default='')
    group_type = Column(Unicode(255), default='label')
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.group_name} {self.description} {self.group_type} {self.is_default} {self.is_active}>"

class Groups():

    def __init__(self, db_url='sqlite:////srv/jupyterhub/jupyterhub.sqlite', db=None):

        if db is not None:
            self.session = db
        else:
            session_factory = orm.new_session_factory(db_url)
            self.session = session_factory()

    @staticmethod
    def _boolean_check(arg):
        if arg in ("1", "True", "true", True, 1):
            ret = True
        elif arg in ("0", "False", "false", False, 0):
            ret = False
        else:
            raise Exception(f"'{arg}' cannot be converted to boolean")

        return ret

    def get_all_groups(self) -> List[orm.Group]:
        return self.session.query(orm.Group).all()

    def get_all_groups_with_meta(self) -> List[GroupMeta]:

        groups = []
        for group_obj in self.session.query(orm.Group).all():
            group_name = group_obj.name
            group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name).first()
            if group_meta is None:
                group_meta = GroupMeta(group_name=group_name)

            print(group_meta)
            groups.append(group_meta)

        return groups

    def add_group(self, group_name: str) -> None:

        try:
            # Check if group exists already
            group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()
            if group is not None:
                print(f"Group '{group_name}' already exists. Aborting adding group.")
                raise Exception(f"Group '{group_name}' already exists. Aborting adding group.")

            group = orm.Group(name=group_name)
            self.session.add(group)
            self.session.commit()

        except Exception as e:
            print(f"Error in adding group: {e}")
            self.session.rollback()
            raise

    def add_group_meta(self, group_name: str, description: str, is_default: Boolean, group_type: str, is_active: Boolean) -> None:

        try:
            # Check if group exists already
            group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name).first()
            if group_meta is not None:
                print(f"Group Meta for '{group_name}' already exists. Aborting adding group meta.")
                raise Exception(f"Group Meta for '{group_name}' already exists. Aborting adding group meta.")

            is_default = self._boolean_check(is_default)
            is_active = self._boolean_check(is_active)

            group_meta = GroupMeta(group_name=group_name, description=description, is_default=is_default, group_type=group_type, is_active=is_active)
            self.session.add(group_meta)
            self.session.commit()

        except Exception as e:
            print(f"Error in adding group meta: {e}")
            self.session.rollback()
            raise

    def update_group_meta(self, group_name: str, description: str, is_default: Boolean, group_type: str, is_active: Boolean) -> None:

        try:
            # Check if group exists already
            group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name)
            if group_meta is None:
                print(f"Group Meta for '{group_name}' does not exist. Aborting update...")
                raise Exception(f"Group Meta for '{group_name}' does not exist. Aborting update...")

            is_default = self._boolean_check(is_default)
            is_active = self._boolean_check(is_active)

            args = {
                'group_name': group_name,
                'description': description,
                'is_default': is_default,
                'group_type': group_type,
                'is_active': is_active
            }
            group_meta.update(args)
            self.session.commit()

        except Exception as e:
            print(f"Error in updating group meta: {e}")
            self.session.rollback()
            raise

    def get_group_meta(self, group_name: str) -> GroupMeta:

        group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name).first()
        if group_meta is None:
            raise Exception(f"No group meta for group '{group_name}'")

        return group_meta

    def delete_group(self, group_name: str) -> None:
        # group meta will also delete via cascade
        try:
            group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

            if group == None:
                print(f"Group {group_name} not found.")
                raise Exception(f"Group {group_name} not found.")

            self.session.delete(group)
            self.session.commit()

        except Exception as e:
            print(f"Error in deleting group: {e}")
            self.session.rollback()
            raise

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
            print(f"Error in adding user to group: {e}")
            self.session.rollback()
            raise

    def add_all_current_users_to_group(self, group_name: str) -> None:
        try:

            group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()
            all_users = self.session.query(orm.User).all()

            if group == None:
                print(f"Group {group_name} not found.")
                raise Exception(f"Group {group_name} not found.")
            if all_users == None:
                print(f"No users found.")
                raise Exception(f"Users not found.")

            for user in all_users:
                group.users.append(user)
            self.session.commit()

        except Exception as e:
            print(f"Error in adding current users to group: {e}")
            self.session.rollback()
            raise

    def remove_user_from_group(self, user_name: str, group_name: str) -> None:
        try:
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

        except Exception as e:
            print(f"Error in removing user from group: {e}")
            self.session.rollback()
            raise
