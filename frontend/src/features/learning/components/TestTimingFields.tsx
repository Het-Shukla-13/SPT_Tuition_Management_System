import { FormField } from "@/components/shared/FormField";
import { Input } from "@/components/ui/input";

import { type Timing, timingSummary } from "../timing";

/** Test day, optional start time and duration, shared by Assign and Edit time. */
export function TestTimingFields({
  value,
  onChange,
}: {
  value: Timing;
  onChange: (t: Timing) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <FormField label="Test date (optional)">
          {(p) => (
            <Input
              {...p}
              type="date"
              value={value.date}
              onChange={(e) => onChange({ ...value, date: e.target.value })}
            />
          )}
        </FormField>
        <FormField label="Start time (optional)">
          {(p) => (
            <Input
              {...p}
              type="time"
              value={value.time}
              disabled={!value.date}
              onChange={(e) => onChange({ ...value, time: e.target.value })}
            />
          )}
        </FormField>
        <FormField label="Duration (minutes)">
          {(p) => (
            <Input
              {...p}
              inputMode="numeric"
              value={value.duration}
              onChange={(e) => onChange({ ...value, duration: e.target.value.replace(/\D/g, "") })}
            />
          )}
        </FormField>
      </div>
      <p className="text-xs text-muted" role="status">
        {timingSummary(value)}
      </p>
    </div>
  );
}
