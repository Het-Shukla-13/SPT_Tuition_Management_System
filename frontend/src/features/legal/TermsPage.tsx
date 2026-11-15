import { LegalLayout } from "./LegalLayout";

/** Plain-language terms of use for the institute's portal. */
export function TermsPage() {
  return (
    <LegalLayout title="Terms of Use" updated="15 November 2026">
      <section>
        <p>
          Chalkboard is run by Sai Personal Tuitions for its students, their parents or guardians,
          and its teachers. By using it, you agree to these terms.
        </p>
      </section>
      <section>
        <h2>Your login</h2>
        <ul>
          <li>Logins are created by the institute. There is no public sign-up.</li>
          <li>
            Keep your password and login codes private. Never share a code that was sent to you,
            even with someone saying they are from the institute.
          </li>
          <li>
            Tell the office straight away if you think someone else has used your login, or if you
            lose access to your email or phone.
          </li>
          <li>The institute may switch off a login, for example when a student leaves.</li>
        </ul>
      </section>
      <section>
        <h2>Tests, notes and marks</h2>
        <ul>
          <li>
            Tests, notes and answer keys are for the student's own study. Please don't copy, sell or
            share them outside the family.
          </li>
          <li>
            Marks and remarks are shared to help the student improve. If something looks wrong,
            speak to the teacher or the office.
          </li>
        </ul>
      </section>
      <section>
        <h2>Fees</h2>
        <ul>
          <li>Fees are paid at the institute. Chalkboard shows your fee history and receipts.</li>
          <li>
            If a payment or amount looks wrong, contact the office. Corrections are always recorded,
            never silently changed.
          </li>
        </ul>
      </section>
      <section>
        <h2>Using Chalkboard properly</h2>
        <p>
          Don't try to see information that isn't yours, interfere with the app, or use it to bother
          others. Doing so may lead to your login being switched off.
        </p>
      </section>
      <section>
        <h2>Availability and changes</h2>
        <p>
          We try to keep Chalkboard working at all times, but it may sometimes be unavailable for
          maintenance. The institute may update the app and these terms; the date at the top shows
          the latest version.
        </p>
      </section>
      <section>
        <h2>Questions</h2>
        <p>For anything about these terms, contact the Sai Personal Tuitions office.</p>
      </section>
    </LegalLayout>
  );
}
