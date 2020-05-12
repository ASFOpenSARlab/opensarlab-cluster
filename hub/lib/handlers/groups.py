
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
        users = [self._user_from_orm(u) for u in users]

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
    def post(self):
        data = {}
        for arg in self.request.arguments:
            data[arg] = self.get_argument(arg, strip=False)

        try:
            print("Posted data: ", data)
            user_name = data['user']
            group_name = data['group']
            is_checked = data['is_checked']

            print(f"POST data includes: {data}")

            g = groups.Groups(db=self.db)
            user_names_in_group = g.get_user_names_in_group(group_name)

            if is_checked == 'true':
                # if user is part of group already, skip
                if user_name in user_names_in_group:
                    print(f"User '{user_name}' is already added to '{group_name}'. Do nothing.")
                else:
                    print(f"Add '{user_name}' to group '{group_name}'")
                    g.add_user_to_group(user_name, group_name)

            else:
                # If user is not in group, skip
                if user_name not in user_names_in_group:
                    print(f"User '{user_name}' is already removed from '{group_name}'. Do nothing.")
                else:
                    print(f"Remove '{user_name}' from group '{group_name}'")
                    g.remove_user_from_group(user_name, group_name)

        except Exception as e:
            print("Something went wrong with the POST...")
            print(e)

default_handlers = [
    (r'/groups', GroupsHandler)
]
