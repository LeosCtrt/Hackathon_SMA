"""
HDJ Agent — Interface hospitalière d'aide à la décision.

Lecture seule des outputs JSON générés par export_dashboard_outputs.py.
Ne pas afficher d'IPP individuel.

Lancement : streamlit run streamlit_app.py
"""

import json
from pathlib import Path

import streamlit as st
import pandas as pd

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


# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.title("HDJ Agent")
st.sidebar.caption("CHU Guyane — Endocrino-Diabétologie")
st.sidebar.markdown("---")

pages = [
    "Synthèse exécutive",
    "Qualité des données",
    "Fragmentation IPP",
    "Scénarios HDJ",
    "Capacité / Saturation",
    "Priorisation HDJ",
    "Impact médico-économique",
    "Note de décision",
]
page = st.sidebar.radio("Navigation", pages)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Outil d'aide à la décision organisationnelle.  \n"
    "Validation DIM/PMSI requise avant mise en œuvre."
)

# ──────────────────────────────────────────────────────────────────────────
if page == "Synthèse exécutive":
    st.title("HDJ Agent — Outil hospitalier d'aide à la décision")
    st.caption("CHU Guyane · Endocrinologie-Diabétologie · Simulation restructuration ambulatoire")

    kpi = _load("kpi_summary.json")
    if not kpi:
        st.warning("Fichier kpi_summary.json introuvable. Lancez `python export_dashboard_outputs.py`.")
        st.stop()

    st.warning(kpi["meta"].get("avertissement", ""))

    vol = kpi.get("volume", {})
    sc_A = kpi.get("scenario_A", {})
    sc_B = kpi.get("scenario_B", {})
    rec = kpi.get("patients_recurrents", {})

    st.subheader("Chiffres clés")
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Séjours analysés", vol.get("total_sejours_analyses", "—"))
    _metric(c2, "Planifiés Scénario A", sc_A.get("planifies", "—"))
    _metric(c3, "Simulés Scénario B", sc_B.get("simules", "—"))
    _metric(c4, "Gain B vs A", f"+{sc_B.get('gain_vs_A', 0)}", " séj.")

    st.subheader("Fragmentation patients")
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "IPP uniques", rec.get("ipp_uniques", "—"))
    _metric(c2, "Patients récurrents", rec.get("patients_recurrents", "—"))
    _metric(c3, "% récurrents", rec.get("pct_recurrents", "—"), "%")
    _metric(c4, "Venues max / patient", rec.get("venues_max", "—"))

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
    q = _load("data_quality_report.json")
    if not q:
        st.warning("data_quality_report.json introuvable.")
        st.stop()

    verdict = q.get("verdict", "")
    detail = q.get("verdict_detail", "")
    if verdict == "usable_for_decision_support":
        st.markdown(f"<div class='ok-box'>✅ <b>{verdict}</b> — {detail}</div>", unsafe_allow_html=True)
    elif verdict == "usable_with_warnings":
        st.markdown(f"<div class='warn-box'>⚠️ <b>{verdict}</b> — {detail}</div>", unsafe_allow_html=True)
    else:
        st.error(f"❌ {verdict} — {detail}")

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
    _metric(c1, "IPP uniques", tot.get("ipp_uniques", "—"))
    _metric(c2, "Patients récurrents", tot.get("patients_recurrents", "—"))
    _metric(c3, "% récurrents", f"{tot.get('pct_recurrents', 0):.1f}", "%")
    _metric(c4, "Venues max", tot.get("venues_max", "—"))

    st.subheader("Distribution des venues")
    dist = pr.get("distribution_venues", {})
    df_dist = pd.DataFrame([
        {"Tranche": k.replace("_", " "), "Patients": v}
        for k, v in dist.items()
    ])
    st.bar_chart(df_dist.set_index("Tranche"))

    if fs and "segments" in fs:
        st.subheader("Segments de fragmentation")
        df_seg = pd.DataFrame([
            {
                "Tranche": s["label"],
                "Patients": s["n_patients"],
                "Lignes": s["lignes_associees"],
                "Niveau": s["niveau_fragmentation"],
                "Action": s["action_recommandee"],
            }
            for s in fs["segments"]
        ])
        st.dataframe(df_seg, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Scénarios HDJ":
    st.title("Matrice de scénarios HDJ")
    sm = _load("scenario_matrix.json")
    if not sm:
        st.warning("scenario_matrix.json introuvable.")
        st.stop()

    st.info(sm.get("recommandation", ""))

    synt = sm.get("synthese_comparative", {})
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Séjours référence", synt.get("volume_reference", "—"))
    _metric(c2, "PMSI guardrail (A)", synt.get("volume_pmsi_guardrail", "—"))
    _metric(c3, "Réorganisation (B)", synt.get("volume_reorganisation_cible", "—"))
    _metric(c4, "Gain B vs A", f"+{synt.get('gain_reorganisation_vs_guardrail', 0)}", " séj.")

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
elif page == "Capacité / Saturation":
    st.title("Simulation de capacité HDJ")
    cap = _load("capacity_simulation.json")
    if not cap:
        st.warning("capacity_simulation.json introuvable.")
        st.stop()

    st.info(cap.get("recommandation", ""))
    st.caption(cap.get("note", ""))

    rows = []
    for cfg in cap.get("configurations", []):
        p = cfg.get("parametres", {})
        rA = cfg.get("resultats", {}).get("scenario_A", {})
        rB = cfg.get("resultats", {}).get("scenario_B", {})
        rows.append({
            "Configuration": cfg["label"],
            "Horizon (j)": p.get("horizon_jours"),
            "Places/créneau": p.get("places_creneau"),
            "Rétino ×": p.get("retinographe_total"),
            "Fauteuil ×": p.get("fauteuil_total"),
            "Planifiés A": rA.get("planifies"),
            "Simulés B": rB.get("simules"),
            "Gain vs base B": cfg.get("gain_vs_baseline_B"),
            "Fauteuil occ B (%)": rB.get("fauteuil_occ_pct"),
            "Goulot": cfg.get("goulot_detranglement"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Priorisation HDJ":
    st.title("Priorisation des parcours HDJ")
    prior = _load("pathway_prioritization.json")
    recs = _load("decision_recommendations.json")
    if not prior:
        st.warning("pathway_prioritization.json introuvable.")
        st.stop()

    st.caption(prior.get("methodologie", ""))

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
        for item in prior.get("classement", [])
    ])
    st.dataframe(df_p.style.background_gradient(subset=["Score"], cmap="Greens"),
                 use_container_width=True)

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

# ──────────────────────────────────────────────────────────────────────────
elif page == "Impact médico-économique":
    st.title("Estimation médico-économique")
    eco = _load("medico_economic_estimates.json")
    if not eco:
        st.warning("medico_economic_estimates.json introuvable.")
        st.stop()

    st.warning(eco.get("avertissement", ""))
    st.info(eco.get("note_estimation", ""))

    vnf = eco.get("valeur_non_financiere", {})
    st.subheader("Valeur non financière")
    for k, v in vnf.items():
        st.write(f"- **{k.replace('_', ' ').capitalize()}** : {v}")

    st.subheader("3 niveaux d'estimation")
    for niv in eco.get("niveaux", []):
        with st.expander(f"**{niv['label']}** — {niv['volume_concerne']} cas"):
            st.write(niv.get("description", ""))
            st.write(f"**Hypothèse :** {niv.get('hypothese', '—')}")
            pot = niv.get("potentiel_valorisation_a_valider", "—")
            if isinstance(pot, (int, float)):
                st.metric("Valorisation estimée (à valider DIM)", f"{pot:,.0f}€")
            else:
                st.write(f"**Valorisation :** {pot}")
            st.caption(f"Validation requise : {niv.get('validation_requise', '—')}")
            st.write("**Valeur non financière :**")
            for v in niv.get("non_financial_value", []):
                st.write(f"  - {v}")

# ──────────────────────────────────────────────────────────────────────────
elif page == "Note de décision":
    st.title("Note de décision hospitalière")
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
