#!/usr/bin/env python3
"""Transcribe the voice notes for a travel-log post.

Phone recordings arrive in two states that defeat whisper on their own: a WAV
header that lies about how much audio follows, and a recording level so low that
whisper hears one sentence in a minute of speech. Both are repaired here before
transcription, so the caller just gets text.

    python3 transcribe_notes.py ~/Downloads
    python3 transcribe_notes.py ~/Downloads --pattern 'C *.m4a'

Needs whisper-cpp (brew install whisper-cpp) and a model; medium is the smallest
that handles Bulgarian proper nouns tolerably.
"""
import argparse, glob, os, re, struct, subprocess, sys, tempfile, textwrap, wave

MODEL = os.path.expanduser('~/.cache/whisper/ggml-medium.bin')


def repair_wav(path, out):
    """Fix a RIFF header whose declared sizes do not match the file.

    Recorders that stop without finalising the file leave the size fields at
    their initial values, so decoders read a few kilobytes and give up.
    """
    d = bytearray(open(path, 'rb').read())
    if d[:4] != b'RIFF':
        return False
    size = len(d)
    p, data_off = 12, None
    while p < size - 8:
        cid = bytes(d[p:p + 4])
        sz = struct.unpack('<I', d[p + 4:p + 8])[0]
        if cid == b'data':
            data_off = p
            break
        p += 8 + sz + (sz & 1)
    if data_off is None:
        return False
    struct.pack_into('<I', d, 4, size - 8)
    struct.pack_into('<I', d, data_off + 4, size - (data_off + 8))
    open(out, 'wb').write(d)
    return True


def to_wav16k(src, dst):
    """Convert anything afconvert understands to 16 kHz mono, which whisper wants."""
    subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1', src, dst],
                   capture_output=True)
    return os.path.exists(dst) and os.path.getsize(dst) > 44


def normalise(src, dst):
    """Scale the loudest sample up to about 90% of full scale.

    Notes recorded at arm's length sit around 1% of full scale; whisper
    transcribes a fragment and stops. Returns (peak, gain) so a hopeless
    recording can be spotted rather than silently mistranscribed.
    """
    w = wave.open(src, 'rb')
    n, rate = w.getnframes(), w.getframerate()
    raw = w.readframes(n)
    w.close()
    s = list(struct.unpack(f'<{len(raw) // 2}h', raw))
    peak = max((abs(x) for x in s), default=1) or 1
    gain = max(1, int(0.9 * 32767 / peak))
    out = [max(-32768, min(32767, x * gain)) for x in s]
    o = wave.open(dst, 'wb')
    o.setnchannels(1); o.setsampwidth(2); o.setframerate(rate)
    o.writeframes(struct.pack(f'<{len(out)}h', *out))
    o.close()
    return peak, gain, n / rate


def transcribe(path, lang, beam, model):
    """Run whisper and return the text.

    Always with timestamps: the -nt flag is broken in this build and returns a
    fragment or hallucinated filler. Stripping the timestamps afterwards costs
    nothing and is reliable.

    Beam search is on by default because greedy decoding drops most of these
    recordings -- on one note it returned a single clause where beam search
    returned the whole minute. It is slower, which is a fine trade for notes
    that are transcribed once.
    """
    cmd = ['whisper-cli', '-m', model, '-l', lang, '-f', path]
    if beam:
        cmd += ['-bs', '8', '-bo', '8']
    r = subprocess.run(cmd, capture_output=True, text=True)
    return ' '.join(re.sub(r'^\[[^\]]+\]\s*', '', l.strip())
                    for l in r.stdout.splitlines() if '-->' in l).strip()


def images_in(name):
    """Photo names the recording is about; 'for info X' marks X as not for upload."""
    stem = os.path.splitext(os.path.basename(name))[0]
    names = re.findall(r'(?:20\d{6}_\d+|received_\d+)', stem)
    skip = set(re.findall(r'for info\s+((?:20\d{6}_\d+|received_\d+))', stem))
    return [n for n in names if n not in skip], sorted(skip)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--pattern', default='*.m4a', help="default '*.m4a'; try '*.wav'")
    ap.add_argument('--lang', default='bg')
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--fast', action='store_true',
                    help='skip beam search; quicker but noticeably worse on these recordings')
    a = ap.parse_args()

    if not os.path.exists(a.model):
        sys.exit(f'no model at {a.model}\n'
                 '  curl -L -o ~/.cache/whisper/ggml-medium.bin \\\n'
                 '    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin')

    files = sorted(glob.glob(os.path.join(a.folder, a.pattern)))
    if not files:
        sys.exit(f'nothing matching {a.pattern} in {a.folder}')

    for src in files:
        with tempfile.TemporaryDirectory() as tmp:
            conv, normed = f'{tmp}/c.wav', f'{tmp}/n.wav'
            if src.lower().endswith('.wav'):
                fixed = f'{tmp}/fixed.wav'
                repair_wav(src, fixed)
                ok = to_wav16k(fixed if os.path.exists(fixed) else src, conv)
            else:
                ok = to_wav16k(src, conv)
            if not ok:
                print(f'\n=== {os.path.basename(src)} ===\n  could not decode')
                continue
            peak, gain, dur = normalise(conv, normed)
            text = transcribe(normed, a.lang, not a.fast, a.model)

        keep, skip = images_in(src)
        print(f'\n=== {os.path.basename(src)} ===')
        print(f'  {dur:.0f}s, peak {peak}/32768, gain x{gain}')
        if keep:
            print(f'  photos: {", ".join(keep)}')
        if skip:
            print(f'  for info only, do not import: {", ".join(skip)}')
        if peak < 400:
            print('  NOTE: recorded very quietly; if the text below looks thin, '
                  'ask for a re-record rather than guessing')
        print(textwrap.fill(text or '(nothing transcribed — check the level above, then ask for a re-record)',
                            110, initial_indent='  ', subsequent_indent='  '))


if __name__ == '__main__':
    main()
