# Publications, Research, and Supervision Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the separate preview's Publications and Research pages, update the public postgraduate supervision record, and preserve the CV's teaching-only privacy boundary.

**Architecture:** Keep the website content-driven: publication visibility and homepage selection remain in publication front matter, the Research page becomes one concise Hugo Blox landing page, and supervision stays in the existing teaching record. Source contracts provide fast feedback, generated-site tests verify Hugo output, and the existing CV generator remains unchanged but is revalidated after the content update.

**Tech Stack:** Hugo Blox with Hugo Extended 0.162.0, YAML/Markdown content, Python 3.13, `unittest`, PyYAML, ReportLab/pypdf, GitHub Actions, and GitHub Pages.

## Global Constraints

- Work only in `D:\codex_workplace\MyResearchWebsite\research-website-preview` and publish only to `leo06051212/research-website-preview`.
- Do not modify or replace `leo06051212.github.io`.
- Publish the 33 existing local migrated publication records; do not fabricate or silently import the eight-output difference from the University profile.
- Feature exactly the four publication records named in the approved design.
- Use the four approved English Research headings and paragraphs verbatim.
- Keep both course teaching and detailed postgraduate supervision visible on the website.
- Keep all student names, degrees, topics, and supervision relationships out of the CV teaching section; retain complete publication author lists.
- Preserve review-first behaviour for future DOI/IEEE imports.
- Follow red-green-refactor for each content change and commit each independently reviewable task.

## File Map

- `tests/test_site_contract.py`: source-level publication, Research, and supervision contracts.
- `content/publications/*/index.md`: publication visibility for all 33 records and featured selection for four records.
- `content/research/_index.md`: single-page Research landing content.
- `content/teaching/uoa-cs-pg-teaching.md`: public postgraduate supervision history.
- `tests/test_cv_pdf.py`: CV boundary regression assertions for newly named students.
- `tests/test_generated_site.py`: end-to-end assertions against Hugo's generated HTML.
- `static/uploads/sean-ma-cv.pdf`: regenerated CV artifact; content must remain teaching-only.

---

### Task 1: Publish the Local Bibliography and Select Four Homepage Publications

**Files:**
- Modify: `tests/test_site_contract.py`
- Modify: all 33 `content/publications/*/index.md` files
- Feature: `content/publications/2025-12-15-a-review-of-fpga-driven-llm-acceleration/index.md`
- Feature: `content/publications/2025-12-15-adaptive-gradual-quantization-with-a-custom-risc-v-simd-accelerator/index.md`
- Feature: `content/publications/2025-09-23-enhancing-synthesis-efficiency-in-hls-through-llm-based-automated-cod/index.md`
- Feature: `content/publications/2025-06-30-lha-layer-wise-hardware-acceleration-of-progressive-quantizing-infere/index.md`

**Interfaces:**
- Consumes: Hugo publication front matter fields `draft: bool` and `featured: bool`.
- Produces: 33 publishable records and the exact four-slug featured set consumed by the homepage collection block and generated-site tests.

- [ ] **Step 1: Add a front-matter loader and the failing publication contract**

Add this method to `SiteContractTests` after `load_yaml`:

```python
    def load_frontmatter(self, path: Path):
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        self.assertEqual(parts[0], "", path)
        self.assertEqual(len(parts), 3, path)
        loaded = yaml.safe_load(parts[1])
        self.assertIsInstance(loaded, dict, path)
        return loaded
```

Add this test after `test_homepage_contains_required_sections`:

```python
    def test_existing_publications_are_published_with_exact_featured_selection(self):
        indexes = sorted((ROOT / "content/publications").glob("*/index.md"))
        self.assertEqual(len(indexes), 33)
        featured = set()
        for index in indexes:
            metadata = self.load_frontmatter(index)
            self.assertIs(metadata.get("draft"), False, index)
            if metadata.get("featured") is True:
                featured.add(index.parent.name)

        self.assertEqual(
            featured,
            {
                "2025-12-15-a-review-of-fpga-driven-llm-acceleration",
                "2025-12-15-adaptive-gradual-quantization-with-a-custom-risc-v-simd-accelerator",
                "2025-09-23-enhancing-synthesis-efficiency-in-hls-through-llm-based-automated-cod",
                "2025-06-30-lha-layer-wise-hardware-acceleration-of-progressive-quantizing-infere",
            },
        )
```

- [ ] **Step 2: Run the focused test and confirm the expected failure**

Run:

```powershell
python -m unittest tests.test_site_contract.SiteContractTests.test_existing_publications_are_published_with_exact_featured_selection -v
```

Expected: FAIL on the first publication because its `draft` value is `True`.

- [ ] **Step 3: Apply the minimal publication front-matter changes**

Use `apply_patch` to make this scalar replacement in every one of the 33 publication index files:

```diff
-draft: true
+draft: false
```

In only the four feature files listed under **Files**, also apply:

```diff
-featured: false
+featured: true
```

Do not change titles, authors, dates, venues, abstracts, citations, DOI fields, provenance markers, correction fields, links, or BibTeX files.

- [ ] **Step 4: Run the focused publication test**

Run:

```powershell
python -m unittest tests.test_site_contract.SiteContractTests.test_existing_publications_are_published_with_exact_featured_selection -v
```

Expected: the test reports `OK`.

- [ ] **Step 5: Commit the publication visibility change**

```powershell
git add tests/test_site_contract.py content/publications
git commit -m "fix: publish reviewed bibliography"
```

Expected: one commit containing the source test and front-matter-only changes.

- [ ] **Step 6: Run the publication synchronisation gate against the committed task**

```powershell
python scripts/check_publication_sync.py --repo-root .
```

Expected: the gate prints `Managed publication content is synchronized and committed` and does not report citation drift or fabricated metadata.

---

### Task 2: Build the Concise Research Landing Page

**Files:**
- Modify: `tests/test_site_contract.py`
- Modify: `content/research/_index.md`

**Interfaces:**
- Consumes: Hugo Blox `type: landing` and `block: markdown` front matter.
- Produces: one Research page whose first section contains the four approved headings and paragraphs.

- [ ] **Step 1: Write the failing Research source contract**

Add this test after the publication visibility test:

```python
    def test_research_page_contains_approved_official_profile_summary(self):
        metadata = self.load_frontmatter(ROOT / "content/research/_index.md")
        self.assertEqual(metadata.get("type"), "landing")
        sections = metadata.get("sections")
        self.assertIsInstance(sections, list)
        self.assertEqual(len(sections), 1)
        section = sections[0]
        self.assertEqual(section.get("block"), "markdown")
        self.assertEqual(section["content"]["title"], "Research")
        text = section["content"]["text"]
        for required in (
            "FPGA-Based Computing and Acceleration",
            "Design of domain-specific FPGA architectures for accelerating AI/ML inference, signal processing, and communication workloads",
            "RISC-V Customisation and System-on-Chip Design",
            "Custom RISC-V processors and SoC architectures incorporating specialised instructions",
            "High-Level Synthesis and Microarchitecture Optimisation",
            "Hardware optimisation through high-level synthesis, parallelism, pipelining, dataflow and memory-system design",
            "Hardware–Software Co-Design for Edge and Heterogeneous Computing",
            "Integrated algorithm and architecture design for efficient AI deployment on edge and heterogeneous platforms",
        ):
            self.assertIn(required, text)
```

- [ ] **Step 2: Run the focused test and confirm the expected failure**

Run:

```powershell
python -m unittest tests.test_site_contract.SiteContractTests.test_research_page_contains_approved_official_profile_summary -v
```

Expected: FAIL because the current Research index has no `type` or `sections` value.

- [ ] **Step 3: Replace the empty Research list with the approved landing content**

Replace the complete contents of `content/research/_index.md` with:

```yaml
---
title: Research
type: landing
sections:
  - block: markdown
    content:
      title: Research
      text: |-
        ## FPGA-Based Computing and Acceleration

        Design of domain-specific FPGA architectures for accelerating AI/ML inference, signal processing, and communication workloads, with an emphasis on high performance, low latency, and energy efficiency.

        ## RISC-V Customisation and System-on-Chip Design

        Custom RISC-V processors and SoC architectures incorporating specialised instructions, tightly coupled accelerators, and efficient processor–accelerator integration.

        ## High-Level Synthesis and Microarchitecture Optimisation

        Hardware optimisation through high-level synthesis, parallelism, pipelining, dataflow and memory-system design, quantised arithmetic, and performance–area–energy trade-offs.

        ## Hardware–Software Co-Design for Edge and Heterogeneous Computing

        Integrated algorithm and architecture design for efficient AI deployment on edge and heterogeneous platforms, including emerging intelligent and semantic communication applications.
    design:
      columns: '1'
---
```

- [ ] **Step 4: Run the Research and navigation contracts**

Run:

```powershell
python -m unittest tests.test_site_contract.SiteContractTests.test_research_page_contains_approved_official_profile_summary tests.test_site_contract.SiteContractTests.test_navigation_contract -v
```

Expected: both tests report `OK`.

- [ ] **Step 5: Commit the Research page**

```powershell
git add tests/test_site_contract.py content/research/_index.md
git commit -m "feat: add concise research overview"
```

---

### Task 3: Update Postgraduate Supervision Without Expanding the CV

**Files:**
- Modify: `tests/test_site_contract.py`
- Modify: `content/teaching/uoa-cs-pg-teaching.md`
- Modify: `tests/test_cv_pdf.py`

**Interfaces:**
- Consumes: the existing public teaching Markdown record and `teaching_type: Postgraduate supervision` exclusion in `scripts/cv_data.py`.
- Produces: updated public supervision text while preserving a `CvDocument.teaching` tuple containing only undergraduate course teaching.

- [ ] **Step 1: Replace the weak supervision source contract with a failing exact contract**

Replace `test_canonical_postgraduate_supervision_record_retains_details` in `tests/test_site_contract.py` with:

```python
    def test_canonical_postgraduate_supervision_record_matches_owner_updates(self):
        text = (
            ROOT / "content/teaching/uoa-cs-pg-teaching.md"
        ).read_text(encoding="utf-8")
        for detail in (
            "Postgraduate supervision",
            "Doctor of Philosophy in Computer Science",
            "Yulin Fu (2025–Present)",
            "Optimizing Large Language Models for Edge Devices: A Hardware-Software Co-Design Approach on FPGA",
            "Tingjiang Tan (2026–Present)",
            "Hardware/Software Co-Design for FPGA-Based AI Acceleration",
            "Taojingnan Wang (2025–2026, Graduated)",
            "Ziyuan Zhang (2025–2026, Graduated)",
            "Chenge Gao (2025–2026, Graduated)",
            "Cheng Cheng (2025–2026, Graduated)",
            "Yulin Fu (2024- 2025, Graduated)",
        ):
            self.assertIn(detail, text)
        self.assertNotIn("Chen Chen", text)
```

- [ ] **Step 2: Run the focused source contract and confirm the expected failure**

Run:

```powershell
python -m unittest tests.test_site_contract.SiteContractTests.test_canonical_postgraduate_supervision_record_matches_owner_updates -v
```

Expected: FAIL because the new doctoral entries and 2026 graduation statuses are absent.

- [ ] **Step 3: Apply the exact supervision body update**

Keep the existing front matter unchanged. Replace the Markdown body after the closing front-matter delimiter with:

```markdown
Doctor of Philosophy in Computer Science
======
Xu Chen (2025- Now)
------
>Research on Neural Network Circuit and Computing-in-Memory Accelerator Based on Memristor

Jiale Li (2023- Now)
------
>The Computer Architecture for Edge Artificial Intelligence

Zhihang Liu (2023- Now)
------
>Hardware Acceleration of Deep-learning Algorithm on FPGA for Edge Device

Zongcheng Yue (2022- Now)
------
>Computational Architecture for Intelligent Edge Computing

Yulin Fu (2025–Present)
------
>Optimizing Large Language Models for Edge Devices: A Hardware-Software Co-Design Approach on FPGA

Tingjiang Tan (2026–Present)
------
>Hardware/Software Co-Design for FPGA-Based AI Acceleration

Brian Zhong (2019- 2025, Graduated)
------
>A Comprehensive Study on RISC-V's Applications to AIoT Endpoint SoCs

Master of Science (Research)
======
Taojingnan Wang (2025–2026, Graduated)
------
Ziyuan Zhang (2025–2026, Graduated)
------
Chenge Gao (2025–2026, Graduated)
------
Cheng Cheng (2025–2026, Graduated)
------

Yulin Fu (2024- 2025, Graduated)
------
>FPGA-Adapted Neural Network Models for Low-Latency, High-Accuracy Image recognition: An Integrated Approach

Dongwei Yan (2024- 2025, Graduated)
------
>Effective Progressive Quantization: Enhancing Residual Neural Networks with Ultra-Low Precision Validation on ResNet18 and ResNet50

Master of Information and Technology (Internship)
======

Han(Olivia) Li (2023-2024)
------

Roshan Shaheen (2023–2024)
------

Rupak Lingwal (2023–2024)
------
```

- [ ] **Step 4: Strengthen the CV privacy regression for all newly relevant names**

In `test_real_pdf_contains_courses_but_no_supervision_or_student_details`, replace the student-name tuple with:

```python
        for student_name in (
            "Xu Chen",
            "Jiale Li",
            "Yulin Fu",
            "Tingjiang Tan",
            "Taojingnan Wang",
            "Ziyuan Zhang",
            "Chenge Gao",
            "Cheng Cheng",
        ):
            self.assertNotIn(student_name, teaching_text)
```

The assertion remains scoped to `teaching_text`, so student co-authors in the Publications section remain allowed.

- [ ] **Step 5: Run source, CV data, and PDF boundary tests**

Run:

```powershell
python -m unittest tests.test_site_contract.SiteContractTests.test_canonical_postgraduate_supervision_record_matches_owner_updates tests.test_cv_data.CvDataTests.test_real_repository_cv_excludes_supervision_and_retains_course_teaching tests.test_cv_pdf.CvPdfTests.test_real_pdf_contains_courses_but_no_supervision_or_student_details -v
```

Expected: all three tests report `OK`; the generated CV teaching section contains five courses and none of the listed students.

- [ ] **Step 6: Commit the supervision update**

```powershell
git add tests/test_site_contract.py tests/test_cv_pdf.py content/teaching/uoa-cs-pg-teaching.md
git commit -m "feat: update postgraduate supervision records"
```

---

### Task 4: Add Generated-Site Coverage and Rebuild the Preview Artifact

**Files:**
- Modify: `tests/test_generated_site.py`
- Regenerate: `static/uploads/sean-ma-cv.pdf`
- Generate but do not commit: `public/**`

**Interfaces:**
- Consumes: Hugo-generated HTML under `public`, the exact featured slugs from Task 1, Research text from Task 2, and supervision text from Task 3.
- Produces: end-to-end tests proving the source changes are visible in the generated site and the CV remains downloadable.

- [ ] **Step 1: Add a reusable generated-page text/link parser**

Add this class after `GeneratedHomepageParser`:

```python
class GeneratedContentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])

    def handle_data(self, data):
        if data.strip():
            self.text_parts.append(data.strip())

    @property
    def text(self):
        return " ".join(" ".join(self.text_parts).split())


def parse_generated_page(path: Path) -> GeneratedContentParser:
    parser = GeneratedContentParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser
```

- [ ] **Step 2: Write generated-site tests before rebuilding**

Add these methods to `GeneratedSiteTests`:

```python
    def test_publications_listing_contains_all_local_records_and_homepage_features(self):
        expected_slugs = {
            index.parent.name
            for index in (ROOT / "content/publications").glob("*/index.md")
        }
        listing_pages = [ROOT / "public/publications/index.html"] + sorted(
            (ROOT / "public/publications/page").glob("*/index.html")
        )
        listing_links = {
            link
            for page in listing_pages
            for link in parse_generated_page(page).links
        }
        listed_slugs = set()
        for link in listing_links:
            match = re.fullmatch(
                r"/research-website-preview/publications/([^/]+)/",
                link,
            )
            if match:
                listed_slugs.add(match.group(1))
        self.assertEqual(listed_slugs, expected_slugs)

        homepage_links = set(parse_generated_page(ROOT / "public/index.html").links)
        for slug in {
            "2025-12-15-a-review-of-fpga-driven-llm-acceleration",
            "2025-12-15-adaptive-gradual-quantization-with-a-custom-risc-v-simd-accelerator",
            "2025-09-23-enhancing-synthesis-efficiency-in-hls-through-llm-based-automated-cod",
            "2025-06-30-lha-layer-wise-hardware-acceleration-of-progressive-quantizing-infere",
        }:
            self.assertTrue(
                any(f"/publications/{slug}/" in link for link in homepage_links),
                slug,
            )

    def test_research_page_renders_the_four_approved_themes(self):
        text = parse_generated_page(ROOT / "public/research/index.html").text
        for heading in (
            "FPGA-Based Computing and Acceleration",
            "RISC-V Customisation and System-on-Chip Design",
            "High-Level Synthesis and Microarchitecture Optimisation",
            "Hardware–Software Co-Design for Edge and Heterogeneous Computing",
        ):
            self.assertIn(heading, text)

    def test_supervision_page_renders_current_and_completed_students(self):
        page = ROOT / "public/teaching/uoa-cs-pg-teaching/index.html"
        text = parse_generated_page(page).text
        for detail in (
            "Yulin Fu (2025–Present)",
            "Tingjiang Tan (2026–Present)",
            "Taojingnan Wang (2025–2026, Graduated)",
            "Ziyuan Zhang (2025–2026, Graduated)",
            "Chenge Gao (2025–2026, Graduated)",
            "Cheng Cheng (2025–2026, Graduated)",
        ):
            self.assertIn(detail, text)
        self.assertNotIn("Chen Chen", text)
```

- [ ] **Step 3: Run the generated-site tests against the stale build and confirm failure**

Run:

```powershell
python -m unittest tests.test_generated_site.GeneratedSiteTests.test_publications_listing_contains_all_local_records_and_homepage_features tests.test_generated_site.GeneratedSiteTests.test_research_page_renders_the_four_approved_themes tests.test_generated_site.GeneratedSiteTests.test_supervision_page_renders_current_and_completed_students -v
```

Expected: FAIL because the current `public` directory still contains the empty Publications/Research pages and outdated supervision text.

- [ ] **Step 4: Regenerate the CV and build with pinned Hugo Extended**

Run:

```powershell
python -m scripts.generate_cv --repo-root . --portrait assets/media/authors/me.jpg --output static/uploads/sean-ma-cv.pdf --review-report output/cv/publication-review.md
$hugoArchive = Join-Path $env:TEMP 'hugo_extended_0.162.0_windows-amd64.zip'
$hugoDirectory = Join-Path $env:TEMP 'hugo-0.162.0'
Invoke-WebRequest -Uri 'https://github.com/gohugoio/hugo/releases/download/v0.162.0/hugo_extended_0.162.0_windows-amd64.zip' -OutFile $hugoArchive
New-Item -ItemType Directory -Force -Path $hugoDirectory | Out-Null
Expand-Archive -LiteralPath $hugoArchive -DestinationPath $hugoDirectory -Force
& (Join-Path $hugoDirectory 'hugo.exe') --minify --baseURL 'https://leo06051212.github.io/research-website-preview/'
```

Expected: CV generation reports 33 publications and one course-teaching record; Hugo exits 0 and generates publication, Research, and supervision HTML under `public`.

- [ ] **Step 5: Run generated-site and built-site checks**

Run:

```powershell
python -m unittest tests.test_generated_site -v
python scripts/check_built_site.py public --base-path /research-website-preview/ --content content
```

Expected: generated-site tests report `OK`; the checker prints the number of checked HTML pages with no errors.

- [ ] **Step 6: Commit the generated-site regression tests and CV**

```powershell
git add tests/test_generated_site.py static/uploads/sean-ma-cv.pdf
git commit -m "test: verify populated academic pages"
```

Do not add `public/**`, `resources/**`, `.hugo_build.lock`, or temporary Hugo files.

---

### Task 5: Run Full Gates, Publish the Separate Preview, and Verify Online

**Files:**
- Verify only: entire repository
- Remote target: `https://github.com/leo06051212/research-website-preview`
- Preview target: `https://leo06051212.github.io/research-website-preview/`

**Interfaces:**
- Consumes: the four task commits and existing `.github/workflows/deploy.yml`.
- Produces: a successful GitHub Pages deployment of the isolated preview and an evidence-backed completion report.

- [ ] **Step 1: Run the complete local verification suite**

Run:

```powershell
python -m unittest discover -s tests -v
python scripts/check_publication_sync.py --repo-root .
python -m scripts.generate_cv --repo-root . --portrait assets/media/authors/me.jpg --output static/uploads/sean-ma-cv.pdf --review-report output/cv/publication-review.md
python scripts/check_built_site.py public --base-path /research-website-preview/ --content content
git diff --check
git status --short
```

Expected: all tests pass; publication sync is clean; CV generation reports 33 publications and one teaching record; built-site check has no failures; `git diff --check` is empty; `git status --short` is empty after committing any byte-for-byte CV regeneration change.

- [ ] **Step 2: Confirm repository and remote safety boundaries**

Run:

```powershell
git remote -v
git branch --show-current
git log -5 --oneline
```

Expected: `origin` is exactly `https://github.com/leo06051212/research-website-preview.git`, the branch is `main`, and no production-site repository appears.

- [ ] **Step 3: Push the reviewed task commits**

Run:

```powershell
git push origin main
```

Expected: the remote `main` branch advances and the existing Pages deployment workflow starts.

- [ ] **Step 4: Monitor GitHub Actions to a terminal result**

Open:

```text
https://github.com/leo06051212/research-website-preview/actions/workflows/deploy.yml
```

Expected: the newest run for the pushed commit finishes with `Success`; the build job passes publication sync, CV generation, at least 139 tests, Hugo build, built-site checking, artifact upload, and Pages deployment. Treat warnings as non-blocking only when every job is successful.

- [ ] **Step 5: Verify the live preview pages and PDF**

Open and inspect:

```text
https://leo06051212.github.io/research-website-preview/
https://leo06051212.github.io/research-website-preview/publications/
https://leo06051212.github.io/research-website-preview/research/
https://leo06051212.github.io/research-website-preview/teaching/
https://leo06051212.github.io/research-website-preview/teaching/uoa-cs-pg-teaching/
https://leo06051212.github.io/research-website-preview/uploads/sean-ma-cv.pdf
```

Expected:

- Homepage shows four Selected Publications and retains Prospective Students.
- Publications is populated and its pagination exposes all 33 local records.
- Research shows all four approved themes and short descriptions.
- Teaching shows both course teaching and the updated supervision record.
- The supervision detail page contains Yulin Fu and Tingjiang Tan as current PhD students, the four 2026 master's graduations, and `Cheng Cheng`, with no `Chen Chen` entry.
- The CV URL returns HTTP 200 with `Content-Type: application/pdf`; its Teaching section contains courses but no supervision roster or topics.

- [ ] **Step 6: Record final evidence**

Report the deployed commit hash, GitHub Actions run result, total test count, checked HTML page count, online page checks, and confirmation that `leo06051212.github.io` was not modified.
