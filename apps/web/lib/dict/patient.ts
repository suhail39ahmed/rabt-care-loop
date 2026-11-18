import { ar } from "./patient.ar";
import { bn } from "./patient.bn";
import { en } from "./patient.en";
import { hi } from "./patient.hi";
import { ml } from "./patient.ml";
import { tl } from "./patient.tl";
import { ur } from "./patient.ur";

export type PatientKey = keyof typeof en;
export const PATIENT: Record<"en" | "ar" | "hi" | "ur" | "ml" | "tl" | "bn", Record<PatientKey, string>> = {
  en,
  ar,
  hi,
  ur,
  ml,
  tl,
  bn,
};
