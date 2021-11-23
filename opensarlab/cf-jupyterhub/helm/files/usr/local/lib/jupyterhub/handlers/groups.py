
from jupyterhub import orm
from ..utils import admin_only
from .base import BaseHandler

class GroupsHandler(BaseHandler):
    """Render the groups page."""

    def _finish_html(self):
        try:
            from jupyterhub import groups as groups_py

            g = groups_py.Groups(db=self.db)
            groups = g.get_all_groups_with_meta()

            all_users_query = self.db.query(orm.User)
            all_users = [self._user_from_orm(u) for u in all_users_query]

            html = self.render_template(
                'groups.html',
                sync=True,
                current_user=self.current_user,
                groups=groups,
                all_users=all_users,
                admin_access=self.settings.get('admin_access', False)
            )
            print(type(html))
            
            self.finish(html)

        except Exception as e:
            print("Something went wrong in rendering html...")
            raise

    @admin_only
    def get(self):
        try:
            print("Getting group page...")
            self._finish_html()
        except Exception as e:
            print("Something went wrong with the GET...")
            print(e)
            raise

    @admin_only
    def post(self):
        try:
            from jupyterhub import groups as groups_py

            data = {}
            print("req.arg ", self.request.arguments)
            for arg in self.request.arguments:
                data[arg] = self.get_argument(arg, strip=False)
            print("Posted data: ", data)

            g = groups_py.Groups(db=self.db)

            if data['operation'] == 'checked':
                print("Changing checkboxes...")
                user_name = data['user_name']
                group_name = data['group_name']
                change_to_checked = g._boolean_check(data['change_to_checked'])

                user_names_in_group = g.get_user_names_in_group(group_name)

                if change_to_checked == True:
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

            elif data['operation'] == 'add_group':
                print("Adding group...")

                data['group_name'].strip()

                if not data['group_name']:
                    raise Exception("Group name is empty.")

                this_data = {
                    'group_name': data['group_name'],
                    'description': data['description'],
                    'group_type': data['group_type'],
                    'is_all_users': data['is_all_users'],
                    'is_enabled': data['is_enabled']
                }
                print(f"Adding {this_data}")

                current_groups = g.get_all_groups()
                if [True for cg in current_groups if cg.name == this_data['group_name']]:
                    raise Exception("There is already a group by that name.")

                g.add_group_with_meta(**this_data)

                self._finish_html()

            elif data['operation'] == 'update_group':
                print("Updating group...")
                this_data = {
                    'group_name': data['group_name'],
                    'description': data['description'],
                    'group_type': data['group_type'],
                    'is_all_users': data['is_all_users'],
                    'is_enabled': data['is_enabled']
                }
                g.update_group_with_meta(**this_data)

                self._finish_html()

            elif data['operation'] == 'delete_group':
                print("Deleting group...")
                group_name = data['group_name']
                g.delete_group(group_name)

                self._finish_html()

            else:
                raise Exception(f"Unknown POST operation: {data['operation']}")

        except Exception as e:
            print("Something went wrong with the POST...")
            print(e)
            raise

default_handlers = [
    (r'/groups', GroupsHandler)
]
