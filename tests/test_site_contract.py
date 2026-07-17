from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class SiteContractTests(unittest.TestCase):
    def load_yaml(self, relative_path: str):
        return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))

    def load_frontmatter(self, path: Path):
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        self.assertEqual(parts[0], "", path)
        self.assertEqual(len(parts), 3, path)
        loaded = yaml.safe_load(parts[1])
        self.assertIsInstance(loaded, dict, path)
        return loaded

    def load_workflow(self, relative_path: str):
        path = ROOT / relative_path
        self.assertTrue(path.is_file(), f"missing workflow: {relative_path}")
        return yaml.load(
            path.read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )

    def test_preview_url_and_language(self):
        config = self.load_yaml("config/_default/hugo.yaml")
        self.assertEqual(
            config["baseURL"],
            "https://leo06051212.github.io/research-website-preview/",
        )
        self.assertEqual(config["defaultContentLanguage"], "en")

    def test_navigation_contract(self):
        menus = self.load_yaml("config/_default/menus.yaml")
        labels = [item["name"] for item in menus["main"]]
        self.assertEqual(
            labels,
            ["About", "Research", "Publications", "Talks", "Teaching", "Blog", "CV"],
        )

    def test_mobile_navigation_updates_aria_expanded(self):
        hook = (
            ROOT / "layouts/_partials/hooks/head-end/noindex.html"
        ).read_text(encoding="utf-8")
        self.assertIn('button[aria-controls="collapse-main-navbar"]', hook)
        self.assertIn('menu.classList.contains("hidden")', hook)
        self.assertIn('button.addEventListener("click", updateExpandedState)', hook)

    def test_owner_contract(self):
        owner = self.load_yaml("data/authors/me.yaml")
        self.assertEqual(owner["name"]["display"], "Dr Sean Longyu Ma")
        self.assertEqual(owner["role"], "Lecturer in Computer Science")
        urls = {link["url"] for link in owner["links"]}
        self.assertIn("https://orcid.org/0000-0002-3350-004X", urls)
        self.assertIn("https://scholar.google.com/citations?user=zDtLcAUAAAAJ&hl=en", urls)

    def test_required_section_roots_exist(self):
        for path in [
            "content/research/_index.md",
            "content/publications/_index.md",
            "content/events/_index.md",
            "content/teaching/_index.md",
            "content/blog/_index.md",
        ]:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_homepage_contains_required_sections(self):
        text = (ROOT / "content/_index.md").read_text(encoding="utf-8")
        for heading in [
            "Research Interests",
            "Selected Publications",
            "Recent Updates",
            "Prospective Students",
        ]:
            self.assertIn(heading, text)
        self.assertIn("I welcome enquiries from prospective PhD", text)

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

    def test_canonical_postgraduate_supervision_record_retains_details(self):
        text = (
            ROOT / "content/teaching/uoa-cs-pg-teaching.md"
        ).read_text(encoding="utf-8")
        for detail in [
            "Postgraduate supervision",
            "Doctor of Philosophy in Computer Science",
            "Xu Chen",
        ]:
            self.assertIn(detail, text)

    def test_preview_is_not_indexed(self):
        hook = ROOT / "layouts/_partials/hooks/head-end/noindex.html"
        self.assertIn('content="noindex,nofollow"', hook.read_text(encoding="utf-8"))

    def test_editorial_typography_contract(self):
        params = self.load_yaml("config/_default/params.yaml")
        self.assertEqual(params["hugoblox"]["typography"]["pack"], "academic")

        css = (ROOT / "assets/css/custom.css").read_text(encoding="utf-8")
        self.assertIn("--sean-interface-font: ui-sans-serif", css)
        interface_rule = re.search(
            r"([^{}]+)\{[^{}]*font-family:\s*var\(--sean-interface-font\);[^{}]*\}",
            css,
        )
        self.assertIsNotNone(interface_rule)
        interface_selectors = {
            selector.strip() for selector in interface_rule.group(1).split(",")
        }
        for selector in [
            "nav",
            ".navbar",
            ".nav-link",
            ".nav-dropdown-link",
            "button",
            "input",
            "select",
            "textarea",
            '[role="button"]',
            ".btn",
            ".page-footer",
            "footer",
        ]:
            self.assertIn(selector, interface_selectors)
        self.assertNotIn("h1", interface_selectors)

    def test_pages_cms_collections(self):
        cms = self.load_yaml(".pages.yml")
        collections = {item["name"]: item for item in cms["content"]}
        self.assertEqual(
            set(collections),
            {"publication_imports", "publications", "talks", "blog", "teaching", "profile"},
        )

        expected_sources = {
            "publication_imports": (
                "data/publication-imports",
                "yaml",
                "{year}-{month}-{day}-{hour}-{minute}-{source}.yml",
            ),
            "publications": ("content/publications", "yaml-frontmatter", None),
            "talks": (
                "content/events",
                "yaml-frontmatter",
                "{year}-{month}-{day}-{title}.md",
            ),
            "blog": (
                "content/blog",
                "yaml-frontmatter",
                "{year}-{month}-{day}-{title}.md",
            ),
            "teaching": ("content/teaching", "yaml-frontmatter", "{title}.md"),
            "profile": ("data/authors/me.yaml", "yaml", None),
        }
        for name, (path, format_name, filename) in expected_sources.items():
            collection = collections[name]
            self.assertEqual(collection["path"], path)
            self.assertEqual(collection["format"], format_name)
            self.assertEqual(collection.get("filename"), filename)

        publications = collections["publications"]
        self.assertFalse(publications["operations"]["create"])
        self.assertEqual(publications["view"]["node"]["filename"], "index.md")
        publication_fields = {
            field["name"]: field for field in publications["fields"]
        }
        self.assertIn("requires_correction", publication_fields)
        self.assertNotIn("readonly", publication_fields["requires_correction"])
        for name in ["correction_reasons", "date_precision", "publication_date_parts"]:
            self.assertIn(name, publication_fields)
            self.assertTrue(publication_fields[name]["readonly"])
        metadata_fields = {
            field["name"]
            for field in publication_fields["publication"]["fields"]
        }
        self.assertIn("publisher", metadata_fields)
        self.assertIn("article_number", metadata_fields)

        for name in ["talks", "blog", "teaching"]:
            fields = {field["name"]: field for field in collections[name]["fields"]}
            self.assertTrue(fields["draft"]["default"])

        import_fields = {
            field["name"]: field for field in collections["publication_imports"]["fields"]
        }
        self.assertEqual(import_fields["status"]["default"], "pending")
        for name in ["status", "result_path", "error"]:
            self.assertTrue(import_fields[name]["readonly"])

        profile_fields = {field["name"] for field in collections["profile"]["fields"]}
        self.assertEqual(profile_fields, {"role", "bio", "interests"})

        self.assertEqual(cms["media"]["input"], "static/uploads")
        self.assertEqual(cms["media"]["output"], "/research-website-preview/uploads")
        self.assertIs(cms.get("settings", {}).get("content", {}).get("merge"), True)

        def cms_fields(value):
            if isinstance(value, dict):
                for field in value.get("fields", []):
                    if isinstance(field, dict):
                        yield field
                        yield from cms_fields(field)
                for key, child in value.items():
                    if key != "fields":
                        yield from cms_fields(child)
            elif isinstance(value, list):
                for child in value:
                    yield from cms_fields(child)

        for field in cms_fields(cms):
            for key in ["name", "label", "default"]:
                value = field.get(key)
                if isinstance(value, str):
                    normalized = value.casefold()
                    self.assertNotIn("resume", normalized)
                    self.assertNotIn("cv upload", normalized)

    def test_owner_approved_portrait_is_canonical(self):
        from hashlib import sha256
        from PIL import Image

        portrait = ROOT / "assets/media/authors/me.jpg"
        self.assertTrue(portrait.is_file())
        self.assertEqual(
            sha256(portrait.read_bytes()).hexdigest().upper(),
            "DFF374EC5453A74392DB54F8B3C1ADE3F3486C71A1EA86271F5AE6116A1A4423",
        )
        with Image.open(portrait) as image:
            self.assertEqual(image.size, (1752, 2291))

    def test_cv_is_generated_and_template_resume_is_removed(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("static/uploads/sean-ma-cv.pdf", ignore)
        self.assertIn("output/cv/", ignore)
        self.assertIn("tmp/pdfs/", ignore)
        self.assertFalse((ROOT / "static/uploads/resume.pdf").exists())
        homepage = (ROOT / "content/_index.md").read_text(encoding="utf-8")
        self.assertIn("url: uploads/sean-ma-cv.pdf", homepage)
        self.assertNotIn("resume.pdf", homepage)

    def test_publication_import_workflow_is_failure_gated_and_least_privilege(self):
        self.assertFalse(
            (ROOT / ".github/workflows/import-publications.yml").exists(),
            "obsolete template importer must not retain write permissions",
        )
        workflow = self.load_workflow(".github/workflows/import-publication.yml")
        push_paths = workflow["on"]["push"]["paths"]
        self.assertIn("data/publication-imports/**.yml", push_paths)
        self.assertIn("content/publications/**/index.md", push_paths)
        self.assertNotIn("permissions", workflow)

        import_job = workflow["jobs"]["import"]
        self.assertEqual(import_job["permissions"], {"contents": "write"})
        steps = {step["name"]: step for step in import_job["steps"] if "name" in step}
        importer = steps["Import pending requests and synchronise reviewed publications"]
        self.assertEqual(importer["continue-on-error"], "true")
        self.assertEqual(importer["env"], {"IEEE_API_KEY": "${{ secrets.IEEE_API_KEY }}"})
        self.assertIn("--all-pending", importer["run"])

        commit = steps["Commit generated drafts and request statuses"]
        self.assertEqual(commit["if"], "always()")
        self.assertIn("git add -- data/publication-imports content/publications", commit["run"])
        self.assertNotIn("git add .", commit["run"])

        report = steps["Report importer failure after preserving status"]
        self.assertEqual(report["if"], "steps.importer.outcome == 'failure'")
        self.assertIn("exit 1", report["run"])

        dispatch = workflow["jobs"]["dispatch"]
        self.assertEqual(dispatch["needs"], "import")
        self.assertEqual(dispatch["if"], "needs.import.result == 'success'")
        self.assertEqual(dispatch["permissions"], {"actions": "write"})
        self.assertNotIn("secrets", dispatch)
        dispatch_step = dispatch["steps"][0]
        self.assertIn(
            'gh workflow run deploy.yml --repo "${{ github.repository }}" --ref main',
            dispatch_step["run"],
        )

    def test_deploy_defers_publication_changes_to_import_validation(self):
        workflow = self.load_workflow(".github/workflows/deploy.yml")
        self.assertIn("paths-ignore", workflow["on"]["push"])
        ignored = workflow["on"]["push"]["paths-ignore"]
        self.assertIn("data/publication-imports/**", ignored)
        self.assertIn("content/publications/**", ignored)

    def test_build_validates_managed_content_before_build_and_output_after_build(self):
        workflow = self.load_workflow(".github/workflows/build.yml")
        steps = workflow["jobs"]["build"]["steps"]
        names = [step.get("name") for step in steps]
        for required_name in [
            "Setup Python",
            "Validate managed publication content",
            "Build with Hugo",
            "Run Python contract and importer tests",
            "Check generated site",
        ]:
            self.assertIn(required_name, names)
        setup_python = names.index("Setup Python")
        validate_content = names.index("Validate managed publication content")
        build_hugo = names.index("Build with Hugo")
        run_tests = names.index("Run Python contract and importer tests")
        check_site = names.index("Check generated site")

        self.assertLess(setup_python, validate_content)
        self.assertLess(validate_content, build_hugo)
        self.assertLess(build_hugo, run_tests)
        self.assertLess(run_tests, check_site)
        validation = steps[validate_content]["run"]
        self.assertEqual(
            validation,
            "python scripts/check_publication_sync.py --repo-root .",
        )
        sync_gate = (ROOT / "scripts/check_publication_sync.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("--porcelain", sync_gate)
        self.assertIn("--untracked-files=all", sync_gate)
        self.assertIn("content/publications", sync_gate)
        self.assertIn("--content content", steps[check_site]["run"])

    def test_build_python_cache_uses_the_declared_requirements_file(self):
        workflow = self.load_workflow(".github/workflows/build.yml")
        steps = workflow["jobs"]["build"]["steps"]
        setup_python = next(step for step in steps if step.get("name") == "Setup Python")

        self.assertEqual(
            setup_python["with"]["cache-dependency-path"],
            "requirements-dev.txt",
        )

    def test_build_generates_cv_before_hugo_and_artifact_upload(self):
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        )
        steps = workflow["jobs"]["build"]["steps"]
        names = [step.get("name", "") for step in steps]
        generate_index = names.index("Generate Academic CV")
        hugo_index = names.index("Build with Hugo")
        upload_index = names.index("Upload artifact")
        self.assertLess(generate_index, hugo_index)
        self.assertLess(hugo_index, upload_index)
        command = steps[generate_index]["run"]
        self.assertIn("python -m scripts.generate_cv", command)
        self.assertIn("--portrait assets/media/authors/me.jpg", command)
        self.assertIn("--output static/uploads/sean-ma-cv.pdf", command)
        self.assertIn("--review-report output/cv/publication-review.md", command)

    def test_workflow_hugo_fallback_matches_repository_pin(self):
        pin = self.load_yaml("hugoblox.yaml")["build"]["hugo_version"]
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn(f'DEFAULT_VERSION="{pin}"', workflow)

if __name__ == "__main__":
    unittest.main()
