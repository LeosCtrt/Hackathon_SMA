"""
Rapport qualité des données d'activité hospitalière.

Vérifie que les données sont suffisamment propres pour lancer
la simulation multi-agents et le triage organisationnel HDJ.

Verdict :
  usable_for_decision_support  — données complètes, prêtes pour simulation
  usable_with_warnings         — données utilisables avec précautions signalées
  not_usable                   — données insuffisantes, simulation non fiable
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


REQUIRED_COLUMNS = [
    "NUM SEJOUR",
    "CODE DIAG",
    "LISTE ACTES CCAM MVT",
    "TYPE SEJOUR",
]

IMPORTANT_COLUMNS = REQUIRED_COLUMNS + [
    "NUM IPP PATIENT",
    "CODE ACTE",
    "DATE ENTREE SEJ",
    "HEURE ENTREE SEJ",
    "HEURE SORTIE SEJ",
    "SPECIALITE OPERATEUR",
]


def _missing_rate(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 1.0
    return round(df[col].isna().sum() / len(df), 4) if len(df) else 1.0


def _count_duplicates(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns or df.empty:
        return 0
    counts = df[col].value_counts()
    return int((counts > 1).sum())


def build_data_quality_report(
    df: pd.DataFrame,
    output_path: str | Path = "outputs/data_quality_report.json",
) -> Dict[str, Any]:
    """
    Analyse la qualité des données et produit un rapport JSON.

    Args:
        df          : DataFrame combiné chargé par hospital_data_loader.
        output_path : chemin de sortie pour le fichier JSON.

    Returns:
        dict du rapport (également sauvegardé dans output_path).
    """
    warnings: List[str] = []
    blocking_issues: List[str] = []

    # ── Dimensions ────────────────────────────────────────────────────────
    n_lines = len(df)
    n_cols = len(df.columns)

    # ── Colonnes obligatoires ─────────────────────────────────────────────
    # Bloquant uniquement si la colonne est ABSENTE du DataFrame.
    # Un taux élevé de valeurs nulles est un avertissement, pas un blocage.
    missing_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_required:
        blocking_issues.append(f"Colonnes obligatoires absentes : {missing_required}")

    # ── Taux de valeurs manquantes ────────────────────────────────────────
    # Un taux élevé de nulls réduit la couverture mais n'empêche pas l'analyse
    # → toujours un avertissement, jamais un blocage.
    missing_rates = {col: _missing_rate(df, col) for col in IMPORTANT_COLUMNS}
    for col, rate in missing_rates.items():
        if rate > 0.3:
            warnings.append(f"{col} : {rate:.0%} de valeurs manquantes — couverture réduite")

    # ── IPP ───────────────────────────────────────────────────────────────
    has_ipp = "NUM IPP PATIENT" in df.columns
    ipp_uniques = 0
    lines_without_ipp = n_lines
    ipp_recurrence_rate = 0.0

    if has_ipp:
        ipp_series = df["NUM IPP PATIENT"].dropna()
        ipp_uniques = int(ipp_series.nunique())
        lines_without_ipp = int(df["NUM IPP PATIENT"].isna().sum())
        if ipp_uniques > 0:
            counts = ipp_series.value_counts()
            ipp_recurrence_rate = round((counts > 1).sum() / ipp_uniques, 4)
        if lines_without_ipp > 0:
            warnings.append(
                f"{lines_without_ipp} ligne(s) sans IPP — analyse récurrence incomplète"
            )
    else:
        warnings.append("Colonne IPP absente — analyse de fragmentation non disponible")

    # ── Doublons séjours ──────────────────────────────────────────────────
    duplicate_sejours = 0
    if "NUM SEJOUR" in df.columns:
        counts = df["NUM SEJOUR"].value_counts()
        duplicate_sejours = int((counts > 1).sum())

    # ── TYPE_SEJOUR ───────────────────────────────────────────────────────
    type_sejour_warning = False
    if "TYPE SEJOUR" in df.columns:
        types = df["TYPE SEJOUR"].dropna().unique().tolist()
        if all(t == "EXT" for t in types):
            type_sejour_warning = True
            warnings.append(
                "Toutes les données sont TYPE_SEJOUR=EXT (consultations externes) — "
                "simulation organisationnelle à valider DIM/PMSI, pas une reclassification PMSI réelle"
            )

    # ── Cohérence CCAM ────────────────────────────────────────────────────
    ccam_coverage = 0.0
    if "LISTE ACTES CCAM MVT" in df.columns:
        filled = df["LISTE ACTES CCAM MVT"].dropna()
        non_empty = filled[filled.astype(str).str.strip().str.len() > 0]
        ccam_coverage = round(len(non_empty) / n_lines, 4) if n_lines else 0.0
        if ccam_coverage < 0.5:
            warnings.append(
                f"Seulement {ccam_coverage:.0%} des lignes ont des actes CCAM "
                "— éligibilité HDJ sous-estimée"
            )

    # ── Cohérence dates ───────────────────────────────────────────────────
    dates_coherent = None
    if "DATE ENTREE SEJ" in df.columns:
        try:
            dates = pd.to_datetime(
                df["DATE ENTREE SEJ"].dropna(), errors="coerce"
            )
            valid_dates = dates.notna().sum()
            dates_coherent = bool(valid_dates > 0)
            if valid_dates < len(df) * 0.5:
                warnings.append("Moins de 50% de dates d'entrée valides")
        except Exception:
            dates_coherent = False

    # ── Verdict ───────────────────────────────────────────────────────────
    # not_usable uniquement si des colonnes structurelles sont ABSENTES du fichier.
    # Des taux élevés de nulls ou le format TYPE_SEJOUR=EXT ne bloquent pas l'analyse.
    if blocking_issues:
        verdict = "not_usable"
        verdict_detail = (
            "Colonnes structurelles absentes — simulation impossible. "
            "Fournir un fichier avec NUM_SEJOUR, CODE_DIAG, LISTE_ACTES_CCAM_MVT, TYPE_SEJOUR."
        )
    elif warnings:
        verdict = "usable_with_warnings"
        verdict_detail = (
            "Données exploitables pour aide à la décision organisationnelle. "
            "Les avertissements signalés (couverture actes, TYPE_SEJOUR=EXT) "
            "sont attendus pour ce type d'extraction PMSI. "
            "Validation DIM/PMSI requise avant mise en œuvre."
        )
    else:
        verdict = "usable_for_decision_support"
        verdict_detail = (
            "Données de bonne qualité pour la simulation organisationnelle HDJ. "
            "Validation DIM/PMSI requise avant mise en œuvre."
        )

    report = {
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "dimensions": {
            "n_lignes": n_lines,
            "n_colonnes": n_cols,
        },
        "colonnes": {
            "requises_presentes": [c for c in REQUIRED_COLUMNS if c not in missing_required],
            "requises_manquantes": missing_required,
            "taux_manquants": missing_rates,
        },
        "ipp": {
            "present": has_ipp,
            "ipp_uniques": ipp_uniques,
            "lignes_sans_ipp": lines_without_ipp,
            "taux_recurrence": ipp_recurrence_rate,
        },
        "qualite": {
            "sejours_doublons": duplicate_sejours,
            "type_sejour_ext_seulement": type_sejour_warning,
            "couverture_actes_ccam": ccam_coverage,
            "dates_coherentes": dates_coherent,
        },
        "warnings": warnings,
        "blocking_issues": blocking_issues,
        "note": (
            "Ce rapport qualité est produit automatiquement. "
            "Une validation par le DIM est recommandée avant toute décision opérationnelle."
        ),
    }

    out = Path(output_path)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report
