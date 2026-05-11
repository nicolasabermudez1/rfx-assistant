# Category Strategy — Data Centre Cooling Systems

**Category code:** IT-INF-DC-COOL-2026
**Sponsor:** Mark Hendricks, Director of IT Infrastructure (British Gas)
**Category lead:** Priya Rai, Senior Category Manager — IT & Digital
**Spend baseline (FY25):** £14.7m across 11 active suppliers
**Target spend (FY26):** £18.2m (rebalanced to 3–4 strategic suppliers)
**Status:** Approved at Procurement Council, 12 February 2026

---

## 1. Business context

Centrica plc — operating across British Gas, Centrica Business Solutions, Bord Gáis Energy, Centrica Energy Storage, and Spirit Energy — is consolidating its IT estate as part of the FY26–FY28 *Connected Home & Net Zero Infrastructure* programme.

The smart-meter data platform (which now ingests **~14 billion meter reads per month** from 11.6m installed SMETS2 endpoints) is being moved from a single Slough-based facility into **four regional edge data centres** (Slough, Manchester, Glasgow, Cardiff). Each new site has a 5–8 MW IT load and a Tier III+ availability target.

This category strategy covers cooling for those four sites plus the in-flight refresh of two existing facilities (Hams Hall, Reading). Cooling represents **~38% of operational PUE drag** at our current data centres and is therefore the single largest lever for hitting our 2030 Scope 2 reduction target (–55% vs 2022 baseline).

## 2. Demand signal

| Site | IT load (MW) | Cooling load (MW) | RFP scope | Go-live |
|---|---|---|---|---|
| Slough East (new) | 8.0 | 9.6 | Full chilled water + CRAH | Q4 2026 |
| Manchester Trafford (new) | 6.5 | 7.8 | Full chilled water + CRAH | Q1 2027 |
| Glasgow Eurocentral (new) | 5.0 | 6.0 | Full chilled water + CRAH | Q2 2027 |
| Cardiff Imperial Park (new) | 5.0 | 6.0 | Full chilled water + CRAH | Q3 2027 |
| Hams Hall (refresh) | 4.0 | 4.8 | CRAH refresh + free cooling retrofit | Q3 2026 |
| Reading West (refresh) | 3.5 | 4.2 | CRAH refresh + economiser retrofit | Q4 2026 |
| **Total** | **32.0** | **38.4** | | |

## 3. Strategic priorities

1. **Net zero alignment.** Centrica's Group target is net zero operational emissions by 2045, with –55% by 2030. Cooling is the largest single workstream feeding into our 2030 Scope 2 plan.
2. **Resilience.** SMETS2 data ingestion is now a regulated obligation under the Smart Energy Code. Any cooling outage that takes the platform offline is a reportable incident to Ofgem.
3. **Total cost of ownership.** Energy at industrial rates is currently £138/MWh (Q1 2026 average across our four supply points). A 0.05 PUE improvement saves £1.92m per year at full Q4-2027 IT load.
4. **Skilled-labour resilience.** Maintenance must be deliverable by both the supplier's own field engineers and our incumbent FM partner (Mitie). No single-source maintenance lock-in.
5. **Water stewardship.** Two of the four new sites (Manchester, Cardiff) sit in catchments classified as "moderate stress" by the Environment Agency — adiabatic / water-side economisers must report make-up water consumption.

## 4. Sourcing approach

A two-stage RFP, published via SAP Ariba Sourcing:
- **Stage 1 (RFI):** Open invitation, ~6 weeks. Capability shortlist down to 5.
- **Stage 2 (RFP):** This document. ~10 weeks. Three-supplier shortlist for SME panel review, single award per regional cluster.

Allocation is by regional cluster:
- **Cluster A:** Slough East + Hams Hall + Reading West (south of M4 corridor)
- **Cluster B:** Manchester Trafford + Glasgow Eurocentral
- **Cluster C:** Cardiff Imperial Park

A supplier may bid for one, two, or all three clusters. We will not award all three to a single supplier (single-source risk).

## 5. Mandatory requirements

- **Tier III+ uptime certification** of CRAH unit families bid (Uptime Institute or TIA-942 evidence).
- **N+1 redundancy** on every cooling subsystem — chilled water plant, CRAH, pumps, controls.
- **PUE design point ≤ 1.25** at full IT load, ASHRAE A1 envelope, UK climate.
- **Water-side economiser or equivalent free cooling** active for ≥ 4,200 hours/year (UK Met Office TMY3).
- **F-Gas Regulation (EU 517/2014, retained UK law)** compliance — refrigerants with GWP ≤ 675 only.
- **ISO 14001, ISO 45001, ISO 27001** at corporate and site level for all maintenance activities.
- **Modern Slavery Act 2015 statement** + tier-2 supply chain disclosure.
- **24/7/365 UK-based critical-response engineering**, 4-hour response SLA, 8-hour fix SLA.

## 6. Evaluation framework (preview — full criteria in §7 of the RFP)

| Pillar | Weight | Notes |
|---|---|---|
| Commercial (CapEx + 10-yr OpEx) | 30% | NPV at 6.5% discount rate |
| Technical fit | 25% | SME-led — Procurement does NOT score |
| Sustainability & PUE | 15% | PUE design point + lifecycle carbon |
| Resilience & SLA | 12% | Tier compliance + outage history |
| Implementation plan | 8% | Phased to match site go-lives |
| Innovation | 5% | AI-driven setpoint optimisation, two-phase immersion readiness |
| Social value | 5% | UK apprentice hours, local sub-contractor spend |

## 7. Key risks

- **R1 — Refrigerant phase-down.** F-Gas quotas tighten again in 2027. Suppliers locked to R410A face a substitution event mid-contract. Mitigation: contract clause requiring refrigerant change-out at supplier cost.
- **R2 — Skilled-engineer scarcity.** UK has ~1,400 certified critical-cooling engineers. Geographic coverage in Glasgow is thin. Mitigation: cluster-based allocation, no single-supplier lock-out.
- **R3 — Water permitting in Cardiff.** Imperial Park sits within a Welsh Water "moderate stress" catchment — adiabatic permitting is conditional. Mitigation: technical scope allows fallback to dry coolers with PUE waiver.
- **R4 — Supplier concentration.** Two of the five RFI-shortlisted suppliers belong to the same parent group (Vertiv → Stulz acquisition rumoured Q3 2026). Mitigation: corporate disclosure clause in the RFP.

## 8. Stakeholders

- **Mark Hendricks** — IT Infrastructure Director (sponsor, decision authority)
- **Priya Rai** — Senior Category Manager (procurement lead)
- **Lucy Okafor** — Head of Procurement Operations (Ariba & process)
- **Neil Gallagher** — Principal Critical-Facilities Engineer (technical SME chair)
- **Aisha Bello (Abi)** — TPRM lead (third-party risk)
- **Rob Fenwick** — ESG & Sustainability Director (PUE and carbon sign-off)
- **Mitie FM partner team** — incumbent, advisory only
- **Ofgem RIIO compliance team** — informed, not consulted

## 9. Timeline

| Milestone | Target date |
|---|---|
| Approval at Procurement Council | 12 Feb 2026 |
| RFP issue (this document) | **w/c 11 May 2026** |
| Supplier Q&A window closes | 5 Jun 2026 |
| Bid submission deadline | 19 Jun 2026 |
| SME panel scoring | w/c 6 Jul 2026 |
| Procurement Council recommendation | 28 Jul 2026 |
| Award & contract negotiation start | w/c 4 Aug 2026 |
| First site mobilisation (Hams Hall) | 1 Oct 2026 |

*— End of category strategy —*
