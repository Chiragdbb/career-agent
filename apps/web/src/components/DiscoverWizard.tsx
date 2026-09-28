"use client";

import { FormEvent } from "react";

import { Button, GhostButton } from "@/components/ui/Button";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { FormStepper } from "@/components/ui/FormStepper";
import { currencyOptions, formatCurrencyLabel } from "@/lib/currency";
import {
  APP_AUTOMATION,
  COMPANY_SIZES,
  EMPLOYMENT_TYPES,
  formatOptionLabel,
  JOB_FRESHNESS,
  OUTREACH_APPROVAL,
  parseList,
  PreferenceSettings,
  SENIORITY,
  toggleInList,
  WIZARD_STEPS,
  WORK_ARRANGEMENTS,
} from "@/lib/preferences";

type DiscoverWizardProps = {
  settings: PreferenceSettings;
  onSettingsChange: (settings: PreferenceSettings) => void;
  targetRolesText: string;
  onTargetRolesTextChange: (value: string) => void;
  locationsText: string;
  onLocationsTextChange: (value: string) => void;
  industriesText: string;
  onIndustriesTextChange: (value: string) => void;
  activeStep: number;
  onActiveStepChange: (step: number) => void;
  onSave: () => void;
  saving: boolean;
  onStartFromPrompt?: () => void;
};

const inputClassName =
  "mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm text-ink shadow-sm focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/20";

const selectClassName =
  "mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm text-ink shadow-sm focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/20 appearance-none";

function CheckboxGroup({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: readonly string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <fieldset className="text-sm">
      <legend className="font-medium text-ink">{label}</legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => {
          const active = selected.includes(option);
          return (
            <label
              key={option}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 transition-colors ${
                active
                  ? "border-coral/40 bg-lavender font-medium text-lavender-deep"
                  : "border-line bg-white text-text-muted hover:border-coral/25"
              }`}
            >
              <input
                type="checkbox"
                checked={active}
                onChange={() => onChange(toggleInList(selected, option))}
                className="sr-only"
              />
              <span className="text-[13px]">{formatOptionLabel(option)}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function DiscoverWizard({
  settings,
  onSettingsChange,
  targetRolesText,
  onTargetRolesTextChange,
  locationsText,
  onLocationsTextChange,
  industriesText,
  onIndustriesTextChange,
  activeStep,
  onActiveStepChange,
  onSave,
  saving,
  onStartFromPrompt,
}: DiscoverWizardProps) {
  const currencies = currencyOptions(settings.salary_currency);
  const currencySelectOptions = currencies.map((option) => ({
    value: option.code,
    label: formatCurrencyLabel(option),
  }));
  const salaryCurrency =
    currencySelectOptions.find((o) => o.value === settings.salary_currency)
      ?.value ?? currencySelectOptions[0]?.value ?? "USD";
  const isLastStep = activeStep === WIZARD_STEPS.length - 1;

  function patchSettings(partial: Partial<PreferenceSettings>) {
    onSettingsChange({ ...settings, ...partial });
  }

  function handleNext() {
    if (activeStep < WIZARD_STEPS.length - 1) {
      onActiveStepChange(activeStep + 1);
    }
  }

  function handleBack() {
    if (activeStep > 0) {
      onActiveStepChange(activeStep - 1);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (isLastStep) {
      onSave();
    } else {
      handleNext();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <FormStepper steps={WIZARD_STEPS} activeStep={activeStep} />
        {onStartFromPrompt ? (
          <GhostButton type="button" onClick={onStartFromPrompt} className="shrink-0">
            Update from prompt
          </GhostButton>
        ) : null}
      </div>

      {activeStep === 0 ? (
        <div className="space-y-6">
          <label className="block text-sm">
            <span className="font-medium text-ink">Target roles</span>
            <span className="ml-2 text-text-muted">(comma-separated)</span>
            <input
              className={inputClassName}
              value={targetRolesText}
              onChange={(e) => onTargetRolesTextChange(e.target.value)}
              placeholder="Backend Engineer, Platform Engineer"
            />
          </label>

          <label className="block text-sm">
            <span className="font-medium text-ink">Locations</span>
            <span className="ml-2 text-text-muted">(comma-separated)</span>
            <input
              className={inputClassName}
              value={locationsText}
              onChange={(e) => onLocationsTextChange(e.target.value)}
              placeholder="Remote, New York NY"
            />
          </label>

          <CheckboxGroup
            label="Work arrangements"
            options={WORK_ARRANGEMENTS}
            selected={settings.work_arrangements}
            onChange={(next) => patchSettings({ work_arrangements: next })}
          />
        </div>
      ) : null}

      {activeStep === 1 ? (
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            Set your minimum compensation. Jobs in other currencies are scored
            neutrally until we know the exchange rate.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="font-medium text-ink">Minimum salary</span>
              <input
                type="number"
                min={0}
                className={inputClassName}
                value={settings.minimum_salary ?? ""}
                onChange={(e) =>
                  patchSettings({
                    minimum_salary: e.target.value ? Number(e.target.value) : null,
                  })
                }
                placeholder="150000"
              />
            </label>
            <div className="block text-sm">
              <span className="font-medium text-ink">Currency</span>
              <CustomSelect
                className="mt-1"
                value={salaryCurrency}
                onChange={(next) => patchSettings({ salary_currency: next })}
                options={currencySelectOptions}
                aria-label="Salary currency"
              />
            </div>
          </div>
        </div>
      ) : null}

      {activeStep === 2 ? (
        <div className="space-y-6">
          <CheckboxGroup
            label="Seniority"
            options={SENIORITY}
            selected={settings.seniority}
            onChange={(next) => patchSettings({ seniority: next })}
          />

          <label className="block text-sm">
            <span className="font-medium text-ink">Industries</span>
            <span className="ml-2 text-text-muted">(comma-separated)</span>
            <input
              className={inputClassName}
              value={industriesText}
              onChange={(e) => onIndustriesTextChange(e.target.value)}
              placeholder="Fintech, SaaS"
            />
          </label>

          <CheckboxGroup
            label="Company size"
            options={COMPANY_SIZES}
            selected={settings.company_sizes}
            onChange={(next) => patchSettings({ company_sizes: next })}
          />

          <CheckboxGroup
            label="Employment type"
            options={EMPLOYMENT_TYPES}
            selected={settings.employment_types}
            onChange={(next) => patchSettings({ employment_types: next })}
          />

          <label className="block text-sm">
            <span className="font-medium text-ink">Job freshness</span>
            <select
              className={selectClassName}
              value={settings.job_freshness}
              onChange={(e) => patchSettings({ job_freshness: e.target.value })}
            >
              {JOB_FRESHNESS.map((option) => (
                <option key={option} value={option}>
                  {formatOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {activeStep === 3 ? (
        <div className="space-y-6">
          <label className="block text-sm">
            <span className="font-medium text-ink">
              Application automation mode
            </span>
            <select
              className={selectClassName}
              value={settings.application_automation_mode}
              onChange={(e) =>
                patchSettings({ application_automation_mode: e.target.value })
              }
            >
              {APP_AUTOMATION.map((option) => (
                <option key={option} value={option}>
                  {formatOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="font-medium text-ink">
              Outreach approval mode
            </span>
            <select
              className={selectClassName}
              value={settings.outreach_approval_mode}
              onChange={(e) =>
                patchSettings({ outreach_approval_mode: e.target.value })
              }
            >
              {OUTREACH_APPROVAL.map((option) => (
                <option key={option} value={option}>
                  {formatOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="font-medium text-ink">
                Daily application limit
              </span>
              <input
                type="number"
                min={0}
                max={100}
                className={inputClassName}
                value={settings.daily_application_limit}
                onChange={(e) =>
                  patchSettings({
                    daily_application_limit: Number(e.target.value),
                  })
                }
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium text-ink">
                Daily outreach limit
              </span>
              <input
                type="number"
                min={0}
                max={100}
                className={inputClassName}
                value={settings.daily_outreach_limit}
                onChange={(e) =>
                  patchSettings({
                    daily_outreach_limit: Number(e.target.value),
                  })
                }
              />
            </label>
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <GhostButton
          type="button"
          onClick={handleBack}
          disabled={activeStep === 0 || saving}
        >
          Back
        </GhostButton>
        <Button type="submit" loading={saving && isLastStep}>
          {isLastStep ? (saving ? "Saving…" : "Save preferences") : "Next"}
        </Button>
      </div>
    </form>
  );
}

export function buildSettingsPayload(
  settings: PreferenceSettings,
  targetRolesText: string,
  locationsText: string,
  industriesText: string,
): PreferenceSettings {
  return {
    ...settings,
    target_roles: parseList(targetRolesText),
    locations: parseList(locationsText),
    industries: parseList(industriesText),
  };
}
