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

    st.info(
        "Données TYPE_SEJOUR=EXT (consultations externes) — "
        "simulation organisationnelle à valider DIM/PMSI avant mise en œuvre."
    )

    vol = kpi.get("volume", {})
    sc_A = kpi.get("scenario_A", {})
    sc_B = kpi.get("scenario_B", {})
    rec = kpi.get("patients_recurrents", {})

    st.subheader("Chiffres clés")
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Séjours analysés", vol.get("total_sejours_analyses", "—"))
    _metric(c2, "Scénario prudent (A)", sc_A.get("planifies", "—"))
    _metric(c3, "Scénario réorganisation (B)", sc_B.get("simules", "—"))
    _metric(c4, "Gain réorganisation vs prudent", f"+{sc_B.get('gain_vs_A', 0)}", " séj.")

    st.subheader("Fragmentation patients")
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "IPP uniques", rec.get("ipp_uniques", "—"))
    _metric(c2, "Patients récurrents", rec.get("patients_recurrents", "—"))
    _metric(c3, "% récurrents", rec.get("pct_recurrents", "—"), "%")
    _metric(c4, "Venues max / patient", rec.get("venues_max", "—"))

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
- Données IPP réelles disponibles (2020–2026, 249 patients uniques)
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
elif page == "Capacité / Saturation":
    st.title("Simulation de capacité HDJ")
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
- La capacité matérielle actuelle permet d'absorber les **33 séjours simulés** du scénario de réorganisation.
- L'ajout de fauteuils ou rétinographes réduit l'occupation, mais n'augmente pas le volume tant que la **validation DIM/PMSI** et les **protocoles HDJ** ne sont pas formalisés.
- Le goulot principal est **organisationnel et réglementaire**, pas matériel.
""")

    rows = []
    for cfg in cap.get("configurations", []):
        p = cfg.get("parametres", {})
        rB = cfg.get("resultats", {}).get("scenario_B", {})
        rows.append({
            "Configuration": cfg["label"],
            "Horizon (j)": p.get("horizon_jours"),
            "Places/créneau": p.get("places_creneau"),
            "Rétino ×": p.get("retinographe_total"),
            "Fauteuil ×": p.get("fauteuil_total"),
            "Séjours B absorbables": rB.get("simules"),
            "Occupation fauteuil B (%)": rB.get("fauteuil_occ_pct"),
            "Message": cfg.get("message_decisionnel", "—"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=280)

# ──────────────────────────────────────────────────────────────────────────
elif page == "Priorisation HDJ":
    st.title("Priorisation des parcours HDJ")
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

# ──────────────────────────────────────────────────────────────────────────
elif page == "Impact médico-économique":
    st.title("Estimation médico-économique")
    eco = _load("medico_economic_estimates.json")
    if not eco:
        st.warning("medico_economic_estimates.json introuvable.")
        st.stop()

    st.warning(eco.get("avertissement", ""))

    st.markdown("""
<div style='background:#fff3cd;border-left:5px solid #ffc107;padding:12px 16px;border-radius:6px;margin-bottom:12px'>
<b>Hypothèse paramétrable</b> : forfait journalier HDJ de référence.<br>
Valeur d'exemple : <b>420 €/journée</b>, à remplacer par le tarif validé DIM/PMSI du CHU Guyane.<br>
<small>Les montants affichés ci-dessous sont indicatifs — non certifiés, non opposables.</small>
</div>
""", unsafe_allow_html=True)

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
        with st.expander(f"**{niv['label']}** — {niv['volume_concerne']} cas"):
            st.write(niv.get("valeur_organisationnelle", niv.get("description", "")))
            st.write("**Valeur non financière :**")
            for v in niv.get("non_financial_value", []):
                st.write(f"  - {v}")
            pot = niv.get("potentiel_valorisation_a_valider", "—")
            if isinstance(pot, (int, float)):
                st.caption(
                    f"Valorisation indicative selon paramètre tarifaire : {pot:,.0f} € — non certifiée."
                )
            else:
                st.caption(f"Valorisation : {pot}")
            st.caption(f"Validation requise : {niv.get('validation_requise', '—')}")

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
