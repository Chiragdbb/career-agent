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
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { HeroBand } from "@/components/ui/HeroBand";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { ListSkeleton } from "@/components/ui/Skeleton";
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
      setSuccess("Preferences saved — opening job discovery…");
      setPhase("wizard");
      router.push("/jobs?discover=1");
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
      <HeroBand className="mb-8">
        <SoftBadge tone="lavender" className="mb-3">
          Search preferences
        </SoftBadge>
        <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Discover{" "}
          <span className="font-serif italic text-coral">your fit.</span>
        </h1>
        <p className="mt-3 max-w-xl text-sm text-text-muted">
          Describe your ideal role in plain language, refine structured filters, and
          save — we&apos;ll route you to discovery when you&apos;re done.
        </p>
      </HeroBand>

      {error ? <ErrorBanner message={error} /> : null}
      {success ? (
        <p className="mb-4 rounded-2xl border border-line bg-teal-bg/80 px-4 py-3 text-sm font-medium text-teal">
          {success}
        </p>
      ) : null}

      {loading ? (
        <ListSkeleton rows={6} />
      ) : phase === "prompt" ? (
        <div className="mx-auto flex max-w-2xl flex-col items-center py-4 text-center">
          <h2 className="font-serif text-2xl font-semibold text-ink sm:text-3xl">
            What kind of role are you looking for?
          </h2>
          <p className="mt-2 max-w-lg text-sm text-text-muted">
            Describe your ideal role in your own words — we&apos;ll turn it into structured
            preferences you can review.
          </p>
          <textarea
            className="mt-8 min-h-[140px] w-full rounded-xl border border-line bg-paper-raised px-4 py-3 text-left text-sm text-ink shadow-sm focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/20"
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            placeholder="e.g. Senior backend engineer in NYC or remote, $180k+, fintech startups"
          />
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Button loading={parsing} onClick={() => void handleParsePrompt()}>
              Continue
            </Button>
            <GhostButton type="button" onClick={skipToWizard}>
              Set up manually
            </GhostButton>
          </div>
        </div>
      ) : (
        <Card className="border-line bg-white shadow-soft">
          {parseNotes.length > 0 ? (
            <div className="mb-4 rounded-xl border border-line bg-paper px-3 py-2 text-xs text-text-muted">
              <span className="font-medium text-ink">Notes: </span>
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
