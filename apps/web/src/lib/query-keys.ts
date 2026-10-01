export const queryKeys = {
  dashboard: {
    all: ["dashboard"] as const,
    summary: ["dashboard", "summary"] as const,
  },
  preferences: {
    all: ["preferences"] as const,
    settings: ["preferences", "settings"] as const,
  },
  resumes: {
    all: ["resumes"] as const,
    list: ["resumes", "list"] as const,
  },
  jobs: {
    all: ["jobs"] as const,
    list: (includeDismissed: boolean) =>
      ["jobs", "list", { includeDismissed }] as const,
  },
  applications: {
    all: ["applications"] as const,
    list: ["applications", "list"] as const,
  },
  approvals: {
    all: ["approvals"] as const,
    tasks: ["approvals", "human-tasks"] as const,
    outreach: ["approvals", "outreach"] as const,
  },
} as const;
