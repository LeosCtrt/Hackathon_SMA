"""
Ressources limitantes HDJ — chargées depuis core/config/hdj_metier.yaml.

MVP : 2 ressources (§ressources_hdj.mvp_ressources_goulot) :
  - retinographe_001 : rétinographe non mydriatique, quantite et nom lus depuis YAML
  - fauteuil_medicalise : fauteuils médicalisés, quantite et nom lus depuis YAML

Interface publique inchangée : create_mvp_resources() retourne
{"retinographe": ..., "fauteuil": ...} — clés stables pour CoordinateurAgent.

Les ~20 autres équipements du YAML (ECG, IPS, moniteurs, chariot urgence, etc.)
sont ignorés pour ce MVP. Ils peuvent être ajoutés en instanciant RessourceLimitante
avec les paramètres correspondants.
"""

import yaml
from pathlib import Path
from typing import Dict

_YAML_PATH = Path(__file__).parent.parent / "config" / "hdj_metier.yaml"


class RessourceLimitante:
    """
    Ressource avec capacité finie pouvant créer attente ou saturation.

    Le temps est découpé en créneaux globaux (day * slots_per_day + slot).
    L'occupation est tracée par créneau global pour permettre le calcul du
    taux d'occupation et du pic d'utilisation simultanée.
    """

    def __init__(self, name: str, total_units: int):
        self.name = name
        self.total_units = total_units
        # _occ[global_slot] = nb d'unités occupées à ce créneau
        self._occ: Dict[int, int] = {}
        self._total_usage_slots = 0  # somme des créneaux occupés (toutes unités)

    def available_at(self, global_slot: int, duration_slots: int) -> bool:
        """True si au moins une unité libre sur toute la durée demandée."""
        for s in range(global_slot, global_slot + duration_slots):
            if self._occ.get(s, 0) >= self.total_units:
                return False
        return True

    def occupy(self, global_slot: int, duration_slots: int) -> None:
        """Réserve une unité sur les créneaux demandés."""
        for s in range(global_slot, global_slot + duration_slots):
            self._occ[s] = self._occ.get(s, 0) + 1
        self._total_usage_slots += duration_slots

    def occupancy_rate(self, total_slots_in_horizon: int) -> float:
        """Taux d'occupation global sur l'horizon simulé [0.0 → 1.0]."""
        if total_slots_in_horizon == 0 or self.total_units == 0:
            return 0.0
        capacity = total_slots_in_horizon * self.total_units
        return min(self._total_usage_slots / capacity, 1.0)

    def peak_simultaneous(self) -> int:
        """Nombre max d'unités simultanément occupées sur l'horizon."""
        return max(self._occ.values(), default=0)

    def __repr__(self) -> str:
        return f"RessourceLimitante('{self.name}', units={self.total_units})"


def create_mvp_resources() -> Dict[str, RessourceLimitante]:
    """
    Instancie les deux ressources MVP depuis YAML §ressources_hdj.mvp_ressources_goulot.

    Clés retournées (stables) : "retinographe" et "fauteuil".
    Nom et quantité chargés depuis le YAML — aucune valeur hardcodée.
    """
    with open(_YAML_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    mvp = cfg["ressources_hdj"]["mvp_ressources_goulot"]
    retino   = mvp["retinographe"]
    fauteuil = mvp["fauteuil_medicalise"]
    return {
        "retinographe": RessourceLimitante(
            name=f"{retino['nom']} (×{retino['quantite']})",
            total_units=int(retino["quantite"]),
        ),
        "fauteuil": RessourceLimitante(
            name=f"{fauteuil['nom']} (×{fauteuil['quantite']})",
            total_units=int(fauteuil["quantite"]),
        ),
    }
