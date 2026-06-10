"""
Règles d'éligibilité HDJ — endocrino-diabétologie CHU Guyane.

DEUX DIMENSIONS DE DÉCISION (v3 — scénarios A et B) :

  SCÉNARIO A — Garde-fou PMSI / réglementaire
    → hdj_potential : planifie uniquement official_hdj et pmsi_reference_available
    → Critère : acte CCAM documenté dans YAML ou unité HDJ explicite dans les données
    → Si l'Instruction Gradation (DGOS/R1/DSS/1A/2020/52) est requise et absente
      → cas marqué requires_review, non planifié automatiquement

  SCÉNARIO B — Cible de réorganisation HDJ (simulation pitch)
    → reorganization_potential + candidate_pathway
    → Planifie high_hdj_candidate et medium_hdj_candidate
    → Ne planifie PAS low_hdj_candidate (comptés séparément)
    → Tous les cas planifiés en B mais sans PMSI confirmé :
      pmsi_validation_required = True

  Règle de prudence transversale :
    Si une règle cite un document absent (Instruction Gradation) et qu'on ne
    peut pas préciser → marqueur "guide_reference_to_verify" + pmsi_validation_required=True

Sources :
  [MCO26]  Guide méthodologique MCO 2026, ATIH
             §1.1 : FA 04 = hospitalisation à temps partiel de jour (HDJ)
             §1.2 : Admission UM MCO = facteur déclenchant du RUM
             §1.3.4 : Consultations externes ≠ admission UM → pas de RUM MCO
             §1.5 : Soins sans nuitée → Instruction Gradation DGOS/R1/DSS/1A/2020/52
  [YAML]   Référentiel équipements HDJ endocrino, Ahmed EL BAHRI, 2026-06-08
             §mvp_bottleneck_resources : rétinographe ×1, fauteuil ×2
             §bilan_annuel_complications : acte BLQP010
             §tests_dynamiques_endocriniens : acte PZQP018
  [DATA]   Données consultations externes endocrino CHU Guyane 2020-2026

Limites EXPLICITES :
  - Instruction Gradation DGOS/R1/DSS/1A/2020/52 absente → critères GHS non codés
  - Données TYPE_SEJOUR=EXT uniquement → simulation organisationnelle à valider DIM/PMSI
  - Actes CCAM pour initiation pompe/capteur et pied diabétique absents des données
  - Règles médicales absentes des documents disponibles → non codées
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal, List, Tuple

_YAML_PATH = Path(__file__).parent.parent / "config" / "hdj_metier.yaml"


def _load_eligibility_config(yaml_path: Path = _YAML_PATH) -> dict:
    """Charge le référentiel métier depuis hdj_metier.yaml."""
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Référentiel métier introuvable : {yaml_path}\n"
            "Vérifier que core/config/hdj_metier.yaml est présent dans le repo."
        )
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


_cfg = _load_eligibility_config()

# ── Dimension 1 : contexte administratif courant ───────────────────────────
CareContext = Literal[
    "urgence",              # CONSULT EXT URGENCES, UHCD MEDURG, URGENCE GYNECO
    "consultation_externe", # consultations programmées hors urgences et hors HDJ
    "hdj_existing",         # unité déjà structurée HDJ (HDJ CONSULTATION)
    "unknown",
]

# ── Dimension 2a — Scénario A : garde-fou PMSI ─────────────────────────────
HdjPotential = Literal[
    "already_hdj",                        # Unité HDJ dans les données → official_hdj
    "convertible_to_hdj",                 # CCAM documenté (YAML/MCO) → pmsi_reference_available
    "convertible_to_hdj_requires_review", # Potentiel org., Gradation manquante — A:review, B:scheduled
    "candidate_hdj_requires_pmsi_validation",  # Pathway identifié + indice clinique (medium)
                                               # → A:non planifié, B:simulé avec pmsi_validation_required
    "not_hdj_relevant",                   # Hors périmètre endocrino HDJ
    "uncertain_requires_human_review",    # Signal faible (diag seul), vraiment incertain
                                          # → jamais planifié, ni A ni B
]

# Degré de certitude PMSI (facturation GHS)
PmsiStatus = Literal[
    "official_hdj",             # Unité HDJ existante, pas de question de facturation
    "pmsi_reference_available", # Acte CCAM + référence YAML/MCO disponibles
                                # → GHS à confirmer via Instruction Gradation
    "pmsi_pathway_candidate",   # Parcours organisationnel, documentation PMSI incomplète
    "pmsi_not_applicable",      # Hors périmètre endocrino HDJ
]

# ── Dimension 2b — Scénario B : potentiel de réorganisation HDJ ────────────
ReorganizationPotential = Literal[
    "high",    # Parcours clair + acte CCAM ou unité dédiée dans les données
    "medium",  # Parcours identifiable + indice clinique (dosage, diagnostic précis)
    "low",     # Signal faible — diagnostic seul, sans acte ni unité spécifique
    "none",    # Hors périmètre
]

# Parcours candidats HDJ (liste définie par l'équipe projet Défi 5)
CandidatePathway = Literal[
    "already_hdj",
    "depistage_retinopathie",       # actes ACTES_RETINOGRAPHE — [YAML]
    "test_dynamique_endocrinien",   # PZQP018 ou diag E2x — [YAML]
    "etp_diabete_obesite",          # unité DIETETIQUE/ETP ou E66
    "bilan_annuel_diabete",         # E10/E11 + actes dosage
    "bilan_angiopathies",           # E10/E11 + actes multi-organes
    "bilan_endocrino_metabolique",  # E2x/E3x/E87 + consultation programmable
    # Note : initiation_dispositif et pied_diabetique sont dans la liste projet
    # mais leurs CCAM spécifiques sont ABSENTS des données → non codés
    "none",
]

# ── Actes CCAM ─────────────────────────────────────────────────────────────
# Source : [YAML] §ressources_hdj.mvp_ressources_goulot.*.actes_ccam
ACTES_RETINOGRAPHE: set = set(
    str(c) for c in _cfg["ressources_hdj"]["mvp_ressources_goulot"]["retinographe"]["actes_ccam"]
)
ACTES_FAUTEUIL: set = set(
    str(c) for c in _cfg["ressources_hdj"]["mvp_ressources_goulot"]["fauteuil_medicalise"]["actes_ccam"]
)
# Source : [YAML] §actes_et_taches.actes_hors_scope_hdj.codes
ACTES_HORS_SCOPE: set = set(
    str(c) for c in _cfg["actes_et_taches"]["actes_hors_scope_hdj"]["codes"]
)

# ── Unités / spécialités ────────────────────────────────────────────────────
# Source : [YAML] §codes_diagnostics
UNITES_HDJ_EXPLICITES: set = set(_cfg["codes_diagnostics"]["unites_hdj_explicites"])
SPECIALITES_HORS_ENDOCRINO: set = set(_cfg["codes_diagnostics"]["specialites_hors_endocrino"])

# ── Préfixes CIM-10 — convertis en tuple pour str.startswith() ──────────────
# Source : [YAML] §codes_diagnostics.*
_diag_cfg = _cfg["codes_diagnostics"]
PREFIXES_DIABETE:       tuple = tuple(str(p) for p in _diag_cfg["diabete"])
PREFIXES_THYROIDE:      tuple = tuple(str(p) for p in _diag_cfg["thyroide"])
PREFIXES_OBESITE:       tuple = tuple(str(p) for p in _diag_cfg["obesite"])
PREFIXES_TROUBLES_ENDO: tuple = tuple(str(p) for p in _diag_cfg["troubles_endocriniens"])
PREFIXES_METABOLIQUE:   tuple = tuple(str(p) for p in _diag_cfg["metabolique"])

# ── Durées estimées (minutes) — à valider équipe médicale ───────────────────
# Source : [YAML] §actes_et_taches.actes_ccam_hdj_endocrino.*.duree_min
_actes_cfg = _cfg["actes_et_taches"]["actes_ccam_hdj_endocrino"]
DUREES_MIN: dict = {
    "consultation_simple": int(_actes_cfg["consultation_simple"]["duree_min"]),
    "bilan_diabete":       int(_actes_cfg["bilan_annuel_diabete"]["duree_min"]),
    "retinographe":        int(_actes_cfg["retinographie"]["duree_min"]),
    "fauteuil_dynamique":  int(_actes_cfg["test_dynamique_endocrinien"]["duree_min"]),
}

_ALL_ENDOCRINO_PREFIXES_3 = frozenset(
    p[:3]
    for group in (PREFIXES_DIABETE, PREFIXES_THYROIDE, PREFIXES_OBESITE,
                  PREFIXES_TROUBLES_ENDO, PREFIXES_METABOLIQUE)
    for p in group
)


@dataclass
class EligibilityResult:
    # ── Dimension 1 : contexte administratif (informatif) ─────────────────
    current_care_context: CareContext

    # ── Dimension 2a : Scénario A — garde-fou PMSI ────────────────────────
    hdj_potential: HdjPotential
    pmsi_status: PmsiStatus

    # ── Dimension 2b : Scénario B — réorganisation HDJ ────────────────────
    reorganization_potential: ReorganizationPotential
    candidate_pathway: CandidatePathway
    pmsi_validation_required: bool  # True si Instruction Gradation manquante

    # ── Commun ─────────────────────────────────────────────────────────────
    guide_references: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    matched_rules: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    required_resources: List[str] = field(default_factory=list)
    estimated_duration_min: int = 30


def is_hdj_eligible(row) -> EligibilityResult:
    """
    Classifie un séjour selon deux scénarios orthogonaux.

    Scénario A (hdj_potential + pmsi_status) : garde-fou PMSI/réglementaire.
    Scénario B (reorganization_potential + candidate_pathway) : simulation cible.

    Args:
        row: dict ou pandas.Series

    Returns:
        EligibilityResult complet avec les deux dimensions.
    """
    def _get(key: str) -> str:
        val = row.get(key, "") if hasattr(row, "get") else getattr(row, key, "")
        return "" if (val is None or str(val).upper() in ("NAN", "NONE", "")) else str(val).strip()

    unite          = _get("LIBELLE UNITE MVT").upper()
    code_acte      = _get("CODE ACTE").upper()
    specialite_op  = _get("SPECIALITE OPERATEUR").upper()
    specialite_ngap= _get("SPECIALITE EXECUTANT NGAP").upper()
    code_diag      = _get("CODE DIAG").upper()
    actes_raw      = _get("LISTE ACTES CCAM MVT").upper()

    actes: set = set()
    if code_acte:
        actes.add(code_acte)
    for a in actes_raw.split(","):
        a = a.strip()
        if a:
            actes.add(a)

    specialite = specialite_op or specialite_ngap

    care_context: CareContext = _determine_care_context(unite)

    reasons: List[str] = [f"[contexte courant: {care_context}]"]
    matched_rules: List[str] = []
    guide_refs: List[str] = []
    missing_info: List[str] = []
    required_resources: List[str] = []

    diag_endocrino    = (len(code_diag) >= 3 and code_diag[:3] in _ALL_ENDOCRINO_PREFIXES_3)
    diag_diabete      = code_diag.startswith(PREFIXES_DIABETE)
    diag_thyroide     = code_diag.startswith(PREFIXES_THYROIDE)
    diag_obesite      = code_diag.startswith(PREFIXES_OBESITE)
    diag_troubles_endo= code_diag.startswith(PREFIXES_TROUBLES_ENDO)
    diag_metabolique  = code_diag.startswith(PREFIXES_METABOLIQUE)

    pathway, reorg = _detect_pathway(actes, code_diag, unite)

    # ── R07 : already_hdj ─────────────────────────────────────────────────
    # Scénario A : planifié. Scénario B : planifié (high, already_hdj).
    # PMSI : unité déjà HDJ → pas de question de facturation GHS.
    if unite in UNITES_HDJ_EXPLICITES:
        guide_refs += [
            "[MCO26] §1.1 : FA 04 = hospitalisation à temps partiel de jour",
            "[DATA] : unité 'HDJ CONSULTATION' dans les données source",
        ]
        reasons.append(f"Unité '{unite}' déjà structurée en HDJ dans les données")
        matched_rules.append("R07 — [DATA]+[MCO26]§1.1 : unité HDJ explicite")
        _enrich_resources(actes, required_resources, reasons, matched_rules, guide_refs)
        return EligibilityResult(
            current_care_context=care_context,
            hdj_potential="already_hdj",
            pmsi_status="official_hdj",
            reorganization_potential="high",
            candidate_pathway="already_hdj",
            pmsi_validation_required=False,
            guide_references=guide_refs,
            reasons=reasons,
            matched_rules=matched_rules,
            missing_information=missing_info,
            required_resources=required_resources,
            estimated_duration_min=_estimate_duration(required_resources),
        )

    # ── R09a : not_hdj_relevant — actes hors scope ────────────────────────
    if actes and actes.issubset(ACTES_HORS_SCOPE):
        guide_refs.append("[DATA] : actes hors périmètre endocrino HDJ")
        reasons.append(f"Actes {actes} hors périmètre endocrino")
        matched_rules.append("R09a — [DATA] : actes hors scope")
        return EligibilityResult(
            current_care_context=care_context,
            hdj_potential="not_hdj_relevant",
            pmsi_status="pmsi_not_applicable",
            reorganization_potential="none",
            candidate_pathway="none",
            pmsi_validation_required=False,
            guide_references=guide_refs, reasons=reasons,
            matched_rules=matched_rules, missing_information=missing_info,
            required_resources=[], estimated_duration_min=0,
        )

    # ── R09b : not_hdj_relevant — spécialité hors endocrino ───────────────
    if specialite in SPECIALITES_HORS_ENDOCRINO and not diag_endocrino:
        guide_refs.append("[DATA] : spécialité non endocrino + diagnostic non endocrino")
        reasons.append(
            f"Spécialité '{specialite}' hors endocrino + diagnostic '{code_diag}' non endocrino"
        )
        matched_rules.append("R09b — [DATA] : spécialité + diagnostic hors scope")
        return EligibilityResult(
            current_care_context=care_context,
            hdj_potential="not_hdj_relevant",
            pmsi_status="pmsi_not_applicable",
            reorganization_potential="none",
            candidate_pathway="none",
            pmsi_validation_required=False,
            guide_references=guide_refs, reasons=reasons,
            matched_rules=matched_rules, missing_information=missing_info,
            required_resources=[], estimated_duration_min=0,
        )

    # ── R04 : convertible_to_hdj — actes rétinographe confirmés ──────────
    # Scénario A : planifié (pmsi_reference_available).
    # Scénario B : planifié (high_hdj_candidate, depistage_retinopathie).
    # PMSI : acte CCAM explicitement cité dans [YAML]. Critères GHS sans nuitée
    #        dans Instruction Gradation → pmsi_validation_required=True.
    actes_retino = actes & ACTES_RETINOGRAPHE
    if actes_retino:
        guide_refs += [
            "[YAML] §bilan_annuel_complications : rétinographe, acte BLQP010 cité",
            "[MCO26] §1.5 : soins sans nuitée → Instruction DGOS/R1/DSS/1A/2020/52",
            "guide_reference_to_verify : modalités GHS rétinopathie — Instruction Gradation DGOS/R1/DSS/1A/2020/52",
        ]
        reasons.append(f"Actes dépistage rétinopathie : {actes_retino}")
        matched_rules.append("R04 — [YAML]§bilan_annuel_complications : rétinographe CCAM confirmé")
        required_resources.append("retinographe")
        _enrich_resources(actes - actes_retino, required_resources, reasons, matched_rules, guide_refs)
        return EligibilityResult(
            current_care_context=care_context,
            hdj_potential="convertible_to_hdj",
            pmsi_status="pmsi_reference_available",
            reorganization_potential="high",
            candidate_pathway="depistage_retinopathie",
            pmsi_validation_required=True,
            guide_references=guide_refs, reasons=reasons,
            matched_rules=matched_rules, missing_information=missing_info,
            required_resources=required_resources,
            estimated_duration_min=_estimate_duration(required_resources),
        )

    # ── R05 : convertible_to_hdj — test dynamique CCAM confirmé ──────────
    # Scénario A : planifié. Scénario B : planifié (high).
    actes_fauteuil = actes & ACTES_FAUTEUIL
    if actes_fauteuil:
        guide_refs += [
            "[YAML] §tests_dynamiques_endocriniens : acte PZQP018 cité",
            "[MCO26] §1.5 : soins sans nuitée → Instruction DGOS/R1/DSS/1A/2020/52",
            "guide_reference_to_verify : modalités GHS tests dynamiques — Instruction Gradation DGOS/R1/DSS/1A/2020/52",
        ]
        reasons.append(f"Test dynamique endocrinien — acte PZQP018 confirmé : {actes_fauteuil}")
        matched_rules.append("R05 — [YAML]§tests_dynamiques_endocriniens : PZQP018 présent")
        required_resources.append("fauteuil")
        return EligibilityResult(
            current_care_context=care_context,
            hdj_potential="convertible_to_hdj",
            pmsi_status="pmsi_reference_available",
            reorganization_potential="high",
            candidate_pathway="test_dynamique_endocrinien",
            pmsi_validation_required=True,
            guide_references=guide_refs, reasons=reasons,
            matched_rules=matched_rules, missing_information=missing_info,
            required_resources=required_resources,
            estimated_duration_min=DUREES_MIN["fauteuil_dynamique"],
        )

    # ── R11 : ETP/diététique ──────────────────────────────────────────────
    # Scénario A : requires_review (Instruction Gradation manquante).
    # Scénario B : planifié (high_hdj_candidate — unité dédiée identifiée).
    if any(kw in unite for kw in ("DIETETIQUE", "ETP")):
        guide_refs += [
            "[DATA] : unité diététique/ETP avec profil obésité/diabète identifiée",
            "guide_reference_to_verify : modalités HDJ ETP — Instruction Gradation DGOS/R1/DSS/1A/2020/52",
        ]
        reasons.append(f"Unité ETP/diététique '{unite}' — potentiel HDJ éducation thérapeutique")
        matched_rules.append("R11 — [DATA] : unité ETP/diététique")
        missing_info += [
            "Protocole HDJ ETP validé équipe médicale",
            "Instruction Gradation DGOS/R1/DSS/1A/2020/52 §ETP",
        ]
        return EligibilityResult(
            current_care_context=care_context,
            hdj_potential="convertible_to_hdj_requires_review",
            pmsi_status="pmsi_pathway_candidate",
            reorganization_potential="high",
            candidate_pathway="etp_diabete_obesite",
            pmsi_validation_required=True,
            guide_references=guide_refs, reasons=reasons,
            matched_rules=matched_rules, missing_information=missing_info,
            required_resources=[], estimated_duration_min=DUREES_MIN["bilan_diabete"],
        )

    # ── R05b : diag E2x sans acte PZQP018 ────────────────────────────────
    # Scénario A : requires_review (acte CCAM absent).
    # Scénario B : planifié si medium (acte dosage présent), low sinon.
    if diag_troubles_endo:
        guide_refs += [
            "[YAML] §tests_dynamiques_endocriniens : diagnostic E2x suggestif de test dynamique",
            "guide_reference_to_verify : acte PZQP018 + protocole HDJ requis avant planification A",
        ]
        reasons.append(
            f"Diagnostic surrénalien/hypophysaire '{code_diag}' sans PZQP018 — test dynamique présumé"
        )
        matched_rules.append("R05b — [YAML]§tests_dynamiques_endocriniens : diag seul, acte absent")
        missing_info.append("Acte CCAM PZQP018 ou protocole test dynamique")
        required_resources.append("fauteuil")
        return EligibilityResult(
            current_care_context=care_context,
            hdj_potential="convertible_to_hdj_requires_review",
            pmsi_status="pmsi_pathway_candidate",
            reorganization_potential=reorg,          # medium si dosage présent, low sinon
            candidate_pathway="test_dynamique_endocrinien",
            pmsi_validation_required=True,
            guide_references=guide_refs, reasons=reasons,
            matched_rules=matched_rules, missing_information=missing_info,
            required_resources=required_resources,
            estimated_duration_min=DUREES_MIN["fauteuil_dynamique"],
        )

    # ── R10 : profil endocrino sans acte HDJ confirmé ────────────────────
    # Scindé en deux branches selon reorganization_potential (détecté par _detect_pathway) :
    #
    # R10a : medium — pathway identifié + acte de dosage (DEQP*) présent
    #   → candidate_hdj_requires_pmsi_validation
    #   → Scénario A : non planifié (Gradation manquante)
    #   → Scénario B : simulé avec pmsi_validation_required=True
    #
    # R10b : low — diagnostic seul, aucun acte confirmant le parcours
    #   → uncertain_requires_human_review
    #   → Scénario A : non planifié
    #   → Scénario B : jamais simulé (requires_human_review_before_simulation)
    if diag_diabete or diag_thyroide or diag_obesite or diag_metabolique:
        guide_refs += [
            "[MCO26] §1.5 : soins sans nuitée → Instruction DGOS/R1/DSS/1A/2020/52 (non disponible)",
            "guide_reference_to_verify : critères GHS pour ce profil diagnostique",
        ]
        reasons.append(
            f"Diagnostic endocrino/métabolique '{code_diag}' sans acte technique HDJ confirmé"
        )
        missing_info += [
            "Instruction Gradation DGOS/R1/DSS/1A/2020/52",
            "Plan de soins HDJ validé équipe médicale",
        ]

        if reorg == "medium":
            # R10a — candidat organisationnel avec indice clinique (dosage présent)
            matched_rules.append(
                "R10a — [MCO26]§1.5 : pathway identifié + dosage présent → candidate_hdj_requires_pmsi_validation"
            )
            return EligibilityResult(
                current_care_context=care_context,
                hdj_potential="candidate_hdj_requires_pmsi_validation",
                pmsi_status="pmsi_pathway_candidate",
                reorganization_potential="medium",
                candidate_pathway=pathway,
                pmsi_validation_required=True,
                guide_references=guide_refs, reasons=reasons,
                matched_rules=matched_rules, missing_information=missing_info,
                required_resources=[], estimated_duration_min=DUREES_MIN["bilan_diabete"],
            )
        else:
            # R10b — signal faible, diagnostic seul, vraiment incertain
            matched_rules.append(
                "R10b — [MCO26]§1.5 : diagnostic seul, aucun acte confirmant → uncertain"
            )
            return EligibilityResult(
                current_care_context=care_context,
                hdj_potential="uncertain_requires_human_review",
                pmsi_status="pmsi_pathway_candidate",
                reorganization_potential="low",
                candidate_pathway=pathway,
                pmsi_validation_required=True,
                guide_references=guide_refs, reasons=reasons,
                matched_rules=matched_rules, missing_information=missing_info,
                required_resources=[], estimated_duration_min=DUREES_MIN["bilan_diabete"],
            )

    # ── DEFAULT : not_hdj_relevant ────────────────────────────────────────
    guide_refs.append("[DATA] : absence de profil endocrino dans actes et diagnostic")
    reasons.append(
        f"Aucun profil endocrino (unite='{unite}', diag='{code_diag}', actes={actes or '∅'})"
    )
    matched_rules.append("DEFAULT — not_hdj_relevant")
    return EligibilityResult(
        current_care_context=care_context,
        hdj_potential="not_hdj_relevant",
        pmsi_status="pmsi_not_applicable",
        reorganization_potential="none",
        candidate_pathway="none",
        pmsi_validation_required=False,
        guide_references=guide_refs, reasons=reasons,
        matched_rules=matched_rules, missing_information=missing_info,
        required_resources=[], estimated_duration_min=0,
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _determine_care_context(unite: str) -> CareContext:
    """Contexte administratif courant — informatif, orthogonal aux deux scénarios."""
    if "URGENCES" in unite or "URGENCE GYNECO" in unite or "UHCD" in unite:
        return "urgence"
    if unite in UNITES_HDJ_EXPLICITES:
        return "hdj_existing"
    if unite:
        return "consultation_externe"
    return "unknown"


def _detect_pathway(
    actes: set, code_diag: str, unite: str
) -> Tuple[CandidatePathway, ReorganizationPotential]:
    """
    Détecte le parcours candidat HDJ pour le scénario B.

    Retourne (pathway, reorganization_potential) indépendamment du scénario A.
    La présence d'un acte de dosage (DEQP*) élève le potentiel de low à medium
    pour les cas sans acte CCAM HDJ confirmé.
    """
    has_dosage = any(a.startswith("DEQP") for a in actes)

    if actes & ACTES_RETINOGRAPHE:
        return "depistage_retinopathie", "high"

    if actes & ACTES_FAUTEUIL:
        return "test_dynamique_endocrinien", "high"

    if any(kw in unite for kw in ("DIETETIQUE", "ETP")):
        return "etp_diabete_obesite", "high"

    if code_diag.startswith(PREFIXES_TROUBLES_ENDO):
        return "test_dynamique_endocrinien", "medium" if has_dosage else "low"

    if code_diag.startswith(PREFIXES_DIABETE):
        return "bilan_annuel_diabete", "medium" if has_dosage else "low"

    if code_diag.startswith(PREFIXES_THYROIDE):
        return "bilan_endocrino_metabolique", "medium" if has_dosage else "low"

    if code_diag.startswith(PREFIXES_OBESITE):
        return "etp_diabete_obesite", "low"

    if code_diag.startswith(PREFIXES_METABOLIQUE):
        return "bilan_endocrino_metabolique", "medium" if has_dosage else "low"

    return "none", "none"


def _enrich_resources(
    actes: set, required_resources: list,
    reasons: list, matched_rules: list, guide_refs: list,
) -> None:
    retino = actes & ACTES_RETINOGRAPHE
    if retino and "retinographe" not in required_resources:
        required_resources.append("retinographe")
        reasons.append(f"Actes ophtalmologiques complémentaires : {retino}")
        matched_rules.append("R04 — [YAML] : rétinographe complémentaire")
        guide_refs.append("[YAML] §bilan_annuel_complications : rétinographe complémentaire")

    fauteuil_acts = actes & ACTES_FAUTEUIL
    if fauteuil_acts and "fauteuil" not in required_resources:
        required_resources.append("fauteuil")
        reasons.append(f"Actes test dynamique complémentaires : {fauteuil_acts}")
        matched_rules.append("R05 — [YAML] : fauteuil complémentaire")
        guide_refs.append("[YAML] §tests_dynamiques_endocriniens : fauteuil complémentaire")


def _estimate_duration(required_resources: list) -> int:
    if "fauteuil" in required_resources:
        return DUREES_MIN["fauteuil_dynamique"]
    if "retinographe" in required_resources:
        return DUREES_MIN["retinographe"]
    return DUREES_MIN["consultation_simple"]
