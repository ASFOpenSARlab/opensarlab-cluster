
from typing import List, Dict

from jupyterhub import orm
"""
    db_url = ''
    groups = Groups(db_url)

    groups.get_all_groups()
"""

class Groups():

    def __init__(self, db: orm.db = None, db_url: str = None) -> None:

        if db is not None:
            self.db = db
        elif db is None and db_url is not None:
            session_factory = orm.new_session_factory(db_url)
            self.db = session_factory()
        else:
            raise Exception("No db object or db url given.")

    def get_all_groups(self) -> List[orm.Group]:
        return orm.Group.all()

    def add_group(self, group_metadata: Dict) -> None:
        """
        group_metadata:
            name: name of group
        """
        group = orm.Group(*group_metadata)
        self.db.add(group)
        self.db.commit()

    def remove_group(self, group_name: str) -> None:
        pass

    def get_users_of_group(self, group_name: str) -> List[orm.User]:
        group = orm.Group.find(self.db, name=group_name)
        return [g.user for g in group]

    def get_group_names_for_user(self, user_name: str) -> List[str]:
        groups = self.get_all_groups()
        return [g.name for g in groups]

    def add_user_to_group(self, user_name: str, group_name: str) -> None:
        group = orm.Group.find(self.db, name=group_name)
        user = _find_user(user_name)
        group.users.append(user)
        self.db.commit()

    def remove_user_from_group(self, user_name: str, group_name: str) -> None:
        pass

    def _find_user(self, user_name: str) -> str:
        """Find user in database."""
        orm_user = self.db.query(orm.User).filter(orm.User.name == user_name).first()
        return orm_user

    def _add_user(self, **kwargs) -> str:
        """Add a user to the database."""
        orm_user = _find_user(name=kwargs.get('name'))
        if orm_user is None:
            orm_user = orm.User(**kwargs)
            self.db.add(orm_user)
        else:
            for attr, value in kwargs.items():
                setattr(orm_user, attr, value)
        self.db.commit()
        return orm_user
