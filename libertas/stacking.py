"""Multi-orientation stacking for anisotropic topology optimization.

Implements homogenized stiffness tensors for stacking sequences
(e.g., [0/90], [+10/-10]) by rotating the orientation tensors and
building the stiffness tensor from the rotated tensors directly.
This avoids rotating the 4th-order stiffness tensor with 8-index
contractions, keeping the UFL expression tree small.
"""

from math import pi
from typing import List, Optional

try:
    from fenics import cos, sin, as_matrix, as_tensor, inner, sym, grad, dx, Constant
    from ufl import indices
    from pytop.physics.elasticity import ortho_elast_2D_stiffness_tensor_from_orientation_tensor
except ImportError:
    pass


def _normalize_weights(weights: Optional[List[float]], n: int) -> List[float]:
    """Return normalized weights that sum to 1.

    Args:
        weights: Raw weights, or ``None`` for equal weights.
        n: Number of layers.

    Returns:
        List of floats summing to 1.0.

    Raises:
        ValueError: If length mismatches or weights are non-positive.
    """
    if weights is None:
        return [1.0 / n] * n
    if len(weights) != n:
        raise ValueError(
            f"stacking_weights length ({len(weights)}) must match "
            f"stacking_sequence length ({n})."
        )
    if any(w <= 0 for w in weights):
        raise ValueError("All stacking_weights must be positive.")
    total = sum(weights)
    return [w / total for w in weights]


def _rotate_orientation_tensors(orient_tensor_2, orient_tensor_4, theta_rad: float):
    """Rotate 2nd and 4th order orientation tensors by theta_rad.

    Instead of rotating the full 4th-order stiffness tensor (which requires
    8-index contractions and creates huge UFL trees), we rotate the orientation
    tensors and then build C from them.  This is algebraically equivalent but
    produces much smaller UFL expressions.

    Args:
        orient_tensor_2: 2nd-order orientation tensor (UFL 2x2).
        orient_tensor_4: 4th-order orientation tensor (UFL 2x2x2x2).
        theta_rad: Rotation angle in radians.

    Returns:
        Tuple of (rotated_a2, rotated_a4).
    """
    cos_t = cos(theta_rad)
    sin_t = sin(theta_rad)
    R = as_matrix([[cos_t, -sin_t], [sin_t, cos_t]])

    # a2' = R @ a2 @ R^T
    i, j, m, n = indices(4)
    a2_rot = as_tensor(R[i, m] * R[j, n] * orient_tensor_2[m, n], (i, j))

    # a4' = R_ip R_jq R_kr R_ls a4_pqrs
    i, j, k, l, p, q, r, s = indices(8)
    a4_rot = as_tensor(
        R[i, p] * R[j, q] * R[k, r] * R[l, s] * orient_tensor_4[p, q, r, s],
        (i, j, k, l)
    )

    return a2_rot, a4_rot


def build_stacked_stiffness_tensor(
    orient_tensor_2,
    orient_tensor_4,
    E1: float,
    E2: float,
    G12: float,
    nu12: float,
    angle_offsets_rad: List[float],
    weights: Optional[List[float]] = None,
):
    """Build a homogenized stiffness tensor for a stacking sequence.

    For each ply offset, the orientation tensors are rotated and then the
    stiffness tensor is built from the rotated tensors.  This avoids rotating
    the 4th-order C tensor directly (which needs 8-index contractions).

        C_hom = Σ_k  w_k * C(R_k @ a2 @ R_k^T,  R_k @ a4 @ R_k^T),   Σ w_k = 1

    Args:
        orient_tensor_2: 2nd-order orientation tensor (design variable).
        orient_tensor_4: 4th-order orientation tensor.
        E1: Young's modulus in material direction 1.
        E2: Young's modulus in material direction 2.
        G12: In-plane shear modulus.
        nu12: In-plane Poisson's ratio.
        angle_offsets_rad: Relative angle offsets in radians for each layer.
        weights: Thickness fraction of each layer.  ``None`` = equal thickness.

    Returns:
        Homogenized 4th-order stiffness tensor (UFL expression).
    """
    n = len(angle_offsets_rad)
    w = _normalize_weights(weights, n)

    C_total = None
    for theta, wk in zip(angle_offsets_rad, w):
        if abs(theta) < 1e-12:
            a2, a4 = orient_tensor_2, orient_tensor_4
        else:
            a2, a4 = _rotate_orientation_tensors(orient_tensor_2, orient_tensor_4, theta)

        C_layer = ortho_elast_2D_stiffness_tensor_from_orientation_tensor(
            a2, a4, E1, E2, G12, nu12
        )
        weighted = wk * C_layer
        C_total = weighted if C_total is None else C_total + weighted

    return C_total


def stacked_stress_tensor(
    u,
    E1: float,
    E2: float,
    G12: float,
    nu12: float,
    orient_tensor_2,
    orient_tensor_4,
    angle_offsets_rad: List[float],
    weights: Optional[List[float]] = None,
):
    """Compute the stress tensor using a homogenized stacking-sequence material.

    Args:
        u: Displacement field.
        E1, E2, G12, nu12: Orthotropic material constants.
        orient_tensor_2: 2nd-order orientation tensor.
        orient_tensor_4: 4th-order orientation tensor.
        angle_offsets_rad: Relative angle offsets in radians for each layer.
        weights: Thickness fractions.  ``None`` = equal thickness.

    Returns:
        2nd-order stress tensor (UFL expression).
    """
    C = build_stacked_stiffness_tensor(
        orient_tensor_2, orient_tensor_4, E1, E2, G12, nu12,
        angle_offsets_rad, weights
    )
    i, j, k, l = indices(4)
    eps = sym(grad(u))
    return as_tensor(C[i, j, k, l] * eps[k, l], (i, j))


def stacked_bilinear_form(
    trial_function,
    test_function,
    E1: float,
    E2: float,
    G12: float,
    nu12: float,
    orient_tensor_2,
    orient_tensor_4,
    angle_offsets_rad: List[float],
    weights: Optional[List[float]] = None,
    weight=None,
):
    """Build the bilinear form for a stacked multi-orientation material.

    Args:
        trial_function: FEniCS TrialFunction.
        test_function: FEniCS TestFunction.
        E1, E2, G12, nu12: Orthotropic material constants.
        orient_tensor_2: 2nd-order orientation tensor.
        orient_tensor_4: 4th-order orientation tensor.
        angle_offsets_rad: Relative angle offsets in radians for each layer.
        weights: Thickness fractions.  ``None`` = equal thickness.
        weight: Optional SIMP penalty / density weighting function.

    Returns:
        UFL bilinear form ``a(u, v)``.
    """
    if weight is None:
        weight = Constant(1)

    sigma = stacked_stress_tensor(
        trial_function, E1, E2, G12, nu12,
        orient_tensor_2, orient_tensor_4, angle_offsets_rad, weights
    )
    return inner(weight * sigma, sym(grad(test_function))) * dx
