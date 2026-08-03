"""
ServiceNow ESC form filler — Playwright-based submission.

Used by cli.py when the REST cart API is unavailable (Workday's ServiceNow config).
Handles Select2 dropdowns, cascading fields, and confirmation parsing.
"""

import json
import re
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os, sys
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

AUTH_FILE = Path.home() / ".browser_automation" / "servicenow_auth.json"
INSTANCE = "https://workday.service-now.com"

# ------------------------------------------------------------------ #
# Known catalog items with their field specs
# ------------------------------------------------------------------ #

CATALOG_ITEMS = {
    "snowflake": {
        "sys_id": "9708058d1bf2c650857ea8e82d4bcba3",
        "name":   "Request access to Snowflake",
        "fields": [
            ("select_env",            "select2",  True,  "Environment",           ["Production", "Non-Production", "Prism - Sandbo﻿x", "Adaptive Planning P&T (Cloud Data Connect)"]),
            ("role_type",             "select2",  True,  "Role type",             ["Legacy", "Consumer"]),
            ("role",                  "select2",  True,  "Snowflake legacy role", ["ROLE_ANALYTICS_ENGINEER", "ROLE_BI_ADMIN_ACCESS", "ROLE_CAOBIT_REPORTING", "ROLE_CX_REPORTER", "ROLE_DATAOPS_SUPPORT", "ROLE_DATA_ANALYST", "ROLE_DATA_ANALYST_PII", "ROLE_DATA_SCIENCE", "ROLE_DATA_VALIDATION", "ROLE_EDS_DATA_ENGINEER", "ROLE_EXPLORATORY_ML", "ROLE_FINANCE_REPORTER", "ROLE_FINANCE_SENSITIVE", "ROLE_GOVERNANCE_ADMIN", "ROLE_GOVERNANCE_ANALYST", "ROLE_MARKETING_REPORTER", "ROLE_PAYROLL_FINANCE_RESTRICTED", "ROLE_PAYROLL_FINANCE_RESTRICTED_PII", "ROLE_PLATFORM_ARCHITECT", "ROLE_PLATFORM_ENGINEER", "ROLE_PP_REPORTER", "ROLE_PT_REPORTER", "ROLE_REVOPS_REPORTER", "ROLE_SALES_REPORTER"]),
            ("consumer_role",         "text",     False, "Consumer role name (shown when role_type='Consumer')", None),
            ("business_justification","textarea", True,  "Business justification", None),
        ],
        "default_vars": {
            "select_env": "Production",
            "role_type": "Legacy",
            "role": "ROLE_DATA_ANALYST",
            "business_justification": "New hire onboarding - need Snowflake access for data analytics work",
        },
        "notes": (
            "TODO: revisit after full migration to Consumer RBAC roles — switch role_type to 'Consumer' and set consumer_role.\n"
            "Current default: Production / Legacy / ROLE_DATA_ANALYST.\n"
            "Role guide: https://workdaybt.atlassian.net/wiki/spaces/EADPS/pages/784171011/\n"
            "Support: #snowflake-help Slack"
        ),
    },
    "sigma": {
        "sys_id": "e8538ab21b5b9e90857ea8e82d4bcbeb",
        "name":   "Request access to Sigma",
        "fields": [
            ("business_function",      "select2",  True,  "Business unit",         ["Enterprise Data & Analytics (ED&A)", "Marketing", "Office of CFO - Business Finance", "Office of CFO - Data & Insights", "Office of CFO - Revenue Accounting & Compensation", "Partner Operations", "Revenue Alignment Operations (RAO)", "Revenue Insights", "Solution Consulting", "Value Management", "Others"]),
            ("url_link_sigma_workbook", "text",    False, "Sigma workbook URL(s)", None),
            ("pii_information",        "select2",  False, "PII access needed",     ["No", "Yes"]),
            ("business_justification", "textarea", True,  "Business justification", None),
        ],
        "default_vars": {
            "business_function":      "Enterprise Data & Analytics (ED&A)",
            "pii_information":        "No",
            "business_justification": "New hire onboarding - need Sigma access for team dashboards and analytics",
        },
        "notes": "email_id, business_title, department are auto-filled from requested_for user context",
    },
    "atlan": {
        "sys_id": "f4bf6e0ddb24c010b89d7e88f496192f",
        "name":   "AD Groups - Request Access",
        "fields": [
            ("u_groups", "select2_multi", True, "AD group to add (type to search)", None),
        ],
        "default_vars": {"u_groups": "Okta - Atlan - HT"},
        "notes": "Atlan: u_groups='Okta - Atlan - HT'  |  Nimbus SQL Lab: u_groups='Okta - Goku'  |  Bitbucket: u_groups='stash-users Atlassian OU'",
    },
    "nimbus_sql_lab": {
        "sys_id": "f4bf6e0ddb24c010b89d7e88f496192f",
        "name":   "AD Groups - Request Access (Nimbus SQL Lab)",
        "fields": [
            ("u_groups", "select2_multi", True, "AD group: Okta - Goku", None),
        ],
        "default_vars": {"u_groups": "Okta - Goku"},
        "notes": (
            "Grants SQL Lab tab access in Nimbus (Apache Superset / Pharos analytics).\n"
            "ALSO requires pharos_swh (pdx.swh.general) to query dw.* schemas.\n"
            "After approval: log into Nimbus first so the team can assign SQL Lab access."
        ),
    },
    "pharos_swh": {
        "sys_id": "f509b9ca593f7100b993434d2ccf882b",
        "name":   "Pharos Data Lake (SWH) Access",
        "fields": [
            ("swh_use_case", "textarea", True, "Business use case / justification", None),
        ],
        "notes": (
            "PREREQUISITE: User must complete required Workday training before submitting:\n"
            "  https://wd5.myworkday.com/workday/learning/course/fe6a776782e610015cd22d43fa5f0000?type=9882927d138b100019b928e75843018d\n"
            "requested_for and swh_supervisory_org are auto-filled from the session user.\n"
            "Approval adds you to LDAP group pdx.swh.general.\n"
            "Data classification: Confidential. No PII allowed in Pharos."
        ),
    },
    "ghe": {
        "sys_id": "1c91a03fdb4ae700b89d7e88f49619de",
        "name":   "Github Access for Jira2 (GHE)",
        "fields": [
            ("justification_for_the_addition", "textarea", True, "Justification for GHE access", None),
        ],
    },
    "bitbucket": {
        "sys_id": "f4bf6e0ddb24c010b89d7e88f496192f",
        "name":   "AD Groups - Request Access (Bitbucket)",
        "fields": [
            ("u_groups", "select2_multi", True, "AD group: Stash-users", None),
        ],
        "default_vars": {"u_groups": "stash-users Atlassian OU"},
        "notes": "Grants access to Bitbucket Server (Stash). Also see: https://workday.service-now.com/esc?id=sc_cat_item&sys_id=something for dedicated Bitbucket form.",
    },
    "lightdash": {
        "sys_id": "dd9332b81b1db550857ea8e82d4bcbcf",
        "name":   "Okta P&T Group Access",
        "fields": [
            ("environment",            "select2",  True, "Okta environment", ['gcpdev', 'corp', 'gcp', 'dcim', 'poweriq', 'inf-idm', 'veza', 'smartscribe', 'cursor', 'coder', 'lightdash', 'fable', 'instabug', 'ixp-delieng', 'greynoise', 'aws_q_developer', 'kube-jenkins', 'aura', 'langsmith', 'temporal', 'peakon_pinecone', 'jenkins', 'devops-planning', 'content_tool', 'imse-analytics', 'testcentral', 'perf-jenkins-prod', 'tango-card', 'perf-jenkins-eng', 'peakon-control', 'analytics-sre', 'bard', 'doppel', 'testrail', 'standardmetric', 'watchdog', 'claude', 'claude-dev', 'genai-studio']),
            ("okta_group_access_needed","typeahead", True, "Specific Okta group name (reference field)", None),
            ("business_justification", "textarea", True, "Business justification", None),
        ],
        "default_vars": {
            "environment":             "coder",
            "okta_group_access_needed":"appsync-coder-prod",
            "business_justification":  "I need to build some models plz",
        },
        "extra_submissions": [
            {
                "environment":             "lightdash",
                "okta_group_access_needed":"appsync-lightdash-prod",
                "business_justification":  "I need to build some models plz",
            },
        ],
    },
    "thycotic": {
        "sys_id": "d49e10ae1b6a46108a3810ad2d4bcbb4",
        "name":   "Service Account - Thycotic/Delinea Onboarding",
        "fields": [
            ("service_account_to_be_added",              "text",     True, "Service account name (exact)", None),
            ("please_specify_the_type_of_service_account", "select2", True, "Type of service account", ["This account be will used to bind with Services", "This account will be used for login", "Both"]),
            ("who_will_be_the_primary_owner_of_this_account", "text", True, "Primary owner email", None),
            ("who_needs_access_to_this_service_account", "text",     True, "Who needs access (email/team)", None),
            ("team_name",                                "text",     True, "Team/folder name", None),
            ("service_account_purpose",                  "textarea", True, "Purpose of the service account", None),
            ("account_usage",                            "textarea", True, "Where the account is currently used", None),
        ],
        "default_vars": {
            "service_account_to_be_added":               "svc-uxdatascience",
            "please_specify_the_type_of_service_account": "Both",
            "who_will_be_the_primary_owner_of_this_account": "suraj.sinha@workday.com",
            "who_needs_access_to_this_service_account":  "blake.tagget@workday.com",
            "team_name":                                 "UX Data Science",
            "service_account_purpose":                   "Pharos Airflow access for automated data pipeline execution",
            "account_usage":                             "Automation scripts",
        },
    },
    "redshift": {
        "sys_id": "4fddcbd31be67810ef8355351a4bcbc7",
        "name":   "Redshift - EDH Environment - Database Access",
        "fields": [
            ("account_type",          "select2",  True,  "Account type",    ["Individual User", "Integration user"]),
            ("environment",           "select2",  True,  "Environment",     ["Dev", "Pfix", "Prod", "UAT"]),
            ("business_group",        "select2",  True,  "Business group",  ["Adaptive", "Data Governance", "Data Management", "Global Support", "Machine Learning", "Marketing", "Presales", "Pricing", "Prism", "Product", "Revops", "Sales", "ServiceNow", "Services", "Other"]),
            ("role",                  "select2",  True,  "Role",            ["Data Analyst", "Data Engineer", "Data Governance", "Operations Engineer", "Power User"]),
            ("business_justification","textarea", True,  "Business justification", None),
        ],
        "default_vars": {
            "account_type":           "Individual User",
            "environment":            "Prod",
            "business_group":         "Product",
            "role":                   "Data Analyst",
            "business_justification": "New hire onboarding - need Redshift access for data analytics work mid snowflake migration",
        },
        "notes": (
            "Credentials delivered via Thycotic after approval.\n"
            "Note: Redshift is being migrated to Snowflake — prefer Snowflake for new workloads."
        ),
    },
    "tableau_user": {
        "sys_id": "524b319dc1faa100b993afb6fbb30858",
        "name":   "Tableau Access Request (User / Viewer)",
        "fields": [
            ("business_justification", "textarea", True, "Business justification for Tableau access", None),
        ],
        "notes": (
            "Grants access to view Tableau Server dashboards.\n"
            "Server: https://tableau-aws-prod.workdayinternal.com\n"
            "CoE docs: https://confluence.workday.com/pages/viewpage.action?pageId=1146830567\n"
            "Support: #tableau-users Slack"
        ),
    },
    "tableau_creator": {
        "sys_id": "968902e5db0e8c50b89d7e88f496195c",
        "name":   "Tableau Desktop License Request (Creator)",
        "fields": [
            ("business_justification", "textarea", True, "Business justification for Tableau Creator license", None),
        ],
        "notes": (
            "Grants Tableau Desktop Creator license — can publish/edit workbooks and data sources.\n"
            "Activate Desktop: sign into tableau-aws-prod.workdayinternal.com with Creator role after approval.\n"
            "Also requires Snowflake role ROLE_BI_ADMIN_ACCESS for Snowflake-connected workbooks.\n"
            "CoE docs: https://confluence.workday.com/pages/viewpage.action?pageId=1146830567\n"
            "Support: #tableau-creators Slack"
        ),
    },
    "github_cloud": {
        "sys_id": "9cc75b6f1b999810fe1443f4bd4bcbdf",
        "name":   "Request form for Github Cloud (BT)",
        # USE CASES:
        #   Platform Access (default — new hire general access):
        #     add_or_remove_access = "Github Cloud - Platform Access"
        #     team = "Other Team", other_team = "<team name>"
        #     No github_username or repository fields needed.
        #
        #   Repository Access (specific repo read/write):
        #     add_or_remove_access = "Github Cloud - Repository Access"
        #     team = "Other Team", other_team = "<team name>"
        #     repository_name = "workday-inc/<repo-name>"
        #     github_username = "<AD username>_workday"
        #     access_level = "Read" | "Maintain" | "Triage" | "Write"
        #
        #   Create New Repository:
        #     add_or_remove_access = "Github Cloud - Create New Repository"
        #     team + other_team, repository_name, repository_type ("Private"|"Internal"), github_username
        #
        #   Remove Access:
        #     add_or_remove_access = "Github Cloud - Remove Access"
        #     team + other_team, business_justification
        "fields": [
            ("add_or_remove_access",   "select2",  True,  "Request type",          ["Github Cloud - Platform Access", "Github Cloud - Create New Repository", "Github Cloud - Repository Access", "Github Cloud - Remove Access"]),
            ("team",                   "select2",  True,  "Team name",             ["BT Enterprise Architecture and Data Services", "BT GTM", "BT ETS", "BT Integrations", "BT Network", "BT ServiceManagement Delivery", "BT Strategy and Business Ops", "BT SystemsEngineering", "BT WoW", "Other Team"]),
            ("other_team",             "text",     False, "Other team name (shown when team='Other Team')", None),
            ("repository_name",        "textarea", False, "Repository name — format: workday-inc/<repo> (shown for Create/Repository Access)", None),
            ("repository_type",        "select2",  False, "Repository type (shown for Create New Repository only)", ["Private", "Internal"]),
            ("github_username",        "text",     False, "GitHub username: AD username + _workday, e.g. first.last_workday (shown for Create/Repository Access)", None),
            ("access_level",           "select2",  False, "Access level (shown for Repository Access only)", ["Read", "Maintain", "Triage", "Write"]),
            ("business_justification", "textarea", True,  "Business justification", None),
        ],
        "default_vars": {
            "add_or_remove_access": "Github Cloud - Platform Access",
            "team": "Other Team",
            "other_team": "P&T RAD Analytics Data Science",
        },
        "notes": (
            "Grants access to GitHub Cloud (github.com/workday* repositories).\n"
            "requested_for, department, email are auto-filled from the session.\n"
            "GitHub username = AD username + _workday (first.last_workday from first.last@workday.com).\n"
            "Support: #bt-devsecops Slack"
        ),
    },
    "bt_jira": {
        "sys_id": "051da0670ffe4b40421a8b2022050eff",
        "name":   "BTJira Application Access",
        "fields": [
            ("u_tower",      "select2",  True,  "BTJira project category", ["EDS", "ED&A", "GTM", "Internal Controls", "Infrastructure", "Services", "BT UX Design", "WoW"]),
            ("u_name",       "typeahead", True,  "BTJira project name (typeahead, filtered by u_tower)", None),
            ("justification", "textarea", True,  "Justification for access", None),
        ],
        "default_vars": {
            "u_tower": "ED&A",
            "u_name": "ED&A - Data Governance (EDADG)",
            "justification": "New hire onboarding - need BT Jira access for team project tracking",
        },
        "notes": (
            "Grants access to BT Jira (workdaybt.atlassian.net — Atlassian Cloud Jira).\n"
            "u_tower = project category; u_name = specific project name (typeahead, options appear after selecting tower).\n"
            "Different from GHE (ghe.megaleo.com) and jira2.workday.com — this is the cloud Jira instance.\n"
            "BT Confluence is a SEPARATE form — use bt_confluence key.\n"
            "Support: #jira-public Slack"
        ),
    },
    "bt_confluence": {
        "sys_id": "934bfbfbfb8ea250f847f8454eefdc51",
        "name":   "BTConfluence Application Access",
        "fields": [
            ("select_confluence",       "select2",   True,  "BTConfluence category", ["EDS", "ED&A", "GTM", "Internal Controls", "Infrastructure", "Services", "BT UX Design", "WoW"]),
            ("u_name",                  "typeahead", True,  "BTConfluence space name (reference field, filtered by select_confluence)", None),
            ("justification_for_addition", "textarea", True, "Justification for access", None),
        ],
        "default_vars": {
            "select_confluence": "ED&A",
            "u_name": "ED&A - Data Governance (EDADG)",
            "justification_for_addition": "New hire onboarding - need BT Confluence access for team documentation",
        },
        "notes": (
            "Grants access to BT Confluence (workdaybt.atlassian.net/wiki — Atlassian Cloud Confluence).\n"
            "select_confluence = space category; u_name = specific space (reference typeahead, filtered by category).\n"
            "Separate form from BT Jira — both are on the same Atlassian tenant but require separate requests.\n"
            "Support: #jira-public Slack"
        ),
    },
    "tableau_user": {
        "sys_id": "524b319dc1faa100b993afb6fbb30858",
        "name":   "Tableau Access Request",
        "fields": [
            ("environment",                                    "select2",  True,  "Tableau environment",      ["Tableau Production Environment [https://tableau-aws-prod.workdayinternal.com]", "Tableau Development Environment [https://tableau-dev-rd.workdayinternal.com]"]),
            ("business_function",                              "select2",  True,  "Business function",        ["Data Quality and Governance", "CDM", "Community Analytics", "Corporate Accounting Office", "Corporate Strategy", "CX Strategy & Operations (Customer Adoption Analytics/Customer Support/CX Analytics/WSP Analytics)", "Enterprise Data & Analytics (ED&A)", "Enterprise Planning & Performance", "Global Partners", "Global Pricing", "IMSE Analytics", "IPE Service Health", "Legal Analytics", "Marketing Strategy, Analytics and Planning", "Marketing Analytics", "Marketing Operations", "OMS", "PCC Insights", "People Analytics", "Product Adoption/Intelligence", "P&T Analytics", "Quantitative Research", "Revenue Operations", "Sales Analytics", "Software Development Engineering", "Solution Consulting", "Value Management", "WFM Time Management", "Others (Enterprise Analytics)"]),
            ("please_select_the_type_of_quantitative_user_research", "select2", False, "Quantitative research sub-type (shown when business_function='Quantitative Research')", ["Quantitative Customer Research (Mobile Usage Customer Success)", "Quantitative-User-Research"]),
            ("business_justification",                         "textarea", True,  "Business justification (include Tableau workbook URL if known)", None),
        ],
        # ONBOARDING: submit this form TWICE — once per use case below.
        "default_vars": {
            "environment": "Tableau Production Environment [https://tableau-aws-prod.workdayinternal.com]",
            "business_function": "Quantitative Research",
            "please_select_the_type_of_quantitative_user_research": "Quantitative-User-Research",
            "business_justification": "New hire onboarding - need Tableau access for team dashboards and analytics",
        },
        "extra_submissions": [
            {
                "environment": "Tableau Production Environment [https://tableau-aws-prod.workdayinternal.com]",
                "business_function": "Product Adoption/Intelligence",
                "business_justification": "New hire onboarding - need Tableau access for Product Adoption dashboards",
            },
        ],
        "notes": (
            "title and department are auto-filled from the user profile.\n"
            "SUBMIT TWICE for onboarding:\n"
            "  1. business_function = 'Quantitative Research' → sub-type = 'Quantitative-User-Research'\n"
            "  2. business_function = 'Product Adoption/Intelligence' (no sub-type)\n"
            "business_justification should include specific Tableau workbook URL(s) when known.\n"
            "Creator access (publish/edit) is a separate form — use tableau_creator key.\n"
            "Support: #tableau-help Slack"
        ),
    },
    "tableau_creator": {
        "sys_id": "968902e5db0e8c50b89d7e88f496195c",
        "name":   "Tableau Desktop License Request",
        "fields": [
            ("please_identify_which_business_function_team_you_are_in", "select2",  True,  "Business function team", ["ARR Analytics", "CDM Product", "Community Analytics", "CX Analytics", "Engineering Product Development", "Global Support Analytics", "Marketing Analytics", "Mobile Analytics", "Pre-Sales Analytics", "Product Insights Hub", "Product Intelligence", "Sales Analytics", "Tech Ops Analytics", "Others"]),
            ("others_is_selected",                                        "text",     False, "Team name when 'Others' is selected", None),
            ("please_list_the_primary_data_sources_you_plan_to_use_for_developing_tableau_dashboards", "textarea", True, "Primary data sources", None),
            ("please_make_self_assessment_to_your_tableau_desktop_skill_level", "select2", True, "Tableau skill level", ["Beginner", "Intermediate", "Advanced"]),
            ("tableau_desktop_license",                                   "textarea", True,  "How you plan to use the license", None),
        ],
        "default_vars": {
            "please_identify_which_business_function_team_you_are_in": "Product Intelligence",
            "please_list_the_primary_data_sources_you_plan_to_use_for_developing_tableau_dashboards": "Redshift, Snowflake, and Pharos/SWH",
            "please_make_self_assessment_to_your_tableau_desktop_skill_level": "Intermediate",
            "tableau_desktop_license": "I will use Tableau Desktop to develop and publish dashboards connecting to Redshift, Snowflake, and Pharos/SWH data sources. I plan to build product usage dashboards when I can't use sigma and iterate on existing dashboards to support data-driven decision making.",
        },
        "notes": (
            "Grants Tableau Creator (Desktop) license for publishing dashboards.\n"
            "Viewer-only access is a separate form — use tableau_user key.\n"
            "Support: #tableau-help Slack"
        ),
    },
}


# ------------------------------------------------------------------ #
# Low-level helpers
# ------------------------------------------------------------------ #

def _load_state() -> dict:
    if not AUTH_FILE.exists():
        raise RuntimeError(f"Auth file not found: {AUTH_FILE}\nRun: python3 tool_connections/servicenow/sso.py")
    return json.loads(AUTH_FILE.read_text())


def _select2_set(page, field_name: str, value: str):
    """Click a Select2 dropdown by field name and pick a matching option."""
    container_id = f"s2id_sp_formfield_{field_name}"
    choice = page.locator(f"#{container_id} .select2-choice, #{container_id} .select2-selection")
    try:
        choice.wait_for(timeout=5000)
        choice.click()
    except PlaywrightTimeout:
        # Fallback: find via select name
        sel_id = page.evaluate(f"document.querySelector(\"select[name='{field_name}']\")?.id || ''")
        page.locator(f"#s2id_{sel_id} .select2-choice").click()
    time.sleep(0.4)

    # Click the matching option
    opts = page.locator(".select2-results li, .select2-results__option")
    for opt in opts.all():
        try:
            text = opt.inner_text().strip()
            if value.lower() in text.lower():
                opt.click()
                time.sleep(1.2)
                return
        except Exception:
            pass
    all_opts = [o.inner_text().strip() for o in opts.all() if o.inner_text().strip()]
    raise RuntimeError(f"Option {value!r} not found in Select2 dropdown for {field_name!r}. Visible options: {all_opts[:10]}")


def _select2_multi_type(page, field_name: str, value: str):
    """Type into a Select2 multi-value field (like u_groups) and pick the matching result."""
    # Try to click the container to activate the input
    container_id = f"s2id_sp_formfield_{field_name}"
    container = page.locator(f"#{container_id}")
    try:
        container.wait_for(timeout=5000)
        container.click()
    except PlaywrightTimeout:
        pass
    time.sleep(0.5)

    # Find the active search input
    input_field = page.locator(".select2-input:visible").first
    try:
        input_field.wait_for(timeout=5000)
    except PlaywrightTimeout:
        raise RuntimeError(f"Could not find Select2 input for {field_name!r}")

    # Type character by character to trigger AJAX search (dropdown already open, don't click again)
    search_term = value[:8]
    input_field.type(search_term, delay=80)
    time.sleep(2.5)  # Wait for AJAX results

    opts = page.locator(".select2-results li, .select2-results__option")
    for opt in opts.all():
        try:
            text = opt.inner_text().strip()
            if text and value.lower() in text.lower():
                opt.click()
                time.sleep(1.0)
                return
        except Exception:
            pass

    # Log what options were actually returned to help diagnose mismatches
    all_opts = [o.inner_text().strip() for o in opts.all() if o.inner_text().strip()]
    raise RuntimeError(f"Group {value!r} not found in multi-select for {field_name!r}. Options visible: {all_opts[:5]}")


def _typeahead_set(page, field_name: str, value: str):
    """
    Fill a ServiceNow reference field (aria-hidden input backed by a glide reference widget).
    The visible search input is a sibling; we find it via the label-id attribute on the hidden input.
    """
    label_id = f"sp_reference_element_sr_{field_name}"
    # The visible search input is identified by aria-labelledby pointing to label_id
    visible_input = page.locator(f"[aria-labelledby='{label_id}']:not([aria-hidden='true'])").first
    try:
        visible_input.wait_for(state="visible", timeout=8000)
    except PlaywrightTimeout:
        # Fallback: force-click the hidden input itself
        visible_input = page.locator(f"[name='{field_name}']")

    visible_input.click(force=True)
    time.sleep(0.5)
    visible_input.type(value[:8], delay=80)
    time.sleep(2.5)

    opts = page.locator(".dropdown-menu li, [role='option'], .select2-results li, .sn-widget-ref-results li")
    for opt in opts.all():
        try:
            text = opt.inner_text().strip()
            if text and value.lower() in text.lower():
                opt.click()
                time.sleep(1.0)
                return
        except Exception:
            pass

    all_opts = [o.inner_text().strip() for o in opts.all() if o.inner_text().strip()]
    raise RuntimeError(f"Typeahead value {value!r} not found for {field_name!r}. Options visible: {all_opts[:5]}")


def _fill_form(page, variables: dict, hint_types: dict | None = None):
    """
    Fill the currently loaded catalog item form with the given variables dict.
    Keys are field names; values are strings to set.
    hint_types: optional dict of field_name -> type string from CATALOG_ITEMS spec
                (select2, select2_multi, text, textarea). Takes precedence over DOM detection.
    Handles: select2, select2_multi, text, textarea, hidden selects.
    """
    hint_types = hint_types or {}
    for field_name, value in variables.items():
        if not value:
            continue

        # Use spec hint if available
        hint = hint_types.get(field_name)
        if hint == "select2_multi":
            try:
                _select2_multi_type(page, field_name, value)
            except RuntimeError as e:
                print(f"  WARNING: {e}", flush=True)
            continue
        if hint == "typeahead":
            try:
                _typeahead_set(page, field_name, value)
            except RuntimeError as e:
                print(f"  WARNING: {e}", flush=True)
            continue
        if hint == "select2":
            try:
                _select2_set(page, field_name, value)
            except RuntimeError as e:
                print(f"  WARNING: {e}", flush=True)
            # Debug: check what value the select actually has after Select2 interaction
            actual_val = page.evaluate(f"document.querySelector(\"select[name='{field_name}']\")?.value || '(not found)'")
            print(f"  [debug] {field_name!r} underlying select value after Select2: {actual_val!r}", flush=True)
            # Force AngularJS ng-model + ng-change to pick up the Select2 change
            page.evaluate(f"""
                () => {{
                    const sel = document.querySelector("select[name='{field_name}']");
                    if (!sel) return;
                    // Ensure underlying select value is set
                    for (let opt of sel.options) {{
                        if (opt.text.trim().toLowerCase().includes("{value.lower()}")) {{
                            sel.value = opt.value;
                            break;
                        }}
                    }}
                    const scope = angular.element(sel).scope();
                    if (!scope) return;
                    scope.$apply(function() {{
                        // Update ng-model's stagedValue directly
                        if (scope.field) scope.field.stagedValue = sel.value;
                        // Call the ng-change handler to trigger cascade
                        if (typeof scope.stagedValueChange === 'function') scope.stagedValueChange();
                    }});
                }}
            """)
            time.sleep(2.5)  # Give Angular time to re-render cascaded fields
            continue
        if hint in ("text", "textarea"):
            # Try normal fill if visible; fall back to AngularJS scope injection if hidden
            try:
                loc = page.locator(f"[name='{field_name}']")
                loc.wait_for(state="visible", timeout=5000)
                loc.click()
                loc.fill("")
                loc.type(value, delay=50)
                # Also push into Angular ng-model in case type() alone isn't enough
                page.evaluate(f"""
                    () => {{
                        const el = document.querySelector("[name='{field_name}']");
                        if (!el) return;
                        try {{
                            const ngModel = angular.element(el).controller('ngModel');
                            if (ngModel) {{ ngModel.$setViewValue("{value}"); ngModel.$render(); }}
                        }} catch(e) {{}}
                        try {{
                            const scope = angular.element(el).scope();
                            if (scope && scope.field) scope.$apply(function() {{ scope.field.stagedValue = "{value}"; }});
                        }} catch(e) {{}}
                    }}
                """)
            except PlaywrightTimeout:
                print(f"  [scope-inject] {field_name!r} not visible — setting via AngularJS scope", flush=True)
                page.evaluate(f"""
                    () => {{
                        const el = document.querySelector("[name='{field_name}']");
                        if (!el) return;
                        const scope = angular.element(el).scope();
                        if (scope) {{
                            scope.$apply(function() {{
                                if (scope.field) scope.field.stagedValue = "{value}";
                            }});
                        }}
                        // Also try ngModel controller
                        try {{
                            const ngModel = angular.element(el).controller('ngModel');
                            if (ngModel) ngModel.$setViewValue("{value}");
                        }} catch(e) {{}}
                    }}
                """)
            time.sleep(0.2)
            continue

        # Fallback: detect from DOM
        field_info = page.evaluate(f"""
            () => {{
                const el = document.querySelector("[name='{field_name}']");
                if (!el) return null;
                return {{ tag: el.tagName.toLowerCase(), type: el.type || '', visible: el.offsetParent !== null }};
            }}
        """)
        if not field_info:
            try:
                _select2_set(page, field_name, value)
            except Exception:
                pass
            continue

        tag = field_info["tag"]
        if tag == "select":
            try:
                _select2_set(page, field_name, value)
            except Exception as e:
                print(f"  WARNING select2 failed for {field_name!r}: {e}", flush=True)
                opts_text = page.evaluate(f"""
                    () => {{
                        const sel = document.querySelector("select[name='{field_name}']");
                        if (!sel) return [];
                        return Array.from(sel.options).map(o => o.text.trim());
                    }}
                """)
                print(f"  [fallback] {field_name!r} options: {opts_text}", flush=True)
                page.evaluate(f"""
                    () => {{
                        const sel = document.querySelector("select[name='{field_name}']");
                        if (sel) {{
                            for (let opt of sel.options) {{
                                if (opt.text.trim().toLowerCase().includes("{value.lower()}")) {{
                                    sel.value = opt.value;
                                    sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                                    if (window.$) $(sel).trigger('change.select2');
                                    break;
                                }}
                            }}
                        }}
                    }}
                """)
                time.sleep(1.5)
        elif tag == "textarea" or (tag == "input" and field_info.get("type") in ("text", "")):
            try:
                page.locator(f"[name='{field_name}']").wait_for(state="visible", timeout=8000)
            except PlaywrightTimeout:
                print(f"  WARNING: {field_name!r} not visible after 8s — skipping", flush=True)
                continue
            page.fill(f"[name='{field_name}']", value)
            time.sleep(0.2)
        elif tag == "input" and "u_groups" in field_name:
            _select2_multi_type(page, field_name, value)


def _parse_confirmation(page) -> dict:
    """Extract RITM/REQ numbers and tracking URL from the confirmation page."""
    body_text = page.locator("body").inner_text()
    url = page.url

    ritm = re.search(r"RITM\d+", body_text)
    req = re.search(r"REQ\d+", body_text)

    # Also look in URL
    sys_id_match = re.search(r"sys_id=([a-f0-9]{32})", url)

    return {
        "ritm": ritm.group(0) if ritm else None,
        "req":  req.group(0) if req else None,
        "sys_id": sys_id_match.group(1) if sys_id_match else None,
        "page_text": body_text[:500],
        "url": url,
    }


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

def submit_item(item_key: str, variables: dict, dry_run: bool = False) -> dict:
    """
    Fill and submit a single ServiceNow catalog item form.

    item_key: 'snowflake', 'sigma', or 'atlan'
    variables: dict of field_name → value
    dry_run: if True, fill the form but don't click Submit

    Returns dict with submission confirmation details.
    """
    if item_key not in CATALOG_ITEMS:
        raise ValueError(f"Unknown item: {item_key!r}. Known: {list(CATALOG_ITEMS)}")

    item = CATALOG_ITEMS[item_key]
    sys_id = item["sys_id"]
    # Merge default_vars (e.g. pharos_metrics always needs u_groups=pharos.metrics)
    merged_vars = {**item.get("default_vars", {}), **variables}
    variables = merged_vars
    state = _load_state()

    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,900", "--window-position=50,50"],
        )
        ctx = browser.new_context(storage_state=state, ignore_https_errors=True)
        page = ctx.new_page()

        url = f"{INSTANCE}/esc?id=sc_cat_item&sys_id={sys_id}&table=sc_cat_item"
        page.goto(url, wait_until="networkidle", timeout=30_000)
        time.sleep(3)

        print(f"  Loaded: {page.title()}", flush=True)

        if dry_run:
            fields = page.evaluate("""
                () => Array.from(document.querySelectorAll('input[name], select[name], textarea[name]'))
                    .map(el => ({ name: el.name, tag: el.tagName.toLowerCase(), id: el.id }))
                    .filter(f => f.name)
            """)
            print(f"  [dry_run] Form fields: {fields}", flush=True)

        # Build hint_types from field spec for accurate field-type routing
        hint_types = {f[0]: f[1] for f in item["fields"]}

        # Fill fields in the order defined by the item spec so cascades work
        field_order = [f[0] for f in item["fields"]]
        for field_name in field_order:
            if field_name in variables and variables[field_name]:
                print(f"  Setting {field_name!r} = {variables[field_name]!r}", flush=True)
                try:
                    _fill_form(page, {field_name: variables[field_name]}, hint_types=hint_types)
                except RuntimeError as e:
                    print(f"  WARNING: {e}", flush=True)
                # Longer pause after selects to allow Angular cascade to render
                field_type = hint_types.get(field_name, "")
                time.sleep(2.0 if field_type in ("select2", "select2_multi") else 0.3)

        # Fill any remaining variables not in the spec order
        for field_name, value in variables.items():
            if field_name not in field_order and value:
                print(f"  Setting {field_name!r} = {value!r}", flush=True)
                try:
                    _fill_form(page, {field_name: value}, hint_types=hint_types)
                except RuntimeError as e:
                    print(f"  WARNING: {e}", flush=True)

        form_url = page.url

        if dry_run:
            print("  [dry_run] Form filled — review and correct in the browser, then click Submit.", flush=True)
            print("  [dry_run] Waiting for you to submit the form...", flush=True)
            try:
                # Wait up to 10 minutes for URL to change (Submit navigates to confirmation)
                page.wait_for_url(lambda url: url != form_url, timeout=600_000)
                time.sleep(2)  # Let confirmation page settle
                result = _parse_confirmation(page)
                # Distinguish real submission from accidental navigation
                if not result.get("ritm") and not result.get("req"):
                    print(f"  [dry_run] URL changed but no RITM/REQ found — may have navigated away without submitting.", flush=True)
                    result["cancelled"] = True
                else:
                    print(f"  Submitted: {result.get('ritm') or result.get('req')}", flush=True)
            except PlaywrightTimeout:
                print("  [dry_run] Timed out waiting for submission.", flush=True)
                result = {"cancelled": True}
            except Exception as e:
                # Browser closed or tab crashed
                print(f"  [dry_run] Browser closed before submission: {e}", flush=True)
                result = {"cancelled": True}
            result["dry_run"] = True
            result["item"] = item_key
            result["item_name"] = item["name"]
            try:
                ctx.close()
                browser.close()
            except Exception:
                pass
            return result

        # Programmatic submit
        print("  Submitting...", flush=True)
        submit_btn = page.locator("button:has-text('Submit')").first
        submit_btn.click()
        time.sleep(5)

        # Check for validation errors
        body_text = page.locator("body").inner_text()
        if "Error" in body_text[:200] or "incomplete" in body_text[:500].lower():
            error_match = re.search(r"Error\s*\n([^\n]+)", body_text)
            error_msg = error_match.group(1).strip() if error_match else "Form validation error (unknown)"
            ctx.close()
            browser.close()
            raise RuntimeError(f"Form validation failed: {error_msg}")

        result = _parse_confirmation(page)
        result["item"] = item_key
        result["item_name"] = item["name"]
        print(f"  Submitted: {result.get('ritm') or result.get('req') or 'unknown'}", flush=True)

        ctx.close()
        browser.close()

    return result


def bundle_submit(bundle: list[dict], dry_run: bool = False) -> list[dict]:
    """
    Submit multiple catalog items sequentially.

    bundle: list of {"item": "snowflake"|"sigma"|"atlan", "variables": {...}}
    Returns list of submission results.
    """
    results = []
    for entry in bundle:
        item_key = entry["item"]
        variables = entry.get("variables", {})
        print(f"\n[{item_key.upper()}]", flush=True)
        try:
            result = submit_item(item_key, variables, dry_run=dry_run)
            results.append(result)
        except Exception as e:
            results.append({"item": item_key, "error": str(e)})
            print(f"  ERROR: {e}", flush=True)
    return results


def list_items() -> dict:
    """Return the catalog item registry with field specs."""
    return {
        key: {
            "sys_id": v["sys_id"],
            "name":   v["name"],
            "fields": [
                {
                    "name":     f[0],
                    "type":     f[1],
                    "required": f[2],
                    "label":    f[3],
                    "choices":  f[4] if f[4] != "dynamic" else "(loaded at runtime)",
                }
                for f in v["fields"]
            ],
            "notes": v.get("notes"),
        }
        for key, v in CATALOG_ITEMS.items()
    }
