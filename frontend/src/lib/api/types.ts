/**
 * Friendly names for the generated API types. `schema.d.ts` is generated from
 * the backend's OpenAPI schema (`npm run api:types`): never edit it by hand.
 */
import type { components } from "./schema";

export type Schemas = components["schemas"];

export type User = Schemas["User"];
export type Role = Schemas["RoleEnum"];
export type LoginResult = Schemas["LoginResult"];
export type UserSession = Schemas["UserSession"];
export type TrustedDevice = Schemas["TrustedDevice"];

// Users (admin)
export type AdminUser = Schemas["AdminUser"];
export type InviteResult = Schemas["InviteResult"];

// Academics reference data
export type Board = Schemas["Board"];
export type Standard = Schemas["Standard"];
export type Subject = Schemas["Subject"];
export type Chapter = Schemas["Chapter"];
export type School = Schemas["School"];
export type AcademicYear = Schemas["AcademicYear"];

// Students (admin)
export type StudentListItem = Schemas["StudentList"];
export type StudentDetail = Schemas["StudentDetail"];
export type StudentStatus = Schemas["StudentStatusEnum"];
export type AcademicHistory = Schemas["AcademicHistory"];
export type LinkedLogin = Schemas["LinkedLogin"];
export type AdmissionResult = Schemas["AdmissionResult"];

// Fees (summary rows; full fee screens in F5)
export type FeeAccountListItem = Schemas["FeeAccountList"];

// Tests & notes (staff)
export type TestPaper = Schemas["TestPaper"];
export type Note = Schemas["Note"];
export type DocumentFile = Schemas["DocumentFile"];
export type TestAssignment = Schemas["TestAssignment"];
export type NoteAssignment = Schemas["NoteAssignment"];
export type StaffStudent = Schemas["StaffStudent"];

// Fees (admin)
export type FeeAccountDetail = Schemas["FeeAccountDetail"];
export type LedgerEntry = Schemas["LedgerEntry"];
export type FeeStructure = Schemas["FeeStructure"];
export type PaymentListItem = Schemas["PaymentList"];
