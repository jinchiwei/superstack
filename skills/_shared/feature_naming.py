"""Human-readable name expansion for pyradiomics / pyalfe / common ML feature columns.

Use this anywhere a feature column name is going to be rendered for human eyes
(SHAP plots, feature-importance bar charts, table column headers, slide labels).

The convention is:
  <Feature> — <Family> (<Filter>)

Family names are spelled out in full (no GLCM/GLRLM/etc. abbreviations on the rendered label).
Common feature-name abbreviations (Imc1, Idn, Idmn, Idm) are expanded.
Filter prefix (LoG σ=2 mm, Wavelet LLH, etc.) renders as a parenthetical suffix.

Examples:
    original_glcm_Idn                          -> "Inverse Difference Normalized — Co-occurrence"
    log-sigma-2-0-mm-3D_glcm_Imc1              -> "Information Measure of Correlation 1 — Co-occurrence (LoG σ=2.0 mm)"
    wavelet-LLH_firstorder_Median              -> "Median — First-order (Wavelet LLH)"
    original_shape_VoxelVolume                 -> "Voxel Volume — Shape"
    FLAIR_percentage_volume_in_Pons            -> "FLAIR Lesion in Pons (%)"
    age_years                                  -> "Age at Diagnosis (years)"
    is_male                                    -> "Male Sex"
"""
from __future__ import annotations
import re


_FAMILY_FULL = {
    "glcm": "Co-occurrence",
    "glrlm": "Run-length",
    "glszm": "Size-zone",
    "gldm": "Dependence",
    "ngtdm": "Neighborhood",
    "firstorder": "First-order",
    "shape": "Shape",
}

_ABBREVIATION_EXPANSIONS = {
    "Imc1": "Information Measure of Correlation 1",
    "Imc2": "Information Measure of Correlation 2",
    "Idn":  "Inverse Difference Normalized",
    "Idmn": "Inverse Difference Moment Normalized",
    "Idm":  "Inverse Difference Moment",
    "MCC":  "Maximal Correlation Coefficient",
}


def clean_radiomic_feature_name(name: str) -> str:
    """Return a human-readable version of `name`.

    Handles pyradiomics names, pyalfe lesion-volume features, and common
    demographic columns. Falls back to a CamelCase split if the name doesn't
    match a known pattern.
    """
    if name == "age_years":
        return "Age at Diagnosis (years)"
    if name in ("is_male", "isMale"):
        return "Male Sex"

    # pyalfe location features
    if name.startswith("FLAIR_percentage_volume_in_"):
        loc = name.replace("FLAIR_percentage_volume_in_", "").replace("_", " ").strip()
        return f"FLAIR Lesion in {loc} (%)"
    if name.startswith("FLAIR_lesion_volume_in_"):
        loc = name.replace("FLAIR_lesion_volume_in_", "").replace("_", " ").strip()
        return f"FLAIR Lesion Volume in {loc}"
    if name.startswith("FLAIR_average_dist_to_"):
        loc = (name.replace("FLAIR_average_dist_to_", "")
                   .replace("_(voxels)", "").replace("_", " ").strip())
        return f"FLAIR Mean Distance to {loc}"
    if name.startswith("FLAIR_minimum_dist_to_"):
        loc = (name.replace("FLAIR_minimum_dist_to_", "")
                   .replace("_(voxels)", "").replace("_", " ").strip())
        return f"FLAIR Min Distance to {loc}"
    if name.startswith("FLAIR_"):
        return name.replace("FLAIR_", "FLAIR ").replace("_", " ")

    # pyradiomics: <filter>_<family>_<feature>
    n = name
    filt_label = ""
    m = re.match(r"log-sigma-(\d+)-(\d+)-mm-3D_(.+)", n)
    if m:
        sig_int, sig_frac, rest = m.groups()
        filt_label = f"LoG σ={sig_int}.{sig_frac} mm"
        n = rest
    elif n.startswith("wavelet-"):
        m = re.match(r"wavelet-([A-Z]+)_(.+)", n)
        if m:
            band, rest = m.groups()
            filt_label = f"Wavelet {band}"
            n = rest
    elif n.startswith("squareroot_"):
        filt_label = "Square-root"; n = n[len("squareroot_"):]
    elif n.startswith("square_"):
        filt_label = "Squared"; n = n[len("square_"):]
    elif n.startswith("logarithm_"):
        filt_label = "Logarithm"; n = n[len("logarithm_"):]
    elif n.startswith("exponential_"):
        filt_label = "Exponential"; n = n[len("exponential_"):]
    elif n.startswith("gradient_"):
        filt_label = "Gradient"; n = n[len("gradient_"):]
    elif n.startswith("lbp-3D-"):
        m = re.match(r"lbp-3D-([a-z]+)_(.+)", n)
        if m:
            band, rest = m.groups()
            filt_label = f"LBP {band}"; n = rest
    elif n.startswith("original_"):
        n = n[len("original_"):]

    family_label = ""
    for key, full in _FAMILY_FULL.items():
        if n.startswith(key + "_"):
            family_label = full
            n = n[len(key) + 1:]
            break

    feat_label = _ABBREVIATION_EXPANSIONS.get(n)
    if feat_label is None:
        # CamelCase -> "Camel Case", drop leftover underscores
        feat_label = re.sub(r"(?<!^)(?=[A-Z])", " ", n).replace("_", " ").strip()

    parts = [feat_label]
    if family_label:
        parts.append(f"— {family_label}")
    if filt_label:
        parts.append(f"({filt_label})")
    return " ".join(parts)
