try:
    # c is the built-in JupyterHub config 

    from generic_with_logout import GenericOAuthenticator
    c.JupyterHub.authenticator_class = GenericOAuthenticator

except Exception as e:
    print(e)