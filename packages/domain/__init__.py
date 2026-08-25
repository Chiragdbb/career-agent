"""Domain / business logic for the Career Agent.

API route handlers and MCP tools must call into this package; they must not
embed business rules or talk to vendor SDKs directly.
"""

from packages.domain.career_workflow import (
    CareerWorkflowResult,
    CareerWorkflowService,
    CareerWorkflowStart,
    CareerWorkflowStep,
)
from packages.domain.human_tasks import (
    HumanTaskCreate,
    HumanTaskResolveInput,
    HumanTaskService,
    HumanTaskType,
    HumanTaskView,
)
from packages.domain.outreach import (
    EmailDeliveryState as OutreachEmailDeliveryState,
    OutreachDraftInput,
    OutreachService,
    OutreachType,
    OutreachView,
)
from packages.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
    NotFoundError,
)
from packages.domain.application_content import ApplicationContentService, GeneratedContent
from packages.domain.application_engine import ApplicationEngine, EngineState, VALID_TRANSITIONS
from packages.domain.application_strategy import (
    ApplicationStrategy,
    ApplicationStrategyService,
    StrategyAction,
    StrategyInput,
)
from packages.domain.company_research import CompanyResearchService, DEFAULT_FRESHNESS_DAYS
from packages.domain.job_discovery import JobDiscoveryService
from packages.domain.job_match import JobMatchService, MatchWeights, ScoreBreakdown
from packages.domain.job_models import ExtractedJob
from packages.domain.jobs import (
    DiscoveryTriggerService,
    JobListingService,
    load_resume_skills,
)
from packages.domain.llm_tasks import LLMTaskService
from packages.domain.people_models import DiscoveredPerson, PeopleResearchResult, RolePriority
from packages.domain.people_research import PeopleResearchService
from packages.domain.preferences import PreferenceSettings, PreferencesService
from packages.domain.profile import ProfileData, ProfileService
from packages.domain.resume_customization import ResumeCustomizationService
from packages.domain.resume_models import (
    PARSER_VERSION,
    StructuredResume,
)
from packages.domain.resume_pdf import ResumePdfService, render_resume_pdf
from packages.domain.resumes import ResumeService, ResumeUploadInput
from packages.domain.tenant_resources import TenantResourceService
from packages.domain.users import UserService

__all__ = [
    "ApplicationContentService",
    "ApplicationEngine",
    "ApplicationStrategy",
    "ApplicationStrategyService",
    "AuthenticationError",
    "AuthorizationError",
    "CareerWorkflowResult",
    "CareerWorkflowService",
    "CareerWorkflowStart",
    "CareerWorkflowStep",
    "CompanyResearchService",
    "DEFAULT_FRESHNESS_DAYS",
    "DiscoveredPerson",
    "DomainError",
    "DiscoveryTriggerService",
    "EngineState",
    "ExtractedJob",
    "GeneratedContent",
    "HumanTaskCreate",
    "HumanTaskResolveInput",
    "HumanTaskService",
    "HumanTaskType",
    "HumanTaskView",
    "JobDiscoveryService",
    "JobListingService",
    "JobMatchService",
    "LLMTaskService",
    "MatchWeights",
    "NotFoundError",
    "OutreachDraftInput",
    "OutreachEmailDeliveryState",
    "OutreachService",
    "OutreachType",
    "OutreachView",
    "PARSER_VERSION",
    "PeopleResearchResult",
    "PeopleResearchService",
    "PreferenceSettings",
    "PreferencesService",
    "ProfileData",
    "ProfileService",
    "ResumeCustomizationService",
    "ResumePdfService",
    "ResumeService",
    "ResumeUploadInput",
    "RolePriority",
    "ScoreBreakdown",
    "StrategyAction",
    "StrategyInput",
    "StructuredResume",
    "TenantResourceService",
    "UserService",
    "VALID_TRANSITIONS",
    "load_resume_skills",
    "render_resume_pdf",
]
