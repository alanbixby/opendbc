"""Adapt the parent renderer in memory, keeping its source unchanged.
Short legends fit the research layer labels. Corner-only mode includes -15 m
behind ego in the bird's-eye view (rear targets cannot appear in front video).
"""
from pathlib import Path
import sys, tempfile
_tmp=Path(__file__).resolve().parent / "tmp"
_tmp.mkdir(exist_ok=True)
tempfile.tempdir=str(_tmp)
source=(Path(__file__).resolve().parent.parent/'render_media.py').read_text()
source=source.replace('d.line([to_px(dd, yy) for dd, yy in tr], fill=(70, 80, 92), width=1)', 'pass  # omit unclipped trails extending above the panel')
source=source.replace('legend(LEAD, "track matched to vision lead", "box")','legend(LEAD, "tracks", "box") if any(o[1] for o in dump["outputs"]) else None')
source=source.replace('legend(RADAR, "moving radar track", "box")','pass').replace('legend(RADAR_STAT, "stationary return", "dot")','pass')
source=source.replace('"model lead (vision)"','"vision lead"')
if '--corner-view' in sys.argv:
 sys.argv.remove('--corner-view')
 source=source.replace('(VH - 40 - top_pad) / R','(VH - 40 - top_pad) / (R + 15)')
 source=source.replace('py0 + VH - 40\n','py0 + VH - 40 - 15 * ppm_y\n')
 source=source.replace('range(0, int(R) + 1, 10)','range(-10, int(R) + 1, 10)')
 source=source.replace('if 0 < p[1] < R','if -15 < p[1] < R')
 # Explicit numeric example exposes unsigned overflow while its marker is off-panel.
 source=source.replace('d.text((px0 + 12, py0 + 8)', '''
    if ex_out:
      near = [p for p in ex_out[1] if p[0] == 0x280 and -15 < p[1] < 60]
      if near:
        p = min(near, key=lambda p: abs(p[1]))
        unsigned = p[1] if p[1] >= 0 else p[1] + 409.6
        d.text((px0 + 12, py0 + 48), f"slot {p[0]:X}: signed {p[1]:.1f} m", fill=EXTRA, font=f_lbl)
        d.text((px0 + 12, py0 + 65), f"unsigned {unsigned:.1f} m", fill=BEFORE, font=f_lbl)
    d.text((px0 + 12, py0 + 8)''')
exec(compile(source,str(Path(__file__).resolve().parent.parent/'render_media.py'),'exec'),{'__name__':'__main__'})
