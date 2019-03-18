import tsinsar as ts
import argparse
import numpy as np

def parse():
    parser= argparse.ArgumentParser(description='Preparation of XML files for setting up the processing chain. Check tsinsar/tsxml.py for details on the parameters.')
    parser.parse_args()


parse()
g = ts.TSXML('data')
g.prepare_data_xml('insarProc.xml',proc='ISCE',inc=21.,cohth=0.1,chgendian='False',unwfmt='RMG',corfmt='RMG')
g.writexml('data.xml')


