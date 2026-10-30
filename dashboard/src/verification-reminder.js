export const VERIFICATION_REMINDER_COOKIE = "data_app_verification_reminder_v1";

export function readVerificationReminderDismissed({ storage = globalThis.localStorage } = {}) {
  try { return storage?.getItem(VERIFICATION_REMINDER_COOKIE) === "1"; }
  catch { return false; }
}

export function rememberVerificationReminderDismissed({ storage = globalThis.localStorage } = {}) {
  try {
    storage?.setItem(VERIFICATION_REMINDER_COOKIE, "1");
    return storage?.getItem(VERIFICATION_REMINDER_COOKIE) === "1";
  } catch { return false; }
}
