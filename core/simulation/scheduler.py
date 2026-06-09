"""
Scheduler créneaux horaires pour l'HDJ endocrino.

Hypothèses documentées (non issues de données réelles — à valider équipe médicale) :
  - Horaires HDJ     : 8h00 – 17h00
  - Granularité      : créneaux de 30 minutes → 18 créneaux / jour
  - Capacité salle   : MAX_PARALLEL patients simultanés (défaut = 6)
  - Horizon          : N_DAYS jours ouvrés (défaut = 5)
  - Replanification  : si aucun créneau J, essai J+1 … jusqu'à J+N_DAYS-1
  - Au-delà horizon  : patient marqué non planifié (non replanifié automatiquement)

Les ressources (rétinographe, fauteuil) sont vérifiées SIMULTANÉMENT à la capacité
salle conformément à la règle R001 du YAML §simulation_rules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.resources.ressources_hdj import RessourceLimitante

SLOT_DURATION_MIN = 30
SLOTS_PER_DAY = 18         # 8h00 → 17h00 = 9 h = 18 créneaux de 30 min
DEFAULT_N_DAYS = 5
DEFAULT_MAX_PARALLEL = 6   # places HDJ simultanées (hypothèse documentée)


@dataclass
class ScheduledEntry:
    patient_id: str
    day: int                      # 0-indexé
    slot: int                     # 0 = 8h00, 1 = 8h30, …
    duration_slots: int
    required_resources: List[str]
    eligibility_decision: str
    wait_days: int = 0            # jours d'attente par rapport au premier jour demandé

    @property
    def start_label(self) -> str:
        total_min = self.slot * SLOT_DURATION_MIN
        h = 8 + total_min // 60
        m = total_min % 60
        return f"J{self.day + 1} {h:02d}h{m:02d}"

    @property
    def end_label(self) -> str:
        total_min = (self.slot + self.duration_slots) * SLOT_DURATION_MIN
        h = 8 + total_min // 60
        m = total_min % 60
        return f"{h:02d}h{m:02d}"


@dataclass
class UnscheduledEntry:
    patient_id: str
    reason: str
    required_resources: List[str]
    eligibility_decision: str


class Scheduler:
    """
    Planificateur de créneaux HDJ avec vérification des ressources limitantes.

    Algorithme : greedy first-fit (premier créneau disponible sur l'horizon).
    Suffisant pour le MVP datathon ; un algorithme d'optimisation (OR-Tools)
    pourrait remplacer le greedy en production.
    """

    def __init__(
        self,
        resources: Dict[str, RessourceLimitante],
        n_days: int = DEFAULT_N_DAYS,
        max_parallel: int = DEFAULT_MAX_PARALLEL,
    ):
        self.resources = resources
        self.n_days = n_days
        self.max_parallel = max_parallel
        # _cap[day][slot] = nombre de patients simultanément planifiés
        self._cap: List[List[int]] = [
            [0] * SLOTS_PER_DAY for _ in range(n_days)
        ]
        self.scheduled: List[ScheduledEntry] = []
        self.unscheduled: List[UnscheduledEntry] = []

    def total_slots(self) -> int:
        return self.n_days * SLOTS_PER_DAY

    def _global(self, day: int, slot: int) -> int:
        return day * SLOTS_PER_DAY + slot

    def _capacity_ok(self, day: int, slot: int, duration_slots: int) -> bool:
        """Vérifie que la salle HDJ n'est pas saturée sur la durée."""
        end = min(slot + duration_slots, SLOTS_PER_DAY)
        return all(self._cap[day][s] < self.max_parallel for s in range(slot, end))

    def _resources_ok(self, day: int, slot: int, duration_slots: int,
                      required: List[str]) -> bool:
        """Vérifie que toutes les ressources requises sont disponibles.

        Source: YAML §simulation_rules R001 — allocation selon équipement requis.
        """
        g = self._global(day, slot)
        return all(
            self.resources[r].available_at(g, duration_slots)
            for r in required
            if r in self.resources
        )

    def _find_slot(
        self, duration_slots: int, required: List[str], start_day: int
    ) -> Optional[Tuple[int, int]]:
        """Premier créneau disponible (capacité + ressources) dès start_day."""
        for day in range(start_day, self.n_days):
            for slot in range(SLOTS_PER_DAY - duration_slots + 1):
                if self._capacity_ok(day, slot, duration_slots) and \
                   self._resources_ok(day, slot, duration_slots, required):
                    return day, slot
        return None

    def _book(self, day: int, slot: int, duration_slots: int,
              required: List[str]) -> None:
        """Réserve le créneau et les ressources."""
        end = min(slot + duration_slots, SLOTS_PER_DAY)
        for s in range(slot, end):
            self._cap[day][s] += 1
        g = self._global(day, slot)
        for r in required:
            if r in self.resources:
                self.resources[r].occupy(g, duration_slots)

    def assign(
        self,
        patient_id: str,
        duration_min: int,
        required_resources: List[str],
        eligibility_decision: str,
        preferred_day: int = 0,
    ) -> bool:
        """
        Tente de planifier un patient.

        Si aucun créneau disponible sur l'horizon → ajouté à unscheduled.
        Returns True si planifié, False sinon.
        """
        duration_slots = max(1, duration_min // SLOT_DURATION_MIN)
        result = self._find_slot(duration_slots, required_resources, preferred_day)

        if result is None:
            self.unscheduled.append(UnscheduledEntry(
                patient_id=patient_id,
                reason=(
                    f"Aucun créneau disponible sur {self.n_days} jours "
                    f"(ressources requises : {required_resources or ['aucune']})"
                ),
                required_resources=required_resources,
                eligibility_decision=eligibility_decision,
            ))
            return False

        day, slot = result
        self._book(day, slot, duration_slots, required_resources)
        self.scheduled.append(ScheduledEntry(
            patient_id=patient_id,
            day=day,
            slot=slot,
            duration_slots=duration_slots,
            required_resources=required_resources,
            eligibility_decision=eligibility_decision,
            wait_days=day - preferred_day,
        ))
        return True
