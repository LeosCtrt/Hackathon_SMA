"""
EnvironnementAgent — agent Mesa représentant les contraintes hospitalières globales.

Rôle dans l'architecture :
  hopital_model.py  → moteur Mesa : initialise, orchestre, avance l'horloge.
  environnement.py  → agent Mesa : porte l'état de l'environnement hospitalier.
  salle.py          → agent Mesa : espace physique (périmètre séparé).

Responsabilités de cet agent :
  - Horaires d'ouverture / pauses
  - Files d'attente globales par salle
  - Retards actifs et propagation
  - Indisponibilités temporaires (ressource ou soignant)
  - Événements environnementaux (panne, retard labo, bionettoyage)
  - Métriques globales de simulation

Chargement YAML :
  Lit core/config/hdj_metier.yaml §contraintes_systeme.horaires_simulation.
  Les valeurs marquées 'a_parametrer' dans le YAML → fallback technique neutre,
  documenté explicitement ci-dessous. Aucune valeur métier inventée.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import mesa

_YAML_PATH = Path(__file__).parent.parent / "config" / "hdj_metier.yaml"


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _parse_heure(val: Any) -> float:
    """Convertit '08h00', '8h00', 8.0 ou 8 en float (heures décimales)."""
    s = str(val).strip().lower().replace("h", ":")
    parts = s.split(":")
    try:
        h = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 else 0.0
        return h + m / 60.0
    except (ValueError, IndexError):
        return float(val)


def _parse_nullable_int(val: Any, fallback: Optional[int]) -> Optional[int]:
    """Retourne fallback si val est None ou 'a_parametrer'."""
    if val is None or str(val).strip().lower() == "a_parametrer":
        return fallback
    try:
        return int(val)
    except (ValueError, TypeError):
        return fallback


# ── Chargement config depuis YAML ─────────────────────────────────────────────

def _load_env_config(yaml_path: Path = _YAML_PATH) -> Dict[str, Any]:
    """
    Extrait les paramètres d'environnement depuis hdj_metier.yaml
    §contraintes_systeme.

    Valeurs a_parametrer dans le YAML → fallbacks techniques documentés :
      pauses              → []   (aucune pause configurée — à ajouter dans le YAML)
      turnover_min        → 0    (pas de délai de nettoyage simulé — à renseigner)
      seuil_abandon_steps → None (pas de timeout d'abandon — à renseigner)
    """
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Référentiel métier introuvable : {yaml_path}\n"
            "Vérifier que core/config/hdj_metier.yaml est présent dans le repo."
        )

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cs: Dict[str, Any] = config.get("contraintes_systeme", {})
    horaires: Dict[str, Any] = cs.get("horaires_simulation", {})

    return {
        # Horaires — source : [YAML] §contraintes_systeme.horaires_simulation
        "heure_ouverture": _parse_heure(horaires.get("ouverture", "08h00")),
        "heure_fermeture": _parse_heure(horaires.get("fermeture", "17h00")),
        "step_mesa_min": int(horaires.get("step_mesa_min", 10)),

        # Pauses — non définies dans hdj_metier.yaml → a_parametrer → liste vide
        # Pour ajouter une pause déjeuner : ajouter pauses: [[12.0, 13.0]] dans le YAML
        "pauses": [],

        # Turnover salle — [YAML] turnover_salle.duree_min: a_parametrer → 0 step
        "turnover_min": _parse_nullable_int(
            cs.get("turnover_salle", {}).get("duree_min"), fallback=0
        ),

        # Seuil abandon patient — [YAML] tolerance_abandon_patient.seuil_attente_min: a_parametrer
        "seuil_abandon_steps": _parse_nullable_int(
            cs.get("tolerance_abandon_patient", {}).get("seuil_attente_min"), fallback=None
        ),

        # Types de boucles rework documentés dans le YAML
        "rework_types": list(cs.get("rework_loops", {}).get("types") or []),

        # Deadline circuit court labo — [YAML] circuit_court_labo.deadline: "mi-journée"
        # Non parseable en heure précise → a_parametrer → None (pas de deadline active)
        "deadline_labo_heure": None,
    }


# ── Agent ──────────────────────────────────────────────────────────────────────

class EnvironnementAgent(mesa.Agent):
    """
    Agent Mesa représentant les contraintes hospitalières globales.

    N'est pas placé sur la grille spatiale (pas d'espace physique propre).
    Son step() est appelé en premier dans HopitalModel.step(),
    avant les agents patient et soignants.

    Interface principale pour les autres agents :
      est_ouvert(heure)             → bool
      en_pause(heure)               → bool
      est_disponible(resource_id)   → bool
      signaler_indisponible(id)
      restaurer_disponibilite(id)
      propager_retard(source_id, steps)
      ajouter_evenement(step, type, details)
      ajouter_en_file(salle_id, patient_id)
      retirer_de_file(salle_id)     → Optional[Any]
      longueur_file(salle_id)       → int
      rapport_metriques()           → str
    """

    def __init__(self, model: mesa.Model, yaml_path: Path = _YAML_PATH):
        super().__init__(model)

        cfg = _load_env_config(yaml_path)

        # ── Horaires (depuis YAML) ─────────────────────────────────────────
        self.heure_ouverture: float = cfg["heure_ouverture"]   # 8.0
        self.heure_fermeture: float = cfg["heure_fermeture"]   # 17.0
        self.step_mesa_min: int = cfg["step_mesa_min"]          # 10
        # Pauses : liste de (debut, fin) en heures décimales
        # a_parametrer dans le YAML → [] pour le MVP
        self.pauses: List[Tuple[float, float]] = cfg["pauses"]

        # ── Contraintes opérationnelles (depuis YAML) ──────────────────────
        # Durée de nettoyage entre patients — a_parametrer → 0 step (pas simulé)
        self.turnover_steps: int = (
            max(0, cfg["turnover_min"] // self.step_mesa_min)
            if cfg["turnover_min"] else 0
        )
        # Seuil d'abandon patient — a_parametrer → None (pas de timeout actif)
        self.seuil_abandon_steps: Optional[int] = cfg["seuil_abandon_steps"]
        # Deadline labo — a_parametrer → None (pas de contrainte active)
        self.deadline_labo_heure: Optional[float] = cfg["deadline_labo_heure"]
        # Types de rework documentés (informatif)
        self.rework_types: List[str] = cfg["rework_types"]

        # ── État dynamique ─────────────────────────────────────────────────
        # Files d'attente par salle : {salle_id: [patient_id, ...]}
        self.files_attente: Dict[str, List[Any]] = {}

        # Retards actifs : {resource_id: steps_restants}
        self.retards_actifs: Dict[str, int] = {}

        # Ressources / soignants temporairement indisponibles
        self.indisponibles: Set[str] = set()

        # File d'événements à déclencher : [{step, type, details}, ...]
        self._evenements_en_attente: List[Dict[str, Any]] = []
        # Historique des événements traités
        self.evenements_traites: List[Dict[str, Any]] = []

        # ── Métriques globales ─────────────────────────────────────────────
        self.metriques: Dict[str, Any] = {
            "steps_simules": 0,
            "evenements_traites": 0,
            "retards_propages": 0,
            "pics_file_attente": {},   # {salle_id: longueur_max}
        }

    # ── Horaires ──────────────────────────────────────────────────────────────

    def est_ouvert(self, heure: Optional[float] = None) -> bool:
        """True si l'HDJ est en heures d'ouverture."""
        h = heure if heure is not None else self.model.heure_actuelle
        return self.heure_ouverture <= h < self.heure_fermeture

    def en_pause(self, heure: Optional[float] = None) -> bool:
        """True si l'heure tombe dans une pause configurée."""
        h = heure if heure is not None else self.model.heure_actuelle
        return any(debut <= h < fin for debut, fin in self.pauses)

    def en_service(self, heure: Optional[float] = None) -> bool:
        """True si ouvert et hors pause."""
        return self.est_ouvert(heure) and not self.en_pause(heure)

    # ── Disponibilité ressources / soignants ──────────────────────────────────

    def est_disponible(self, resource_id: str) -> bool:
        """False si la ressource ou le soignant est marqué indisponible."""
        return resource_id not in self.indisponibles

    def signaler_indisponible(self, resource_id: str) -> None:
        """Marque une ressource ou un soignant comme temporairement indisponible."""
        self.indisponibles.add(resource_id)

    def restaurer_disponibilite(self, resource_id: str) -> None:
        """Remet une ressource ou un soignant en disponibilité."""
        self.indisponibles.discard(resource_id)

    # ── Retards ───────────────────────────────────────────────────────────────

    def propager_retard(self, source_id: str, steps: int) -> None:
        """
        Enregistre un retard propagé depuis source_id.
        Exemple : retard labo → retard consultation endocrinologue.
        """
        self.retards_actifs[source_id] = self.retards_actifs.get(source_id, 0) + steps
        self.metriques["retards_propages"] += 1

    def retard_restant(self, source_id: str) -> int:
        """Steps de retard restants pour une source donnée (0 si aucun)."""
        return self.retards_actifs.get(source_id, 0)

    # ── Files d'attente ───────────────────────────────────────────────────────

    def ajouter_en_file(self, salle_id: str, patient_id: Any) -> None:
        """Ajoute un patient à la file d'attente d'une salle."""
        self.files_attente.setdefault(salle_id, []).append(patient_id)
        longueur = len(self.files_attente[salle_id])
        pic = self.metriques["pics_file_attente"]
        if longueur > pic.get(salle_id, 0):
            pic[salle_id] = longueur

    def retirer_de_file(self, salle_id: str) -> Optional[Any]:
        """Retire et retourne le premier patient de la file (FIFO). None si vide."""
        file = self.files_attente.get(salle_id, [])
        return file.pop(0) if file else None

    def longueur_file(self, salle_id: str) -> int:
        """Nombre de patients en attente dans la file d'une salle."""
        return len(self.files_attente.get(salle_id, []))

    # ── Événements ────────────────────────────────────────────────────────────

    def ajouter_evenement(
        self, step_declenchement: int, type_evt: str, details: str = ""
    ) -> None:
        """
        Planifie un événement environnemental.

        Types reconnus :
          "panne"  → signaler_indisponible(details)
          "retour" → restaurer_disponibilite(details)
          "retard" → propager_retard(details, steps=1)

        Pour tout autre type, l'événement est enregistré sans effet automatique.
        """
        self._evenements_en_attente.append({
            "step": step_declenchement,
            "type": type_evt,
            "details": details,
        })

    def _traiter_evenement(self, evt: Dict[str, Any]) -> None:
        t = evt.get("type", "")
        d = evt.get("details", "")
        if t == "panne":
            self.signaler_indisponible(d)
        elif t == "retour":
            self.restaurer_disponibilite(d)
        elif t == "retard":
            self.propager_retard(d, steps=1)

    # ── Step ──────────────────────────────────────────────────────────────────

    def step(self) -> None:
        """
        Appelé en premier dans HopitalModel.step(), avant patient et soignants.

        Actions :
          1. Déclenche les événements planifiés dont le step est atteint.
          2. Décrémente les retards actifs.
          3. Met à jour les métriques.
        """
        step_courant = self.model.steps

        # Déclencher les événements arrivés à échéance
        restants = []
        for evt in self._evenements_en_attente:
            if evt["step"] <= step_courant:
                self._traiter_evenement(evt)
                self.evenements_traites.append(evt)
                self.metriques["evenements_traites"] += 1
            else:
                restants.append(evt)
        self._evenements_en_attente = restants

        # Décrémenter les retards actifs
        for rid in list(self.retards_actifs):
            self.retards_actifs[rid] -= 1
            if self.retards_actifs[rid] <= 0:
                del self.retards_actifs[rid]

        self.metriques["steps_simules"] += 1

    # ── Rapport ───────────────────────────────────────────────────────────────

    def rapport_metriques(self) -> str:
        """Retourne un résumé lisible de l'état de l'environnement."""
        h = self.model.heure_actuelle
        lignes = [
            "=== EnvironnementAgent — état ===",
            f"  Heure actuelle    : {h:.2f}h",
            f"  Ouvert            : {self.est_ouvert(h)}",
            f"  En pause          : {self.en_pause(h)}",
            f"  Steps simulés     : {self.metriques['steps_simules']}",
            f"  Événements traités: {self.metriques['evenements_traites']}",
            f"  Retards propagés  : {self.metriques['retards_propages']}",
        ]
        if self.retards_actifs:
            lignes.append(f"  Retards actifs    : {self.retards_actifs}")
        if self.indisponibles:
            lignes.append(f"  Indisponibles     : {self.indisponibles}")
        if self.files_attente:
            lignes.append(f"  Files d'attente   : {self.files_attente}")
        pics = self.metriques["pics_file_attente"]
        if pics:
            lignes.append(f"  Pics file attente : {pics}")
        return "\n".join(lignes)
