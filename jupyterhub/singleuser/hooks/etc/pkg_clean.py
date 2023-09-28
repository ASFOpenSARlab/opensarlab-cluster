from pathlib import Path
import shutil

pkgs = list(Path('./.local/lib/python3.10/site-packages/').glob('*'))

togo = ['examples', 'mpldatacursor', 'hide_code', 'nbconvert', 'plumbum' 'qtpy', 'ply',
        'rise', 'jupyter_console', 'pypandoc', 'pandoc', 'qtconsole', 'traitlets', 'pdfkit']

for p in pkgs:
    for name in togo:
        if name in p.name and p.is_dir():
            shutil.rmtree(p)
            break
