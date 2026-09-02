"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import {
  buildSettingsPayload,
  DiscoverWizard,
} from "@/components/DiscoverWizard";
import { Button, GhostButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { apiFetch } from "@/lib/api";
import { detectLocaleCurrency, localeHint } from "@/lib/currency";
import {
  DEFAULT_PREFERENCE_SETTINGS,
  hasConfiguredPreferences,
  joinList,
  PreferenceSettings,
} from "@/lib/preferences";
import { createClient } from "@/lib/supabase/client";

type Phase = "prompt" | "wizard";

export default function PreferencesPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("prompt");
  const [wizardStep, setWizardStep] = useState(0);
  const [promptText, setPromptText] = useState("");
  const [parseNotes, setParseNotes] = useState<string[]>([]);
  const [settings, setSettings] = useState<PreferenceSettings>({
    ...DEFAULT_PREFERENCE_SETTINGS,
    salary_currency: detectLocaleCurrency(),
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
          const loaded = {
            ...DEFAULT_PREFERENCE_SETTINGS,
            ...payload.settings,
            salary_currency:
              payload.settings.salary_currency || detectLocaleCurrency(),
          };
          setSettings(loaded);
          setTargetRolesText(joinList(loaded.target_roles));
          setLocationsText(joinList(loaded.locations));
          setIndustriesText(joinList(loaded.industries));
          if (hasConfiguredPreferences(loaded)) {
            setPhase("wizard");
          }
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

  async function savePreferences() {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = buildSettingsPayload(
        settings,
        targetRolesText,
        locationsText,
        industriesText,
      );
      const response = await apiFetch("/api/v1/preferences", {
        method: "PUT",
        body: JSON.stringify({ settings: payload }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const saved = (await response.json()) as { settings: PreferenceSettings };
      const merged = {
        ...DEFAULT_PREFERENCE_SETTINGS,
        ...saved.settings,
        salary_currency: saved.settings.salary_currency || detectLocaleCurrency(),
      };
      setSettings(merged);
      setTargetRolesText(joinList(merged.target_roles));
      setLocationsText(joinList(merged.locations));
      setIndustriesText(joinList(merged.industries));
      setSuccess("Preferences saved.");
      setPhase("wizard");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save preferences",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleParsePrompt() {
    const prompt = promptText.trim();
    if (!prompt) {
      setError("Describe what you're looking for before continuing.");
      return;
    }

    setParsing(true);
    setError(null);
    setSuccess(null);
    setParseNotes([]);
    try {
      const response = await apiFetch("/api/v1/preferences/parse-prompt", {
        method: "POST",
        body: JSON.stringify({
          prompt,
          locale_hint: localeHint(),
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const parsed = (await response.json()) as {
        settings: PreferenceSettings;
        unparsed_notes: string[];
      };
      const merged = {
        ...DEFAULT_PREFERENCE_SETTINGS,
        ...parsed.settings,
        salary_currency:
          parsed.settings.salary_currency || detectLocaleCurrency(),
      };
      setSettings(merged);
      setTargetRolesText(joinList(merged.target_roles));
      setLocationsText(joinList(merged.locations));
      setIndustriesText(joinList(merged.industries));
      setParseNotes(parsed.unparsed_notes ?? []);
      setWizardStep(0);
      setPhase("wizard");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to parse your prompt",
      );
    } finally {
      setParsing(false);
    }
  }

  function startFromPrompt() {
    setPhase("prompt");
    setWizardStep(0);
    setError(null);
    setSuccess(null);
  }

  function skipToWizard() {
    setPhase("wizard");
    setWizardStep(0);
    setError(null);
  }

  return (
    <AppShell active="discover">
      <PageHeader
        title="Discover"
        large
        serif
        subtitle="Describe your ideal role, refine the details, and save your search preferences."
      />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {success ? <p className="mb-4 text-sm text-primary">{success}</p> : null}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : phase === "prompt" ? (
        <Card>
          <div className="space-y-4">
            <label className="block text-sm">
              <span className="font-medium text-foreground">
                What kind of roles are you looking for?
              </span>
              <textarea
                className="mt-2 min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="Senior backend engineer in NYC or remote, $180k+, fintech startups"
              />
            </label>
            <p className="text-xs text-muted-foreground">
              We&apos;ll extract roles, locations, salary, and filters from your
              description. You can review and edit everything in the next steps.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Button loading={parsing} onClick={() => void handleParsePrompt()}>
                Continue
              </Button>
              <GhostButton type="button" onClick={skipToWizard}>
                Set up manually
              </GhostButton>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          {parseNotes.length > 0 ? (
            <div className="mb-4 rounded-md border border-border bg-paper-raised px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Notes: </span>
              {parseNotes.join(" ")}
            </div>
          ) : null}
          <DiscoverWizard
            settings={settings}
            onSettingsChange={setSettings}
            targetRolesText={targetRolesText}
            onTargetRolesTextChange={setTargetRolesText}
            locationsText={locationsText}
            onLocationsTextChange={setLocationsText}
            industriesText={industriesText}
            onIndustriesTextChange={setIndustriesText}
            activeStep={wizardStep}
            onActiveStepChange={setWizardStep}
            onSave={() => void savePreferences()}
            saving={saving}
            onStartFromPrompt={startFromPrompt}
          />
        </Card>
      )}
    </AppShell>
  );
}
