import numpy as np
import configobj
import ast

class Container():
    pass

def config2obj(cin):
    '''Convert a configobj instance into a nested object.
    Recursively calls itself.'''
    if isinstance(cin, configobj.ConfigObj) or isinstance(cin, configobj.Section):
        out = Container()

        kk = cin.keys()
        for keyin in kk:
            setattr(out, keyin, config2obj(cin[keyin]))
        
        return out

    elif len(cin) ==0:
        return None

    else:
        try:
            return ast.literal_eval(cin)
        except:
            return str(cin)



