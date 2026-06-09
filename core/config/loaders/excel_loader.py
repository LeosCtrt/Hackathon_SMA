"""
core/config/loaders/excel_loader.py

Charge HDJ_Agent_modele_donnees.xlsx et expose les données structurées
pour les agents Mesa.

Architecture cible :
  Excel  → données opérationnelles (salles, ressources, actes, personnel,
            patients, graphe spatial, mouvements PMSI)
  YAML   → règles métier (codes CCAM, préfixes CIM-10, candidate pathways,
            contraintes inter-agents, recommandations MVP)
  Python → moteur multi-agents générique (Mesa)

Niveau 1 (actuel) : loader + rapport, sans modifier les agents.
Niveau 2 (futur)  : HopitalModel.from_excel() avec fallback YAML.
Niveau 3 (futur)  : agents totalement instanciés depuis Excel + YAML métier.

Usage :
    from core.config.loaders.excel_loader import load_hdj_excel
    data = load_hdj_excel("HDJ_Agent_modele_donnees.xlsx")
    data.rapport()

    # Accès direct aux DataFrames
    print(data.salles)
    print(data.actes)

    # Paramètres simulation
    print(data.parametres["horizon_simulation"])   # "5"
    print(data.parametres["granularite_temps"])    # "5"

    # Helpers agents
    configs = data.soignants_pour_mesa()           # liste prête pour HopitalModel
    ressources = data.ressources_limitantes_mvp()  # {id: (nom, quantite)}
    G = data.graphe_spatial()                      # networkx.DiGraph
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

# ── Schéma obligatoire par feuille ─────────────────────────────────────────
# Seules les colonnes strictement nécessaires pour les agents sont listées.
REQUIRED_COLUMNS: Dict[str, List[str]] = {
    "Parametres":         ["parametre", "valeur"],
    "Sites":              ["site_id", "site_libelle"],
    "Specialites":        ["specialite_id", "specialite_libelle"],
    "Unites":             ["unite_id", "unite_libelle", "site_id"],
    "HDJ":                ["hdj_id", "hdj_libelle", "site_id", "capacite_places", "statut"],
    "Salles":             ["salle_id", "salle_libelle", "type_salle", "capacite_max",
                           "heure_ouverture", "heure_fermeture"],
    "Ressources":         ["ressource_id", "ressource_libelle", "type_ressource"],
    "Actes":              ["acte_id", "acte_libelle", "duree_minutes", "type_salle_requis"],
    "Personnel":          ["personnel_id", "nom", "role", "specialite_id",
                           "dispo_debut", "dispo_fin"],
    "Patients":           ["patient_id"],
    "Salle_Actes":        ["salle_id", "acte_id"],
    "Salle_Ressources":   ["salle_id", "ressource_id", "quantite"],
    "Acte_Ressources":    ["acte_id", "ressource_id", "quantite_requise"],
    "Acte_Prerequis":     ["acte_id", "acte_prerequis_id", "obligatoire"],
    "Personnel_Actes":    ["personnel_id", "acte_id"],
    "HDJ_Salles":         ["hdj_id", "salle_id"],
    "Plan_Adjacence":     ["noeud_depart", "noeud_arrivee", "temps_trajet_min"],
    "Sejours_Mouvements": ["num_sejour", "code_acte", "code_diag"],
    "Creneaux_Template":  ["creneau_id", "salle_id", "acte_id"],
}

# Feuilles clés pour la simulation de base (salles, actes, personnel, graphe)
CORE_SHEETS = frozenset({"Salles", "Ressources", "Actes", "Personnel", "Plan_Adjacence",
                          "Salle_Actes", "Salle_Ressources", "Acte_Ressources", "Personnel_Actes"})

# Feuille documentaire — chargée comme texte brut, pas comme données
_DOC_SHEET = "_LisezMoi"


# ── Valeurs YAML de référence pour la détection de conflits ────────────────
# Mises à jour si le YAML change — intentionnellement non lues depuis le YAML
# pour garder ce module indépendant (lecture séparée dans rapport()).
_YAML_REFERENCE = {
    "step_mesa_min":        10,     # YAML contraintes_systeme.horaires_simulation
    "fermeture":            "17h00",
    "ouverture":            "08h00",
}


@dataclass
class SheetReport:
    name: str
    rows: int
    columns: List[str]
    missing_required: List[str]
    is_core: bool
    status: str  # "ok" | "incomplete" | "empty" | "missing" | "doc"


@dataclass
class HdjExcelData:
    """
    Données structurées issues de HDJ_Agent_modele_donnees.xlsx.
    Toutes les feuilles sont accessibles comme DataFrames (attributs en snake_case).
    Les feuilles vides ou manquantes sont remplacées par un DataFrame vide avec
    les colonnes attendues, pour ne pas casser le code appelant.
    """

    # ── Nœuds ─────────────────────────────────────────────────────────────
    parametres:       Dict[str, str]   # {parametre: valeur}
    sites:            pd.DataFrame
    specialites:      pd.DataFrame
    unites:           pd.DataFrame
    hdj:              pd.DataFrame
    salles:           pd.DataFrame
    ressources:       pd.DataFrame
    actes:            pd.DataFrame
    personnel:        pd.DataFrame
    patients:         pd.DataFrame

    # ── Liens ─────────────────────────────────────────────────────────────
    salle_actes:      pd.DataFrame
    salle_ressources: pd.DataFrame
    acte_ressources:  pd.DataFrame
    acte_prerequis:   pd.DataFrame
    personnel_actes:  pd.DataFrame
    hdj_salles:       pd.DataFrame
    plan_adjacence:   pd.DataFrame

    # ── Dynamiques ────────────────────────────────────────────────────────
    sejours_mouvements: pd.DataFrame
    creneaux_template:  pd.DataFrame

    # ── Méta ──────────────────────────────────────────────────────────────
    source_path:    Path                = field(default_factory=Path)
    sheet_reports:  List[SheetReport]   = field(default_factory=list)
    warnings:       List[str]           = field(default_factory=list)

    # ─────────────────────────────────────────────────────────────────────
    # Accesseurs pratiques (jointures courantes pour les agents)
    # ─────────────────────────────────────────────────────────────────────

    def actes_pour_personnel(self, personnel_id: str) -> pd.DataFrame:
        """DataFrame des actes qu'un soignant peut réaliser (Personnel_Actes → Actes)."""
        ids = self.personnel_actes.loc[
            self.personnel_actes["personnel_id"] == personnel_id, "acte_id"
        ]
        return self.actes[self.actes["acte_id"].isin(ids)].copy()

    def ressources_pour_acte(self, acte_id: str) -> pd.DataFrame:
        """Ressources requises pour un acte + quantités (Acte_Ressources → Ressources)."""
        req = self.acte_ressources[self.acte_ressources["acte_id"] == acte_id]
        return req.merge(self.ressources, on="ressource_id", how="left")

    def prerequis_obligatoires(self, acte_id: str) -> pd.DataFrame:
        """Prérequis obligatoires d'un acte, triés par délai max croissant."""
        mask = (
            (self.acte_prerequis["acte_id"] == acte_id) &
            (self.acte_prerequis["obligatoire"].astype(str) == "1")
        )
        return self.acte_prerequis[mask].copy()

    def salles_pour_hdj(self, hdj_id: str) -> pd.DataFrame:
        """Salles composant un HDJ (HDJ_Salles → Salles)."""
        ids = self.hdj_salles.loc[self.hdj_salles["hdj_id"] == hdj_id, "salle_id"]
        return self.salles[self.salles["salle_id"].isin(ids)].copy()

    def ressources_limitantes_mvp(self) -> Dict[str, Tuple[str, int]]:
        """
        Retourne les ressources limitantes à modéliser pour le MVP.

        Format : {ressource_id: (ressource_libelle, quantite_max_sur_tous_salles)}

        Source : Salle_Ressources (quantité dans la salle la plus équipée).
        Compatible avec create_mvp_resources() de ressources_hdj.py.
        """
        if self.salle_ressources.empty:
            return {}
        agg = (
            self.salle_ressources
            .assign(quantite=lambda d: pd.to_numeric(d["quantite"], errors="coerce").fillna(0))
            .groupby("ressource_id")["quantite"]
            .max()
            .astype(int)
        )
        result: Dict[str, Tuple[str, int]] = {}
        for rid, qty in agg.items():
            libelle_series = self.ressources.loc[
                self.ressources["ressource_id"] == rid, "ressource_libelle"
            ]
            libelle = libelle_series.iloc[0] if not libelle_series.empty else rid
            result[rid] = (libelle, qty)
        return result

    def soignants_pour_mesa(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des soignants au format proche de
        configuration_simulation.soignants_demo (YAML).

        Champs retournés :
          nom, role (Excel), specialite_id, etp,
          heure_debut (float), heure_fin (float),
          actes (liste acte_id compétents)

        Note : le champ 'type_soignant' (clé YAML roles_soignants) n'est
        PAS dérivé automatiquement — la correspondance
          Excel role  → YAML type_soignant
        doit être définie par l'équipe métier dans hdj_metier.yaml.
        """
        configs: List[Dict[str, Any]] = []
        for _, row in self.personnel.iterrows():
            pid = row["personnel_id"]
            acte_ids = self.personnel_actes.loc[
                self.personnel_actes["personnel_id"] == pid, "acte_id"
            ].tolist()
            configs.append({
                "personnel_id":  pid,
                "nom":           str(row.get("nom", pid)),
                "role":          str(row.get("role", "")),
                "specialite_id": str(row.get("specialite_id", "")),
                "etp":           float(str(row.get("etp", "1.0")).replace(",", ".")),
                "heure_debut":   _parse_heure(str(row.get("dispo_debut", "8"))),
                "heure_fin":     _parse_heure(str(row.get("dispo_fin", "17"))),
                "jours_presence": str(row.get("jours_presence", "")),
                "actes":         acte_ids,
            })
        return configs

    def graphe_spatial(self):
        """
        Construit un DiGraph networkx depuis Plan_Adjacence.

        Nœuds : salle_id (depuis Salles + ACCUEIL implicite)
        Arêtes : (noeud_depart, noeud_arrivee, temps_trajet_min=X)

        Si bidirectionnel=1, ajoute l'arête inverse.
        Retourne None si networkx n'est pas disponible.
        """
        if not _NX_AVAILABLE:
            return None
        if self.plan_adjacence.empty:
            return None

        G = nx.DiGraph()
        # Ajouter tous les nœuds connus
        for _, row in self.salles.iterrows():
            G.add_node(row["salle_id"], **{
                "type":     str(row.get("type_salle", "unknown")),
                "capacite": int(str(row.get("capacite_max", 1))),
                "libelle":  str(row.get("salle_libelle", row["salle_id"])),
            })

        # Ajouter les arêtes
        for _, row in self.plan_adjacence.iterrows():
            src  = str(row["noeud_depart"])
            dst  = str(row["noeud_arrivee"])
            tmin = float(str(row.get("temps_trajet_min", 0)))
            bidi = str(row.get("bidirectionnel", "1")) == "1"
            G.add_edge(src, dst, temps_trajet_min=tmin)
            if bidi:
                G.add_edge(dst, src, temps_trajet_min=tmin)

        return G

    def parcours_depuis_sejour(self, num_sejour: str) -> List[Tuple[str, str, int]]:
        """
        Reconstruit le parcours Mesa d'un séjour depuis Sejours_Mouvements.

        Retourne [(salle_id, libelle_acte, duree_steps), ...] trié par heure_entree.
        duree_steps = duree_minutes_acte / 10 (1 step Mesa = 10 min).

        Note : salle déduite via Actes.type_salle_requis → Salle_Actes (première salle valide).
        """
        mvts = self.sejours_mouvements[
            self.sejours_mouvements["num_sejour"] == num_sejour
        ].copy()
        if mvts.empty:
            return []

        if "heure_entree" in mvts.columns:
            mvts = mvts.sort_values("heure_entree")

        parcours: List[Tuple[str, str, int]] = []
        for _, row in mvts.iterrows():
            acte_id = str(row.get("code_acte", ""))
            # Durée depuis Actes si disponible
            duree_min = 30  # fallback
            acte_row = self.actes[self.actes["acte_id"] == acte_id]
            if not acte_row.empty:
                try:
                    duree_min = int(float(str(acte_row.iloc[0]["duree_minutes"])))
                except (ValueError, TypeError):
                    pass
            duree_steps = max(1, duree_min // 10)
            # Salle : première salle pouvant réaliser cet acte
            salle_rows = self.salle_actes[self.salle_actes["acte_id"] == acte_id]
            salle_id = salle_rows.iloc[0]["salle_id"] if not salle_rows.empty else "ACCUEIL"
            libelle = str(row.get("libelle_acte", acte_id))
            parcours.append((salle_id, libelle, duree_steps))
        return parcours

    # ─────────────────────────────────────────────────────────────────────
    # Rapport
    # ─────────────────────────────────────────────────────────────────────

    def rapport(self) -> None:
        """Affiche un rapport structuré du chargement Excel."""
        sep = "═" * 70
        print(f"\n{sep}")
        print("  HDJ Agent — Rapport chargement Excel")
        print(f"  Source : {self.source_path.name}")
        print(sep)

        by_status: Dict[str, List[SheetReport]] = {}
        for r in self.sheet_reports:
            by_status.setdefault(r.status, []).append(r)

        counts = {
            "ok":         len(by_status.get("ok", [])),
            "incomplete": len(by_status.get("incomplete", [])),
            "empty":      len(by_status.get("empty", [])),
            "missing":    len(by_status.get("missing", [])),
            "doc":        len(by_status.get("doc", [])),
        }
        print(f"\n  Feuilles chargées OK : {counts['ok']:>3}")
        print(f"  Incomplètes          : {counts['incomplete']:>3}")
        print(f"  Vides                : {counts['empty']:>3}")
        print(f"  Documentaires        : {counts['doc']:>3}")
        if counts["missing"]:
            print(f"  Manquantes           : {counts['missing']:>3}  ← ATTENTION")

        sym_map = {"ok": "✓", "incomplete": "⚠", "empty": "○",
                   "missing": "✗", "doc": "─"}
        print(f"\n  {'':1} {'Feuille':<24} {'Statut':<12} {'Lignes':>6}  {'Colonnes manquantes'}")
        print(f"  {'─'*68}")
        for r in sorted(self.sheet_reports, key=lambda x: x.name.lower()):
            sym   = sym_map.get(r.status, "?")
            core  = "*" if r.is_core else " "
            miss  = ", ".join(r.missing_required) if r.missing_required else ""
            rows_ = str(r.rows) if r.rows >= 0 else "—"
            print(f"  {sym}{core} {r.name:<23} {r.status:<12} {rows_:>6}  {miss}")
        print("  (* = feuille clé pour la simulation de base)")

        # Paramètres simulation
        if self.parametres:
            print(f"\n  Paramètres simulation :")
            for k, v in self.parametres.items():
                print(f"    {k:<38} {v}")

        # Conflits avec YAML
        if self.warnings:
            print(f"\n  Conflits / avertissements :")
            for w in self.warnings:
                print(f"    ⚠  {w}")

        # Résumé agents
        print(f"\n  Données disponibles pour les agents :")
        print(f"    SoignantAgent   : {len(self.personnel)} soignants, "
              f"{len(self.personnel_actes)} compétences (Personnel_Actes)")
        print(f"    Salle           : {len(self.salles)} salles, "
              f"{len(self.salle_actes)} liens salle↔acte")
        print(f"    RessourceLimitante: {len(self.ressources)} ressources, "
              f"{len(self.salle_ressources)} dans salles")
        print(f"    CoordinateurAgent : {len(self.actes)} actes, "
              f"{len(self.acte_prerequis)} prérequis (DAG)")
        print(f"    Patient (Mesa)  : {len(self.patients)} patients master, "
              f"{len(self.sejours_mouvements)} mouvements PMSI")
        print(f"    Plan_Adjacence  : {len(self.plan_adjacence)} arêtes (graphe spatial)")

        print(f"\n{sep}\n")


# ── Fonction principale ────────────────────────────────────────────────────

def load_hdj_excel(path: "str | Path") -> HdjExcelData:
    """
    Charge HDJ_Agent_modele_donnees.xlsx et retourne un HdjExcelData.

    Valide la présence des colonnes obligatoires par feuille.
    Signale les conflits avec les valeurs de référence YAML connues.
    Les feuilles manquantes ou vides retournent un DataFrame vide (ne lève pas d'exception).

    Args:
        path: chemin vers le fichier Excel (.xlsx).

    Returns:
        HdjExcelData avec toutes les feuilles normalisées.

    Raises:
        FileNotFoundError: si le fichier Excel est introuvable.
        ValueError: si la dépendance openpyxl est manquante.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier Excel introuvable : {path}\n"
            "Vérifier que HDJ_Agent_modele_donnees.xlsx est dans le répertoire du projet."
        )

    try:
        all_sheets: Dict[str, pd.DataFrame] = pd.read_excel(
            path, sheet_name=None, dtype=str
        )
    except ImportError as e:
        raise ValueError(
            "openpyxl requis pour lire les fichiers .xlsx : pip install openpyxl"
        ) from e

    warnings: List[str] = []
    reports:  List[SheetReport] = []

    def _load(sheet_name: str) -> pd.DataFrame:
        """Charge une feuille, valide les colonnes, renvoie un DataFrame propre."""
        if sheet_name == _DOC_SHEET:
            reports.append(SheetReport(
                name=sheet_name, rows=-1, columns=[],
                missing_required=[], is_core=False, status="doc",
            ))
            return pd.DataFrame()

        if sheet_name not in all_sheets:
            reports.append(SheetReport(
                name=sheet_name, rows=0,
                columns=[], missing_required=list(REQUIRED_COLUMNS.get(sheet_name, [])),
                is_core=sheet_name in CORE_SHEETS, status="missing",
            ))
            return _empty_df(sheet_name)

        df = all_sheets[sheet_name].dropna(how="all")
        # Supprimer les lignes commentaires (première cellule commence par '#')
        if not df.empty and df.columns[0] in df.columns:
            first_col = df.iloc[:, 0].astype(str)
            df = df[~first_col.str.startswith("#")].reset_index(drop=True)

        # Normaliser les noms de colonnes
        df.columns = [str(c).strip() for c in df.columns]

        actual_cols   = list(df.columns)
        required      = REQUIRED_COLUMNS.get(sheet_name, [])
        missing       = [c for c in required if c not in actual_cols]
        n_rows        = len(df)

        if n_rows == 0:
            status = "empty"
        elif missing:
            status = "incomplete"
        else:
            status = "ok"

        reports.append(SheetReport(
            name=sheet_name, rows=n_rows, columns=actual_cols,
            missing_required=missing, is_core=sheet_name in CORE_SHEETS,
            status=status,
        ))
        return df

    def _empty_df(sheet_name: str) -> pd.DataFrame:
        cols = REQUIRED_COLUMNS.get(sheet_name, [])
        return pd.DataFrame(columns=cols)

    # ── Chargement de toutes les feuilles ──────────────────────────────────
    parametres_df       = _load("Parametres")
    sites               = _load("Sites")
    specialites         = _load("Specialites")
    unites              = _load("Unites")
    hdj                 = _load("HDJ")
    salles              = _load("Salles")
    ressources          = _load("Ressources")
    actes               = _load("Actes")
    personnel           = _load("Personnel")
    patients            = _load("Patients")
    salle_actes         = _load("Salle_Actes")
    salle_ressources    = _load("Salle_Ressources")
    acte_ressources     = _load("Acte_Ressources")
    acte_prerequis      = _load("Acte_Prerequis")
    personnel_actes     = _load("Personnel_Actes")
    hdj_salles          = _load("HDJ_Salles")
    plan_adjacence      = _load("Plan_Adjacence")
    sejours_mouvements  = _load("Sejours_Mouvements")
    creneaux_template   = _load("Creneaux_Template")
    _load(_DOC_SHEET)

    # ── Paramètres → dict key:value ────────────────────────────────────────
    parametres: Dict[str, str] = {}
    if not parametres_df.empty and "parametre" in parametres_df.columns:
        for _, row in parametres_df.iterrows():
            k = str(row.get("parametre", "")).strip()
            v = str(row.get("valeur", "")).strip()
            if k and k != "nan":
                parametres[k] = v

    # ── Détection conflits Excel ↔ YAML référence ──────────────────────────
    excel_granularite = parametres.get("granularite_temps", "")
    if excel_granularite and excel_granularite != "nan":
        try:
            if int(excel_granularite) != _YAML_REFERENCE["step_mesa_min"]:
                warnings.append(
                    f"granularite_temps Excel = {excel_granularite} min "
                    f"≠ step_mesa_min YAML = {_YAML_REFERENCE['step_mesa_min']} min "
                    f"→ à harmoniser dans hdj_metier.yaml §contraintes_systeme.horaires_simulation"
                )
        except ValueError:
            pass

    excel_fermeture = parametres.get("heure_fermeture_defaut", "")
    if excel_fermeture and excel_fermeture != "nan":
        fermeture_ref = _YAML_REFERENCE["fermeture"].replace("h", ":")
        if excel_fermeture != fermeture_ref:
            warnings.append(
                f"heure_fermeture_defaut Excel = {excel_fermeture} "
                f"≠ fermeture YAML = {_YAML_REFERENCE['fermeture']} "
                f"→ à harmoniser dans hdj_metier.yaml §contraintes_systeme.horaires_simulation"
            )

    # Séparateur liste_actes dans Sejours_Mouvements
    if not sejours_mouvements.empty:
        col = "liste_actes_codes"
        if col in sejours_mouvements.columns:
            sample = sejours_mouvements[col].dropna().head(3).tolist()
            has_semi  = any(";" in str(v) for v in sample)
            has_comma = any("," in str(v) for v in sample)
            if has_semi and not has_comma:
                warnings.append(
                    f"Sejours_Mouvements.liste_actes_codes utilise le séparateur ';' "
                    f"→ hdj_eligibility.py parse avec ',' "
                    f"(colonne LISTE ACTES CCAM MVT) — à normaliser lors du branchement"
                )

    return HdjExcelData(
        parametres=parametres,
        sites=sites,
        specialites=specialites,
        unites=unites,
        hdj=hdj,
        salles=salles,
        ressources=ressources,
        actes=actes,
        personnel=personnel,
        patients=patients,
        salle_actes=salle_actes,
        salle_ressources=salle_ressources,
        acte_ressources=acte_ressources,
        acte_prerequis=acte_prerequis,
        personnel_actes=personnel_actes,
        hdj_salles=hdj_salles,
        plan_adjacence=plan_adjacence,
        sejours_mouvements=sejours_mouvements,
        creneaux_template=creneaux_template,
        source_path=path,
        sheet_reports=reports,
        warnings=warnings,
    )


# ── Helpers internes ───────────────────────────────────────────────────────

def _parse_heure(val: str) -> float:
    """Convertit '08:00', '8h00', '08h00', '8' → float heures décimales."""
    s = val.strip().lower().replace("h", ":").replace("h00", ":00")
    parts = s.split(":")
    try:
        h = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 else 0.0
        return h + m / 60.0
    except (ValueError, IndexError):
        try:
            return float(val)
        except ValueError:
            return 8.0
