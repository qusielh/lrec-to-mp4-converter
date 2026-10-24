import sys, os, json, subprocess, tempfile, shutil
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import l2m_engine as e

VIEWPORT = e.VIEWPORT
VOICE = e.VOICE


def ffprobe_packets(path):
    out = {}
    for sel in ('v', 'a'):
        try:
            ff = os.path.join('bin', 'ffprobe.exe')
            if not os.path.exists(ff):
                ff = 'ffprobe.exe'
            p = subprocess.run([ff, '-v', 'quiet', '-select_streams', sel,
                                '-show_entries', 'packet=pts_time',
                                '-of', 'csv=p=0', path],
                               capture_output=True, text=True, timeout=300)
            vals = []
            for x in p.stdout.replace('\r', '').split('\n'):
                x = x.strip().rstrip(',')
                if not x:
                    continue
                try:
                    vals.append(float(x))
                except Exception:
                    pass
            out[sel] = (min(vals), max(vals), len(vals)) if vals else None
        except Exception:
            out[sel] = None
    return out


def stats(lrec_path):
    res = {'lrec': os.path.basename(lrec_path), 'dur_lrec': 0.0,
           'vspan': 0.0, 'aspan': 0.0, 't_first': 0.0, 't_last': 0.0,
           'has_vid': False, 'has_aud': False, 'n_view': 0, 'n_voice': 0,
           'reasons': []}
    try:
        frames = e.parse_lrec(lrec_path)
    except Exception:
        res['reasons'].append('parse_fail')
        return res
    if not frames:
        res['reasons'].append('no_frames')
        return res
    ts = [f[0] for f in frames]
    t0, tl = min(ts), max(ts)
    res['t_first'] = round(t0 / 1000.0, 3)
    res['t_last'] = round(tl / 1000.0, 3)
    res['dur_lrec'] = round((tl - t0) / 1000.0, 3)
    c = Counter(f[1] for f in frames)
    res['n_view'] = c.get(VIEWPORT, 0)
    res['n_voice'] = c.get(VOICE, 0)
    res['has_vid'] = res['n_view'] > 0
    res['has_aud'] = res['n_voice'] > 0
    vs = [f[0] for f in frames if f[1] == VIEWPORT]
    As = [f[0] for f in frames if f[1] == VOICE and len(f[2]) >= 40]
    if vs:
        res['vspan'] = round((max(vs) - min(vs)) / 1000.0, 3)
    if As:
        res['aspan'] = round((max(As) - min(As)) / 1000.0, 3)
    return res


def probe_verify(st, out_path, tol=3.0):
    res = {'ok': False, 'pass': False, 'lrec': st['lrec'],
           'dur_lrec': st['dur_lrec'], 'vspan': st['vspan'],
           'aspan': st['aspan'], 'has_vid': st['has_vid'],
           'has_aud': st['has_aud'], 'n_view': st['n_view'],
           'n_voice': st['n_voice'], 'vdur': None, 'adur': None,
           'vframes': None, 'aframes': None, 'size': 0,
           'reasons': list(st['reasons'])}
    if st['reasons']:
        return res
    if not os.path.exists(out_path):
        res['reasons'].append('mp4_missing')
        return res
    res['size'] = os.path.getsize(out_path)
    if res['size'] == 0:
        res['reasons'].append('mp4_zero')
        return res
    pk = ffprobe_packets(out_path)
    v = pk.get('v')
    a = pk.get('a')
    if res['has_vid'] and not v:
        res['reasons'].append('no_video_stream')
    if res['has_aud'] and not a:
        res['reasons'].append('no_audio_stream')
    if v:
        res['vdur'] = round(v[1], 3)
        res['vframes'] = v[2]
    if a:
        res['adur'] = round(a[1], 3)
        res['aframes'] = a[2]
    ok = True
    if res['has_vid'] and res['vdur'] is None:
        ok = False; res['reasons'].append('vdur_missing')
    if res['has_aud'] and res['adur'] is None:
        ok = False; res['reasons'].append('adur_missing')
    if res['vdur'] is not None and res['has_vid']:
        if res['vdur'] < res['vspan'] - tol:
            ok = False; res['reasons'].append('video_short')
        if res['vdur'] > res['dur_lrec'] + tol:
            ok = False; res['reasons'].append('video_overrun')
    if res['adur'] is not None and res['has_aud']:
        if res['adur'] < res['aspan'] - tol:
            ok = False; res['reasons'].append('audio_short')
        if res['adur'] > res['dur_lrec'] + tol:
            ok = False; res['reasons'].append('audio_overrun')
    res['ok'] = ok
    res['pass'] = ok
    if ok and not res['reasons']:
        res['reasons'] = ['ok']
    return res


def convert(lrec_path, out_path):
    e.convert_one(lrec_path, out_path, lambda l: None, lambda: False,
                  lambda f, r: None)
    return out_path


def check_one(lrec_path, out_path=None, tol=3.0):
    st = stats(lrec_path)
    if st['reasons']:
        return {'ok': False, 'pass': False, 'lrec': st['lrec'],
                'dur_lrec': st['dur_lrec'], 'vspan': st['vspan'],
                'aspan': st['aspan'], 'has_vid': st['has_vid'],
                'has_aud': st['has_aud'], 'n_view': st['n_view'],
                'n_voice': st['n_voice'], 'vdur': None, 'adur': None,
                'vframes': None, 'aframes': None, 'size': 0,
                'reasons': list(st['reasons'])}
    if out_path is None:
        d = tempfile.mkdtemp(prefix='vlrec_')
        out_path = os.path.join(d, 'out.mp4')
    try:
        convert(lrec_path, out_path)
    except Exception:
        res = probe_verify(st, out_path, tol)
        res['reasons'] = ['convert_fail'] + res['reasons']
        return res
    res = probe_verify(st, out_path, tol)
    try:
        tmpdir = os.path.dirname(out_path)
        if tmpdir and tmpdir.startswith(tempfile.gettempdir()):
            shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass
    return res


def main():
    if len(sys.argv) < 2:
        print('usage: verify_lrec.py <lrec_path> [out_path]')
        sys.exit(1)
    l = sys.argv[1]
    o = sys.argv[2] if len(sys.argv) > 2 else None
    r = check_one(l, o)
    print(json.dumps(r))
    sys.exit(0 if r['pass'] else 1)


if __name__ == '__main__':
    main()
