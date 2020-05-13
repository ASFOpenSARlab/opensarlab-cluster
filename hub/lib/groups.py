
from typing import List, Dict

from jupyterhub import orm

"""
    db_url = ''
    groups = Groups(db_url)

    groups.get_all_groups()
"""

class Groups():

    def __init__(self, db_url='sqlite:////srv/jupyterhub/jupyterhub.sqlite', db=None):

        if db is not None:
            self.session = db
        else:
            session_factory = orm.new_session_factory(db_url)
            self.session = session_factory()

    def get_all_groups(self) -> List[orm.Group]:
        return self.session.query(orm.Group).all()

    def add_group(self, group_name: str) -> None:
        group = orm.Group(name=group_name)
        self.session.add(group)
        self.session.commit()

        return True

    def delete_group(self, group_name: str) -> None:
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group == None:
            print(f"Group {group_name} not found.")
            return False

        self.session.remove(group)
        self.session.commit()

        return True

    def get_users_in_group(self, group_name: str) -> List[orm.User]:
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group == None:
            print(f"Group {group_name} not found.")
            return

        return group.users

    def get_user_names_in_group(self, group_name: str) -> List[str]:
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group == None:
            print(f"Group {group_name} not found.")
            return

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
                return
            if user == None:
                print(f"User {user_name} not found.")
                return

            group.users.append(user)
            self.session.commit()
            return 'Success'

        except Exception as e:
            self.session.rollback()
            return str(e)

    def remove_user_from_group(self, user_name: str, group_name: str) -> None:
        user = self.session.query(orm.User).filter(orm.User.name == user_name).first()
        group = self.session.query(orm.Group).filter(orm.Group.name == group_name).first()

        if group == None:
            print(f"Group {group_name} not found.")
            return
        if user == None:
            print(f"User {user_name} not found.")
            return

        group.users.remove(user)
        self.session.commit()
