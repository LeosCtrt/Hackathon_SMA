"""
SoignantAgent — agent Mesa générique regroupant tous les rôles soignants HDJ.

Paramètres chargés depuis core/config/hdj_metier.yaml §roles_soignants.
self.role est dérivé de role_legacy pour rétrocompatibilité avec demo_parcours.py
(s.role == "Med" / "Paramed" utilisé pour la couleur des marqueurs).
"""

import yaml
from pathlib import Path
from mesa import Agent
from typing import Any, Dict, List

# 1 step Mesa = 10 min — source : hopital_model.py (heure_actuelle += 10/60)
_STEP_DURATION_MIN = 10

_YAML_PATH = Path(__file__).parent.parent / "config" / "hdj_metier.yaml"


def _load_role_params(yaml_path: Path = _YAML_PATH) -> Dict[str, Dict[str, Any]]:
    """
    Charge les paramètres des rôles soignants depuis §roles_soignants du YAML métier.

    Conversions appliquées :
      duree_acte_min (min)      → duree_acte_steps (steps de 10 min)
      delai_dilatation_min (min)→ delai_dilatation (steps de 10 min)

    Valeurs absentes ou marquées 'a_parametrer' dans le YAML :
      duree_acte_min    → 1 step (minimum technique — pas une valeur médicale,
                          à renseigner dans hdj_metier.yaml §roles_soignants)
      delai_dilatation  → 0 step (pas de délai)
    """
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Référentiel métier introuvable : {yaml_path}\n"
            "Vérifier que core/config/hdj_metier.yaml est présent dans le repo."
        )

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    raw_roles: Dict[str, Any] = config.get("roles_soignants", {})
    if not raw_roles:
        raise ValueError("hdj_metier.yaml : section 'roles_soignants' absente ou vide.")

    params: Dict[str, Dict[str, Any]] = {}
    for role_name, raw in raw_roles.items():
        # duree_acte_min → steps
        duree_raw = raw.get("duree_acte_min")
        if duree_raw is None or str(duree_raw).strip().lower() == "a_parametrer":
            duree_steps = 1  # fallback technique minimal — valeur médicale absente du YAML
        else:
            duree_steps = max(1, int(duree_raw) // _STEP_DURATION_MIN)

        # delai_dilatation_min → steps (30 min ophtalmo → 3 steps)
        delai_raw = raw.get("delai_dilatation_min", 0)
        if delai_raw is None or str(delai_raw).strip().lower() == "a_parametrer":
            delai_steps = 0
        else:
            delai_steps = max(0, int(delai_raw) // _STEP_DURATION_MIN)

        params[role_name] = {
            "role": str(raw.get("role_legacy", "Paramed")),
            "duree_acte_steps": duree_steps,
            "taches": list(raw.get("taches") or []),
            "dependances_amont": list(raw.get("dependances_amont") or []),
            "delai_dilatation": delai_steps,
            "vacation_only": bool(raw.get("vacation_only", False)),
        }

    return params


# Chargé une fois à l'import du module
PARAMS_PAR_ROLE: Dict[str, Dict[str, Any]] = _load_role_params()


class SoignantAgent(Agent):
    """
    Soignant HDJ — IDE, endocrinologue, ophtalmologue ou diététicienne.

    Paramètres
    ----------
    model         : HopitalModel
    nom           : str    nom d'affichage
    type_soignant : str    rôle défini dans hdj_metier.yaml §roles_soignants
    salle         : str    nœud du graphe où le soignant est posé
    heure_debut   : float  début de service (heures)
    heure_fin     : float  fin de service (heures)
    """

    def __init__(
        self,
        model,
        nom: str,
        type_soignant: str,
        salle: str,
        heure_debut: float = 0,
        heure_fin: float = 24,
    ):
        super().__init__(model)

        if type_soignant not in PARAMS_PAR_ROLE:
            raise ValueError(
                f"type_soignant '{type_soignant}' inconnu — "
                f"valeurs acceptées (depuis hdj_metier.yaml) : {list(PARAMS_PAR_ROLE)}"
            )

        p = PARAMS_PAR_ROLE[type_soignant]

        self.nom = nom
        self.type_soignant = type_soignant
        self.role: str = p["role"]          # "Med"/"Paramed" — rétrocompat demo_parcours.py
        self.salle = salle
        self.heure_debut = heure_debut
        self.heure_fin = heure_fin

        # Paramètres métier chargés depuis hdj_metier.yaml §roles_soignants
        self.duree_acte_steps: int = p["duree_acte_steps"]
        self.taches: List[str] = p["taches"]
        self.dependances_amont: List[str] = p["dependances_amont"]
        self.delai_dilatation: int = p["delai_dilatation"]
        self.vacation_only: bool = p["vacation_only"]

        # État courant
        self.patient_actuel = None
        self.temps_soin_restant: int = 0

    def step(self):
        # ── Vérification des horaires ──────────────────────────────────────
        if (self.model.heure_actuelle < self.heure_debut
                or self.model.heure_actuelle >= self.heure_fin):
            return

        # ── Soin en cours : décrémenter le timer ───────────────────────────
        if self.patient_actuel is not None:
            self.temps_soin_restant -= 1
            if self.temps_soin_restant <= 0:
                print(
                    f"[{self.type_soignant} {self.nom}] Termine avec "
                    f"le patient {self.patient_actuel.unique_id}."
                )
                if hasattr(self.model, "notifier_fin_prestation"):
                    self.model.notifier_fin_prestation(self, self.patient_actuel)
                else:
                    self.patient_actuel.nb_interactions += 1
                self.patient_actuel = None

        # ── Cherche un patient en attente dans sa salle ────────────────────
        if self.patient_actuel is None:
            nouveau = self.model.fournir_patient(self)
            if nouveau is not None:
                self.patient_actuel = nouveau
                self.patient_actuel.etat = "SOIN"
                # Durée depuis le parcours patient ; fallback sur la durée par rôle (YAML)
                self.temps_soin_restant = (
                    nouveau.temps_soin_actuel
                    if nouveau.temps_soin_actuel > 0
                    else self.duree_acte_steps
                )
                print(
                    f"[{self.type_soignant} {self.nom}] Débute avec "
                    f"le patient {nouveau.unique_id}."
                )
                self.model.notifier_debut_prestation(self, nouveau)
