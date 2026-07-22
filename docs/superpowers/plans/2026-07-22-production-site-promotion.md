# Production Site Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the approved Hugo preview to `https://leo06051212.github.io/` while preserving the previous Jekyll production revision as a rollback point.

**Architecture:** Prepare a production-only tree on an isolated branch derived from the approved preview. Validate that tree in the preview repository without deploying it, then create a fast-forward production commit whose parent is the old production `master` and whose tree is the validated Hugo release.

**Tech Stack:** Hugo Extended 0.161.1, HugoBlox, Python `unittest`, GitHub Actions, GitHub Pages, Git.

## Global Constraints

- Production URL is exactly `https://leo06051212.github.io/` with base path `/`.
- Production repository is exactly `leo06051212/leo06051212.github.io` and default branch is `master`.
- Preserve the previous production commit on remote branch `backup/pre-hugo-2026-07-22` before updating `master`.
- Do not force-push production history.
- Keep all 33 publications, four selected publications, Research content, Teaching and Supervision content, and generated CV behavior unchanged.

---

### Task 1: Produce and validate the production tree

**Files:**
- Modify: `tests/test_site_contract.py`
- Modify: `tests/test_generated_site.py`
- Modify: `config/_default/hugo.yaml`
- Modify: `config/_default/params.yaml`
- Modify: `.pages.yml`
- Modify: `layouts/_partials/hooks/head-end/noindex.html`
- Modify: `.github/workflows/build.yml`
- Modify: `.github/workflows/deploy.yml`
- Modify: `.github/workflows/import-publication.yml`

**Interfaces:**
- Consumes: approved preview commit `13b79724959c6af07f9e8802909e9100c6eca00e`.
- Produces: a production-root Hugo source tree validated by Linux GitHub Actions.

- [ ] **Step 1: Change contract tests first**

Update assertions to require the root production URL, `/uploads`, indexable pages, production repository and `master` workflows. Update generated-site link patterns from `/research-website-preview/...` to root-relative paths.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest tests.test_site_contract -v`

Expected: failures for the preview URL, noindex hook, preview repository, CMS output, and `main` workflow references.

- [ ] **Step 3: Apply the minimal production configuration**

Set `baseURL` to `https://leo06051212.github.io/`, enable robots, set repository URL and branch to production/master, set Pages media output to `/uploads`, remove only the noindex meta tag, make deploy/import workflows target `master`, and make the build use production base URL and `--base-path /`. Add a standalone candidate validation trigger for `agent/production-release` without adding that branch to the deploy workflow.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_site_contract -v`

Expected: all site contract tests pass.

- [ ] **Step 5: Commit and push the candidate branch**

Run: `git add -- .github .pages.yml config layouts tests docs/superpowers/plans/2026-07-22-production-site-promotion.md && git commit -m "feat: prepare production site release" && git push -u origin agent/production-release`

Expected: GitHub starts the standalone Build workflow; the Deploy workflow does not run for this branch.

- [ ] **Step 6: Verify candidate Actions**

Expected: publication sync, CV generation, Hugo build at the production root, 141+ tests, generated-site check, and artifact upload all succeed.

### Task 2: Preserve and replace production safely

**Files:**
- Remote branch: `leo06051212/leo06051212.github.io:backup/pre-hugo-2026-07-22`
- Remote branch: `leo06051212/leo06051212.github.io:master`

**Interfaces:**
- Consumes: the successful candidate tree from Task 1 and current production `origin/master`.
- Produces: a fast-forward production `master` commit plus a remote rollback branch.

- [ ] **Step 1: Fetch and verify production state**

Confirm the live production SHA still equals the fetched production `master`, and record that SHA.

- [ ] **Step 2: Push the rollback branch**

Push the recorded old production SHA to `refs/heads/backup/pre-hugo-2026-07-22` and verify the remote ref.

- [ ] **Step 3: Create a history-preserving production commit**

Import the candidate tree into the production repository and use `git commit-tree <candidate-tree> -p <old-production-sha>` with message `feat: launch refreshed academic website`. This makes the replacement a fast-forward child of the old production revision without force-pushing.

- [ ] **Step 4: Push production master**

Push the new commit to `refs/heads/master` and verify the remote ref matches it.

- [ ] **Step 5: Verify production Actions and live site**

Expected: Build and Deploy succeed. HTTP 200 checks pass for `/`, `/publications/`, `/research/`, `/teaching/`, `/teaching/uoa-cs-pg-teaching/`, and `/uploads/sean-ma-cv.pdf`; HTML canonical URLs and internal links use the root production path.

