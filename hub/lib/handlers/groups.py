
from jupyterhub import orm
from ..utils import admin_only
from .base import BaseHandler

class GroupsHandler(BaseHandler):
    """Render the groups page."""

    #@web.authenticated
    @admin_only
    def get(self):
        from jupyterhub import groups as groups_py

        g = groups_py.Groups(db=self.db)
        group_list_obj = g.get_all_groups()
        groups = []
        for group_obj in group_list_obj:
            groups.append( {
                'name': group_obj.name,
                'members': [u.name for u in group_obj.users]
            })

        all_users_query = self.db.query(orm.User)
        all_users = [self._user_from_orm(u) for u in all_users_query]

        html = self.render_template(
            'groups.html',
            current_user=self.current_user,
            groups=groups,
            all_users=all_users,
            admin_access=self.settings.get('admin_access', False),
        )
        self.finish(html)

    #@web.authenticated
    #@admin_only
    def post(self):
        try:
            from jupyterhub import groups as groups_py

            data = {}
            print("req.arg ", self.request.arguments)
            for arg in self.request.arguments:
                data[arg] = self.get_argument(arg, strip=False)
            print("Posted data: ", data)

            if 'checked' in data:
                user_name = data['checked']['user']
                group_name = data['checked']['group']
                change_to_checked = data['checked']['change_to_checked']

                g = groups_py.Groups(db=self.db)
                user_names_in_group = g.get_user_names_in_group(group_name)

                if change_to_checked == 'true':
                    # if user is part of group already, skip
                    if user_name in user_names_in_group:
                        print(f"User '{user_name}' is already part of group '{group_name}'. Do nothing.")
                    else:
                        print(f"Add '{user_name}' to group '{group_name}'")
                        g.add_user_to_group(user_name, group_name)

                else:
                    # If user is not already in group, skip
                    if user_name not in user_names_in_group:
                        print(f"User '{user_name}' is already not in group '{group_name}'. Do nothing.")
                    else:
                        print(f"Remove '{user_name}' from group '{group_name}'")
                        g.remove_user_from_group(user_name, group_name)

            elif 'add_group' in data:
                group_name = data['add_group']['group_name']

                g = groups_py.Groups(db=self.db)
                return g.add_group(group_name)

            elif 'delete_group' in data:
                group_name = data['delete_group']['group_name']

                g = groups_py.Groups(db=self.db)
                return g.delete_group(group_name)

        except Exception as e:
            print("Something went wrong with the POST...")
            print(e)

default_handlers = [
    (r'/groups', GroupsHandler)
]
