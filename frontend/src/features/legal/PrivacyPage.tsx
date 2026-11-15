import { LegalLayout } from "./LegalLayout";

/** Plain-language privacy policy, written from what Chalkboard actually stores and does. */
export function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy" updated="15 November 2026">
      <section>
        <p>
          Chalkboard is the online portal of Sai Personal Tuitions for students, parents and
          teachers. This page explains what information it keeps, why, and who can see it.
        </p>
      </section>
      <section>
        <h2>What we keep</h2>
        <ul>
          <li>
            <b>Student details</b> given at admission: name, date of birth, gender, address, school,
            board, standard, medium of instruction, subjects and an optional photo.
          </li>
          <li>
            <b>Parent or guardian details</b>: name, relation, phone number and email.
          </li>
          <li>
            <b>Studies</b>: the tests and notes shared with the student, marks and teachers'
            remarks.
          </li>
          <li>
            <b>Fees</b>: the agreed fee, payments, receipts and any adjustments or refunds.
          </li>
          <li>
            <b>Logins</b>: your email or phone, a scrambled (never readable) form of your password
            if you set one, whether Google sign-in is linked, and a record of the devices and times
            you log in, to keep your account safe.
          </li>
          <li>
            <b>Admission enquiries</b>: the details a family sends through “Ask about admission”.
          </li>
        </ul>
      </section>
      <section>
        <h2>Why we keep it</h2>
        <p>
          Only to run the tuition classes: admissions, sharing tests and notes, recording marks,
          keeping fee records and receipts, and contacting families. We don't sell your information
          or use it for advertising.
        </p>
      </section>
      <section>
        <h2>Who can see it</h2>
        <ul>
          <li>
            <b>Parents and students</b> see only the student or students linked to their login.
          </li>
          <li>
            <b>Teachers</b> see what they need to teach: students, tests, notes and marks. They
            don't see fees.
          </li>
          <li>
            <b>The institute's office (admins)</b> sees everything needed to run the classes,
            including fees and enquiries.
          </li>
        </ul>
        <p>
          Some trusted services handle information for us only to make the app work: sending emails
          and text messages (login codes, invites, receipts), storing uploaded files and photos, and
          Google sign-in if you choose to use it.
        </p>
      </section>
      <section>
        <h2>Keeping it safe</h2>
        <p>
          Logins need a password, Google or a one-time code. A new device is checked with a code
          sent to you, and you can see and remove your trusted devices from “My account”. Files and
          photos are only shown to logged-in people who are allowed to see them, never through
          public links.
        </p>
      </section>
      <section>
        <h2>Cookies</h2>
        <p>
          Chalkboard uses only the cookies it needs to keep you logged in and to remember trusted
          devices. There are no advertising or tracking cookies.
        </p>
      </section>
      <section>
        <h2>How long we keep it</h2>
        <p>
          Records stay while the student studies with us and afterwards for as long as the institute
          needs them for its records, such as fee history and receipts. Ask the office if you'd like
          to know more or want something removed.
        </p>
      </section>
      <section>
        <h2>Your choices</h2>
        <p>
          You can update your own name, email and phone under “My account”. To correct a student's
          details or ask any question about your information, contact the institute office.
        </p>
      </section>
    </LegalLayout>
  );
}
