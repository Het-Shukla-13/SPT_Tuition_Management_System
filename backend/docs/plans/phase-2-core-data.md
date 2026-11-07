# Phase 2: Core data modelling (design v2)

Status: **agreed flow, final review before code.** Supersedes v1 (open self-signup + approval).

Decisions (owner, 2026-11-07):
- **One institute** (the owner's parents' tuition). No multi-institute support.
- **Invite-only.** Nobody can create an account themselves. The institute adds people; they log in.
- **One login can see several students; one student can be seen by several logins**
  (Netflix-profiles style). Parents usually log in for younger kids; a kid can get their own
  login later. Everyone linked to a student sees exactly what the student sees.
- **Teachers** teach only: tests, notes, assignments, grading. They can't invite anyone or see fees.

Conventions (Labe1): integer PKs, `GlobalTimeStampedModel` / `AbstractTimeStampedModel`,
plural `db_table`s, `*_history` tables with `changed_by`, `created_by`/`updated_by`, services
hold logic, audit log for sensitive changes, per-session state on `UserSession` (like Labe1's
`active_group`).

---

## 1. Who logs in (`User`): roles and names

| Role | Who | Created by |
|---|---|---|
| Owner (`is_superuser` + `ADMIN`) | Platform owner | `createsuperuser` (exists) |
| `ADMIN` | Institute staff running it | Owner |
| `TEACHER` *(new)* | Teaching staff | Admin |
| `PORTAL` *(renames `STUDENT`)* | Parents / students who view linked students | Admin |

`STUDENT` becomes `PORTAL` because the person logging in is often a parent. Existing rows are
migrated. (Only the owner exists today.)

New `User` fields:

| Field | Purpose |
|---|---|
| `first_name`, `last_name` | Filled in by whoever creates the login (like Labe1's invite). Editable by the user in account settings. |
| `invited_by` (FK User, null) | Who created the login |
| `activated_at` (null) | Set on first successful login ("invite accepted", like Labe1's `last_login is None` check) |

## 2. Invite-only (changes to Phase 1 behaviour)

| Today | After |
|---|---|
| `otp/request` + `otp/verify` with `REGISTER` creates a STUDENT | **`REGISTER` removed** from public purposes. Unknown email/phone on `LOGIN` → nothing sent, same response (already so). |
| Google step 2 creates an account if the email has none | **Google never creates accounts** (like Labe1). Unknown email → same `OTP_REQUIRED`-shaped response, but no code is sent, so it can't be used to probe. |
| No way for staff to create logins | **Admin creates logins** (name, role, phone and/or email). An invite message goes out: "You've been added to <institute>. Log in with this number/email." |

## 3. `academics` app: reference data (admin-managed)

`is_active` everywhere (deactivate, never delete while referenced; FKs are `PROTECT`).

| Model (table) | Fields | Unique |
|---|---|---|
| `Board` (`boards`) | `name`, `code` (CBSE) | `code` (ci) |
| `Standard` (`standards`) | `name` ("10th"), `level` (10) | `level` |
| `Subject` (`subjects`) | `name`, `code` | `name` (ci) |
| `Chapter` (`chapters`) | `board`, `standard`, `subject`, `number`, `name` | (board, standard, subject, number) |
| `School` (`schools`) | `name`, `city`, `board` (null) | (name, city) ci |
| `AcademicYear` (`academic_years`) | `name` ("2026-27"), `start_date`, `end_date`, `is_current` | `name`; one `is_current` |

## 4. `students` app

### `StudentProfile` (`student_profiles`), soft-deletable
The student as a person. **Not** a login.

| Group | Fields |
|---|---|
| Identity | `admission_number` (unique, auto), `first_name`, `last_name`, `photo` (optional) |
| Personal | `date_of_birth`, `gender`, `address` (optional) |
| Contact on file | `guardian_name`, `guardian_phone`, `guardian_email` (for the institute to call; NOT a login) |
| Academic (current) | `board`, `standard`, `school` (null), `admission_date` |
| Status | `ACTIVE` / `ON_HOLD` / `LEFT`, `left_on` |
| Admin-only | `remarks`, `created_by`, `updated_by` |

Same names allowed; likely duplicates (same name + DOB, or same guardian phone) are returned as a
warning on create; admin confirms.

### `StudentAccess` (`student_access`): which logins can see which students
| Field | |
|---|---|
| `user` FK (PORTAL login), `student` FK | |
| `granted_by`, `granted_at` | |
| `revoked_by`, `revoked_at` (null = active) | unlinking keeps history |

- Unique: one **active** link per (user, student).
- A login only ever sees students with an active link **and** status `ACTIVE`
  (`ON_HOLD`/`LEFT` → shown as such, no tests/notes/fees; exact rule finalised with those phases).
- Checked in the database on every request: another student's id → `403`/`404`.

### `StudentAcademicHistory` (`student_academic_history`)
`student`, `academic_year`, `board`, `standard`, `school`, `started_on`, `ended_on` (null = current),
`reason` (ADMISSION / PROMOTION / SCHOOL_CHANGE / CORRECTION), `changed_by`.
Changing board/standard/school closes the current row and opens a new one (one transaction).

### Selected student per device
`UserSession.selected_student` (FK, null), like Labe1's per-session `active_group`.
Remembers the last picked student on that device; the API always takes the student id explicitly
and re-checks access, so the stored choice is convenience, never a permission.

## 5. `AdmissionEnquiry` (`admission_enquiries`): public form
`parent_name`, `phone`, `email`, `student_name`, `standard`, `board`, `message`,
`status` (NEW / CONTACTED / ACCEPTED / REJECTED), `handled_by`, `notes`, `student` (set when converted).
Public `POST` is throttled (and gets a CAPTCHA before launch). Never creates a login.

## 6. APIs

| Who | Endpoints |
|---|---|
| Public | `POST /public/enquiries/` |
| Admin: logins | `/admin/users/`: existing list/detail/activate/deactivate/role/contact **+ create login (invite)**, search by phone/email |
| Admin: reference data | `/academics/...` create/update/deactivate (everyone logged in can read active items) |
| Admin: students | `/admin/students/`: list (search name/admission no./guardian phone; filter standard/board/school/status/year; sort; paginate), create (profile + link to existing or new login, one transaction), read, update, change standard/school (history), status, history |
| Admin: access | `/admin/students/{id}/access/`: list / link login / unlink |
| Admin: enquiries | `/admin/enquiries/`: list, update status/notes, convert → prefilled student |
| Portal login | `GET /portal/students/` (my linked students = the picker), `GET /portal/students/{id}/` (profile), `POST /portal/students/{id}/select/` (remember on this device). Tests/notes/fees endpoints come in Phases 3-4 under the same `/portal/students/{id}/` prefix. |
| Teacher | Read students (for assigning work, Phase 3). No fees, no invites, no contact edits. |

Permission classes: `IsAdmin`, `IsTeacher`, `IsStaff` (admin or teacher), `IsPortalUser`, plus an
object-level `HasStudentAccess`.

## 7. Edge cases (tests)
Stranger can't register (OTP or Google); invite login works on first OTP; sibling linking reuses a
login; two parents linked; kid's own login sees only themselves; unlink removes access immediately
and keeps history; login with zero active students sees nothing; student id tampering (IDOR);
teacher can't see fees / invite; student leaves → history intact; change standard keeps history;
duplicate-student warning; admission number unique under concurrency; referenced reference data
can't be deleted; pagination cap.

---

## Still to confirm (small)
1. **Seed data:** which boards, standards and subjects does the tuition teach?
2. **Required student fields:** first & last name, board, standard required; guardian name + phone
   strongly suggested; rest optional. OK?
3. **Admission number format:** `SPT-2026-0001`?
