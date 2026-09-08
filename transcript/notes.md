# cam utility use for test captures

cam -c 1 -C6 -F'/tmp/frame#.ppm' -s role=viewfinder,width=1932,height=1092

# Convert frames

python3 << 'PYSCRIPT'
from PIL import Image
import glob
files = sorted(glob.glob('/tmp/framecam*.ppm'))
for f in files[2:]:
    img = Image.open(f)
    out = f.replace('.ppm', '.png')
    img.save(out)
    print(f'{f.split("/")[-1]} → {out.split("/")[-1]}')
PYSCRIPT


----------------------

OTHER TRICKS:

- to write to protected directories / files use 'tee' command

sudo tee /etc/portage/repos.conf/emilienmottet.conf > /dev/null << 'EOF'
[emilienmottet]
location = /var/db/repos/emilienmottet
sync-type = rsync
sync-uri = rsync://rsync.overlays.gentoo.org/gentoo-overlays/emilienmottet
EOF

- to configure Epiphany's USER_AGENT:

WEBKIT_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36" epiphany 2>/dev/null &!
