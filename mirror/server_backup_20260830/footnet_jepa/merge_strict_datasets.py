#!/usr/bin/env python3
"""Merge same-cycle strict datasets (jul05+apr02+...) into one dataset dir.
Usage: python3 merge_strict_datasets.py --out <dir> --input <prefix1> [--input <prefix2> ...]
Each --input is a prefix like /root/autodl-tmp/footnet_jepa/data/jul05_samecycle_strict
"""
import argparse, json, os, sys, shutil, hashlib
import numpy as np

def load(prefix):
    x = np.load(prefix + '_inputs.npy').astype(np.float32)
    y = np.load(prefix + '_targets.npy').astype(np.float32)
    with open(prefix + '_meta.json') as f:
        meta = json.load(f)
    samples = meta.get('samples') if isinstance(meta, dict) else meta
    if len(samples) != len(x):
        raise ValueError(f'{prefix}: {len(samples)} samples vs {len(x)} rows')
    return x, y, samples, meta

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
    x = np.concatenate(xs, axis=0)
    y = np.concatenate(ys, axis=0)

    # merge contracts: keep first, note per-source
    contract = metas[0].get('contract', {}) if isinstance(metas[0], dict) else {}
    combined_meta = {
        'n_samples': len(all_samples),
        'samples': all_samples,
        'contract': contract,
        'sources': [{'prefix': p, 'n': len(meta.get('samples', [])) if isinstance(meta, dict) else len(meta)}
                    for p, meta in zip(args.input, metas)],
        'merge_sha256': hashlib.sha256(x.tobytes()).hexdigest()[:16],
    }
    os.makedirs(args.out, exist_ok=True)
    np.save(os.path.join(args.out, 'x.npy'), x)
    np.save(os.path.join(args.out, 'y.npy'), y)
    with open(os.path.join(args.out, 'meta.json'), 'w') as f:
        json.dump(combined_meta, f, indent=2)
    print(f'merged {len(all_samples)} samples -> {args.out}')
    print('per-source:', json.dumps(combined_meta['sources']))
    print('dates:', sorted({str(s['snapshot'])[:8] for s in all_samples}))

if __name__ == '__main__':
    main()
