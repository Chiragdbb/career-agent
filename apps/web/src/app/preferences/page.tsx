"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type PreferenceSettings = {
  target_roles: string[];
  locations: string[];
  work_arrangements: string[];
  minimum_salary: number | null;
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

const WORK_ARRANGEMENTS = ["remote", "hybrid", "on_site"];
const SENIORITY = [
  "intern",
  "entry",
  "mid",
  "senior",
  "staff",
  "principal",
  "executive",
];
const COMPANY_SIZES = ["startup", "small", "medium", "large", "enterprise"];
const EMPLOYMENT_TYPES = [
  "full_time",
  "part_time",
  "contract",
  "internship",
  "temporary",
];
const JOB_FRESHNESS = [
  "last_24h",
  "last_3d",
  "last_7d",
  "last_14d",
  "last_30d",
  "any",
];
const APP_AUTOMATION = ["manual", "assisted", "auto_with_approval"];
const OUTREACH_APPROVAL = [
  "always_approve",
  "approve_each",
  "auto_when_rules",
];

function parseList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(values: string[]): string {
  return values.join(", ");
}

function toggleInList(list: string[], value: string): string[] {
  return list.includes(value)
    ? list.filter((item) => item !== value)
    : [...list, value];
}

export default function PreferencesPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [settings, setSettings] = useState<PreferenceSettings>({
    target_roles: [],
    locations: [],
    work_arrangements: [],
    minimum_salary: null,
    seniority: [],
    industries: [],
    company_sizes: [],
    employment_types: [],
    job_freshness: "last_7d",
    application_automation_mode: "manual",
    outreach_approval_mode: "approve_each",
    daily_application_limit: 5,
    daily_outreach_limit: 10,
  });
  const [targetRolesText, setTargetRolesText] = useState("");
  const [locationsText, setLocationsText] = useState("");
  const [industriesText, setIndustriesText] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) {
          router.replace("/login");
          return;
        }

        const response = await apiFetch("/api/v1/preferences");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        const payload = (await response.json()) as { settings: PreferenceSettings };
        if (!cancelled) {
          setSettings(payload.settings);
          setTargetRolesText(joinList(payload.settings.target_roles));
          setLocationsText(joinList(payload.settings.locations));
          setIndustriesText(joinList(payload.settings.industries));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load preferences",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: PreferenceSettings = {
        ...settings,
        target_roles: parseList(targetRolesText),
        locations: parseList(locationsText),
        industries: parseList(industriesText),
      };
      const response = await apiFetch("/api/v1/preferences", {
        method: "PUT",
        body: JSON.stringify({ settings: payload }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const saved = (await response.json()) as { settings: PreferenceSettings };
      setSettings(saved.settings);
      setSuccess("Preferences saved.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save preferences",
      );
    } finally {
      setSaving(false);
    }
  }

  function checkboxGroup(
    label: string,
    options: string[],
    selected: string[],
    onChange: (next: string[]) => void,
  ) {
    return (
      <fieldset className="text-sm">
        <legend className="font-medium text-foreground">{label}</legend>
        <div className="mt-2 flex flex-wrap gap-3">
          {options.map((option) => (
            <label key={option} className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={selected.includes(option)}
                onChange={() => onChange(toggleInList(selected, option))}
                className="rounded border-input text-primary focus:ring-ring"
              />
              <span className="text-muted-foreground">{option.replace(/_/g, " ")}</span>
            </label>
          ))}
        </div>
      </fieldset>
    );
  }

  return (
    <AppShell active="discover">
      <PageHeader title="Discover" large serif subtitle="Target roles, locations, automation limits, and approval rules for your search." />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {success ? <p className="mb-4 text-sm text-primary">{success}</p> : null}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <Card>
          <form onSubmit={(e) => void onSubmit(e)} className="space-y-6">
          <label className="block text-sm">
            <span className="font-medium text-foreground">Target roles</span>
            <span className="ml-2 text-muted-foreground">(comma-separated)</span>
            <input
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
              value={targetRolesText}
              onChange={(e) => setTargetRolesText(e.target.value)}
              placeholder="Backend Engineer, Platform Engineer"
            />
          </label>

          <label className="block text-sm">
            <span className="font-medium text-foreground">Locations</span>
            <span className="ml-2 text-zinc-500">(comma-separated)</span>
            <input
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
              value={locationsText}
              onChange={(e) => setLocationsText(e.target.value)}
              placeholder="Remote, New York NY"
            />
          </label>

          {checkboxGroup(
            "Work arrangements",
            WORK_ARRANGEMENTS,
            settings.work_arrangements,
            (next) => setSettings((s) => ({ ...s, work_arrangements: next })),
          )}

          <label className="block text-sm">
            <span className="font-medium text-foreground">Minimum salary (USD)</span>
            <input
              type="number"
              min={0}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
              value={settings.minimum_salary ?? ""}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  minimum_salary: e.target.value ? Number(e.target.value) : null,
                }))
              }
            />
          </label>

          {checkboxGroup("Seniority", SENIORITY, settings.seniority, (next) =>
            setSettings((s) => ({ ...s, seniority: next })),
          )}

          <label className="block text-sm">
            <span className="font-medium text-foreground">Industries</span>
            <span className="ml-2 text-muted-foreground">(comma-separated)</span>
            <input
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
              value={industriesText}
              onChange={(e) => setIndustriesText(e.target.value)}
            />
          </label>

          {checkboxGroup(
            "Company size",
            COMPANY_SIZES,
            settings.company_sizes,
            (next) => setSettings((s) => ({ ...s, company_sizes: next })),
          )}

          {checkboxGroup(
            "Employment type",
            EMPLOYMENT_TYPES,
            settings.employment_types,
            (next) => setSettings((s) => ({ ...s, employment_types: next })),
          )}

          <label className="block text-sm">
            <span className="font-medium text-foreground">Job freshness</span>
            <select
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
              value={settings.job_freshness}
              onChange={(e) =>
                setSettings((s) => ({ ...s, job_freshness: e.target.value }))
              }
            >
              {JOB_FRESHNESS.map((option) => (
                <option key={option} value={option}>
                  {option.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="font-medium text-foreground">
              Application automation mode
            </span>
            <select
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
              value={settings.application_automation_mode}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  application_automation_mode: e.target.value,
                }))
              }
            >
              {APP_AUTOMATION.map((option) => (
                <option key={option} value={option}>
                  {option.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="font-medium text-foreground">Outreach approval mode</span>
            <select
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
              value={settings.outreach_approval_mode}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  outreach_approval_mode: e.target.value,
                }))
              }
            >
              {OUTREACH_APPROVAL.map((option) => (
                <option key={option} value={option}>
                  {option.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="font-medium text-foreground">
                Daily application limit
              </span>
              <input
                type="number"
                min={0}
                max={100}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
                value={settings.daily_application_limit}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    daily_application_limit: Number(e.target.value),
                  }))
                }
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium text-foreground">
                Daily outreach limit
              </span>
              <input
                type="number"
                min={0}
                max={100}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
                value={settings.daily_outreach_limit}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    daily_outreach_limit: Number(e.target.value),
                  }))
                }
              />
            </label>
          </div>

          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save preferences"}
          </Button>
          </form>
        </Card>
      )}
    </AppShell>
  );
}
