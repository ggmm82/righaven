"""Pluggable fine-grained authorization (resource-level RBAC and beyond)."""

from righaven_core.authz.adapter import GuardrailAuthorizationAdapter
from righaven_core.authz.enforcement import filter_resources_by_authorization, filter_tools_by_authorization
from righaven_core.authz.plugin_authz import (
    PluginAuthorizationError,
    aenforce_plugin_action,
    aenforce_plugin_management,
    afilter_plugin_management,
    afilter_plugin_pages,
    enforce_plugin_action,
    enforce_plugin_management,
)
from righaven_core.authz.plugin_targets import (
    MANAGEMENT_READ_PART,
    MANAGEMENT_WRITE_PART,
    plugin_action_target,
    plugin_management_target,
    plugin_page_target,
)
from righaven_core.authz.principal import build_principal_from_context, normalize_authz_attributes
from righaven_core.authz.provider import AuthorizationProvider, AuthzDecision, AuthzReason, AuthzRequest, Principal
from righaven_core.authz.rbac import RbacAuthorizationProvider
from righaven_core.authz.runtime import resolve_authorization_provider
from righaven_core.authz.sandbox_authz import authorize_sandbox_execution
from righaven_core.authz.skill_filter import filter_available_skills_by_authorization
from righaven_core.authz.tool_filter import apply_tool_authorization

__all__ = [
    "AuthzDecision",
    "AuthzReason",
    "AuthzRequest",
    "AuthorizationProvider",
    "GuardrailAuthorizationAdapter",
    "MANAGEMENT_READ_PART",
    "MANAGEMENT_WRITE_PART",
    "PluginAuthorizationError",
    "Principal",
    "RbacAuthorizationProvider",
    "aenforce_plugin_action",
    "aenforce_plugin_management",
    "afilter_plugin_management",
    "afilter_plugin_pages",
    "apply_tool_authorization",
    "authorize_sandbox_execution",
    "build_principal_from_context",
    "enforce_plugin_action",
    "enforce_plugin_management",
    "filter_available_skills_by_authorization",
    "filter_resources_by_authorization",
    "filter_tools_by_authorization",
    "normalize_authz_attributes",
    "plugin_action_target",
    "plugin_management_target",
    "plugin_page_target",
    "resolve_authorization_provider",
]
