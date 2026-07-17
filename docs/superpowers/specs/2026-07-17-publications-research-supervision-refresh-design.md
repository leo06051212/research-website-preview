# Publications, Research, and Supervision Refresh

Date: 2026-07-17
Status: Approved design, awaiting written-spec review

## Objective

Repair the empty Publications and Research pages on the separate GitHub Pages preview, then update the public postgraduate supervision record with the owner-provided 2025–2026 changes. The preview remains isolated from the existing production site.

## Evidence and Current State

- The repository contains 33 migrated publication records, but every record has `draft: true`, so Hugo excludes all of them from the deployed Publications page.
- None of the 33 records has `featured: true`, so the homepage Selected Publications block is also empty.
- `content/research/_index.md` contains a title and a list view but no body content or child research pages, producing an empty grid.
- The University of Auckland profile identifies the relevant themes as FPGA-based computing architectures, domain-specific acceleration, RISC-V customisation, microarchitecture optimisation, hardware/software co-design, and communication workloads.
- The University's Research Outputs page currently lists 41 outputs, while this repository contains 33. This refresh will publish the 33 reviewed local records but will not guess or silently import the eight-record difference.

Authoritative sources:

- https://profiles.auckland.ac.nz/sean-ma
- https://profiles.auckland.ac.nz/sean-ma/grants
- https://profiles.auckland.ac.nz/sean-ma/publications

## Alternatives Considered

1. **Publish the complete local bibliography and maintain a concise local Research page — selected.** This gives visitors a useful standalone academic site and preserves the DOI/IEEE import workflow.
2. Publish only a hand-curated publication subset. This reduces initial review work but leaves the bibliography incomplete and duplicates selection logic already handled by `featured`.
3. Replace local content with links to the University profile. This is low maintenance but defeats the purpose of the standalone website and generated CV data source.

## Research Page Design

The Research page will be a single concise English page rather than four mostly empty child pages. It will introduce four themes using short headings and one paragraph each. The wording is a synthesis of the official University profile, not copied promotional text.

### FPGA-Based Computing and Acceleration

Design of domain-specific FPGA architectures for accelerating AI/ML inference, signal processing, and communication workloads, with an emphasis on high performance, low latency, and energy efficiency.

### RISC-V Customisation and System-on-Chip Design

Custom RISC-V processors and SoC architectures incorporating specialised instructions, tightly coupled accelerators, and efficient processor–accelerator integration.

### High-Level Synthesis and Microarchitecture Optimisation

Hardware optimisation through high-level synthesis, parallelism, pipelining, dataflow and memory-system design, quantised arithmetic, and performance–area–energy trade-offs.

### Hardware–Software Co-Design for Edge and Heterogeneous Computing

Integrated algorithm and architecture design for efficient AI deployment on edge and heterogeneous platforms, including emerging intelligent and semantic communication applications.

The page will preserve the site's restrained academic typography and will not add decorative illustrations, animations, or invented project claims.

## Publications Design

- Change all 33 existing migrated local publication records from draft to published so they appear on the Publications page.
- Keep full author lists, DOI/source links, venues, dates, citations, and abstracts unchanged.
- Mark exactly these four existing records as featured for the homepage:
  1. *A Review of FPGA-Driven LLM Acceleration*
  2. *Adaptive Gradual Quantization with a Custom RISC-V SIMD Accelerator*
  3. *Enhancing Synthesis Efficiency in HLS through LLM-Based Automated Code Correction*
  4. *LHA: Layer-wise Hardware Acceleration of Progressive Quantizing Inference through Partial Reconfiguration for Edge Computing*
- The Publications page will show all published records in reverse chronological order using the existing citation presentation.
- Future DOI/IEEE imports will retain the existing review-first behaviour: newly imported or incomplete records remain drafts until explicitly reviewed.
- The eight-output difference between the University profile and the local repository is outside this refresh. Those records can be added later through the existing DOI/IEEE workflow.

## Supervision Record Design

The public website will retain both course teaching and detailed postgraduate supervision. The postgraduate record will be updated as follows.

### Doctor of Philosophy in Computer Science

- Add **Yulin Fu (2025–Present)** — *Optimizing Large Language Models for Edge Devices: A Hardware-Software Co-Design Approach on FPGA*.
- Retain Yulin Fu's completed master's entry as a separate historical qualification.
- Add **Tingjiang Tan (2026–Present)** — *Hardware/Software Co-Design for FPGA-Based AI Acceleration*.
- Do not label Tingjiang Tan as co-supervised; the public record will use the same presentation as other doctoral entries.

### Master of Science (Research)

- Update **Taojingnan Wang**, **Ziyuan Zhang**, **Chenge Gao**, and **Cheng Cheng** to `2025–2026, Graduated`.
- Correct the erroneous name `Chen Chen` to `Cheng Cheng`.
- Keep **Yulin Fu (2024–2025, Graduated)** and the existing master's topic unchanged.

No other student, topic, or supervision dates will be altered.

## CV Boundary

- Student names, degrees, supervision topics, and supervision relationships remain excluded from the generated CV.
- Teaching courses remain included in the CV.
- Publication author lists remain complete, even when an author is or was a student.
- The supervision changes must not change the CV's page content or privacy contract.

## Validation and Failure Handling

Implementation will follow test-first development.

1. Add source-level contract tests that initially fail because Publications and Research are empty and the supervision records are outdated.
2. Assert that the current 33 local publication records are published and exactly the four approved records are featured.
3. Assert the Research page contains the four approved headings and descriptions.
4. Assert the postgraduate source contains the two doctoral additions, the four 2026 graduations, and `Cheng Cheng`, while rejecting the obsolete `Chen Chen` record.
5. Build the site and verify the deployed Publications page contains publication entries, the Research page contains all four themes, and Teaching exposes the updated supervision record.
6. Regenerate and inspect the CV to confirm that student and supervision details remain absent while course teaching and publication co-authors remain intact.
7. Run the full Python suite, publication synchronisation gate, built-site checker, and GitHub Pages workflow before reporting completion.

If publishing a record violates an existing metadata or synchronisation contract, implementation will stop and report the exact record rather than weakening the validation gate or fabricating metadata.

## Deployment Scope

- Commit and push changes only to `leo06051212/research-website-preview`.
- Allow the existing GitHub Actions workflow to rebuild the separate preview URL.
- Verify the live preview after deployment.
- Do not modify or replace `leo06051212.github.io` without a later explicit approval.

