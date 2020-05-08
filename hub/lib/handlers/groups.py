
from .. import groups
from ..utils import admin_only
from .base import BaseHandler

class GroupsHandler(BaseHandler):
    """Render the groups page."""

    @admin_only
    def get(self):

        g = groups.Groups(db=self.db)
        group_list = g.get_all_groups()

        html = self.render_template(
            'groups.html',
            current_user=self.current_user,
            admin_access=self.settings.get('admin_access', False),
            group_list=group_list,
        )
        self.finish(html)

default_handlers = [
    (r'/groups', GroupsHandler)
]
