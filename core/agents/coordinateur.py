"""
AgentCoordinateur — Ordonnanceur HDJ endocrino-diabétologie, scénarios A et B.

Rôle (source: Défi 5 HDJ Agent, ELBAHRI/BELIN/CARTIER, CHU Guyane) :
  Analyse chaque séjour selon deux scénarios orthogonaux :

  SCÉNARIO A — Garde-fou PMSI / réglementaire
    Planifie uniquement les séjours avec une référence PMSI solide disponible
    (unité HDJ existante ou acte CCAM documenté dans le YAML + MCO §1.1/§1.5).
    Objectif : ne pas surestimer la facturation GHS réelle.

  SCÉNARIO B — Cible de réorganisation HDJ (simulation pitch)
    Planifie les candidats high_hdj_candidate et medium_hdj_candidate même
    sans validation PMSI complète. Tous les cas planifiés en B mais non validés
    PMSI portent le flag pmsi_validation_required=True.
    Objectif : montrer quel flux peut être absorbé par un HDJ structuré.
    Pitch : "L'activité endocrino-diabéto actuelle est dispersée dans les urgences /
    consultations ; l'agent détecte les parcours candidats à une structuration en HDJ
    et simule leur planification dans un scénario cible avec ressources limitées."

  Les deux schedulers sont indépendants (ressources séparées).

Conception :
  - Classe Python autonome (pas de dépendance Mesa dans ce module)
    → peut être enveloppée dans un mesa.Agent pour s'intégrer au modèle
      HopitalModel de plan_hdj_complet_balade.ipynb en post-MVP
  - Séparation claire : règles (hdj_eligibility) / ressources / scheduling / agent

Fichier existant NON modifié :
  core/agents/soignant.py — contient un bug ligne 24 (variable `nouveau_patient`
  référencée dans le bloc "fin de soin" avant sa définition). Non corrigé ici.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from core.rules.hdj_eligibility import EligibilityResult, is_hdj_eligible
from core.resources.ressources_hdj import RessourceLimitante, create_mvp_resources
from core.simulation.scheduler import (
    Scheduler, ScheduledEntry, UnscheduledEntry,
    DEFAULT_N_DAYS, DEFAULT_MAX_PARALLEL, SLOT_DURATION_MIN,
)


@dataclass
class PatientRecord:
    patient_id: str
    row_data: Dict[str, Any]
    eligibility: Optional[EligibilityResult] = None
    # Scénario A
    scheduled_entry_A: Optional[ScheduledEntry] = None
    scheduling_status_A: str = "not_determined"
    # scheduled | requires_review | uncertain | not_applicable
    # Scénario B
    scheduled_entry_B: Optional[ScheduledEntry] = None
    scheduling_status_B: str = "not_determined"
    # scheduled | requires_review_b | low_candidate | not_applicable


@dataclass
class KpisA:
    """KPIs Scénario A — garde-fou PMSI."""
    not_applicable: int = 0        # not_hdj_relevant
    already_hdj: int = 0           # already_hdj (planifiés)
    convertible: int = 0           # convertible_to_hdj (planifiés)
    requires_review: int = 0       # convertible_to_hdj_requires_review
    candidate_pmsi_validation: int = 0  # candidate_hdj_requires_pmsi_validation (non planifié A)
    uncertain: int = 0             # uncertain_requires_human_review (jamais planifié)
    scheduled: int = 0
    not_scheduled: int = 0         # already_hdj/convertible sans créneau
    wait_days: List[int] = field(default_factory=list)

    @property
    def avg_wait_days(self) -> float:
        return sum(self.wait_days) / len(self.wait_days) if self.wait_days else 0.0


@dataclass
class KpisB:
    """KPIs Scénario B — cible de réorganisation HDJ."""
    scheduled: int = 0             # simulated_in_target_hdj_pending_validation
    not_scheduled: int = 0         # candidat B mais aucun créneau disponible
    low_candidate: int = 0         # low_candidate_not_simulated
    requires_human_review: int = 0 # requires_human_review_before_simulation (uncertain)
    pmsi_validation_required: int = 0  # parmi scheduled B
    gain_vs_a: int = 0             # scheduled_B - scheduled_A
    wait_days: List[int] = field(default_factory=list)
    by_pathway: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def avg_wait_days(self) -> float:
        return sum(self.wait_days) / len(self.wait_days) if self.wait_days else 0.0


class CoordinateurAgent:
    """
    Agent coordinateur/ordonnanceur HDJ endocrino — deux scénarios.

    Cycle :
      1. load_data(df)    — ingestion
      2. run()            — éligibilité → scheduling A → scheduling B → KPIs
      3. print_dashboard() — tableau de bord A + B
    """

    def __init__(self, n_days: int = DEFAULT_N_DAYS, max_parallel: int = DEFAULT_MAX_PARALLEL):
        # Deux schedulers INDÉPENDANTS — ressources séparées entre les deux simulations
        self.resources_A: Dict[str, RessourceLimitante] = create_mvp_resources()
        self.resources_B: Dict[str, RessourceLimitante] = create_mvp_resources()
        self.scheduler_A = Scheduler(self.resources_A, n_days=n_days, max_parallel=max_parallel)
        self.scheduler_B = Scheduler(self.resources_B, n_days=n_days, max_parallel=max_parallel)
        self.patients: List[PatientRecord] = []
        self.kpis_A = KpisA()
        self.kpis_B = KpisB()
        self.total = 0

    # ── Chargement ─────────────────────────────────────────────────────────

    def load_data(self, df: pd.DataFrame) -> None:
        for idx, row in df.iterrows():
            pid = str(row.get("NUM SEJOUR", f"SEJ_{idx}"))[:20]
            self.patients.append(PatientRecord(patient_id=pid, row_data=row.to_dict()))
        self.total = len(self.patients)

    # ── Exécution ──────────────────────────────────────────────────────────

    def run(self) -> None:
        """Éligibilité → scheduling A (PMSI) → scheduling B (réorganisation) → KPIs."""
        for record in self.patients:
            record.eligibility = is_hdj_eligible(record.row_data)
            self._schedule_A(record)
            self._schedule_B(record)

        # Calcul gain B vs A
        self.kpis_B.gain_vs_a = self.kpis_B.scheduled - self.kpis_A.scheduled

    def _schedule_A(self, record: PatientRecord) -> None:
        """
        Scénario A — garde-fou PMSI.
        Planifie : already_hdj + convertible_to_hdj uniquement.
        """
        el = record.eligibility
        pot = el.hdj_potential

        if pot == "not_hdj_relevant":
            self.kpis_A.not_applicable += 1
            record.scheduling_status_A = "not_applicable"
            return

        if pot in ("already_hdj", "convertible_to_hdj"):
            if pot == "already_hdj":
                self.kpis_A.already_hdj += 1
            else:
                self.kpis_A.convertible += 1
            ok = self.scheduler_A.assign(
                patient_id=record.patient_id,
                duration_min=el.estimated_duration_min,
                required_resources=el.required_resources,
                eligibility_decision=pot,
            )
            if ok:
                self.kpis_A.scheduled += 1
                record.scheduled_entry_A = self.scheduler_A.scheduled[-1]
                self.kpis_A.wait_days.append(record.scheduled_entry_A.wait_days)
                record.scheduling_status_A = "scheduled"
            else:
                self.kpis_A.not_scheduled += 1
                record.scheduling_status_A = "requires_review"
            return

        if pot == "convertible_to_hdj_requires_review":
            self.kpis_A.requires_review += 1
            record.scheduling_status_A = "requires_review"
            self.scheduler_A.unscheduled.append(UnscheduledEntry(
                patient_id=record.patient_id,
                reason="requires_review A — Instruction Gradation manquante",
                required_resources=el.required_resources,
                eligibility_decision=pot,
            ))
            return

        if pot == "candidate_hdj_requires_pmsi_validation":
            # Candidat organisationnel B avec pathway identifié.
            # Non planifié en A : Instruction Gradation manquante.
            # Planifié en B via _schedule_B si reorganization_potential=medium.
            self.kpis_A.candidate_pmsi_validation += 1
            record.scheduling_status_A = "not_scheduled_pending_pmsi_validation"
            return

        if pot == "uncertain_requires_human_review":
            # Signal faible — vraiment incertain. Jamais planifié en A ni en B.
            self.kpis_A.uncertain += 1
            record.scheduling_status_A = "uncertain"
            self.scheduler_A.unscheduled.append(UnscheduledEntry(
                patient_id=record.patient_id,
                reason="uncertain A — critères GHS Gradation manquants",
                required_resources=[],
                eligibility_decision=pot,
            ))

    def _schedule_B(self, record: PatientRecord) -> None:
        """
        Scénario B — réorganisation HDJ cible.

        Règles :
          - uncertain_requires_human_review  → jamais simulé en B (signal faible)
          - reorganization_potential = none  → not_applicable
          - reorganization_potential = low   → low_candidate_not_simulated
          - reorganization_potential = high/medium → simulé avec pmsi_validation_required

        Labels scheduling_B :
          simulated_in_target_hdj_pending_validation  — candidat planifié, PMSI à valider
          requires_human_review_before_simulation     — vraiment incertain, non simulé
          low_candidate_not_simulated                 — signal faible, non simulé
          not_applicable                              — hors périmètre
          no_slot_available_b                         — candidat mais horizon plein
        """
        el = record.eligibility
        reorg = el.reorganization_potential
        pathway = el.candidate_pathway

        # Garde-fou : uncertain = jamais simulé en B, quelle que soit la valeur de reorg
        if el.hdj_potential == "uncertain_requires_human_review":
            self.kpis_B.requires_human_review += 1
            record.scheduling_status_B = "requires_human_review_before_simulation"
            return

        if reorg == "none":
            record.scheduling_status_B = "not_applicable"
            return

        if reorg == "low":
            self.kpis_B.low_candidate += 1
            record.scheduling_status_B = "low_candidate_not_simulated"
            return

        # high ou medium → candidat organisationnel B
        ok = self.scheduler_B.assign(
            patient_id=record.patient_id,
            duration_min=el.estimated_duration_min,
            required_resources=el.required_resources,
            eligibility_decision=f"B:{pathway}",
        )
        if ok:
            self.kpis_B.scheduled += 1
            record.scheduled_entry_B = self.scheduler_B.scheduled[-1]
            self.kpis_B.wait_days.append(record.scheduled_entry_B.wait_days)
            record.scheduling_status_B = "simulated_in_target_hdj_pending_validation"
            self.kpis_B.by_pathway[pathway] += 1
            if el.pmsi_validation_required:
                self.kpis_B.pmsi_validation_required += 1
        else:
            self.kpis_B.not_scheduled += 1
            record.scheduling_status_B = "no_slot_available_b"

    # ── Tableau de bord ────────────────────────────────────────────────────

    def print_dashboard(self) -> None:
        ts_A = self.scheduler_A.total_slots()
        ts_B = self.scheduler_B.total_slots()
        ret_A = self.resources_A["retinographe"]
        fau_A = self.resources_A["fauteuil"]
        ret_B = self.resources_B["retinographe"]
        fau_B = self.resources_B["fauteuil"]

        sep = "═" * 68
        print(f"\n{sep}")
        print("  TABLEAU DE BORD — HDJ Agent Coordinateur v3 (scénarios A/B)")
        print("  CHU Guyane — Simulation restructuration ambulatoire endocrino")
        print(sep)
        print(f"  Total séjours analysés : {self.total}")

        # ── Scénario A ──────────────────────────────────────────────────────
        print(f"\n  {'─'*64}")
        print("  SCÉNARIO A — Garde-fou PMSI / réglementaire")
        print(f"  {'─'*64}")
        print(f"  {'Hors périmètre endocrino HDJ':<50} {self.kpis_A.not_applicable:>5}")
        print(f"  {'Déjà structuré HDJ  [official_hdj]':<50} {self.kpis_A.already_hdj:>5}")
        print(f"  {'Convertible PMSI  [pmsi_reference_available]':<50} {self.kpis_A.convertible:>5}")
        print(f"  {'Requires review  [Gradation manquante]':<50} {self.kpis_A.requires_review:>5}")
        print(f"  {'Candidat PMSI  [pathway+dosage, non planifié A]':<50} {self.kpis_A.candidate_pmsi_validation:>5}")
        print(f"  {'Uncertain  [signal faible, jamais simulé]':<50} {self.kpis_A.uncertain:>5}")
        print(f"  {'── PLANIFIÉS A':<50} {self.kpis_A.scheduled:>5}")
        print(f"  {'Non planifiés (horizon plein)':<44} {self.kpis_A.not_scheduled:>5}")
        print(f"  {'Délai attente moyen (j)':<44} {self.kpis_A.avg_wait_days:>5.1f}")
        print(f"  Rétinographe A  occ={ret_A.occupancy_rate(ts_A):.1%}  pic={ret_A.peak_simultaneous()}/{ret_A.total_units}")
        print(f"  Fauteuil A      occ={fau_A.occupancy_rate(ts_A):.1%}  pic={fau_A.peak_simultaneous()}/{fau_A.total_units}")

        # ── Scénario B ──────────────────────────────────────────────────────
        print(f"\n  {'─'*64}")
        print("  SCÉNARIO B — Cible réorganisation HDJ  [simulation pitch]")
        print(f"  {'─'*64}")
        print(f"  {'Simulés B  [simulated_pending_validation]':<50} {self.kpis_B.scheduled:>5}")
        print(f"  {'dont pmsi_validation_required=True':<50} {self.kpis_B.pmsi_validation_required:>5}")
        print(f"  {'Uncertain  [requires_human_review_before_sim]':<50} {self.kpis_B.requires_human_review:>5}")
        print(f"  {'Low candidate  [not_simulated]':<50} {self.kpis_B.low_candidate:>5}")
        print(f"  {'Candidats B sans créneau (horizon plein)':<50} {self.kpis_B.not_scheduled:>5}")
        print(f"  {'GAIN B vs A  (+candidats organisationnels)':<50} {self.kpis_B.gain_vs_a:>+5}")
        print(f"  {'Délai attente moyen (j)':<50} {self.kpis_B.avg_wait_days:>5.1f}")
        print(f"  Rétinographe B  occ={ret_B.occupancy_rate(ts_B):.1%}  pic={ret_B.peak_simultaneous()}/{ret_B.total_units}")
        print(f"  Fauteuil B      occ={fau_B.occupancy_rate(ts_B):.1%}  pic={fau_B.peak_simultaneous()}/{fau_B.total_units}")

        print(f"\n  Répartition planifiés B par parcours :")
        pathway_order = [
            "already_hdj", "depistage_retinopathie", "test_dynamique_endocrinien",
            "etp_diabete_obesite", "bilan_annuel_diabete", "bilan_angiopathies",
            "bilan_endocrino_metabolique",
        ]
        for pw in pathway_order:
            n = self.kpis_B.by_pathway.get(pw, 0)
            if n:
                print(f"    {pw:<40} {n:>4}")
        other = {k: v for k, v in self.kpis_B.by_pathway.items() if k not in pathway_order}
        for k, v in other.items():
            print(f"    {k:<40} {v:>4}")

        # ── Limites explicites ──────────────────────────────────────────────
        print(f"\n  {'─'*64}")
        print("  LIMITES À VALIDER ÉQUIPE MÉTIER")
        print(f"  {'─'*64}")
        limits = [
            ("Instruction Gradation DGOS/R1/DSS/1A/2020/52 manquante",
             "critères GHS sans nuitée non codés → tous cas B = pmsi_validation_required"),
            ("Actes CCAM initiation pompe/capteur/Holter absents",
             "parcours initiation_dispositif non détectable dans les données"),
            ("Actes CCAM pied diabétique absents des données",
             "parcours pied_diabetique non détectable"),
            ("Données TYPE_SEJOUR=EXT uniquement",
             "simulation hypothétique — pas une reclassification PMSI réelle"),
            ("Durées de séjour HDJ estimées (non issues de temps réels)",
             "bilan_annuel=60min, rétinographie=90min, test_dyn=180min — à valider"),
        ]
        for title, detail in limits:
            print(f"  ⚠ {title}")
            print(f"      → {detail}")

        print(f"\n{sep}\n")

    def print_scheduled_full_detail(self, scenario: str = "A") -> None:
        """
        Affiche le détail complet des séjours planifiés pour le scénario choisi.

        Args:
            scenario: "A" (PMSI) ou "B" (réorganisation)
        """
        if scenario == "A":
            scheduled_records = [r for r in self.patients if r.scheduled_entry_A is not None]
            entry_getter = lambda r: r.scheduled_entry_A
        else:
            scheduled_records = [r for r in self.patients if r.scheduled_entry_B is not None]
            entry_getter = lambda r: r.scheduled_entry_B

        sep_inner = "  " + "─" * 64
        print(f"\n  DÉTAIL COMPLET SCÉNARIO {scenario} — {len(scheduled_records)} séjour(s) planifié(s)")
        print("  " + "═" * 64)

        for i, record in enumerate(scheduled_records, 1):
            el = record.eligibility
            sc = entry_getter(record)
            print(f"\n  [{i}/{len(scheduled_records)}]  {record.patient_id}")
            print(sep_inner)
            print(f"  hdj_potential        : {el.hdj_potential}")
            print(f"  pmsi_status          : {el.pmsi_status}")
            print(f"  pmsi_validation_req  : {el.pmsi_validation_required}")
            print(f"  current_care_context : {el.current_care_context}")
            print(f"  candidate_pathway    : {el.candidate_pathway}")
            print(f"  reorg_potential      : {el.reorganization_potential}")
            print(f"  scheduling_A         : {record.scheduling_status_A}")
            print(f"  scheduling_B         : {record.scheduling_status_B}")
            print(f"  Créneau              : {sc.start_label} → {sc.end_label}  ({sc.duration_slots * SLOT_DURATION_MIN} min)")
            res_str = ", ".join(el.required_resources) if el.required_resources else "—"
            print(f"  Ressources           : {res_str}")
            print(f"\n  reasons :")
            for x in el.reasons:
                print(f"    • {x}")
            print(f"\n  matched_rules :")
            for x in el.matched_rules:
                print(f"    • {x}")
            print(f"\n  guide_references :")
            for x in el.guide_references:
                marker = "  ⚠" if "guide_reference_to_verify" in x else "  ✓"
                print(f"    {marker} {x}")
            if el.missing_information:
                print(f"\n  missing_information :")
                for x in el.missing_information:
                    print(f"    • {x}")
            print(sep_inner)
