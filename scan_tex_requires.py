# scan_tex_requires.py
import re, sys, pathlib
pkgs = set()
use_rx = re.compile(r'\\(?:usepackage|RequirePackage)(?:\[[^\]]*\])?{([^}]*)}')
def scan(p):
    if p.suffix.lower() in {'.tex', '.sty', '.cls'}:
        t = p.read_text(errors='ignore')
        for m in use_rx.finditer(t):
            for name in m.group(1).split(','):
                pkgs.add(name.strip())
for path in map(pathlib.Path, sys.argv[1:] or ['.']):
    for f in path.rglob('*'):
        scan(f)
print("Detected packages:")
print("\n".join(sorted(pkgs)))
