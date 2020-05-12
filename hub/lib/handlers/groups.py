
from .. import groups
from .. import orm
from ..utils import admin_only
from .base import BaseHandler

class GroupsHandler(BaseHandler):
    """Render the groups page."""

    #@web.authenticated
    @admin_only
    def get(self):

        g = groups.Groups(db=self.db)
        group_list = g.get_all_groups()

        users = self.db.query(orm.User)
        print(users)
        users = [self._user_from_orm(u) for u in users]
        print(users)

        html = self.render_template(
            'groups.html',
            current_user=self.current_user,
            users=users,
            admin_access=self.settings.get('admin_access', False),
            group_list=group_list,
        )
        self.finish(html)

    #@web.authenticated
    #@admin_only
    def post(self, *args, **kwargs):
        print("POST groups")
        print(args)
        print(kwargs)


default_handlers = [
    (r'/groups', GroupsHandler)
]
