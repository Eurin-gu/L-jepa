#!/usr/bin/env python3
"""Merge dataset dirs into a combined dataset compatible with train_stilt_strict.py."""
import argparse, json, os, hashlib
import numpy as np

def load(path):
    p = str(path)
    for name in ('x.npy', 'y.npy', 'meta.json'):
        if not os.path.isfile(os.path.join(p, name)):
            raise FileNotFoundError(f'merged dir missing {name} in {p}')
    x = np.load(os.path.join(p, 'x.npy')).astype(np.float32)
    y = np.load(os.path.join(p, 'y.npy')).astype(np.float32)
    with open(os.path.join(p, 'meta.json')) as f:
        meta = json.load(f)
    samples = meta.get('samples', []) if isinstance(meta, dict) else meta
    return x, y, samples, meta

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while b := f.read(16 * 1024 * 1024):
            h.update(b)
    return h.hexdigest()

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
    fp = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    combined = {
        'n_samples': len(all_samples),
        'samples': all_samples,
        'contract': contract,
        'contract_fingerprint': fp,
        'sources': [{'path': p, 'n': len((m.get('samples', []) if isinstance(m, dict) else m))}
                    for p, m in zip(args.input, metas)],
    }
    os.makedirs(args.out, exist_ok=True)
    xp = os.path.join(args.out, 'x.npy')
    yp = os.path.join(args.out, 'y.npy')
    np.save(xp, x)
    np.save(yp, y)
    combined['arrays'] = {
        'inputs': {'sha256': sha256_file(xp), 'shape': list(x.shape), 'dtype': str(x.dtype)},
        'targets': {'sha256': sha256_file(yp), 'shape': list(y.shape), 'dtype': str(y.dtype)},
    }
    with open(os.path.join(args.out, 'meta.json'), 'w') as f:
        json.dump(combined, f, indent=2)
    dates = sorted({str(s['snapshot'])[:8] for s in all_samples})
    print(f'MERGED {len(all_samples)} samples -> {args.out}')
    print('dates:', dates)

if __name__ == '__main__':
    main()
