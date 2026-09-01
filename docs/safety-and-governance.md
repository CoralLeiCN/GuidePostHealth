# Safety and governance specification

## 1. Release position

The repository is an engineering research prototype. It has not completed clinical safety review, clinical validation, medical-device qualification/classification, privacy impact assessment, legal approval, security assurance, or accessibility assurance.

It must not be offered as a public or clinical service until every applicable release blocker in this document has an accountable owner, objective evidence, and written approval.

## 2. Implemented safeguards

| Control | As-built behaviour | Limit |
| --- | --- | --- |
| Product boundary | UI and responses say the product is not a diagnosis and is independent/not NHS-endorsed. | Disclaimers do not remove regulatory or safety obligations created by actual functionality and claims. |
| Persistent emergency routes | The UI shows 999 at the top and NHS 111 below the composer. | Links/actions need formal usability and accessibility evaluation. |
| Emergency phrase floor | Selected non-negated phrases bypass retrieval and Codex and return fixed 999/A&E guidance. | Narrow heuristic, latest message only, and unavailable while the route is unready. Not triage. |
| Urgency-aware retrieval | Urgent/emergency chunks from the first 3 matched documents are appended to dense results. | Final truncation can omit a safety chunk; relevance and coverage are not clinically validated. |
| Evidence-constrained prompt | Health claims and actions are restricted to supplied evidence; prompt forbids diagnosis, doses, tools, and network use. | A prompt rule is not a proof of compliance. |
| Evidence-ID validation | Every generated next step and warning sign must name a retrieved ID. | Summary, urgency, and follow-up are not ID-bound; ID validity is not semantic entailment. |
| Fixed citations | Source title and URL come from the corpus, not the model. | Parsed canonical URLs and local corpus integrity need further validation. |
| Extractive fallback | Any answer-agent exception produces labelled source extracts. | Failures are not yet classified, measured, or alerted. |
| Read-only agent | Ephemeral thread, read-only sandbox, deny-all approvals, no application tools. | User health text still crosses an external processing boundary when Codex is enabled. |
| Data minimisation | No application database or intentional symptom-body logging; browser state is in memory. | Reverse proxies, platforms, SDKs, and providers need verified logging/retention controls. |

## 3. Emergency floor scope

The deterministic rule currently recognises phrases associated with:

- inability to breathe or stopped breathing;
- unconsciousness or inability to wake;
- chest pain or chest tightness;
- selected stroke signs;
- severe or unstoppable bleeding;
- overdose; and
- explicit immediate self-harm danger.

A small preceding-text negation pattern prevents some obvious false alerts. It is not a comprehensive language model, emergency classifier, or triage protocol. It may miss paraphrases and complex context and may trigger on quoted, historical, or third-party symptoms.

## 4. Known safety gaps

| ID | Gap | Required treatment |
| --- | --- | --- |
| SG-001 | `/api/v1/chat` returns `503` before `ChatService` when the index is unavailable, so the fixed emergency response is skipped. | Move a clinically approved emergency route ahead of corpus readiness and test degraded operation. |
| SG-002 | The phrase floor is narrow, latest-message-only, and minimally tested. | Define its role with clinical ownership; build a representative evaluation set; do not market it as triage. |
| SG-003 | Summary, `help_level`, and follow-up question are not evidence-ID validated. | Extend structured grounding and enforce evidence/urgency consistency. |
| SG-004 | A valid evidence ID does not prove that generated text is supported by that passage. | Add entailment/human-review evaluation and regression thresholds. |
| SG-005 | No deterministic rule prevents the model from assigning lower urgency than retrieved NHS evidence. | Define and enforce a clinically approved “never downgrade” policy. |
| SG-006 | Safety-section augmentation is limited to documents in the first 3 matches and the 9-item cap can omit appended sections. | Measure safety recall and redesign retrieval/capping under clinical review. |
| SG-007 | The fixed 999 citation uses the response time as `fetched_at`, not reviewed corpus provenance. | Store and expose an accurate, versioned official-service source record. |
| SG-008 | Agent failures silently degrade from an operational perspective. | Add privacy-safe typed metrics, alerts, and runbooks. |
| SG-009 | “Chat stays in this browser session” can be read as “data stays in the browser”. | Pair storage copy with explicit transmission and processor disclosure. |
| SG-010 | Canonical URLs parsed from HTML and ignored local JSON are trusted downstream. | Revalidate exact NHS URLs and integrity-protect promoted corpus artifacts. |

## 5. Clinical governance requirements

| ID | Requirement | Status |
| --- | --- | --- |
| CG-101 | Appoint an accountable clinical safety owner and define governance responsibilities. | Required |
| CG-102 | Approve intended purpose, populations, exclusions, user claims, and how output may influence decisions. | Required |
| CG-103 | Determine applicability of NHS clinical-risk standards and produce the required clinical safety case, hazard log, safety plan, and evidence. | Required |
| CG-104 | Clinically review the corpus scope, parser urgency mapping, retrieval behaviour, prompts, fallback, UI copy, and every supported pathway. | Required |
| CG-105 | Establish controlled change, sign-off, incident, adverse-event, correction, takedown, rollback, and recall processes. | Required |
| CG-106 | Define post-release monitoring without collecting unnecessary health data. | Required |

NHS England’s [DCB0129 standard](https://digital.nhs.uk/data-and-information/information-standards/governance/latest-activity/standards-and-collections/dcb0129-clinical-risk-management-its-application-in-the-manufacture-of-health-it-systems/) describes clinical-risk management requirements for organisations developing and maintaining health IT systems for health and care use. A qualified owner must determine its applicability and the associated evidence; this document does not make that determination.

## 6. Medical-device regulatory assessment

Before any public pilot, qualified regulatory counsel must assess the product’s actual functionality, intended purpose, labelling, interface, and promotional claims under the then-current UK medical-device framework.

The assessment must not rely on “research only”, “information only”, or “not a medical device” copy as a substitute for analysing what the software is intended to do. If the intended purpose or claims change, the assessment must be repeated.

Primary references:

- [MHRA: crafting an intended purpose for Software as a Medical Device](https://www.gov.uk/government/publications/crafting-an-intended-purpose-in-the-context-of-software-as-a-medical-device-samd/crafting-an-intended-purpose-in-the-context-of-software-as-a-medical-device-samd)
- [MHRA: software and artificial intelligence as a medical device](https://www.gov.uk/government/publications/software-and-artificial-intelligence-ai-as-a-medical-device/software-and-artificial-intelligence-ai-as-a-medical-device)

## 7. Safety evaluation gate

A clinically authored evaluation set must cover at least:

- emergency, urgent, routine, and self-care scenarios;
- children, older people, pregnancy, comorbidities, and relevant exclusions;
- single and multiple symptoms, duration, severity, and change over time;
- lay terms, spelling variation, ambiguity, negation, quoted/history context, and third-party reports;
- insufficient corpus coverage and conflicting or changing guidance;
- prompt injection and malicious instructions embedded in user text or retrieved content;
- agent timeout, authentication failure, malformed output, index failure, and stale corpus states; and
- accessibility and comprehension across the intended user population.

The release owner must approve thresholds for emergency/urgent recall and false reassurance before optimising general answer quality. Secondary measures should include retrieval recall at `k`, evidence entailment, citation precision, urgency preservation, unsupported-claim rate, fallback correctness, availability, latency, and subgroup performance.

No public release may proceed on aggregate answer-quality scores alone. Safety-critical scenarios must have their own blocking thresholds and regression suite.

## 8. Privacy and data governance

Symptom descriptions can reveal health status and therefore can be special-category personal data when linked or linkable to a person. The production design must:

| ID | Requirement | Status |
| --- | --- | --- |
| PG-101 | Identify and document an Article 6 lawful basis and an applicable Article 9 condition with qualified advice. | Required |
| PG-102 | Complete and approve a DPIA before processing in a public pilot. | Required |
| PG-103 | Publish a concise privacy notice before collection, naming controllers/processors, purposes, data flows, retention, rights, and contact routes. | Required |
| PG-104 | Approve provider contracts and controls for data region, retention, training use, subprocessors, deletion, access, and incident notification. | Required |
| PG-105 | Verify that application, proxy, platform, error, analytics, and model-provider logs exclude symptom bodies and sensitive query data. | Required |
| PG-106 | Define minimisation, retention, deletion, subject-rights, breach, and access-control procedures. | Required |
| PG-107 | Prohibit durable conversation storage until it has an explicit purpose, design, lawful basis, retention schedule, and user controls. | Required |

ICO guidance explains that health data is special-category data and that high-risk processing requires a DPIA. See [ICO special-category data rules](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/special-category-data/what-are-the-rules-on-special-category-data/) and [ICO DPIA guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/guide-to-accountability-and-governance/data-protection-impact-assessments/).

## 9. Security, legal, and accessibility gates

Before a public pilot, the release must also have:

- threat modelling and penetration testing covering browser, API, ingestion, corpus, model, and vector database boundaries;
- TLS, security headers, secrets management, least privilege, non-root isolation, dependency/container/SBOM scanning, and patch ownership;
- authentication and rate/abuse controls appropriate to the final service model;
- privacy-safe monitoring, alerting, service objectives, incident response, rollback, and disaster recovery;
- page-level NHS/OGL review, correct attribution/freshness, exclusions and takedown records, and no-endorsement controls;
- formal WCAG/assistive-technology, keyboard, zoom, mobile, health-literacy, and error-recovery assessment; and
- qualified legal review of consumer, accessibility, medical-device, data-protection, and content-reuse obligations.

## 10. Release gate

Public-pilot status remains **blocked** until:

1. All `Required` items have named owners and objective completion evidence.
2. Clinical, regulatory, privacy, legal, security, accessibility, and operational approvers sign the same versioned release candidate.
3. The safety regression suite passes the approved thresholds.
4. Corpus, parser, embedding model, prompt, answer model, application, and infrastructure versions are recorded and reproducible.
5. Monitoring, incident response, rollback, and takedown have been exercised.

Clinical deployment is a separate decision and remains out of scope for the current prototype.

