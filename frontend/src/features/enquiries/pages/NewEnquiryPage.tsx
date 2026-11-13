import { useNavigate } from "react-router";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/PageHeader";
import { Card } from "@/components/ui/card";

import { useCreateEnquiry } from "../api";
import { EnquiryForm } from "../components/EnquiryForm";

/** Staff record a family who walked in, phoned or was referred, before admission is decided. */
export function NewEnquiryPage() {
  const create = useCreateEnquiry();
  const navigate = useNavigate();
  return (
    <>
      <PageHeader
        back={{ to: "/staff/enquiries", label: "Enquiries" }}
        title="New enquiry"
        eyebrow="For a family who came in or called. When they decide to join, use “Admit this student” on the enquiry."
      />
      <Card className="max-w-2xl">
        <EnquiryForm
          mode="staff"
          onSubmit={async (body) => {
            const enquiry = await create.mutateAsync(body);
            toast.success("Enquiry saved.");
            navigate(`/staff/enquiries/${enquiry.id}`);
          }}
        />
      </Card>
    </>
  );
}
