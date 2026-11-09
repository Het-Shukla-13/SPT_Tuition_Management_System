import { PageHeader } from "./PageHeader";
import { EmptyState } from "./States";

/** Placeholder for screens built in a later step (keeps every menu link working). */
export function ComingSoon({ title, step }: { title: string; step: string }) {
  return (
    <>
      <PageHeader title={title} />
      <EmptyState
        title="This screen is being built"
        description={`It arrives in step ${step} of the frontend plan.`}
      />
    </>
  );
}
