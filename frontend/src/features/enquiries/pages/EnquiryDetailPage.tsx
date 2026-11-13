import { useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { FormField } from "@/components/shared/FormField";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/States";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { NativeSelect, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { Enquiry } from "@/lib/api/types";
import { formatDateTime, formatPhone } from "@/lib/format";
import { mediumLabel } from "@/lib/options";

import { ENQUIRY_STATUSES, sourceLabel, useEnquiry, useUpdateEnquiry } from "../api";

export function EnquiryDetailPage() {
  const id = Number(useParams().id);
  const enquiry = useEnquiry(id);

  if (enquiry.isPending) return <Skeleton className="h-80 w-full" />;
  if (enquiry.error)
    return <ErrorState error={enquiry.error} onRetry={() => void enquiry.refetch()} />;
  const e = enquiry.data;

  return (
    <>
      <PageHeader
        back={{ to: "/staff/enquiries", label: "Enquiries" }}
        title={e.student_name}
        eyebrow={
          <span className="flex items-center gap-2">
            Received {formatDateTime(e.created_at)} <StatusBadge status={e.status} />
          </span>
        }
        actions={
          e.student ? (
            <Button asChild variant="secondary">
              <Link to={`/staff/students/${e.student}`}>Open admitted student</Link>
            </Button>
          ) : (
            e.status !== "REJECTED" && (
              <Button asChild>
                <Link to={`/staff/students/new?enquiry=${e.id}`}>Admit this student</Link>
              </Button>
            )
          )
        }
      />
      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
        <Card>
          <CardHeader title="Request" />
          <dl className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-3 text-sm">
            <dt className="font-semibold text-muted">Parent</dt>
            <dd>{e.parent_name}</dd>
            <dt className="font-semibold text-muted">Phone</dt>
            <dd>
              <a href={`tel:${e.phone}`} className="tabular font-bold text-primary hover:underline">
                {formatPhone(e.phone)}
              </a>
            </dd>
            <dt className="font-semibold text-muted">Email</dt>
            <dd>
              {e.email ? (
                <a href={`mailto:${e.email}`} className="text-primary hover:underline">
                  {e.email}
                </a>
              ) : (
                "–"
              )}
            </dd>
            <dt className="font-semibold text-muted">Standard</dt>
            <dd>{[e.standard_name, e.board_code].filter(Boolean).join(" · ") || "Not given"}</dd>
            <dt className="font-semibold text-muted">Medium</dt>
            <dd>{mediumLabel(e.medium) || "Not given"}</dd>
            <dt className="font-semibold text-muted">School</dt>
            <dd>{e.school_name || "Not given"}</dd>
            <dt className="font-semibold text-muted">Came via</dt>
            <dd>{sourceLabel(e.source)}</dd>
            <dt className="font-semibold text-muted">Message</dt>
            <dd className="whitespace-pre-wrap">{e.message || "–"}</dd>
          </dl>
        </Card>
        <FollowUp key={e.updated_at} enquiry={e} />
      </div>
    </>
  );
}

/** Status and private notes. Keyed by updated_at, so it resets after each save. */
function FollowUp({ enquiry }: { enquiry: Enquiry }) {
  const update = useUpdateEnquiry(enquiry.id);
  const [status, setStatus] = useState<string>(enquiry.status);
  const [notes, setNotes] = useState(enquiry.notes);
  const changed = status !== enquiry.status || notes !== enquiry.notes;

  return (
    <Card>
      <CardHeader title="Follow-up" />
      <form
        className="flex flex-col gap-4"
        onSubmit={(ev) => {
          ev.preventDefault();
          update.mutate(
            { status, notes },
            {
              onSuccess: () => toast.success("Saved."),
              onError: (err) => toast.error(err.message),
            },
          );
        }}
      >
        <FormField
          label="Status"
          hint={enquiry.student ? "Linked to the admitted student." : undefined}
        >
          {(p) => (
            <NativeSelect
              {...p}
              value={status}
              onChange={(ev) => setStatus(ev.target.value)}
              disabled={!!enquiry.student}
            >
              {ENQUIRY_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
        <FormField label="Notes (only staff see these)">
          {(p) => (
            <Textarea
              {...p}
              rows={5}
              value={notes}
              onChange={(ev) => setNotes(ev.target.value)}
              placeholder="e.g. Called on Monday, visiting Saturday with the mother."
            />
          )}
        </FormField>
        <Button type="submit" disabled={!changed || update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
        </Button>
      </form>
    </Card>
  );
}
