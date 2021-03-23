
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
    If done within /srv/jupyterhub, any files will be persistent.

    Firstly, within `hub` pod (via `kubectl exec`), run the following
        $ cd /srv/jupyterhub/
        $ sqlite3 jupyterhub.sqlite

    1. As needed, export current data to CSV
        sqlite> .headers on
        sqlite> .mode csv
        sqlite> .output groups-meta-data.csv
        sqlite> SELECT group_name, description, group_type, is_all_users, is_enabled FROM groups_meta;

    2. Drop the groups table
        sqlite> DROP TABLE groups_meta;
        sqlite> .quit;

    3. Do upgrade via Helm or otherwise

    4. Log back into the `hub` and sqlite3 and create `groups_meta` (and temp) table

        CREATE TABLE temp_1 (
           group_name VARCHAR(255) NOT NULL,
           description VARCHAR(255),
           group_type VARCHAR(255),
           is_all_users INTEGER,
           is_enabled INTEGER
        );

        CREATE TABLE groups_meta (
           id INTEGER NOT NULL,
           group_name VARCHAR(255) NOT NULL,
           description VARCHAR(255),
           group_type VARCHAR(255),
           is_all_users INTEGER,
           is_enabled INTEGER,
           PRIMARY KEY (id),
           FOREIGN KEY(group_name) REFERENCES groups (name) ON DELETE CASCADE
        );

    5. Reimport data back into table and check
        sqlite> .mode csv
        sqlite> .import groups-meta-data.csv temp_1
        sqlite> INSERT INTO groups_meta(group_name, description, group_type, is_all_users, is_enabled) SELECT group_name, description, group_type, is_all_users, is_enabled FROM temp_1;
        sqlite> DROP TABLE temp_1;
        sqlite> SELECT group_name, description, group_type, is_all_users, is_enabled FROM groups_meta;

"""

class GroupMeta(orm.Base):
    """Group Meta"""

    __tablename__ = 'groups_meta'
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(Unicode(255), ForeignKey('groups.name', ondelete='CASCADE'))
    description = Column(Unicode(255), default='')
    group_type = Column(Unicode(255), default='label')
    is_all_users = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)

    def __repr__(self):
        return f"<{self.__class__.__name__} name:{self.group_name} description:{self.description} type:{self.group_type} is_all_users:{self.is_all_users} is_enabled:{self.is_enabled}>"

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

    def get_all_enabled_group_names_set_to_all_users(self) -> List[str]:
        groups = self.session.query(GroupMeta).all()
        return [g.group_name for g in groups if g.is_enabled and g.is_all_users]

    def get_all_groups_with_meta(self) -> List[GroupMeta]:

        groups = []
        for group_obj in self.session.query(orm.Group).all():
            group_name = group_obj.name
            group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name).first()
            if group_meta is None:
                # All groups should have some meta (even if default to 'empty')
                self.add_group_with_meta(group_name=group_name, description="", is_all_users=False, group_type='label', is_enabled=False)
                group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name).first()
            group_meta.members = [u.name for u in group_obj.users]

            groups.append(group_meta)

        return groups

    def add_group_with_meta(self, group_name: str, description: str, is_all_users: Boolean, group_type: str, is_enabled: Boolean) -> None:

        try:
            # Check if group exists already
            group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()
            if group is None:
                print(f"Group '{group_name}' does not exist. Adding group.")

                group = orm.Group(name=group_name)
                self.session.add(group)
                self.session.commit()

            group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name).first()
            if group_meta is None:
                print(f"Group Meta for '{group_name}' does not exist. Adding group meta.")

                is_all_users = self._boolean_check(is_all_users)
                is_enabled = self._boolean_check(is_enabled)

                group_meta = GroupMeta(group_name=group_name, description=description, is_all_users=is_all_users, group_type=group_type, is_enabled=is_enabled)
                self.session.add(group_meta)
                self.session.commit()

        except Exception as e:
            print(f"Error in adding group: {e}")
            self.session.rollback()
            raise

    def update_group_with_meta(self, group_name: str, description: str, is_all_users: Boolean, group_type: str, is_enabled: Boolean) -> None:

        try:
            # Check if group exists already
            group = self.session.query(orm.Group).filter(orm.Group.name == group_name)
            if group is None:
                print(f"Group '{group_name}' does not exist. Don't update.")
                raise Exception(f"Group '{group_name}' does not exist. Don't update.")

            group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name)
            if group_meta is None:
                print(f"Group Meta for '{group_name}' does not exist. Don't update.")
                raise Exception(f"Group Meta for '{group_name}' does not exist. Don't update.")

            is_all_users = self._boolean_check(is_all_users)
            is_enabled = self._boolean_check(is_enabled)

            args = {
                GroupMeta.description: description,
                GroupMeta.is_all_users: is_all_users,
                GroupMeta.group_type: group_type,
                GroupMeta.is_enabled: is_enabled
            }

            group_meta.update(args)
            self.session.commit()

        except Exception as e:
            print(f"Error in adding group: {e}")
            self.session.rollback()
            raise

    def get_group_meta(self, group_name: str) -> GroupMeta:

        group_meta = self.session.query(GroupMeta).filter(GroupMeta.group_name == group_name).first()
        print(f"Getting group meta: {group_meta}")

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

    def get_all_enabled_group_names_for_user(self, user_name: str) -> List[str]:
        groups = self.get_all_groups()
        return [g.name for g in groups for u in g.users if u.name == user_name and self.is_group_name_enabled(g.name)]

    def is_group_name_enabled(self, group_name: str) -> Boolean:
        try:
            gm = self.get_group_meta(group_name)
            return gm.is_enabled
        except:
            return False

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
                if user not in group.users:
                    group.users.append(user)
            self.session.commit()

        except Exception as e:
            print(f"Error in adding current users to group: {e}")
            self.session.rollback()
            raise

    def remove_all_current_users_from_group(self, group_name: str) -> None:
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
                group.users.remove(user)
            self.session.commit()

        except Exception as e:
            print(f"Error in removing current users from group: {e}")
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
