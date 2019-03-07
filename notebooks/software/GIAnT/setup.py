import os
import scipy.__config__ as cf
from numpy.distutils.core import Extension
from numpy.distutils.core import Command
'''Usage:
    
    If using g77 for building scipy / numpy:
        fcompiler=gnu in setup.cfg
    
    If using gfortran for building scipy/numpy:
        fcompiler=gnu95 in setup.cfg'''


'''Function obtained from http://www.peterbe.com/plog/uniqifiers-benchmark'''
def f7(seq):
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if x not in seen and not seen_add(x)]


class CleanCommand(Command):
    description = "custom clean command that forcefully removes dist/build directories"
    user_options = []
    def initialize_options(self):
        self.cwd = None
    def finalize_options(self):
        self.cwd = os.getcwd()
    def run(self):
        assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
        os.system('rm -rf ./build Aik/aik_mod.so Aik/aik_modmodule.c solver/gsvd/gensvd.so solver/gsvd/gensvdmodule.c')



########Collecting scipy information

blinfo = cf.get_info('blas_opt')
lpinfo = cf.get_info('lapack_opt')
atinfo = cf.get_info('atlas_threads')
atbinfo = cf.get_info('atlas_blas_threads')

libs = []
include = []
libdirs = []
def_mac = []

for inf in (lpinfo,atbinfo,blinfo,atinfo):
    if len(inf.keys()):
        if 'libraries' in inf.keys():
            libs += inf['libraries']
        if 'include_dirs' in inf.keys():
            include += inf['include_dirs']
        if 'library_dirs' in inf.keys():
            libdirs += inf['library_dirs']
        if 'define_macros' in inf.keys():
            def_mac += inf['define_macros']

libs = f7(libs)
include = f7(include)
libdirs = f7(libdirs)
def_mac = f7(def_mac)

#####Setting up gsvd
solver = Extension(name='solver.gsvd.gensvd',
            sources = ['./solver/gsvd/gensvd.pyf','./solver/gsvd/dggsvd.f'],
            libraries=libs,
            include_dirs=include,
            library_dirs=libdirs,
            define_macros= def_mac)

if __name__ == "__main__":
    from numpy.distutils.core import setup
    setup(name = 'GIAnT',
          version = '1.0',
          author = 'Piyush Agram',
          author_email = 'piyush@gps.caltech.edu',
          packages = ['GIAnT',],
          ext_modules=[solver],
          cmdclass = {'clean': CleanCommand})


############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################

