# Phase 3: Tests & notes (design)

Status: **draft, waiting on 4 owner decisions** (bottom). Spec: parts 3-5 (sections 5, 6, 7),
9.2-9.3 (student view), 10.4 (file security), edge-case register (Tests/Notes/Files).

## Files: private by default
- Stored with Django `FileField`s on the configured storage (local disk now; private cloud bucket
  in Phase 6, with no code change). Like Labe1, the DB keeps only the file's **key/path**, never a URL.
- **No public file URLs.** Every open/download goes through `GET .../download/`, which checks
  login + role + assignment, then streams the file (`Content-Disposition`, `no-store`).
- Uploads: PDF only, size cap (`MAX_UPLOAD_SIZE_MB`, 20 MB), checked by **file signature**
  (`%PDF-`), not just the extension, so a renamed `.exe` is rejected. Random stored names.

## Models (new `learning` app)
| Model (table) | Key fields |
|---|---|
| `TestPaper` (`test_papers`) | title, description, board, standard, subject, chapters (M2M), semester (1/2), academic_year, test_date, max_marks, remarks, uploaded_by, `is_archived` |
| `Note` (`notes`) | title, description, board, standard, subject, chapters, semester, academic_year, remarks, uploaded_by, `is_archived` |
| `DocumentFile` (`document_files`) | owner (test paper / note), kind (`PAPER` / `ANSWER_KEY` / `NOTE`), file, version no., size, sha256, uploaded_by, `is_current` |
| `TestAssignment` (`test_assignments`) | student, test_paper, assigned_by, assigned_at, due/test date, remarks, `answer_key_visible`, status (ASSIGNED / REVOKED), revoked_by/at, **marks_obtained, graded_by/at, grade_remarks** |
| `NoteAssignment` (`note_assignments`) | student, note, assigned_by/at, remarks, status, revoked_by/at |

- One **active** assignment per (student, item); revoke + reassign keeps both rows (spec 7.4).
- Replacing a PDF adds a new `DocumentFile` version; old versions kept (spec 5.5 "preserve history").
- Duplicate upload (same sha256 for the same paper/note) is flagged.

## Who does what
| | Admin | Teacher | Portal (parent/student) |
|---|---|---|---|
| Upload / edit / replace / archive tests & notes | ✅ | ✅ | ❌ |
| Assign / revoke to students (single + bulk, partial-failure report) | ✅ | ✅ | ❌ |
| Release answer key per assignment | ✅ | ✅ | ❌ |
| Enter marks / grade | ✅ | ✅ | ❌ |
| See archive | all | all | ❌ |
| See & download | all | all | **only assigned, not revoked, student ACTIVE** |
| Answer key | ✅ | ✅ | only if released for that assignment |

Search/filter/sort per spec 5.2 / 6.2; pagination; audit log for uploads, replacements,
assignments, revocations, grades.

## Open decisions
1. **Replacing an already-assigned PDF:** students see the **latest** version (old kept for
   history), or each assignment stays **pinned** to the version it was given? *Rec: latest.*
2. **Teachers:** can they work with **all** students/standards, or only the standards/subjects
   assigned to them? *Rec: all for now (small institute); restrict later if needed.*
3. **Marks:** record marks per test assignment now (teachers grade)? *Rec: yes.*
4. **Student submissions** (students uploading answer sheets): needed, or tests are taken on paper
   at the institute? *Rec: not now.*
