#!/usr/bin/env python3
"""Merge dataset dirs or prefixes into a combined dataset compatible with train_stilt_strict.py.
Usage: python3 merge_final.py --out data/combined --input data/prod_train_20160428 --input data/prod_val_20160715 ...
Each input may be a prefix (x.npy/meta.json + _inputs.npy/_targets.npy auto-detected) or dir.
"""
import argparse, json, os, sys, hashlib
import numpy as np

def load(path):
    """Load x/y/samples from either prefix or merged-dir layout."""
    p = str(path)
    candidates = []
    # merged dir: x.npy y.npy meta.json
    for name in ('x.npy', 'y.npy', 'meta.json'):
        if os.path.isfile(os.path.join(p, name)):
            candidates.append(os.path.join(p, name))
    if len(candidates) == 3:
        x = np.load(os.path.join(p, 'x.npy')).astype(np.float32)
        y = np.load(os.path.join(p, 'y.npy')).astype(np.float32)
        with open(os.path.join(p, 'meta.json')) as f:
            meta = json.load(f)
        samples = meta.get('samples', []) if isinstance(meta, dict) else meta
        return x, y, samples, meta
    # prefix: *_inputs.npy *_targets.npy *_meta.json
    inp = p + '_inputs.npy'; tgt = p + '_targets.npy'; mt = p + '_meta.json'
    if os.path.isfile(inp):
        x = np.load(inp).astype(np.float32)
        y = np.load(tgt).astype(np.float32)
        with open(mt) as f:
            meta = json.load(f)
        samples = meta.get('samples', []) if isinstance(meta, dict) else meta
        return x, y, samples, meta
    raise FileNotFoundError(f'cannot load dataset from {p}')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--input', action='append', required=True)
    args = ap.parse_args()
    xs, ys, all_samples, metas = [], [], [], []
    for prefix in args.input:
        x, y, samples, meta = load(prefix)
        xs.append(x); ys.append(y); all_samples.extend(samples)
        metas.append(meta)
        print(f'  {prefix}: {len(samples)} samples', flush=True)
    x = np.concatenate(xs, axis=0)
    y = np.concatenate(ys, axis=0)
    contract = metas[0].get('contract', {}) if isinstance(metas[0], dict) else {}
    combined = {
        'n_samples': len(all_samples),
        'samples': all_samples,
        'contract': contract,
        'sources': [{'path': p, 'n': len((m.get('samples', []) if isinstance(m, dict) else m))}
                    for p, m in zip(args.input, metas)],
        'merged_sha256': hashlib.sha256(x.tobytes()).hexdigest()[:16],
    }
    os.makedirs(args.out, exist_ok=True)
    np.save(os.path.join(args.out, 'x.npy'), x)
    np.save(os.path.join(args.out, 'y.npy'), y)
    with open(os.path.join(args.out, 'meta.json'), 'w') as f:
        json.dump(combined, f, indent=2)
    dates = sorted({str(s['snapshot'])[:8] for s in all_samples})
    print(f'MERGED {len(all_samples)} samples -> {args.out}')
    print('dates:', dates)

if __name__ == '__main__':
    main()
