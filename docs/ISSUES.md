# Documentation Issues and Inconsistencies

This document catalogs all issues found during the documentation standardization review of the cl_server repository.

---

## Issue Index

| ID | Title | Level | Status |
|----|-------|-------|--------|
| DOC-001 | Environment Variables Section Obsolete | Critical | Complete (Store, Compute, pysdk, Auth) |
| DOC-002 | Missing CLI Commands Documentation | High | Complete (Store, Compute, pysdk, Auth, CLI) |
| DOC-003 | Inconsistent tests/QUICK.md Structure | High | Complete (pysdk, CLI) |
| DOC-004 | Missing tests/QUICK.md Files | High | Complete (Store, Compute, Auth) |
| DOC-005 | Testing Strategy in Wrong Location | Medium | Complete (Store, Compute, pysdk, Auth) |
| DOC-006 | Architecture Documentation Scattered | High | Complete (Root) |
| DOC-007 | Missing Testing Redirect in README | Medium | Complete (Store, Compute, pysdk, Auth, CLI) |
| DOC-008 | Non-Standard Markdown Files | Medium | Complete (Store) |
| DOC-009 | Pytest Cache README Files Committed | Low | Open |
| DOC-010 | Inconsistent Installation Documentation | High | Complete (Store, Compute, pysdk, Auth, CLI) |
| DOC-011 | API Endpoints Mixed with CLI Commands | High | Complete (Store, Compute, pysdk, Auth) |
| DOC-012 | Inter-Service Communication in Package Docs | Medium | Complete (Store, Compute, pysdk, Auth) |
| DOC-013 | Missing Workspace Installation Guide | Critical | Complete (Root) |
| DOC-014 | Outdated Documentation vs Code | Critical | Complete (Store, Compute, pysdk, Auth) |
| DOC-015 | Plugin System Documentation Location | Medium | Complete (Store, Compute) |

---

## Critical Issues

### DOC-001: Environment Variables Section Obsolete
**Level:** Critical
**Affected Files:** Most README.md files
**Description:**
The codebase has been restructured to eliminate environment variables except for `CL_SERVER_DIR`. However, most README.md files still contain extensive "Environment Variables" sections documenting variables that are no longer used.

**Current State:**
- Auth service README lists 7 environment variables
- Compute service README lists multiple environment variables
- Store service README lists extensive environment variable configuration

**Expected State:**
- Replace "Environment Variables" section with "CLI Commands & Usage"
- Document command-line arguments for startup scripts
- Only document `CL_SERVER_DIR` if actually used by the service

**Impact:** Users following documentation will try to configure non-existent environment variables

**Files to Update:**
- `services/auth/README.md`
- `services/compute/README.md`
- `services/store/README.md`
- `services/packages/cl_ml_tools/README.md`
- `sdks/pysdk/README.md`
- `sdks/dartsdk/README.md`

---

### DOC-013: Missing Workspace Installation Guide
**Level:** Critical
**Affected Files:** Root README.md
**Description:**
The repository has a workspace installation script (`./install.sh`) that installs all packages in editable mode, but this is not documented in the root README.md. Individual package READMEs don't reference the workspace installation option.

**Current State:**
- `./install.sh` exists at root
- No documentation explaining workspace vs individual installation
- Package READMEs only show individual installation

**Expected State:**
- Root README.md explains workspace installation using `./install.sh`
- Individual package READMEs reference workspace installation
- Clear distinction between two installation approaches

**Impact:** Users don't know about workspace installation option

**Files to Update:**
- `/README.md` (root)
- All package README.md files (installation section)

---

### DOC-014: Outdated Documentation vs Code
**Level:** Critical
**Affected Files:** Multiple
**Description:**
Per user feedback: "The existing documents are not updated for a while" and are inconsistent with actual code. This requires verification that:
- CLI commands match pyproject.toml [project.scripts]
- API endpoints match actual FastAPI route definitions
- Environment variables match actual code usage
- Installation instructions work correctly
- Code examples are tested and accurate

**Current State:**
- Documentation may reference old API endpoints
- CLI commands may not match script names
- Examples may be outdated

**Expected State:**
- All documentation verified against current code
- CLI commands tested and confirmed working
- API endpoint documentation matches routes.py files
- Code examples tested

**Impact:** Users cannot successfully use the services due to incorrect documentation

**Verification Required:**
1. Compare all CLI commands in docs with pyproject.toml
2. Compare all API endpoints in docs with FastAPI route files
3. Test all installation instructions
4. Test all code examples
5. Verify environment variable usage in code

---

## High Issues

### DOC-002: Missing CLI Commands Documentation
**Level:** High
**Affected Files:** Service README.md files
**Description:**
CLI entry points defined in pyproject.toml are not properly documented in README.md files. Some services have multiple scripts that need documentation.

**Missing Documentation:**

**Auth Service (services/auth/):**
- `auth-server` - Documented but may need update

**Compute Service (services/compute/):**
- `compute-migrate` - Migration utility, not documented in README
- `compute-server` - Server startup, needs comprehensive documentation
- `compute-worker` - Worker startup, needs comprehensive documentation

**Store Service (services/store/):**
- `store` - Server startup, needs documentation
- `m-insight-worker` - Worker process, needs documentation

**CLI Python App (apps/cli_python/):**
- `cl-client` - CLI tool, needs documentation updates

**Expected State:**
- Each script has its own section in "CLI Commands & Usage"
- All command-line options documented with examples
- Usage examples for each script

**Impact:** Users don't know how to start services or use CLI tools

**Files to Update:**
- `services/auth/README.md`
- `services/compute/README.md`
- `services/store/README.md`
- `apps/cli_python/README.md`

---

### DOC-003: Inconsistent tests/QUICK.md Structure
**Level:** High
**Affected Files:** Existing tests/QUICK.md files
**Description:**
Existing tests/QUICK.md files contain many sections beyond the required three (unit tests, all tests, integration tests). They include specific test class commands, pattern matching, type checking, etc.

**Current State:**
- `apps/cli_python/tests/QUICK.md` - 9 sections (too many)
- `sdks/pysdk/tests/QUICK.md` - 4 sections (one too many)

**Expected State:**
- ONLY 3 sections:
  1. Run all unit tests
  2. Run all tests
  3. Run all integration tests
- All other commands move to tests/README.md

**Impact:** QUICK.md is not quick - defeats the purpose of a quick reference

**Files to Update:**
- `apps/cli_python/tests/QUICK.md`
- `sdks/pysdk/tests/QUICK.md`

---

### DOC-004: Missing tests/QUICK.md Files
**Level:** High
**Affected Files:** Multiple test directories
**Description:**
Only 2 out of 6+ packages have tests/QUICK.md files. All packages should have this quick reference.

**Missing QUICK.md Files:**
- `services/auth/tests/QUICK.md`
- `services/compute/tests/QUICK.md`
- `services/store/tests/QUICK.md`
- `services/packages/cl_ml_tools/tests/QUICK.md`
- `sdks/dartsdk/test/QUICK.md` (if applicable for Dart)

**Expected State:**
- Every package with tests has a tests/QUICK.md
- All QUICK.md files follow 3-section template

**Impact:** Developers lack quick command reference for most packages

**Files to Create:**
- All missing tests/QUICK.md files listed above

---

### DOC-006: Architecture Documentation Scattered
**Level:** High
**Affected Files:** Multiple INTERNALS.md files
**Description:**
System-wide architecture and inter-service communication are documented in individual INTERNALS.md files. This should be centralized in a root-level architecture document.

**Current State:**
- Each INTERNALS.md describes how its service interacts with others
- No central architecture overview
- Duplicate explanations of JWT auth, MQTT coordination, etc.

**Expected State:**
- Create `docs/ARCHITECTURE.md` with system-wide architecture
- Individual INTERNALS.md focus on package-specific architecture only
- Inter-service communication documented once in central location
- Plugin system documentation in cl_ml_tools only

**Impact:** Understanding system architecture requires reading multiple files

**Files to Create:**
- `docs/ARCHITECTURE.md` (new file)

**Files to Update:**
- Remove inter-service communication from all INTERNALS.md files
- Add reference to docs/ARCHITECTURE.md

---

### DOC-010: Inconsistent Installation Documentation
**Level:** High
**Affected Files:** All README.md files
**Description:**
Installation instructions are inconsistent across packages. Some mention workspace installation, some don't. Format varies between packages.

**Expected State:**
- Standardized installation section in all README.md files
- Two subsections: Individual Package Installation, Workspace Installation
- Workspace installation references root README.md
- Consistent format and commands

**Impact:** Confusing installation experience for users

**Files to Update:**
- All package README.md files

---

### DOC-011: API Endpoints Mixed with CLI Commands
**Level:** High
**Affected Files:** Service README.md files
**Description:**
API Endpoints and CLI Commands are not clearly separated in documentation. They should be distinct sections, and API Endpoints should only appear in service READMEs (not SDKs/libraries).

**Current State:**
- Some READMEs mix API and CLI documentation
- Section naming inconsistent

**Expected State:**
- "CLI Commands & Usage" section for all packages
- "API Endpoints" section ONLY for FastAPI services
- Clear separation between the two
- Libraries/SDKs have no API Endpoints section

**Impact:** Confusion between server API and CLI usage

**Files to Update:**
- `services/auth/README.md`
- `services/compute/README.md`
- `services/store/README.md`
- Verify SDKs don't have API Endpoints sections

---

## Medium Issues

### DOC-005: Testing Strategy in Wrong Location
**Level:** Medium
**Affected Files:** README.md files with Testing sections
**Description:**
Some README.md files contain testing strategy details that belong in tests/README.md. README.md should only have a redirect message.

**Current State:**
- Testing information in README.md files
- Duplicate information between README.md and tests/README.md

**Expected State:**
- README.md has only: redirect to tests/README.md (in top callout box)
- All testing details in tests/README.md

**Impact:** Duplicate information, harder to maintain

**Files to Update:**
- All README.md files with Testing sections

---

### DOC-007: Missing Testing Redirect in README
**Level:** Medium
**Affected Files:** Most README.md files
**Description:**
README.md files should have a testing redirect message at the top (next to the developers message) but most don't.

**Current State:**
- Only developer redirect exists
- Testing information scattered in README

**Expected State:**
```markdown
> **For Developers:** See [INTERNALS.md](INTERNALS.md) for package structure, development workflow, and contribution guidelines.
>
> **For Testing:** See [tests/README.md](tests/README.md) for comprehensive testing guide, test organization, and coverage requirements.
```

**Impact:** Testers don't know where to find testing documentation

**Files to Update:**
- All package README.md files

---

### DOC-008: Non-Standard Markdown Files
**Level:** Medium
**Affected Files:** Various locations
**Description:**
Non-standard markdown files exist throughout the repository that should be relocated to docs/ folder with appropriate naming.

**Files to Relocate:**

**SDK-Specific:**
1. `sdks/dartsdk/CHANGELOG.md` → `docs/dartsdk-changelog.md`
2. `sdks/dartsdk/PYSDK_ADOPTION.md` → `docs/dartsdk-pysdk-adoption.md`
3. `sdks/dartsdk/mqtt_plan.md` → `docs/dartsdk-mqtt-plan.md`
4. `sdks/dartsdk/example/QUICKSTART.md` → `docs/dartsdk-example-quickstart.md`

**App-Specific:**
5. `apps/cli_python/CLI_TEST_RESULTS.md` → `docs/cli-python-test-results.md`
6. `apps/cli_python/IMPLEMENTATION_PLAN.md` → `docs/cli-python-implementation-plan.md`
7. `apps/cli_python/VERIFICATION_RESULTS.md` → `docs/cli-python-verification-results.md`
8. `apps/cli_python/tests/test_integration/TEST_UPDATE_GUIDE.md` → `docs/cli-python-test-update-guide.md`

**Service-Specific:**
9. `services/store/tests/PLUGINS.md` → `docs/store-plugins-testing.md`

**Expected State:**
- All non-standard .md files in docs/ folder
- Naming convention: `{component}-{description}.md`
- No .md files in package directories except standard 4

**Impact:** Repository organization, easier to find reference documentation

---

### DOC-012: Inter-Service Communication in Package Docs
**Level:** Medium
**Affected Files:** INTERNALS.md files
**Description:**
Individual INTERNALS.md files contain explanations of how services interact with each other. This should be in root-level architecture documentation.

**Current State:**
- Each service explains JWT auth flow
- Each service explains MQTT coordination
- Duplicate explanations across files

**Expected State:**
- Inter-service communication only in docs/ARCHITECTURE.md
- Package INTERNALS.md focus on internal architecture only
- Reference to docs/ARCHITECTURE.md for system-wide info

**Impact:** Duplicate information, inconsistent explanations

**Files to Update:**
- All INTERNALS.md files (remove inter-service sections)

---

### DOC-015: Plugin System Documentation Location
**Level:** Medium
**Affected Files:** compute/INTERNALS.md, cl_ml_tools/README.md
**Description:**
Plugin system is specific to cl_ml_tools but may be mentioned in other packages. Clarify where plugin documentation belongs.

**Current State:**
- Plugin system explained in multiple places
- Not clear which packages need plugin updates

**Expected State:**
- Primary plugin documentation in cl_ml_tools
- Other packages mention: "This package uses cl_ml_tools plugins. When adding a new plugin, update X, Y, Z."
- Clear guidance on what needs updating when plugin added

**Impact:** Unclear where to document plugin-related information

**Files to Review:**
- `services/packages/cl_ml_tools/README.md` (primary docs)
- `services/compute/INTERNALS.md` (reference as needed)
- `services/store/INTERNALS.md` (reference as needed)

---

## Low Issues

### DOC-009: Pytest Cache README Files Committed
**Level:** Low
**Affected Files:** .pytest_cache directories
**Description:**
Auto-generated pytest cache README files are committed to the repository. These should be ignored.

**Files Found:**
- `services/auth/.pytest_cache/README.md`
- `services/compute/.pytest_cache/README.md`
- `services/store/.pytest_cache/README.md`
- `services/packages/cl_ml_tools/.pytest_cache/README.md`
- `sdks/pysdk/.pytest_cache/README.md`

**Expected State:**
- `.pytest_cache/` in .gitignore
- These files removed from repository

**Impact:** Repository clutter, no functional impact

**Action Required:**
- Add to .gitignore
- Remove from git tracking

---

## Cosmetic Issues

None identified yet.

---

## Resolution Plan

### Phase 1: Critical Issues (Blocking)
1. DOC-001: Replace Environment Variables with CLI Commands
2. DOC-013: Document workspace installation in root README
3. DOC-014: Verify all documentation against code

### Phase 2: High Issues (Important)
4. DOC-002: Document all CLI commands from pyproject.toml
5. DOC-003: Fix existing tests/QUICK.md to 3 sections
6. DOC-004: Create missing tests/QUICK.md files
7. DOC-006: Create central docs/ARCHITECTURE.md
8. DOC-010: Standardize installation sections
9. DOC-011: Separate API Endpoints from CLI Commands

### Phase 3: Medium Issues (Should Fix)
10. DOC-005: Move testing strategy to tests/README.md
11. DOC-007: Add testing redirect to all READMEs
12. DOC-008: Relocate non-standard markdown files
13. DOC-012: Remove inter-service docs from packages
14. DOC-015: Clarify plugin documentation ownership

### Phase 4: Low Issues (Nice to Have)
15. DOC-009: Add .pytest_cache to gitignore

---

## Verification Checklist

After resolving all issues, verify:

- [ ] All CLI commands documented and match pyproject.toml
- [ ] All API endpoints documented and match route files
- [ ] Environment variables removed except CL_SERVER_DIR
- [ ] Installation works (both individual and workspace)
- [ ] All code examples tested
- [ ] tests/QUICK.md has exactly 3 sections in all packages
- [ ] Architecture documentation centralized
- [ ] No inter-service communication in package docs
- [ ] All non-standard .md files relocated to docs/
- [ ] Testing redirects in all README.md files
- [ ] .pytest_cache in .gitignore

---

## Notes

- This document will be updated as new issues are discovered
- Priority levels: Critical > High > Medium > Low > Cosmetic
- Critical issues must be resolved before template implementation
- Some issues may be discovered during template application
