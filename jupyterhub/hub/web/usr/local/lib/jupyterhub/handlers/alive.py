from .base import BaseHandler


class AliveHandler(BaseHandler):
    """Render the groups page."""

    def get(self):
        try:
            print("Staying alive...")
            html = """
            <html>
            <body>
                <h1>Greetings</h1>
                <p>If you are seeing this then JupyterHub is running!</p>
            </body>
            </html>
            """
            self.finish(html)
        except Exception as e:
            print("Something went wrong with the GET...")
            print(e)
            raise


default_handlers = [(r"/alive", AliveHandler)]
