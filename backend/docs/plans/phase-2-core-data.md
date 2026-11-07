# Phase 2: Core data modelling (design)

Status: **draft for review**. Code starts after the open questions (end of file) are answered.

Spec: sections 4 (student management), 9.4 (student profile), 12 (database architecture),
edge-case register (Students), development rule 4 ("design relationships before models").

Conventions (from Labe1): integer PKs, `GlobalTimeStampedModel` / `AbstractTimeStampedModel`
(soft delete), plural `db_table` names, `*_history` / `*Log` tables with `changed_by`,
`created_by` / `updated_by` on records staff edit, services hold the logic, every change audited.

---

## 1. Names: on `User` (all roles)

| Field | Type | Notes |
|---|---|---|
| `first_name` | char(150), blank | Like Labe1 (`AbstractUser`). |
| `last_name` | char(150), blank | |
| `profile_complete` | computed | `True` once `first_name` is set. Returned by `/auth/me/`. |

- Google sign-up pre-fills both from Google's `given_name` / `family_name`.
- OTP sign-up: frontend sees `profile_complete: false` and asks for the name.
- The email is never stored as a name.

## 2. `academics` app: reference data (admin-managed)

All have `is_active` (deactivate instead of delete) and are **PROTECT**ed from deletion while referenced.

| Model (table) | Fields | Uniqueness |
|---|---|---|
| `Board` (`boards`) | `name` ("Central Board of Secondary Education"), `code` ("CBSE"), `is_active` | `code` unique (case-insensitive) |
| `Standard` (`standards`) | `name` ("10th"), `level` (10, for sorting/promotion), `is_active` | `level` unique |
| `Subject` (`subjects`) | `name` ("Mathematics"), `code` ("MATH"), `is_active` | `name` unique (case-insensitive) |
| `Chapter` (`chapters`) | `board` FK, `standard` FK, `subject` FK, `number`, `name`, `is_active` | (`board`, `standard`, `subject`, `number`) |
| `School` (`schools`) | `name`, `city`, `board` FK (nullable), `is_active` | (`name`, `city`) case-insensitive |
| `AcademicYear` (`academic_years`) | `name` ("2026-27"), `start_date`, `end_date`, `is_current` | `name` unique; at most one `is_current` (partial unique) |

Why chapters are scoped by board + standard + subject: "Chapter 3, Maths" differs between CBSE 10th
and GSEB 10th, and tests/notes (Phase 3) will be tagged with chapters.

Why `School` is a table, not free text: the spec wants filtering by school; free text produces
"St. Xavier's" / "St Xaviers" / "st xavier" as three schools. Admins can add a school in one call.

## 3. `students` app

### `StudentProfile` (`student_profiles`), soft-deletable

| Group | Fields |
|---|---|
| Identity | `user` **OneToOne** (PROTECT), `admission_number` (unique, auto e.g. `SPT-2026-0001`) |
| Personal | `photo` (image, optional), `date_of_birth`, `gender` (optional), `address` |
| Guardian | `guardian_name`, `guardian_relation`, `guardian_phone`, `guardian_email` (emergency contact) |
| Academic (current) | `board` FK, `standard` FK, `school` FK (nullable), `admission_date` |
| Status | `status`: `PENDING` / `ACTIVE` / `ON_HOLD` / `LEFT` |
| Traceability | `created_by`, `updated_by`, `left_on`, `remarks` (admin-only) |

- **One profile per account** (OneToOne), so two students can't share an account, and a student can't get two profiles.
- **Same names are allowed** (spec edge case 1). On admin create, likely duplicates (same name + DOB, or
  same guardian phone) are returned as a warning; the admin confirms with `confirm_duplicate: true`.
- **Leaving** (`LEFT`) keeps everything (fees, tests, history); never hard-deleted.
- **Portal access** (tests/notes/fees, later phases) requires `status = ACTIVE`.

### `StudentAcademicHistory` (`student_academic_history`)

One row per period: `student` FK, `academic_year` FK, `board`, `standard`, `school`,
`started_on`, `ended_on` (null = current), `reason` (`ADMISSION` / `PROMOTION` / `SCHOOL_CHANGE` / `CORRECTION`),
`changed_by`.

Changing a student's board/standard/school closes the current row and opens a new one in the same
transaction (spec edge cases 3-4, "preserve old academic history"). This also enables next year's
"promote all 9th → 10th" (spec's optional *academic year promotion*).

Status changes and other profile edits go to the existing `audit_logs`.

## 4. APIs

**Reference data**: `/api/v1/academics/{boards,standards,subjects,chapters,schools,academic-years}/`
- Any logged-in user: list/read active items (students need them for filters).
- Admin: create / update / deactivate.

**Students (admin)**: `/api/v1/admin/students/`
- List: search (name, email, phone, admission no.), filter (standard, board, school, status, academic year),
  sort (name, admission date, standard, recently added), paginated.
- Create (admission): creates the `User` (email and/or phone) + profile + first history row in one
  transaction; status `ACTIVE`.
- Retrieve: full profile, sections A (personal) and B (academic). C-E (fees/tests/notes) are added in later phases.
- Update; change standard/school (history); set status (approve / hold / left / re-activate); history list.

**Student self**: `/api/v1/students/me/`
- Read own profile.
- Self-signup completion: submit name, board, standard, school → `PENDING` until an admin approves.
- Edit only the fields the spec allows (see Q5).

## 5. Edge cases covered by tests

Duplicate profile for one account; two students same name; student reads/edits another student (IDOR);
student edits academic/admin fields; change standard keeps history; leave with history intact;
deactivating a board/standard in use; deleting a referenced reference row (blocked); admission number
uniqueness under concurrent creates; pagination cap; filters with invalid values.

---

## Open questions (need the owner's decision)

1. **Onboarding**: can students sign up themselves (→ `PENDING` → admin approves), or are they only
   added by admins at admission? *Recommendation: both.*
2. **Required fields** for a student. *Recommendation: required = first & last name, board, standard;
   strongly suggested = guardian name + phone; optional = school, DOB, gender, address, photo.*
3. **Parents**: store guardian contact on the profile now, separate parent accounts later (spec lists
   parent accounts as a future feature)? *Recommendation: yes.*
4. **Seed data**: which boards and standards does the institute teach (e.g. CBSE + GSEB, 5th-12th)?
   Subjects? I'll load these as initial data.
5. **What may a student edit themselves?** *Recommendation: photo and guardian details; name only while
   `PENDING`; board/standard/school always admin-controlled (spec 9.4).*
6. **Admission number**: auto-generate `SPT-<year>-<seq>`, a different format, or none?
7. **Photos**: store now with local storage (served privately in Phase 6), or add photos in Phase 6?
   *Recommendation: add the field now, private serving in Phase 6.*
