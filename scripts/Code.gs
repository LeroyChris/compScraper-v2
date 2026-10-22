/**
 * Audit workflow for the Lomba Aggregator sheet.
 *
 * Tab Audit      -> inbox, filled by the scraper (never edited here)
 * Master Data Lomba -> approved, this is the tab used to draft IG posts
 * Arsip Reject   -> rejected, kept so the scraper never re-adds it
 */

const AUDIT_SHEET_NAME = "Tab Audit";
const MASTER_SHEET_NAME = "Master Data Lomba";
const ARCHIVE_SHEET_NAME = "Arsip Reject";
const STATUS_HEADER = "Status Review";

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("🏆 Lomba Aggregator")
    .addItem("✅ Approve Baris Terpilih", "approveSelectedRows")
    .addItem("⚡ Approve Semua AUTO_APPROVE", "batchApproveAutoRows")
    .addSeparator()
    .addItem("❌ Reject Baris Terpilih", "rejectSelectedRows")
    .addToUi();
}

function getOrCreateSheet(ss, name, headers) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    if (headers && headers.length > 0) {
      sheet.appendRow(headers);
      sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
      sheet.setFrozenRows(1);
    }
  }
  return sheet;
}

function moveRows(sourceSheet, targetSheet, rows, newStatus) {
  const headers = sourceSheet.getRange(1, 1, 1, sourceSheet.getLastColumn()).getValues()[0];
  const statusIndex = headers.indexOf(STATUS_HEADER);
  for (let i = 0; i < rows.length; i++) {
    if (statusIndex !== -1) {
      rows[i][statusIndex] = newStatus;
    }
    targetSheet.appendRow(rows[i]);
  }
}

function approveSelectedRows() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const auditSheet = ss.getSheetByName(AUDIT_SHEET_NAME);

  if (!auditSheet || ss.getActiveSheet().getName() !== AUDIT_SHEET_NAME) {
    ui.alert("Peringatan", "Jalankan dari lembar '" + AUDIT_SHEET_NAME + "'.", ui.ButtonSet.OK);
    return;
  }
  const selection = auditSheet.getActiveRange();
  if (selection.getRow() === 1) {
    ui.alert("Peringatan", "Baris header tidak bisa di-approve.", ui.ButtonSet.OK);
    return;
  }

  const headers = auditSheet.getRange(1, 1, 1, auditSheet.getLastColumn()).getValues()[0];
  const masterSheet = getOrCreateSheet(ss, MASTER_SHEET_NAME, headers);
  const rows = auditSheet
    .getRange(selection.getRow(), 1, selection.getNumRows(), auditSheet.getLastColumn())
    .getValues();

  moveRows(auditSheet, masterSheet, rows, "APPROVED");
  auditSheet.deleteRows(selection.getRow(), selection.getNumRows());
  ui.alert("Berhasil", rows.length + " lomba dipindahkan ke '" + MASTER_SHEET_NAME + "'.", ui.ButtonSet.OK);
}

function batchApproveAutoRows() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const auditSheet = ss.getSheetByName(AUDIT_SHEET_NAME);

  if (!auditSheet) {
    ui.alert("Eror", "Lembar '" + AUDIT_SHEET_NAME + "' tidak ditemukan.", ui.ButtonSet.OK);
    return;
  }
  const data = auditSheet.getDataRange().getValues();
  if (data.length <= 1) {
    ui.alert("Info", "Tidak ada data.", ui.ButtonSet.OK);
    return;
  }
  const statusIndex = data[0].indexOf(STATUS_HEADER);
  if (statusIndex === -1) {
    ui.alert("Eror", "Kolom '" + STATUS_HEADER + "' tidak ditemukan.", ui.ButtonSet.OK);
    return;
  }

  const masterSheet = getOrCreateSheet(ss, MASTER_SHEET_NAME, data[0]);
  let count = 0;
  for (let r = data.length - 1; r >= 1; r--) {
    if (String(data[r][statusIndex]).trim().toUpperCase() === "AUTO_APPROVE") {
      data[r][statusIndex] = "APPROVED";
      masterSheet.appendRow(data[r]);
      auditSheet.deleteRow(r + 1);
      count++;
    }
  }
  ui.alert(
    count > 0 ? "Sukses" : "Info",
    count > 0
      ? count + " lomba AUTO_APPROVE dipindahkan ke Master Data Lomba."
      : "Tidak ada baris AUTO_APPROVE.",
    ui.ButtonSet.OK
  );
}

function rejectSelectedRows() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const auditSheet = ss.getSheetByName(AUDIT_SHEET_NAME);

  if (!auditSheet || ss.getActiveSheet().getName() !== AUDIT_SHEET_NAME) {
    ui.alert("Peringatan", "Jalankan dari lembar '" + AUDIT_SHEET_NAME + "'.", ui.ButtonSet.OK);
    return;
  }
  const selection = auditSheet.getActiveRange();
  if (selection.getRow() === 1) {
    ui.alert("Peringatan", "Baris header tidak bisa di-reject.", ui.ButtonSet.OK);
    return;
  }

  const headers = auditSheet.getRange(1, 1, 1, auditSheet.getLastColumn()).getValues()[0];
  const archiveSheet = getOrCreateSheet(ss, ARCHIVE_SHEET_NAME, headers);
  const rows = auditSheet
    .getRange(selection.getRow(), 1, selection.getNumRows(), auditSheet.getLastColumn())
    .getValues();

  moveRows(auditSheet, archiveSheet, rows, "REJECTED");
  auditSheet.deleteRows(selection.getRow(), selection.getNumRows());
  ui.alert("Selesai", rows.length + " lomba diarsipkan ke '" + ARCHIVE_SHEET_NAME + "'.", ui.ButtonSet.OK);
}
