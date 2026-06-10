"""
Chargement des données d'activité hospitalière endocrino-diabétologie.

Priorité de chargement (par période) :
  1. Fichier avec IPP (*IPP*.xlsx) si présent
  2. Fallback vers fichier sans IPP correspondant

Retourne un DataFrame unique enrichi de colonnes techniques :
  - source_file     : nom du fichier source
  - source_period   : libellé de la période (2020_2023 / 2024_2026)
  - has_ipp         : booléen indiquant si la ligne provient d'un fichier IPP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


# Colonnes attendues dans les données PMSI endocrino
REQUIRED_COLUMNS = [
    "NUM SEJOUR",
    "CODE DIAG",
    "LISTE ACTES CCAM MVT",
    "TYPE SEJOUR",
]
OPTIONAL_COLUMNS = [
    "NUM IPP PATIENT",
    "DATE ENTREE SEJ",
    "HEURE ENTREE SEJ",
    "HEURE SORTIE SEJ",
    "CODE ACTE",
    "SPECIALITE OPERATEUR",
    "AGE PATIENT ANNEES ENT SEJ",
    "LIBELLE UNITE MVT",
]


@dataclass
class LoadMetadata:
    """Métadonnées de chargement — traçabilité et qualité."""
    files_used: Dict[str, str] = field(default_factory=dict)
    lines_per_file: Dict[str, int] = field(default_factory=dict)
    total_lines: int = 0
    has_ipp: bool = False
    ipp_files_count: int = 0
    fallback_files_count: int = 0
    columns_available: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"  Fichiers chargés   : {len(self.files_used)}",
            f"  Fichiers IPP       : {self.ipp_files_count}",
            f"  Fichiers fallback  : {self.fallback_files_count}",
            f"  Lignes totales     : {self.total_lines}",
            f"  IPP disponible     : {'oui' if self.has_ipp else 'non'}",
        ]
        if self.missing_required:
            lines.append(f"  Colonnes manquantes: {self.missing_required}")
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  ⚠  {w}")
        return "\n".join(lines)


def _locate_files(data_dir: Path) -> Dict[str, Dict[str, Optional[Path]]]:
    """Localise les fichiers pour chaque période, avec détection IPP."""
    all_ipp = list(data_dir.glob("*IPP*.xlsx")) if data_dir.exists() else []
    return {
        "2020_2023": {
            "ipp":      next((f for f in all_ipp if "2020_2023" in f.name), None),
            "fallback": data_dir / "Données_Externes_Endocrino_et_diabéto_2020_2023_A.xlsx",
        },
        "2024_2026": {
            "ipp":      next((f for f in all_ipp if "2020_2023" not in f.name), None),
            "fallback": data_dir / "Données_Externes_Endocrino_et_diabéto_A.xlsx",
        },
    }


def load_hospital_activity_data(
    data_dir: str | Path = "data",
    periods: Optional[List[str]] = None,
    verbose: bool = True,
) -> tuple[pd.DataFrame, LoadMetadata]:
    """
    Charge les données d'activité hospitalière endocrino-diabétologie.

    Args:
        data_dir : dossier contenant les fichiers de données.
        periods  : périodes à charger ("2020_2023", "2024_2026"). Toutes par défaut.
        verbose  : afficher les logs de chargement.

    Returns:
        (DataFrame combiné, LoadMetadata)
    """
    data_dir = Path(data_dir)
    meta = LoadMetadata()
    file_map = _locate_files(data_dir)

    if periods:
        file_map = {k: v for k, v in file_map.items() if k in periods}

    dfs: List[pd.DataFrame] = []

    for period, paths in file_map.items():
        ipp_path: Optional[Path] = paths["ipp"]
        fallback: Path = paths["fallback"]

        chosen = ipp_path if (ipp_path and ipp_path.exists()) else None
        if chosen is None and fallback.exists():
            chosen = fallback

        if chosen is None:
            msg = f"{period}: aucun fichier trouvé (ni IPP ni fallback)"
            meta.warnings.append(msg)
            if verbose:
                print(f"[DATA] ⚠  {msg}")
            continue

        is_ipp = ipp_path is not None and chosen == ipp_path
        tag = " avec IPP" if is_ipp else " (sans IPP, fallback)"

        try:
            df = pd.read_excel(chosen, engine="openpyxl", dtype=str)
        except Exception as exc:
            meta.warnings.append(f"{period}: erreur lecture {chosen.name} — {exc}")
            continue

        df["source_file"] = chosen.name
        df["source_period"] = period
        df["has_ipp"] = is_ipp

        meta.files_used[period] = chosen.name
        meta.lines_per_file[period] = len(df)
        if is_ipp:
            meta.ipp_files_count += 1
        else:
            meta.fallback_files_count += 1

        dfs.append(df)
        if verbose:
            print(f"[DATA] {period}{tag} : {len(df)} lignes")

    if not dfs:
        raise FileNotFoundError(
            f"Aucun fichier de données trouvé dans {data_dir}. "
            "Vérifiez la présence des fichiers endocrino."
        )

    combined = pd.concat(dfs, ignore_index=True)
    meta.total_lines = len(combined)
    meta.has_ipp = "NUM IPP PATIENT" in combined.columns and combined["NUM IPP PATIENT"].notna().any()
    meta.columns_available = list(combined.columns)
    meta.missing_required = [c for c in REQUIRED_COLUMNS if c not in combined.columns]

    if meta.missing_required:
        meta.warnings.append(f"Colonnes requises manquantes : {meta.missing_required}")

    if verbose:
        print(f"[DATA] Total combiné — {meta.total_lines} lignes")

    return combined, meta
