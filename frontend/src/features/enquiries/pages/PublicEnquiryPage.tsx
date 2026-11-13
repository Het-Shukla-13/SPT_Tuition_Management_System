import { ArrowLeftIcon, CheckCircle2Icon } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { AuthHeading, AuthLayout } from "@/features/auth/components/AuthLayout";

import { useSubmitEnquiry } from "../api";
import { EnquiryForm } from "../components/EnquiryForm";

/** Public, no login: a family asks about admission and the institute calls back. */
export function PublicEnquiryPage() {
  const submit = useSubmitEnquiry();
  const [done, setDone] = useState<string | null>(null);

  if (done) {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center gap-3 text-center" role="status">
          <CheckCircle2Icon className="size-12 text-success" aria-hidden="true" />
          <AuthHeading
            title={`Thank you, ${done}!`}
            subtitle="Sai Personal Tuitions will call you back soon."
          />
          <Link to="/login" className="flex min-h-11 items-center text-sm font-bold text-primary">
            Back to log in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Link
        to="/login"
        className="-mb-2 flex min-h-11 items-center gap-1.5 self-start text-sm font-bold text-primary"
      >
        <ArrowLeftIcon className="size-4" aria-hidden="true" />
        Log in
      </Link>
      <AuthHeading
        title="Ask about admission"
        subtitle="Leave your details and the institute will call you back. This doesn't create an account."
      />
      <EnquiryForm
        mode="public"
        onSubmit={async (body) => {
          await submit.mutateAsync(body);
          setDone(body.parent_name);
        }}
      />
    </AuthLayout>
  );
}
