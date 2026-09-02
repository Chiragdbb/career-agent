export type PreferenceSettings = {
  target_roles: string[];
  locations: string[];
  work_arrangements: string[];
  minimum_salary: number | null;
  salary_currency: string;
  seniority: string[];
  industries: string[];
  company_sizes: string[];
  employment_types: string[];
  job_freshness: string;
  application_automation_mode: string;
  outreach_approval_mode: string;
  daily_application_limit: number;
  daily_outreach_limit: number;
};

export const DEFAULT_PREFERENCE_SETTINGS: PreferenceSettings = {
  target_roles: [],
  locations: [],
  work_arrangements: [],
  minimum_salary: null,
  salary_currency: "USD",
  seniority: [],
  industries: [],
  company_sizes: [],
  employment_types: [],
  job_freshness: "last_7d",
  application_automation_mode: "manual",
  outreach_approval_mode: "approve_each",
  daily_application_limit: 5,
  daily_outreach_limit: 10,
};

export const WORK_ARRANGEMENTS = ["remote", "hybrid", "on_site"] as const;
export const SENIORITY = [
  "intern",
  "entry",
  "mid",
  "senior",
  "staff",
  "principal",
  "executive",
] as const;
export const COMPANY_SIZES = [
  "startup",
  "small",
  "medium",
  "large",
  "enterprise",
] as const;
export const EMPLOYMENT_TYPES = [
  "full_time",
  "part_time",
  "contract",
  "internship",
  "temporary",
] as const;
export const JOB_FRESHNESS = [
  "last_24h",
  "last_3d",
  "last_7d",
  "last_14d",
  "last_30d",
  "any",
] as const;
export const APP_AUTOMATION = [
  "manual",
  "assisted",
  "auto_with_approval",
] as const;
export const OUTREACH_APPROVAL = [
  "always_approve",
  "approve_each",
  "auto_when_rules",
] as const;

export const WIZARD_STEPS = [
  { label: "What" },
  { label: "Compensation" },
  { label: "Filters" },
  { label: "Automation" },
] as const;

export function parseList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function joinList(values: string[]): string {
  return values.join(", ");
}

export function toggleInList(list: string[], value: string): string[] {
  return list.includes(value)
    ? list.filter((item) => item !== value)
    : [...list, value];
}

export function hasConfiguredPreferences(settings: PreferenceSettings): boolean {
  return settings.target_roles.length > 0 || settings.locations.length > 0;
}

export function formatOptionLabel(value: string): string {
  return value.replace(/_/g, " ");
}
