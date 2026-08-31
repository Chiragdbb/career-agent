import { redirect } from "next/navigation";

type Props = { searchParams: Promise<{ tab?: string }> };

export default async function ResumesRedirectPage({ searchParams }: Props) {
  const params = await searchParams;
  redirect(`/documents?tab=${params.tab || "resumes"}`);
}
