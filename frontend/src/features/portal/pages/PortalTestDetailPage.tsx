import { FileTextIcon, KeyRoundIcon, LockIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useParams } from "react-router";
import { toast } from "sonner";

import { ErrorState } from "@/components/shared/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/envelope";
import { formatDateTime, formatMarks } from "@/lib/format";

import { isUpcoming, openTestFile, usePortalTest } from "../api";
import { PortalHeader } from "../components/PortalHeader";
import { useActiveStudent } from "../student";

const BACK = { to: "/portal/tests", label: "Tests" };

export function PortalTestDetailPage() {
  const { student } = useActiveStudent();
  const id = Number(useParams().id);
  const test = usePortalTest(student.id, id);

  if (test.isPending) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (test.error) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <PortalHeader title="Test" back={BACK} />
        <ErrorState error={test.error} onRetry={() => void test.refetch()} />
      </div>
    );
  }

  const t = test.data;
  const open = (kind: "PAPER" | "ANSWER_KEY") =>
    void openTestFile(student.id, t.id, kind).catch((e: unknown) =>
      toast.error(e instanceof ApiError ? e.message : "Couldn't open the file."),
    );
  const graded = t.marks_obtained != null;

  return (
    <div className="flex flex-col gap-4 p-4">
      <PortalHeader title={t.title} back={BACK} />
      {graded && (
        <Card className="items-center gap-1 border-2 border-primary text-center">
          <span className="text-sm font-bold text-muted">Marks</span>
          <b className="tabular text-4xl">
            {formatMarks(t.marks_obtained)}
            <span className="text-xl text-muted">/{formatMarks(t.max_marks)}</span>
          </b>
          {t.grade_remarks && <p className="text-sm">{t.grade_remarks}</p>}
        </Card>
      )}
      <Card className="gap-0 py-2">
        <dl className="flex flex-col">
          <Fact label="Subject">{t.subject}</Fact>
          <Fact label="Standard">
            {t.standard} · Semester {t.semester}
          </Fact>
          {t.test_starts_at && <Fact label="Starts">{formatDateTime(t.test_starts_at)}</Fact>}
          <Fact label="Ends">{formatDateTime(t.test_ends_at)}</Fact>
          <Fact label="Out of">{formatMarks(t.max_marks)} marks</Fact>
          {t.chapters.length > 0 && (
            <Fact label="Chapters">
              <ul>
                {t.chapters.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </Fact>
          )}
          {(t.remarks || t.description) && (
            <Fact label="From the teacher">{t.remarks || t.description}</Fact>
          )}
        </dl>
      </Card>
      <div className="flex flex-col gap-2">
        <Button size="lg" onClick={() => open("PAPER")}>
          <FileTextIcon className="size-5" aria-hidden="true" />
          Open question paper
        </Button>
        {t.answer_key_available ? (
          <Button size="lg" variant="secondary" onClick={() => open("ANSWER_KEY")}>
            <KeyRoundIcon className="size-5" aria-hidden="true" />
            Open answer key
          </Button>
        ) : (
          t.has_answer_key &&
          isUpcoming(t) && (
            <p className="flex items-center justify-center gap-2 py-2 text-sm text-muted">
              <LockIcon className="size-4" aria-hidden="true" />
              The answer key opens after the test ends.
            </p>
          )
        )}
      </div>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 border-t border-line/70 py-3 first:border-t-0">
      <dt className="text-sm font-semibold text-muted">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}
