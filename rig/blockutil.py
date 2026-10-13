#!/usr/bin/env python
"""blockutil.py -- shared helpers for TDT block access used by the rig scripts.

load_block(path, stores=None)
    path ending in .npz  -> a synthetic block written by rig/make_synthetic_block.py
                            (same attribute shape as tdt.read_block: .streams.X.data/.fs,
                            .scalars.UDP1.data/.ts, .epocs)
    anything else        -> tdt.read_block(path, store=stores) (full read on failure)

newest_block_dir(data_root)
    newest directory under data_root that actually holds a TDT block (a *.tsq at depth
    <= 2), resolved to the folder containing the .tsq. Empty folders (e.g. a tank
    directory created before the first recording) are ignored -- 2026-10-13.
"""

import glob
import io
import json
import os

import numpy as np


class AttrDict(dict):
    """dict with attribute access, like tdt.StructType (membership via .keys())."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


def read_synthetic_block(path):
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z["meta_json"]))
    blk = AttrDict(streams=AttrDict(), scalars=AttrDict(), epocs=AttrDict(), info=AttrDict(meta))
    for name, fs in meta["streams"].items():
        blk.streams[name] = AttrDict(name=name, data=z["stream_" + name], fs=float(fs), start_time=0.0)
    for name in meta["scalars"]:
        blk.scalars[name] = AttrDict(name=name, data=z["scalar_" + name], ts=z["scalar_%s_ts" % name])
    return blk


def load_block(path, stores=None, evtype=None):
    if str(path).lower().endswith(".npz"):
        return read_synthetic_block(path)
    import tdt
    kw = {}
    if evtype:
        kw["evtype"] = list(evtype)
    if stores:
        try:
            blk = tdt.read_block(path, store=list(stores), **kw)
            if all(find_store(blk, s) is not None for s in stores):
                return blk
        except Exception as exc:  # noqa: BLE001
            print("note: filtered read failed (%s); reading full block" % type(exc).__name__)
    return tdt.read_block(path, **kw)


def find_store(blk, name):
    for grp in ("streams", "scalars", "epocs"):
        g = getattr(blk, grp, None)
        if g is not None and name in list(g.keys()):
            return g[name]
    return None


def resolve_block_dir(p):
    """Folder that holds the .tsq: p itself, or its single child that does."""
    if glob.glob(os.path.join(p, "*.tsq")):
        return p
    kids = [os.path.join(p, k) for k in sorted(os.listdir(p))
            if os.path.isdir(os.path.join(p, k)) and glob.glob(os.path.join(p, k, "*.tsq"))]
    if len(kids) == 1:
        return kids[0]
    if len(kids) > 1:
        return max(kids, key=os.path.getmtime)
    return p


def block_dirs(data_root, depth=2):
    """All folders under data_root (depth <= 2) that contain a .tsq, newest first."""
    found = []
    for tsq in glob.glob(os.path.join(data_root, "*", "*.tsq")) + \
            glob.glob(os.path.join(data_root, "*", "*", "*.tsq")):
        found.append(os.path.dirname(tsq))
    found = sorted(set(found), key=os.path.getmtime, reverse=True)
    return found


def newest_block_dir(data_root):
    dirs = block_dirs(data_root)
    return dirs[0] if dirs else None
