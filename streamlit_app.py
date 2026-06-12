"""
HDJ Agent — Interface hospitalière d'aide à la décision.

Lecture seule des outputs JSON générés par export_dashboard_outputs.py.
Ne pas afficher d'IPP individuel.

Lancement : streamlit run streamlit_app.py
"""

import json
from pathlib import Path
import sys

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from core.scenarios.what_if_capacity import run_capacity_what_if, generate_scenario_candidates

OUT = Path("outputs")

st.set_page_config(
    page_title="HDJ Agent — CHU Guyane",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Style ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-box {background:#f8f9fa;border-radius:8px;padding:16px;text-align:center;}
    .metric-val {font-size:2rem;font-weight:700;color:#1a5276;}
    .metric-lab {font-size:0.85rem;color:#555;}
    .warn-box   {background:#fff3cd;border-left:4px solid #ffc107;padding:10px 14px;border-radius:4px;}
    .ok-box     {background:#d4edda;border-left:4px solid #28a745;padding:10px 14px;border-radius:4px;}
</style>
""", unsafe_allow_html=True)


def _load(filename: str) -> dict | list | None:
    p = OUT / filename
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _metric(col, label: str, value, unit: str = ""):
    col.markdown(f"""
    <div class='metric-box'>
        <div class='metric-val'>{value}{unit}</div>
        <div class='metric-lab'>{label}</div>
    </div>""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────
if "active_dataset_source" not in st.session_state:
    st.session_state["active_dataset_source"] = "demo"


def render_active_dataset_banner(page_updated: bool = True) -> None:
    """Bandeau indiquant la source active des données (demo ou établissement)."""
    source = st.session_state.get("active_dataset_source", "demo")
    if source == "uploaded":
        if page_updated:
            st.success(
                "Mode établissement — résultats calculés sur le fichier uploadé "
                "pendant cette session."
            )
        else:
            st.info(
                "Cette page utilise encore les outputs de démonstration. "
                "Les résultats du fichier uploadé sont disponibles dans "
                "**Paramétrage hospitalier**."
            )
    elif page_updated:
        st.info(
            "Mode démonstration — les résultats affichés utilisent les données d'exemple."
        )


def _build_quality_from_df(df: pd.DataFrame) -> dict:
    """Rapport de qualité calculé sur un dataframe en mémoire de session."""
    REQUIRED    = {"NUM SEJOUR", "CODE DIAG", "TYPE SEJOUR"}
    RECOMMENDED = {"NUM IPP PATIENT", "LISTE ACTES CCAM MVT", "DATE ENTREE SEJ"}
    df_u = df.copy()
    df_u.columns = df_u.columns.str.strip().str.upper()
    cols     = set(df_u.columns)
    blocking = [f"Colonne obligatoire absente : {c}" for c in REQUIRED - cols]
    warns    = [f"Colonne recommandée absente : {c}" for c in RECOMMENDED - cols]
    t_miss   = {c: float(df_u[c].isna().mean()) for c in df_u.columns}
    for col, rate in t_miss.items():
        if rate > 0.5 and col not in (REQUIRED - cols):
            warns.append(f"Colonne {col} : {rate:.0%} de valeurs manquantes")
    ipp_present = "NUM IPP PATIENT" in cols
    ipp_uniques, taux_rec = None, 0.0
    if ipp_present:
        ipp_s = df_u["NUM IPP PATIENT"].dropna()
        ipp_uniques = int(ipp_s.nunique())
        if ipp_uniques > 0:
            taux_rec = int((ipp_s.value_counts() > 1).sum()) / ipp_uniques
    if blocking:
        verdict, detail = "not_usable", "Colonnes obligatoires manquantes."
    elif warns:
        verdict, detail = "usable_with_warnings", f"{len(warns)} point(s) à vérifier — analyse possible."
    else:
        verdict, detail = "usable_for_decision_support", "Qualité suffisante pour une analyse d'aide à la décision."
    return {
        "verdict": verdict, "verdict_detail": detail,
        "dimensions": {"n_lignes": len(df_u), "n_colonnes": len(df_u.columns)},
        "ipp": {"present": ipp_present, "ipp_uniques": ipp_uniques, "taux_recurrence": taux_rec},
        "warnings": warns, "blocking_issues": blocking,
        "colonnes": {"taux_manquants": t_miss},
    }


def _build_fragmentation_from_df(df: pd.DataFrame) -> dict | None:
    """Fragmentation IPP calculée sur un dataframe en mémoire de session."""
    df_u = df.copy()
    df_u.columns = df_u.columns.str.strip().str.upper()
    if "NUM IPP PATIENT" not in df_u.columns:
        return None
    ipp_s = df_u["NUM IPP PATIENT"].dropna()
    ipp_uniques = int(ipp_s.nunique())
    if ipp_uniques == 0:
        return None
    vc = ipp_s.value_counts()
    patients_rec = int((vc > 1).sum())
    pct_rec      = patients_rec / ipp_uniques * 100
    dist = {}
    for lo, hi, lbl in [(1,1,"1_visite"),(2,2,"2_visites"),(3,5,"3_a_5_visites"),
                         (6,10,"6_a_10_visites"),(11,9999,"plus_de_10_visites")]:
        n = int(((vc >= lo) & (vc <= hi)).sum())
        if n > 0:
            dist[lbl] = n
    return {
        "totaux": {
            "ipp_uniques": ipp_uniques, "patients_recurrents": patients_rec,
            "pct_recurrents": pct_rec, "venues_max": int(vc.max()),
        },
        "distribution_venues": dist,
        "interpretation_globale": (
            f"{patients_rec} patients sur {ipp_uniques} ({pct_rec:.1f}%) ont plusieurs venues. "
            "Potentiel de regroupement en HDJ pour réduire les déplacements."
        ),
    }


# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.title("HDJ Agent")
st.sidebar.caption("CHU Guyane — Endocrino-Diabétologie")
st.sidebar.markdown("---")

pages = [
    "Synthèse exécutive",
    "Qualité des données",
    "Fragmentation IPP",
    "Scénarios HDJ",
    "Simulateur what-if",
    "Capacité / Saturation",
    "Priorisation HDJ",
    "Impact médico-économique",
    "Note de décision",
    "Paramétrage hospitalier",
    "Modélisation parcours patient",
]
page = st.sidebar.radio("Navigation", pages)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Outil d'aide à la décision organisationnelle.  \n"
    "Validation DIM/PMSI requise avant mise en œuvre."
)
if st.session_state.get("active_dataset_source") == "uploaded":
    st.sidebar.markdown("---")
    st.sidebar.caption("Session active : données du fichier uploadé.")
    if st.sidebar.button("Revenir aux données de démonstration", key="sidebar_reset"):
        for _k in ["uploaded_hospital_data", "local_column_mapping",
                    "standardized_hospital_data", "analysis_summary", "active_results"]:
            st.session_state.pop(_k, None)
        st.session_state["active_dataset_source"] = "demo"
        st.rerun()

# ──────────────────────────────────────────────────────────────────────────
if page == "Synthèse exécutive":
    st.title("HDJ Agent — système multi-agent d'aide à la décision de gouvernance hospitalière capacitaire et organisationnelle")
    st.caption("CHU Guyane · Endocrinologie-Diabétologie · Simulation restructuration ambulatoire")
    render_active_dataset_banner(page_updated=True)

    _src = st.session_state.get("active_dataset_source", "demo")
    _ar  = st.session_state.get("active_results")

    # ── Données session (si fichier uploadé analysé) ──────────────────────
    if _src == "uploaded" and _ar:
        st.subheader("Données de votre établissement")
        c1, c2, c3, c4 = st.columns(4)
        _metric(c1, "Séjours analysés",          _ar["nb_sejours"])
        _metric(c2, "Patients pseudonymisés",     _ar["nb_patients_ipp"] or "—")
        _metric(c3, "Diagnostics distincts",      _ar["nb_diags_distincts"] or "—")
        _metric(c4, "Taux CCAM renseigné",
                f"{_ar['taux_ccam_pct']:.0f}%" if _ar["taux_ccam_pct"] else "—")

        _frag = _ar.get("fragmentation")
        if _frag:
            st.subheader("Fragmentation parcours patients")
            _tot = _frag["totaux"]
            c1, c2, c3, c4 = st.columns(4)
            _metric(c1, "IPP uniques",         _tot["ipp_uniques"])
            _metric(c2, "Patients récurrents",  _tot["patients_recurrents"])
            _metric(c3, "% récurrents",         f"{_tot['pct_recurrents']:.1f}", "%")
            _metric(c4, "Venues max",           _tot["venues_max"])
            st.caption(_frag.get("interpretation_globale", ""))

        if _ar.get("top_diags"):
            st.subheader("Principales catégories diagnostiques")
            st.dataframe(_ar["top_diags"], use_container_width=True, hide_index=True)

        dist_type = _ar.get("distribution_type_sejour")
        if dist_type:
            st.subheader("Distribution des types de séjour")
            df_types = pd.DataFrame(
                [{"Type": k, "Nb séjours": v} for k, v in dist_type.items()]
            )
            st.bar_chart(df_types.set_index("Type"))

        if _ar.get("alertes"):
            for _alert in _ar["alertes"]:
                st.warning(_alert)

        st.markdown("---")
        st.caption(
            "Scénarios A/B et simulation capacitaire ci-dessous : "
            "données de démonstration CHU Guyane — non recalculées sur votre fichier. "
            "Cliquez sur « Générer les exports » dans **Paramétrage hospitalier** pour les actualiser."
        )

    # ── KPI démo (toujours chargé pour les scénarios A/B) ─────────────────
    kpi = _load("kpi_summary.json")
    if not kpi:
        st.warning("Fichier kpi_summary.json introuvable. Lancez `python export_dashboard_outputs.py`.")
        st.stop()

    if _src != "uploaded":
        st.info(
            "Données TYPE_SEJOUR=EXT (consultations externes) — "
            "simulation organisationnelle à valider DIM/PMSI avant mise en œuvre."
        )

    vol  = kpi.get("volume", {})
    sc_A = kpi.get("scenario_A", {})
    sc_B = kpi.get("scenario_B", {})
    rec  = kpi.get("patients_recurrents", {})

    st.subheader(
        "Scénarios de référence (démonstration)" if _src == "uploaded" else "Chiffres clés"
    )
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Séjours référence (démo)", vol.get("total_sejours_analyses", "—"))
    _metric(c2, "Scénario prudent (A)",       sc_A.get("planifies", "—"))
    _metric(c3, "Réorganisation cible (B)",   sc_B.get("simules", "—"))
    _metric(c4, "Gain réorg. vs prudent",     f"+{sc_B.get('gain_vs_A', 0)}", " séj.")

    if _src != "uploaded":
        st.subheader("Fragmentation patients")
        c1, c2, c3, c4 = st.columns(4)
        _metric(c1, "IPP uniques",        rec.get("ipp_uniques", "—"))
        _metric(c2, "Patients récurrents", rec.get("patients_recurrents", "—"))
        _metric(c3, "% récurrents",        rec.get("pct_recurrents", "—"), "%")
        _metric(c4, "Venues max / patient",rec.get("venues_max", "—"))

    st.markdown("---")

    st.subheader("Décision recommandée")
    st.markdown("""
<div style='background:#d4edda;border-left:5px solid #28a745;padding:14px 18px;border-radius:6px;margin-bottom:12px'>
<b>Démarrer par un pilote HDJ "Bilan annuel diabète"</b><br>
Volume le plus large identifié dans les données · Faisabilité opérationnelle maximale ·
Validation DIM/PMSI réalisable en 4–6 semaines · Aucun investissement équipement requis.<br>
<i>Prochaine étape : présenter ce tableau de bord au comité de direction médicale et mandater le DIM pour validation PMSI des cas candidats.</i>
</div>
""", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Ce que l'outil permet à l'hôpital")
        st.markdown("""
- **Quantifier le potentiel HDJ** : séjours ambulatoires restructurables parmi les consultations existantes
- **Prioriser les parcours** : score multicritère sur volume réel, faisabilité et valeur stratégique
- **Simuler la capacité** : comparer 6 configurations ressources (rétinographe, fauteuil, horizon)
- **Détecter la fragmentation** : cartographier les patients multi-venues, réduire les déplacements inutiles
- **Outiller la gouvernance** : note téléchargeable, estimation médico-économique, recommandations comité médical
""")
    with col_b:
        st.subheader("Pourquoi c'est actionnable maintenant")
        st.markdown("""
- Données réelles disponibles (2020–2026, 249 patients uniques)
- Règles métier centralisées dans `hdj_metier.yaml` (CCAM, CIM-10, durées, ressources)
- Scénarios reproductibles et paramétrables
- Note décisionnelle générée automatiquement
- Limites PMSI explicitées — pas de sur-promesse réglementaire
""")

    st.caption(
        "Prototype d'aide à la décision organisationnelle — "
        "validation DIM/PMSI et gouvernance hospitalière requises avant mise en œuvre."
    )

    st.markdown("---")
    st.subheader("Occupation ressources critiques")
    df_res = pd.DataFrame({
        "Ressource": ["Rétinographe", "Fauteuil médicalisé", "Rétinographe", "Fauteuil médicalisé"],
        "Scénario": ["A", "A", "B", "B"],
        "Occupation (%)": [
            sc_A.get("retinographe_occ_pct", 0),
            sc_A.get("fauteuil_occ_pct", 0),
            sc_B.get("retinographe_occ_pct", 0),
            sc_B.get("fauteuil_occ_pct", 0),
        ],
    })
    st.dataframe(df_res, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Qualité des données":
    st.title("Qualité des données")
    render_active_dataset_banner(page_updated=True)
    _src = st.session_state.get("active_dataset_source", "demo")
    _ar  = st.session_state.get("active_results")
    if _src == "uploaded" and _ar and "quality" in _ar:
        q = _ar["quality"]
    else:
        q = _load("data_quality_report.json")
        if not q:
            st.warning("data_quality_report.json introuvable.")
            st.stop()

    verdict = q.get("verdict", "")
    detail = q.get("verdict_detail", "")
    _VERDICT_LABELS = {
        "usable_for_decision_support": "Données exploitables — qualité suffisante",
        "usable_with_warnings": "Données exploitables avec réserves",
        "not_usable": "Données insuffisantes — simulation non fiable",
    }
    verdict_label = _VERDICT_LABELS.get(verdict, verdict)
    if verdict == "usable_for_decision_support":
        st.markdown(f"<div class='ok-box'>✅ <b>{verdict_label}</b><br>{detail}</div>", unsafe_allow_html=True)
    elif verdict == "usable_with_warnings":
        st.markdown(f"<div class='warn-box'>⚠️ <b>{verdict_label}</b><br>{detail}</div>", unsafe_allow_html=True)
    else:
        st.error(f"❌ {verdict_label} — {detail}")

    st.subheader("Dimensions")
    dim = q.get("dimensions", {})
    c1, c2 = st.columns(2)
    c1.metric("Lignes", dim.get("n_lignes", "—"))
    c2.metric("Colonnes", dim.get("n_colonnes", "—"))

    st.subheader("IPP")
    ipp = q.get("ipp", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("IPP présent", "Oui" if ipp.get("present") else "Non")
    c2.metric("IPP uniques", ipp.get("ipp_uniques", "—"))
    c3.metric("Taux récurrence", f"{ipp.get('taux_recurrence', 0):.1%}")

    st.subheader("Warnings")
    for w in q.get("warnings", []):
        st.warning(w)
    for b in q.get("blocking_issues", []):
        st.error(b)

    st.subheader("Taux de valeurs manquantes")
    missing = q.get("colonnes", {}).get("taux_manquants", {})
    df_miss = pd.DataFrame(
        [{"Colonne": k, "Taux manquant": f"{v:.1%}"} for k, v in missing.items()]
    )
    st.dataframe(df_miss, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Fragmentation IPP":
    st.title("Fragmentation des parcours patients")
    render_active_dataset_banner(page_updated=True)
    _src = st.session_state.get("active_dataset_source", "demo")
    _ar  = st.session_state.get("active_results")

    if _src == "uploaded" and _ar and _ar.get("fragmentation"):
        # ── Source : fichier uploadé ────────────────────────────────────
        pr   = _ar["fragmentation"]
        tot  = pr.get("totaux", {})
        st.info(pr.get("interpretation_globale", ""))
        c1, c2, c3, c4 = st.columns(4)
        _metric(c1, "IPP uniques",        tot.get("ipp_uniques", "—"))
        _metric(c2, "Patients récurrents", tot.get("patients_recurrents", "—"))
        _metric(c3, "% récurrents",        f"{tot.get('pct_recurrents', 0):.1f}", "%")
        _metric(c4, "Venues max",          tot.get("venues_max", "—"))
        dist = pr.get("distribution_venues", {})
        if dist:
            st.subheader("Distribution des venues")
            df_dist = pd.DataFrame([
                {"Tranche": k.replace("_", " "), "Patients": v} for k, v in dist.items()
            ])
            st.bar_chart(df_dist.set_index("Tranche"))
        st.caption(
            "Segments de fragmentation détaillés disponibles uniquement avec les exports globaux "
            "(bouton « Générer les exports » dans Paramétrage hospitalier)."
        )
    else:
        # ── Source : JSON de démonstration ─────────────────────────────
        pr = _load("pathway_reconstruction.json")
        fs = _load("fragmentation_segments.json")
        if not pr:
            st.warning("pathway_reconstruction.json introuvable.")
            st.stop()
        if "error" in pr:
            st.error(pr["error"])
            st.stop()
        st.info(pr.get("interpretation_globale", ""))
        tot = pr.get("totaux", {})
        c1, c2, c3, c4 = st.columns(4)
        _metric(c1, "IPP uniques",        tot.get("ipp_uniques", "—"))
        _metric(c2, "Patients récurrents", tot.get("patients_recurrents", "—"))
        _metric(c3, "% récurrents",        f"{tot.get('pct_recurrents', 0):.1f}", "%")
        _metric(c4, "Venues max",          tot.get("venues_max", "—"))
        st.subheader("Distribution des venues")
        dist = pr.get("distribution_venues", {})
        df_dist = pd.DataFrame([
            {"Tranche": k.replace("_", " "), "Patients": v} for k, v in dist.items()
        ])
        st.bar_chart(df_dist.set_index("Tranche"))
        if fs and "segments" in fs:
            st.subheader("Segments de fragmentation")
            df_seg = pd.DataFrame([
                {
                    "Tranche": s["label"], "Patients": s["n_patients"],
                    "Lignes": s["lignes_associees"], "Niveau": s["niveau_fragmentation"],
                    "Action": s["action_recommandee"],
                }
                for s in fs["segments"]
            ])
            st.dataframe(df_seg, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Scénarios HDJ":
    st.title("Matrice de scénarios HDJ")
    render_active_dataset_banner(page_updated=False)
    sm = _load("scenario_matrix.json")
    if not sm:
        st.warning("scenario_matrix.json introuvable.")
        st.stop()

    st.info(sm.get("recommandation", ""))

    synt = sm.get("synthese_comparative", {})
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Séjours référence", synt.get("volume_reference", "—"))
    _metric(c2, "Scénario prudent (A)", synt.get("volume_pmsi_guardrail", "—"))
    _metric(c3, "Réorganisation cible (B)", synt.get("volume_reorganisation_cible", "—"))
    _metric(c4, "Gain réorganisation vs prudent", f"+{synt.get('gain_reorganisation_vs_guardrail', 0)}", " séj.")

    st.subheader("Détail par scénario")
    for sc in sm.get("scenarios", []):
        with st.expander(f"**{sc['nom']}** — {sc.get('volume', 'N/A')} cas"):
            st.write(sc.get("description", ""))
            cols = st.columns(3)
            cols[0].write(f"**Population :** {sc.get('population_cible', '—')}")
            cols[1].write(f"**Statut PMSI :** {sc.get('statut_pmsi', '—')}")
            cols[2].write(f"**Confiance :** {sc.get('score_confiance', '—')}")
            st.caption(f"Validation : {sc.get('validation_requise', '—')}")

# ──────────────────────────────────────────────────────────────────────────
elif page == "Simulateur what-if":
    st.title("Simulateur what-if — Capacité HDJ")
    st.caption("Modifiez les paramètres pour observer l'impact sur la planification et l'occupation.")

    st.info(
        "Ce simulateur calcule dynamiquement la planification HDJ selon vos paramètres. "
        "Les durées sont issues du YAML métier. Les résultats sont à valider avec l'équipe soignante."
    )

    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        scenario_label = st.selectbox(
            "Population cible",
            ["Scénario prudent (5 cas)", "Réorganisation cible (33 cas)", "Patients récurrents (115 cas)"],
        )
        horizon = st.slider("Horizon de planification (jours)", min_value=2, max_value=30, value=5, step=1)
        chairs = st.slider("Fauteuils médicalisés disponibles", min_value=1, max_value=6, value=2)
    with col_ctrl2:
        retinos = st.slider("Rétinographes disponibles", min_value=0, max_value=3, value=1)
        val_rate = st.slider("Taux de validation DIM/PMSI (%)", min_value=0, max_value=100, value=100, step=5)
        priority_sel = st.selectbox(
            "Mode de priorité",
            ["Priorité stratégique", "Priorité volume (courts en premier)", "Patients récurrents en tête"],
        )
        tariff = st.number_input(
            "Forfait journalier HDJ de référence (€) — à valider DIM",
            min_value=100, max_value=2000, value=600, step=10
        )

    _SCENARIO_MAP = {
        "Scénario prudent (5 cas)": "baseline_A",
        "Réorganisation cible (33 cas)": "target_B",
        "Patients récurrents (115 cas)": "recurrent_grouping",
    }
    _PRIORITY_MAP = {
        "Priorité stratégique": "strategic",
        "Priorité volume (courts en premier)": "volume",
        "Patients récurrents en tête": "recurrent",
    }
    scenario_key = _SCENARIO_MAP[scenario_label]
    priority_key = _PRIORITY_MAP[priority_sel]
    val_float = val_rate / 100.0

    candidates = generate_scenario_candidates(scenario_key, validation_rate_B=val_float)
    result = run_capacity_what_if(
        candidates,
        horizon_days=horizon,
        chairs=chairs,
        retinographs=retinos,
        validation_rate_B=1.0,  # déjà appliqué dans generate
        priority_mode=priority_key,
        tariff_per_day=float(tariff),
    )

    st.markdown("---")
    st.subheader("Résultats de simulation")

    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Cas planifiés", result["planned_count"])
    _metric(c2, "Cas non planifiés", result["unplanned_count"])
    _metric(c3, "Attente moyenne", f"{result['mean_wait_days']:.1f}", " j")
    _metric(c4, "Attente max", f"{result['max_wait_days']}", " j")

    c5, c6, c7 = st.columns(3)
    _metric(c5, "Occupation fauteuil", f"{result['occupancy_chair_pct']:.0f}", "%")
    _metric(c6, "Occupation rétinographe", f"{result['occupancy_retinograph_pct']:.0f}", "%")

    bottleneck_color = "#d4edda" if result["unplanned_count"] == 0 else "#fff3cd"
    bottleneck_border = "#28a745" if result["unplanned_count"] == 0 else "#fd7e14"
    c7.markdown(f"""
<div style='background:{bottleneck_color};border-left:4px solid {bottleneck_border};
padding:10px;border-radius:4px;text-align:center'>
<div style='font-size:0.85rem;color:#555'>Goulot principal</div>
<div style='font-size:0.95rem;font-weight:700'>{result['bottleneck']}</div>
</div>""", unsafe_allow_html=True)

    # Message décisionnel
    msg_bg = "#d4edda" if result["unplanned_count"] == 0 else "#fff3cd"
    msg_border = "#28a745" if result["unplanned_count"] == 0 else "#ffc107"
    st.markdown(f"""
<div style='background:{msg_bg};border-left:5px solid {msg_border};padding:12px 16px;
border-radius:6px;margin:12px 0'>{result['decision_message']}</div>
""", unsafe_allow_html=True)

    if result.get("financial_estimate"):
        fe = result["financial_estimate"]
        st.caption(
            f"Valorisation indicative selon paramètre tarifaire : "
            f"**{fe['volume_planifie']} journées × {fe['tariff_reference']} € = "
            f"{fe['valorisation_indicative_euros']:,.0f} €** — {fe['note']}"
        )

    # Graphique planning journalier
    st.subheader("Planning journalier simulé")
    sched = result.get("daily_schedule", [])
    if sched:
        df_sched = pd.DataFrame([
            {
                "Jour": f"J{s['jour']}",
                "Séjours planifiés": s["sejours_planifies"],
                "Occupation fauteuil (%)": s["occupation_fauteuil_pct"],
            }
            for s in sched
        ]).set_index("Jour")
        col_g1, col_g2 = st.columns(2)
        col_g1.bar_chart(df_sched[["Séjours planifiés"]])
        col_g2.line_chart(df_sched[["Occupation fauteuil (%)"]])

    # Table journalière agrégée
    st.subheader("Détail journalier (agrégé — sans IPP)")
    df_detail = pd.DataFrame([
        {
            "Jour": s["jour"],
            "Séjours": s["sejours_planifies"],
            "Parcours (agrégés)": ", ".join(f"{k.replace('_',' ')}:{v}" for k,v in s["parcours"].items()),
            "Fauteuil utilisé (min)": s["minutes_fauteuil_utilisees"],
            "Fauteuil dispo (min)": s["minutes_fauteuil_disponibles"],
            "Occupation (%)": s["occupation_fauteuil_pct"],
        }
        for s in sched
    ])
    st.dataframe(df_detail, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Capacité / Saturation":
    st.title("Simulation de capacité HDJ")
    render_active_dataset_banner(page_updated=False)
    cap = _load("capacity_simulation.json")
    if not cap:
        st.warning("capacity_simulation.json introuvable.")
        st.stop()

    st.info(cap.get("recommandation", ""))

    bottleneck_msg = cap.get("capacity_message", "")
    if bottleneck_msg:
        st.markdown(f"""
<div style='background:#fff3cd;border-left:5px solid #fd7e14;padding:14px 18px;border-radius:6px;margin:8px 0'>
<b>Goulot principal : validation organisationnelle / PMSI</b><br>
{bottleneck_msg}
</div>
""", unsafe_allow_html=True)

    st.caption(cap.get("note", ""))

    st.subheader("Lecture capacitaire")
    st.markdown("""
- Sur le **volume scénario B actuel (33 cas)**, la capacité matérielle est suffisante en 5 jours — le goulot est la validation DIM/PMSI.
- La **saturation matérielle** apparaît lors du regroupement des patients récurrents (115 cas) ou en horizon très court (2 jours).
- Augmenter les fauteuils ou l'horizon permet d'absorber ce flux additionnel.
""")

    # Tableau enrichi depuis what-if results
    wif = _load("what_if_capacity_results.json")
    if wif and "configurations" in wif:
        rows = []
        for cfg in wif["configurations"]:
            rows.append({
                "Configuration": cfg["label"],
                "Volume cible": cfg["scenario_base"].replace("_", " "),
                "Planifiés": cfg["planned_count"],
                "Non planifiés": cfg["unplanned_count"],
                "Attente moy. (j)": cfg["mean_wait_days"],
                "Attente max (j)": cfg["max_wait_days"],
                "Fauteuil occ. (%)": cfg["occupancy_chair_pct"],
                "Goulot": cfg["bottleneck"],
                "Décision": cfg["decision_message"][:60] + "…" if len(cfg["decision_message"]) > 60 else cfg["decision_message"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=350)
        st.caption(wif.get("interpretation", ""))
    else:
        rows = []
        for cfg in cap.get("configurations", []):
            p = cfg.get("parametres", {})
            rB = cfg.get("resultats", {}).get("scenario_B", {})
            rows.append({
                "Configuration": cfg["label"],
                "Horizon (j)": p.get("horizon_jours"),
                "Fauteuil ×": p.get("fauteuil_total"),
                "Séjours B absorbables": rB.get("simules"),
                "Occupation fauteuil (%)": rB.get("fauteuil_occ_pct"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Priorisation HDJ":
    st.title("Priorisation des parcours HDJ")
    render_active_dataset_banner(page_updated=False)
    prior = _load("pathway_prioritization.json")
    recs = _load("decision_recommendations.json")
    if not prior:
        st.warning("pathway_prioritization.json introuvable.")
        st.stop()

    st.caption(prior.get("methodologie", ""))

    st.subheader("A — Parcours HDJ prioritaires")
    pathways = prior.get("ranked_hdj_pathways", prior.get("classement", []))
    df_p = pd.DataFrame([
        {
            "Rang": item["rang"],
            "Parcours": item["label"],
            "Volume": item["volume"],
            "Score": item["score_priorite"],
            "Faisabilité": item["faisabilite"],
            "Valeur strat.": item["valeur_strategique"],
            "Owners": ", ".join(item.get("owners_suggeres", [])),
        }
        for item in pathways
    ])
    st.dataframe(df_p.style.background_gradient(subset=["Score"], cmap="Greens"),
                 use_container_width=True)

    levers = prior.get("transversal_levers", [])
    if levers:
        st.subheader("B — Levier transversal")
        for lev in levers:
            st.markdown(f"""
<div style='background:#e8f4f8;border-left:5px solid #17a2b8;padding:14px 18px;border-radius:6px;margin-bottom:10px'>
<b>{lev['label']}</b><br>
{lev.get('description', '')}<br>
<b>Volume :</b> {lev['volume']} patients ({lev.get('pct_total', 0):.1f}% du total) ·
<b>Valeur stratégique :</b> {lev['valeur_strategique']}<br>
<b>Owners :</b> {', '.join(lev.get('owners_suggeres', []))}<br>
<i>{lev.get('note', '')}</i>
</div>
""", unsafe_allow_html=True)

    if recs:
        st.subheader("Recommandations décisionnelles (Top 3)")
        st.warning(recs.get("avertissement", ""))
        for i, r in enumerate(recs.get("recommandations", []), 1):
            with st.expander(f"{i}. {r['recommandation']}"):
                st.write(f"**Preuve :** {r['preuve_donnees']}")
                st.write("**Étapes :**")
                for e in r.get("etapes_mise_en_oeuvre", []):
                    st.write(f"  - {e}")
                st.write(f"**Owners :** {', '.join(r.get('owners', []))}")

    expl = _load("decision_explainability.json")
    if expl and "parcours" in expl:
        st.subheader("Pourquoi ces recommandations ?")
        for pw in expl["parcours"]:
            with st.expander(f"❓ {pw['label']} — {pw['decision_proposee']}"):
                sig = pw.get("signaux_donnees", {})
                st.write(f"**Données :** {sig.get('volume', '—')} cas · {sig.get('recurrence','—')}")
                st.write(f"**Ressources :** {sig.get('ressources','—')}")
                st.write(f"**Complexité :** {sig.get('complexite','—')}")
                st.info(pw.get("pourquoi_maintenant", ""))
                st.caption(pw.get("pourquoi_pas_facturable_directement", ""))
                st.write(f"**Prochaine action :** {pw.get('prochaine_action','—')}")
                st.write(f"**Validation requise :** {', '.join(pw.get('validation_requise',[]))}")

# ──────────────────────────────────────────────────────────────────────────
elif page == "Impact médico-économique":
    st.title("Estimation médico-économique")
    render_active_dataset_banner(page_updated=False)
    eco = _load("medico_economic_estimates.json")
    if not eco:
        st.warning("medico_economic_estimates.json introuvable.")
        st.stop()

    st.warning(eco.get("avertissement", ""))

    user_tariff = st.number_input(
        "Forfait journalier HDJ de référence (€) — paramètre à valider DIM/PMSI CHU Guyane",
        min_value=100, max_value=2000, value=600, step=10,
        help="Valeur d'exemple : 600 €. Remplacez par le tarif GHS HDJ validé par votre DIM.",
    )
    st.caption(
        f"Ces montants servent à **prioriser l'instruction DIM/PMSI**, "
        "pas à facturer directement. Non certifiés, non opposables."
    )

    vnf = eco.get("valeur_non_financiere", {})
    st.subheader("Valeur organisationnelle (non financière)")
    _VNF_LABELS = {
        "moins_de_deplacements": "Moins de déplacements patients",
        "meilleure_coordination": "Meilleure coordination soignants",
        "anticipation_ressources": "Anticipation des ressources",
        "aide_priorisation_gouvernance": "Aide à la priorisation et gouvernance",
    }
    for k, v in vnf.items():
        label = _VNF_LABELS.get(k, k.replace("_", " ").capitalize())
        st.write(f"- **{label}** : {v}")

    st.subheader("3 niveaux d'estimation indicative")
    for niv in eco.get("niveaux", []):
        vol = niv.get("volume_concerne", 0)
        with st.expander(f"**{niv['label']}** — {vol} cas"):
            st.write(niv.get("valeur_organisationnelle", niv.get("description", "")))
            st.write("**Valeur non financière :**")
            for v in niv.get("non_financial_value", []):
                st.write(f"  - {v}")
            # Recalcul dynamique avec le tarif saisi
            if isinstance(vol, int) and vol > 0:
                val_dyn = vol * user_tariff
                st.caption(
                    f"Valorisation indicative ({vol} cas × {user_tariff} €) = "
                    f"**{val_dyn:,.0f} €** — non certifiée, à valider DIM/PMSI."
                )
            else:
                st.caption("Valorisation : à calculer avec DIM après définition des protocoles.")
            st.caption(f"Validation requise : {niv.get('validation_requise', '—')}")

# ──────────────────────────────────────────────────────────────────────────
elif page == "Note de décision":
    st.title("Note de décision hospitalière")
    render_active_dataset_banner(page_updated=False)
    note_path = OUT / "note_decision_hospitaliere.md"
    if not note_path.exists():
        st.warning("note_decision_hospitaliere.md introuvable.")
        st.stop()
    content = note_path.read_text(encoding="utf-8")
    st.markdown(content)
    st.download_button(
        "Télécharger la note",
        data=content.encode("utf-8"),
        file_name="note_decision_hdj_agent.md",
        mime="text/markdown",
    )

# ── Paramétrage hospitalier ────────────────────────────────────────────────
elif page == "Paramétrage hospitalier":
    import io as _io
    import subprocess as _subprocess
    import yaml as _yaml

    st.title("Paramétrage hospitalier")
    st.caption("Adapter HDJ Agent à un autre hôpital et lancer l'analyse sans modifier le code.")
    st.info(
        "Depuis cette page, l'hôpital peut charger un export Excel/CSV pseudonymisé, "
        "vérifier les colonnes, simuler son organisation HDJ, puis lancer l'analyse HDJ Agent. "
        "Les modifications réalisées ici restent locales à la session."
    )

    # ── Charger le YAML une seule fois ──────────────────────────────────────
    yaml_ok = False
    yaml_cfg: dict = {}
    try:
        yaml_cfg = _yaml.safe_load(
            (Path(__file__).parent / "core/config/hdj_metier.yaml").read_text(encoding="utf-8")
        )
        yaml_ok = True
    except Exception as _e:
        st.warning(f"Impossible de lire le YAML métier : {_e}")

    # Schéma standard attendu
    STANDARD_SCHEMA: dict[str, str] = {
        "NUM SEJOUR":           "Identifiant séjour",
        "NUM IPP PATIENT":      "Identifiant patient pseudonymisé",
        "CODE DIAG":            "Diagnostic principal CIM-10",
        "LISTE ACTES CCAM MVT": "Actes CCAM",
        "TYPE SEJOUR":          "Type de séjour",
        "DATE ENTREE SEJ":      "Date d'entrée",
        "HEURE ENTREE SEJ":     "Heure d'entrée",
        "HEURE SORTIE SEJ":     "Heure de sortie",
    }
    REQUIRED_COLS = {"NUM SEJOUR", "CODE DIAG", "TYPE SEJOUR"}

    PATHWAY_LABELS = {
        "bilan_annuel_diabete":       "Bilan annuel diabète",
        "bilan_endocrino_metabolique":"Bilan endocrino-métabolique",
        "etp_diabete_obesite":        "ETP diabète / obésité",
        "test_dynamique_endocrinien": "Test dynamique endocrinien",
        "depistage_retinopathie":     "Dépistage rétinopathie",
        "already_hdj":                "Patients déjà HDJ (statu quo)",
        "bilan_angiopathies":         "Bilan angiopathies",
    }

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # Section 1 — Charger les données hospitalières
    # ═══════════════════════════════════════════════════════════════════════
    st.header("1 · Charger les données hospitalières")
    st.caption(
        "Le fichier doit contenir les séjours, patients pseudonymisés, diagnostics, actes CCAM, "
        "dates et horaires. **Aucun nom, prénom, adresse, téléphone ou mail ne doit être présent.**"
    )

    uploaded_file = st.file_uploader(
        "Déposer un fichier Excel ou CSV de séjours HDJ pseudonymisés",
        type=["xlsx", "xls", "csv"],
        key="param_uploader",
    )

    if uploaded_file is not None:
        _prev_fname = st.session_state.get("_upload_filename", "")
        try:
            if uploaded_file.name.endswith(".csv"):
                df_uploaded = pd.read_csv(uploaded_file, dtype=str)
            else:
                df_uploaded = pd.read_excel(_io.BytesIO(uploaded_file.read()), dtype=str)

            # Réinitialiser le mapping si nouveau fichier
            if uploaded_file.name != _prev_fname:
                st.session_state.pop("local_column_mapping", None)
                st.session_state.pop("analysis_summary", None)
                st.session_state.pop("active_results", None)
                st.session_state.pop("standardized_hospital_data", None)
                st.session_state.pop("_analysis_success_msg", None)
                if st.session_state.get("active_dataset_source") == "uploaded":
                    st.session_state["active_dataset_source"] = "demo"
                st.session_state["_upload_filename"] = uploaded_file.name

            st.session_state["uploaded_hospital_data"] = df_uploaded
            n_rows, n_cols = df_uploaded.shape
            st.success(f"Fichier chargé : **{n_rows} lignes**, **{n_cols} colonnes**.")
            st.dataframe(df_uploaded.head(5), use_container_width=True)
        except Exception as _e:
            st.error(f"Erreur de lecture du fichier : {_e}")
            st.session_state.pop("uploaded_hospital_data", None)
    elif "uploaded_hospital_data" in st.session_state:
        _fname = st.session_state.get("_upload_filename", "fichier inconnu")
        st.info(
            f"Données en session (`{_fname}`) : "
            f"**{len(st.session_state['uploaded_hospital_data'])} lignes** — "
            "non persisté sur disque."
        )

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # Section 2 — Vérifier et mapper les colonnes
    # ═══════════════════════════════════════════════════════════════════════
    st.header("2 · Vérifier et mapper les colonnes")

    df_session: pd.DataFrame | None = st.session_state.get("uploaded_hospital_data")
    if df_session is None:
        st.info("Chargez d'abord un fichier dans la section 1 pour vérifier le mapping.")
    else:
        detected_cols = set(df_session.columns.str.strip().str.upper())
        schema_cols = set(STANDARD_SCHEMA.keys())

        auto_match   = schema_cols & detected_cols
        missing_cols = schema_cols - detected_cols
        extra_cols   = detected_cols - schema_cols

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Colonnes reconnues", len(auto_match))
        with col_m2:
            st.metric("Colonnes manquantes", len(missing_cols))
        with col_m3:
            st.metric("Colonnes supplémentaires", len(extra_cols))

        # Initialiser le mapping en session
        if "local_column_mapping" not in st.session_state:
            st.session_state["local_column_mapping"] = {c: c for c in auto_match}

        # Mapping manuel pour les colonnes manquantes
        if missing_cols:
            st.subheader("Mapper les colonnes manquantes")
            st.caption(
                "Sélectionnez la colonne de votre fichier qui correspond à chaque champ standard. "
                "Choisissez « — non disponible — » si la colonne est absente."
            )
            available = ["— non disponible —"] + sorted(df_session.columns.tolist())
            for std_col in sorted(missing_cols):
                chosen = st.selectbox(
                    f"{STANDARD_SCHEMA[std_col]} → {std_col}",
                    options=available,
                    key=f"map_{std_col.replace(' ', '_')}",
                )
                if chosen != "— non disponible —":
                    st.session_state["local_column_mapping"][std_col] = chosen

        # Tableau récapitulatif
        mapping_now = st.session_state.get("local_column_mapping", {})
        mapping_rows = []
        for std_col, label in STANDARD_SCHEMA.items():
            if std_col in auto_match:
                status = "Reconnu automatiquement"
                local_col = std_col
            elif std_col in mapping_now and mapping_now[std_col] != std_col:
                status = "Mappé manuellement"
                local_col = mapping_now[std_col]
            else:
                status = "Manquant"
                local_col = "—"
            mapping_rows.append({
                "Champ standard HDJ Agent": f"{label} ({std_col})",
                "Colonne locale": local_col,
                "Statut": status,
            })
        st.dataframe(mapping_rows, use_container_width=True, hide_index=True)

        missing_required = REQUIRED_COLS - {
            c for c, v in mapping_now.items() if v != "— non disponible —"
        } - auto_match
        if missing_required:
            st.warning(
                f"Colonnes obligatoires non mappées : **{', '.join(missing_required)}**. "
                "L'analyse complète ne pourra pas être lancée."
            )
        else:
            st.success("Toutes les colonnes obligatoires sont disponibles.")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # Section 3 — Vérifier l'organisation HDJ
    # ═══════════════════════════════════════════════════════════════════════
    st.header("3 · Organisation de votre service HDJ")
    st.caption("Ajustez les ressources et l'équipe pour votre établissement. Ces valeurs restent en session.")

    # ── Ressources du service ────────────────────────────────────────────
    st.subheader("Ressources du service")
    if yaml_ok:
        mvp      = yaml_cfg.get("ressources_hdj", {}).get("mvp_ressources_goulot", {})
        horaires = yaml_cfg.get("contraintes_systeme", {}).get("horaires_simulation", {})
        default_fauteuils = int(mvp.get("fauteuil_medicalise", {}).get("quantite", 2))
        default_retinos   = int(mvp.get("retinographe", {}).get("quantite", 1))
        default_slots     = int(horaires.get("slots_par_jour", 6))
        default_horizon   = int(yaml_cfg.get("configuration_simulation", {}).get("horizon_jours", 5))
    else:
        default_fauteuils, default_retinos, default_slots, default_horizon = 2, 1, 6, 5

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        sim_fauteuils = st.slider("Fauteuils médicalisés", 1, 8, default_fauteuils,
                                   key="param_fauteuils", help="Nombre de fauteuils dans l'unité HDJ")
        sim_retinos   = st.slider("Rétinographes", 0, 3, default_retinos,
                                   key="param_retinos", help="Appareils de rétinographie non-mydriatique")
    with col_r2:
        sim_slots   = st.slider("Créneaux par jour", 2, 10, default_slots,
                                 key="param_slots", help="Séances par jour et par fauteuil")
        sim_horizon = st.slider("Horizon de simulation (jours)", 1, 30, default_horizon,
                                 key="param_horizon", help="Fenêtre de planification what-if")

    st.info(
        f"Session en cours : **{sim_fauteuils} fauteuils** · **{sim_retinos} rétinographes** · "
        f"**{sim_slots} créneaux/j** · horizon **{sim_horizon} j**  \n"
        "Ces valeurs alimentent aussi le Simulateur what-if."
    )

    # ── Soignants disponibles ────────────────────────────────────────────
    st.subheader("Soignants disponibles")
    if yaml_ok:
        roles_yaml  = yaml_cfg.get("roles_soignants", {})
        roles_data  = [
            {"Nom": v.get("nom_affichage", k), "Description": v.get("description", "—"),
             "Effectif actuel": v.get("nombre", "—")}
            for k, v in roles_yaml.items()
        ]
    else:
        roles_data = [
            {"Nom": "Endocrinologue",    "Description": "Médecin référent HDJ",          "Effectif actuel": 1},
            {"Nom": "IDE",               "Description": "Infirmier·ère diplômé·e d'état", "Effectif actuel": 2},
            {"Nom": "Ophtalmologue",     "Description": "Dépistage rétinopathie",         "Effectif actuel": 1},
            {"Nom": "Diététicienne",     "Description": "ETP nutrition",                   "Effectif actuel": 1},
        ]
    st.dataframe(roles_data, use_container_width=True, hide_index=True)

    with st.expander("Simuler un ajout de soignant (session uniquement)"):
        new_role_name  = st.text_input("Nom du rôle", value="Infirmier·ère de coordination", key="param_new_role")
        new_role_count = st.number_input("Nombre de postes", 1, 10, 1, key="param_new_role_count")
        if st.button("Ajouter à la session", key="param_add_role"):
            st.success(
                f"Rôle « {new_role_name} » ({new_role_count} poste(s)) ajouté pour cette session. "
                "Pour le rendre permanent, ajouter une entrée dans `roles_soignants` du YAML métier."
            )

    # ── Parcours HDJ pris en charge ──────────────────────────────────────
    st.subheader("Parcours HDJ pris en charge")
    if yaml_ok:
        pathways_yaml = yaml_cfg.get("candidate_pathways", {})
        items = pathways_yaml.items() if isinstance(pathways_yaml, dict) else (
            [(pw.get("id", str(i)), pw) for i, pw in enumerate(pathways_yaml) if isinstance(pw, dict)]
        )
        pw_data = []
        for pid, pdef in items:
            actes     = pdef.get("actes_ccam", pdef.get("actes_principaux", []))
            ressources= pdef.get("ressources_requises", [pdef.get("ressource_critique", "—")])
            duree     = pdef.get("duree_min", pdef.get("duree_minutes", "—"))
            if duree == "a_parametrer":
                duree = "À définir"
            elif duree != "—":
                duree = str(duree)
            pw_data.append({
                "Parcours":         PATHWAY_LABELS.get(pid, pid),
                "Durée (min)":      duree,
                "Actes CCAM":       ", ".join(actes[:3]) if actes else "—",
                "Ressource":        ressources[0] if ressources else "—",
                "Validation PMSI":  "Requise" if pdef.get("pmsi_validation_required", True) else "Non requise",
            })
        if pw_data:
            st.dataframe(pw_data, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun parcours défini dans le YAML.")
    else:
        st.info("YAML non disponible — parcours non affichés.")

    with st.expander("Détail technique pour l'équipe data / SIH"):
        st.markdown(
            "- **YAML métier** : `core/config/hdj_metier.yaml`\n"
            "- **Contrat de données** : `HDJ_Agent_modele_donnees.xlsx`\n"
            "- **Outputs** : `outputs/` (JSON + Markdown)\n"
            "- **Règle** : Streamlit ne modifie jamais le YAML. "
            "Les sliders et formulaires restent en `st.session_state`.\n"
            "- **Mise en production** : mettre à jour le YAML, relancer `export_dashboard_outputs.py`."
        )

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # Section 4 — Lancer l'analyse HDJ Agent
    # ═══════════════════════════════════════════════════════════════════════
    st.header("4 · Lancer l'analyse HDJ Agent")
    st.caption(
        "Les ajustements faits dans cette interface sont simulés pour la session. "
        "Pour une mise en production, ils doivent être validés puis reportés dans la configuration métier. "
        "**Le YAML métier n'est jamais modifié depuis l'interface.**"
    )

    # Message succès persistant (affiché après rerun)
    _success_msg = st.session_state.pop("_analysis_success_msg", None)
    if _success_msg:
        st.success(_success_msg)

    df_for_analysis: pd.DataFrame | None = st.session_state.get("uploaded_hospital_data")
    mapping_for_analysis: dict           = st.session_state.get("local_column_mapping", {})

    auto_match_cols = set()
    if df_for_analysis is not None:
        auto_match_cols = set(STANDARD_SCHEMA.keys()) & set(df_for_analysis.columns.str.strip().str.upper())

    # Vérifier les colonnes manquantes pour les colonnes obligatoires
    all_mapped = mapping_for_analysis | {c: c for c in auto_match_cols}
    missing_required_for_run = REQUIRED_COLS - set(all_mapped.keys())

    if st.button("Lancer l'analyse HDJ Agent", type="primary", key="param_run_analysis"):
        if df_for_analysis is None:
            st.warning("Veuillez d'abord charger un fichier Excel/CSV pseudonymisé (section 1).")
        elif missing_required_for_run:
            st.warning(
                f"Certaines colonnes nécessaires ne sont pas reconnues ou mappées : "
                f"**{', '.join(missing_required_for_run)}**. "
                "Complétez le mapping en section 2."
            )
        else:
            with st.spinner("Analyse en cours…"):
                # ── Standardisation en mémoire (pas d'écriture disque) ──────
                df_std = df_for_analysis.copy()
                df_std.columns = df_std.columns.str.strip().str.upper()
                for std_col, local_col in all_mapped.items():
                    local_upper = local_col.strip().upper()
                    if local_upper in df_std.columns and local_upper != std_col:
                        df_std[std_col] = df_std[local_upper]
                st.session_state["standardized_hospital_data"] = df_std

                # ── Métriques de base ────────────────────────────────────────
                n_sejours  = len(df_std)
                n_patients = int(df_std["NUM IPP PATIENT"].nunique()) if "NUM IPP PATIENT" in df_std.columns else None
                n_diags    = int(df_std["CODE DIAG"].nunique()) if "CODE DIAG" in df_std.columns else None

                n_hdj = None
                dist_type: dict = {}
                if "TYPE SEJOUR" in df_std.columns:
                    ts = df_std["TYPE SEJOUR"].str.upper().str.strip()
                    n_hdj = int((ts == "HDJ").sum())
                    dist_type = {str(k): int(v) for k, v in ts.value_counts().items()}

                top_diags = []
                if "CODE DIAG" in df_std.columns:
                    top_diags = (
                        df_std["CODE DIAG"].str[:3]
                        .value_counts().head(5).reset_index()
                        .rename(columns={"CODE DIAG": "Catégorie CIM-10", "count": "Nb séjours"})
                        .to_dict("records")
                    )

                taux_ccam = None
                if "LISTE ACTES CCAM MVT" in df_std.columns:
                    taux_ccam = round(df_std["LISTE ACTES CCAM MVT"].notna().mean() * 100, 1)

                duree_moy = None
                if "HEURE ENTREE SEJ" in df_std.columns and "HEURE SORTIE SEJ" in df_std.columns:
                    try:
                        t_in  = pd.to_datetime(df_std["HEURE ENTREE SEJ"], format="%H:%M", errors="coerce")
                        t_out = pd.to_datetime(df_std["HEURE SORTIE SEJ"], format="%H:%M", errors="coerce")
                        durees = (t_out - t_in).dt.total_seconds() / 60
                        duree_moy = round(float(durees[durees > 0].mean()), 0)
                    except Exception:
                        pass

                # ── Alertes ──────────────────────────────────────────────────
                alertes = []
                if taux_ccam is not None and taux_ccam < 30:
                    alertes.append(f"Actes CCAM : seulement {taux_ccam:.0f}% de lignes renseignées — couverture faible.")
                if duree_moy is None and "HEURE ENTREE SEJ" in df_std.columns:
                    alertes.append("Durées non calculables — format horaire non reconnu (attendu HH:MM).")
                if n_diags is not None and n_diags < 2:
                    alertes.append("Peu de diagnostics distincts — vérifier la colonne CODE DIAG.")

                # ── Qualité et fragmentation ─────────────────────────────────
                quality     = _build_quality_from_df(df_std)
                fragmentation = _build_fragmentation_from_df(df_std)

                # ── Parcours YAML disponibles ────────────────────────────────
                yaml_pathways_list = []
                if yaml_ok:
                    pw_yaml = yaml_cfg.get("candidate_pathways", {})
                    if isinstance(pw_yaml, dict):
                        yaml_pathways_list = [PATHWAY_LABELS.get(k, k) for k in pw_yaml.keys()]

                # ── Résultats actifs ─────────────────────────────────────────
                active_results = {
                    "nb_sejours":          n_sejours,
                    "nb_patients_ipp":     n_patients,
                    "nb_diags_distincts":  n_diags,
                    "nb_sejours_hdj":      n_hdj,
                    "distribution_type_sejour": dist_type,
                    "top_diags":           top_diags,
                    "taux_ccam_pct":       taux_ccam,
                    "duree_moy_min":       duree_moy,
                    "alertes":             alertes,
                    "quality":             quality,
                    "fragmentation":       fragmentation,
                    "ressources_session":  {
                        "fauteuils": sim_fauteuils, "retinos": sim_retinos,
                        "slots_j": sim_slots, "horizon_j": sim_horizon,
                    },
                    "parcours_yaml_disponibles": yaml_pathways_list,
                }
                st.session_state["analysis_summary"] = active_results
                st.session_state["active_results"]   = active_results
                st.session_state["active_dataset_source"] = "uploaded"
                st.session_state["_analysis_success_msg"] = (
                    f"Analyse terminée — {n_sejours} séjours, "
                    f"{n_patients or '?'} patients, "
                    f"{n_diags or '?'} diagnostics distincts. "
                    "Les pages principales sont actualisées — consultez les résultats en section 5 ci-dessous."
                )
                st.rerun()

    # ── Bouton exports ───────────────────────────────────────────────────
    st.caption("Pour regénérer les exports globaux (scénarios A/B, plannings, note de décision) :")
    if st.button("Générer / actualiser les exports de démonstration", key="param_run_export"):
        with st.spinner("Génération des exports en cours (peut prendre 30–60 s)…"):
            try:
                result = _subprocess.run(
                    ["python", "export_dashboard_outputs.py"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(Path(__file__).parent),
                )
                if result.returncode == 0:
                    st.success(
                        "Exports générés avec succès dans `outputs/`.  \n"
                        + result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "OK"
                    )
                else:
                    st.error(f"Erreur lors de la génération :\n```\n{result.stderr[-800:]}\n```")
            except _subprocess.TimeoutExpired:
                st.error("Timeout : la génération a dépassé 120 secondes.")
            except Exception as _e:
                st.error(f"Erreur inattendue : {_e}")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # Section 5 — Résultats et exports
    # ═══════════════════════════════════════════════════════════════════════
    st.header("5 · Résultats et exports")
    st.caption(
        "Dans cette démonstration, l'analyse du fichier uploadé reste locale à la session. "
        "Les exports globaux sont générés dans `outputs/`."
    )

    analysis: dict | None = st.session_state.get("analysis_summary")
    if analysis:
        st.subheader("Résumé de l'analyse session")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Séjours",              analysis["nb_sejours"])
        c2.metric("Patients (IPP)",       analysis.get("nb_patients_ipp") or "—")
        c3.metric("Diagnostics distincts",analysis.get("nb_diags_distincts") or "—")
        c4.metric("Séjours HDJ",          analysis.get("nb_sejours_hdj") if analysis.get("nb_sejours_hdj") is not None else "—")

        c5, c6 = st.columns(2)
        _tccam = analysis.get("taux_ccam_pct")
        c5.metric("Taux CCAM renseigné", f"{_tccam:.0f} %" if _tccam is not None else "—")
        _dur = analysis.get("duree_moy_min")
        import math as _math
        c6.metric("Durée moy. séjour", f"{int(_dur)} min" if _dur and not _math.isnan(_dur) else "—")

        top = analysis.get("top_diags") or analysis.get("top_categories_diag", [])
        if top:
            st.markdown("**Principales catégories diagnostiques :**")
            st.dataframe(top, use_container_width=True, hide_index=True)

        dist_t = analysis.get("distribution_type_sejour")
        if dist_t:
            st.markdown("**Distribution types de séjour :**")
            df_dt = pd.DataFrame([{"Type": k, "Nb": v} for k, v in dist_t.items()])
            st.dataframe(df_dt, use_container_width=True, hide_index=True)

        for _al in analysis.get("alertes", []):
            st.warning(_al)

        res = analysis["ressources_session"]
        st.markdown(
            f"**Ressources simulées :** {res['fauteuils']} fauteuil(s) · "
            f"{res['retinos']} rétinographe(s) · {res['slots_j']} créneaux/j · "
            f"horizon {res['horizon_j']} j"
        )
        if analysis.get("parcours_yaml_disponibles"):
            st.markdown(
                "**Parcours HDJ disponibles :** "
                + ", ".join(analysis["parcours_yaml_disponibles"])
            )
    else:
        st.info("Lancez l'analyse (section 4) pour voir les résultats ici.")

    # ── Fichiers exports disponibles ─────────────────────────────────────
    st.subheader("Exports disponibles dans `outputs/`")
    out_dir = Path(__file__).parent / "outputs"
    key_outputs = [
        ("note_decision_hospitaliere.md", "Note de décision hospitalière"),
        ("configuration_template.json",   "Template de configuration"),
        ("kpi_summary.json",              "KPIs scénarios A/B"),
        ("what_if_capacity_results.json", "Résultats what-if (8 configs)"),
        ("pathway_prioritization.json",   "Parcours HDJ prioritaires"),
        ("operational_action_plan.json",  "Plan d'action opérationnel"),
    ]
    rows_out = []
    for fname, label in key_outputs:
        fpath = out_dir / fname
        rows_out.append({
            "Fichier": fname,
            "Description": label,
            "Disponible": "Oui" if fpath.exists() else "Non — relancer les exports",
        })
    st.dataframe(rows_out, use_container_width=True, hide_index=True)

    note_path = out_dir / "note_decision_hospitaliere.md"
    if note_path.exists():
        st.download_button(
            "Télécharger la note de décision",
            data=note_path.read_text(encoding="utf-8").encode("utf-8"),
            file_name="note_decision_hdj_agent.md",
            mime="text/markdown",
            key="param_dl_note",
        )

# ── Modélisation parcours patient ─────────────────────────────────────────
elif page == "Modélisation parcours patient":
    import subprocess as _subprocess
    try:
        from demo_parcours_animation import infer_representative_parcours_from_active_data
        _anim_import_ok = True
    except Exception as _anim_import_err:
        _anim_import_ok = False

    st.title("Modélisation parcours patient")
    st.caption("Simulation multi-agents du déplacement d'un patient dans l'HDJ")

    st.markdown(
        "Cette animation visualise un parcours patient représentatif et les interactions "
        "opérationnelles du service : déplacements, attentes, occupation des ressources "
        "et interventions des soignants."
    )

    active_source   = st.session_state.get("active_dataset_source", "demo")
    df_active       = st.session_state.get("standardized_hospital_data")
    analysis_result = st.session_state.get("active_results")

    if active_source == "uploaded" and df_active is not None:
        st.success(
            "Mode établissement — animation contextualisée à partir du fichier uploadé "
            "pendant cette session."
        )
        st.info(
            "Les données uploadées permettent de contextualiser l'animation, mais ne contiennent "
            "pas encore toutes les étapes spatiales réelles du patient. L'animation utilise donc "
            "un scénario typique dérivé des données actives."
        )
        if _anim_import_ok:
            inferred = infer_representative_parcours_from_active_data(df_active)
        else:
            inferred = {
                "parcours_type": "demo",
                "type":          "Parcours démo (import indisponible)",
                "raison":        str(_anim_import_err),
                "nb_sejours":    None,
            }
    else:
        st.info("Mode démonstration — animation générée à partir d'un parcours patient exemple.")
        inferred = {
            "parcours_type": "demo",
            "type":          "Parcours démo complet",
            "raison":        "Aucun fichier hospitalier actif.",
            "nb_sejours":    None,
        }

    # ── Fiche parcours ───────────────────────────────────────────────────────
    col_i1, col_i2, col_i3 = st.columns(3)
    col_i1.metric(
        "Source active",
        "Fichier uploadé (session)" if active_source == "uploaded" else "Démonstration",
    )
    col_i2.metric(
        "Séjours analysés",
        inferred["nb_sejours"] if inferred["nb_sejours"] is not None else "—",
    )
    col_i3.metric("Parcours choisi", inferred["type"])
    st.caption(f"Raison : {inferred['raison']}")

    # ── Bouton génération ────────────────────────────────────────────────────
    gif_path      = Path("outputs/plan_balade_soignants.gif")
    parcours_type = inferred.get("parcours_type", "demo")

    if st.button("Générer / regénérer l'animation", type="primary", key="parcours_regen"):
        with st.spinner("Simulation multi-agents en cours…"):
            _res = _subprocess.run(
                ["python", "demo_parcours_animation.py",
                 "--parcours-type", parcours_type],
                capture_output=True, text=True, timeout=120,
                cwd=str(Path(__file__).parent),
            )
        if _res.returncode == 0:
            st.success("Animation générée avec succès.")
        else:
            st.error("Erreur lors de la génération de l'animation.")
            st.code(_res.stdout + _res.stderr, language="text")

    # ── Affichage GIF ────────────────────────────────────────────────────────
    if gif_path.exists() and gif_path.stat().st_size > 0:
        st.image(str(gif_path), caption=f"Simulation spatiale — {inferred['type']}")
    else:
        st.warning(
            "L'animation n'est pas encore disponible. "
            "Cliquez sur « Générer / regénérer l'animation » pour la produire."
        )
