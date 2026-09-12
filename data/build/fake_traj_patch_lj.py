# --- Fake-trajectory controls (F1-F3) for the L-JEPA causality audit ---
#
# F1 reverse: integrate (-u,-v): same path length, direction reversed.
# F2 perp:    integrate (-v, u): 90deg rotated wind (geometric tube, wrong physics).
# F3 random:  per-sample fixed heading theta, step size = true speed:
#             straight tube of same length as the wind skeleton, no advection.
#
# These change ONLY how the tube is drawn; the model, mask rule, and budget
# are identical to the true input-wind arm (see train_stilt_strict).
#

TRAJ_TRANSFORMS = ("none", "reverse", "perp", "random_heading")

def apply_trajectory_transform(u, v, transform, rng=None):
    """Return (u2, v2) with the requested direction control.

    u, v: (B, T) center winds (already de-normalized to m/s).
    transform: none | reverse | perp | random_heading.
    rng: np.random.Generator used for random_heading (per-sample fixed theta).
    """
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if transform == "none":
        return u, v
    if transform == "reverse":
        return -u, -v
    if transform == "perp":
        return -v, u
    if transform == "random_heading":
        if rng is None:
            rng = np.random.default_rng(0)
        theta = rng.uniform(0.0, 2.0 * np.pi, size=u.shape[0])
        speed = np.hypot(u, v)                 # (B, T) true speed keeps tube length
        ct = np.cos(theta)[:, None]
        st = np.sin(theta)[:, None]
        return speed * ct, speed * st
    raise ValueError("unknown trajectory transform: " + str(transform))
