from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from nova.apps.permissions import PermissionEngine, PermissionClass
from nova.apps.audit import AuditLog
from nova.capabilities.registry import CapabilityProfile, Capability
from nova.providers.resolver import ProviderResolver
from .safety import SafetyClass
from .state import ExecutionState


@dataclass
class ExecutionResult:
    ok: bool
    stage: str
    message: str
    data: Any = None
    provider: str | None = None
    state: str = ExecutionState.CREATED.value


class UniversalExecutor:
    def __init__(self, permissions: PermissionEngine, audit: AuditLog | None = None,
                 resolver: ProviderResolver | None = None) -> None:
        self.permissions = permissions
        self.audit = audit
        self.resolver = resolver or ProviderResolver(audit=audit)

    def run(self, *, request: str, discover_fn: Callable[[], CapabilityProfile],
            capability: Capability, executor_fn: Callable[[str], Any],
            safety: SafetyClass = SafetyClass.READ_ONLY,
            permission_class: PermissionClass = PermissionClass.READ_INSPECT,
            approval_callback=None,
            provider_override: str | None = None,
            available_providers: list[str] | None = None,
            profile_mechanisms: list[str] | None = None) -> ExecutionResult:
        state = ExecutionState.CREATED
        # Discovery
        state = ExecutionState.RESOLVING
        try:
            profile = discover_fn()
        except Exception as exc:
            self._audit("discovery", "failed", str(exc))
            return ExecutionResult(False, "discovery", str(exc), state=ExecutionState.FAILED.value)
        # Capability resolution
        if not profile.supports(capability):
            msg = f"unsupported capability {capability.value}"
            self._audit("capability_resolution", "denied", msg)
            return ExecutionResult(False, "capability_resolution", msg, state=ExecutionState.FAILED.value)
        # Provider selection
        available = available_providers or []
        mechanisms = profile_mechanisms or profile.mechanisms
        if provider_override:
            provider = provider_override
        else:
            provider = self.resolver.resolve(capability.value, available, mechanisms)
        if provider is None:
            msg = "no suitable provider"
            self._audit("provider_selection", "failed", msg)
            return ExecutionResult(False, "provider_selection", msg, state=ExecutionState.FAILED.value)
        self._audit("provider_selection", "selected", provider)
        # Permission check
        state = ExecutionState.AWAITING_APPROVAL
        decision = self.permissions.check(permission_class)
        if not decision.allowed and decision.requires_approval:
            if approval_callback is None or not approval_callback(permission_class.value, {}):
                self._audit("permission", "denied", "approval denied")
                return ExecutionResult(False, "permission", "approval denied", state=ExecutionState.CANCELLED.value)
        state = ExecutionState.AUTHORIZED
        # Execution
        state = ExecutionState.EXECUTING
        try:
            data = executor_fn(provider)
        except Exception as exc:
            # unknown outcome for timeout/connection loss
            if safety in (SafetyClass.NON_IDEMPOTENT, SafetyClass.DESTRUCTIVE, SafetyClass.UNKNOWN):
                state = ExecutionState.UNKNOWN
            else:
                state = ExecutionState.FAILED
            self._audit("execution", "failed", str(exc))
            # Safe fallback only for READ_ONLY
            if safety == SafetyClass.READ_ONLY:
                remaining = [p for p in available if p != provider]
                alt = self.resolver.fallback(provider, remaining)
                if alt is not None:
                    state = ExecutionState.RECOVERING
                    try:
                        data = executor_fn(alt)
                        provider = alt
                        state = ExecutionState.VERIFYING
                    except Exception as exc2:
                        self._audit("fallback", "failed", str(exc2))
                        return ExecutionResult(False, "execution", str(exc2), state=ExecutionState.FAILED.value)
            else:
                return ExecutionResult(False, "execution", str(exc), state=state.value, provider=provider)
        # Verification
        state = ExecutionState.VERIFYING
        verified = data is not None
        final_state = ExecutionState.SUCCEEDED if verified else ExecutionState.FAILED
        self._audit("verification", "success" if verified else "failed", "verified" if verified else "unverified")
        return ExecutionResult(verified, "verification", "ok" if verified else "unverified",
                              data=data, provider=provider, state=final_state.value)

    def _audit(self, stage, decision, msg):
        if self.audit:
            self.audit.record("execution", operation=stage, decision=decision, result=msg)