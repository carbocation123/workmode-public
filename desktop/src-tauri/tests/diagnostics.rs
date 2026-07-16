use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use workmode_public_lib::diagnostics::RunDiagnostics;
use zip::ZipArchive;

struct TempDir {
    path: PathBuf,
}

impl TempDir {
    fn new(label: &str) -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "workmode-public-{label}-{}-{nonce}",
            std::process::id()
        ));
        fs::create_dir_all(&path).unwrap();
        Self { path }
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}

fn read_zip_entry(archive_path: &Path, name: &str) -> String {
    let file = fs::File::open(archive_path).unwrap();
    let mut archive = ZipArchive::new(file).unwrap();
    let mut entry = archive.by_name(name).unwrap();
    let mut content = String::new();
    entry.read_to_string(&mut content).unwrap();
    content
}

#[test]
fn report_zip_contains_only_the_current_run_and_redacts_sensitive_values() {
    let temp = TempDir::new("diagnostics-current-run");
    let logs_dir = temp.path.join("logs");
    let reports_dir = temp.path.join("reports");
    let previous_dir = logs_dir.join("runs").join("run-previous");
    fs::create_dir_all(&previous_dir).unwrap();
    fs::write(
        previous_dir.join("backend.err.log"),
        "PREVIOUS_RUN_MUST_NOT_BE_INCLUDED",
    )
    .unwrap();

    let diagnostics =
        RunDiagnostics::start_with_run_id(&logs_dir, &reports_dir, "0.8.4", "run-current").unwrap();
    fs::write(
        diagnostics.backend_stdout_path(),
        "CURRENT_RUN_MARKER token=super-secret D:\\private\\paper.pdf\n",
    )
    .unwrap();
    fs::write(
        diagnostics.backend_stderr_path(),
        "API_KEY=sk-test-123456789012345678 password=hunter2\n",
    )
    .unwrap();
    diagnostics
        .append_frontend_event(
            "error",
            "unhandledrejection",
            "Authorization: Bearer another-secret at C:\\Users\\Alice\\project\\app.tsx and D:/private/source.ts",
        )
        .unwrap();
    let stored_frontend_log = fs::read_to_string(
        logs_dir
            .join("runs")
            .join("run-current")
            .join("frontend.log"),
    )
    .unwrap();
    assert!(!stored_frontend_log.contains("another-secret"));
    assert!(!stored_frontend_log.contains("C:\\Users\\Alice"));
    assert!(!stored_frontend_log.contains("D:/private"));

    let bundle = diagnostics
        .generate_report("# Error report\nX-Workmode-Token: report-secret\nD:\\private\\notes.md")
        .unwrap();

    assert!(bundle.path.is_file());
    assert_eq!(bundle.path.parent(), Some(reports_dir.as_path()));
    assert_eq!(bundle.run_id, "run-current");

    let report = read_zip_entry(&bundle.path, "report.md");
    let manifest = read_zip_entry(&bundle.path, "manifest.json");
    let log = read_zip_entry(&bundle.path, "current-run.log");

    assert!(report.contains("# Error report"));
    assert!(manifest.contains("\"run_id\": \"run-current\""));
    assert!(manifest.contains("\"version\": \"0.8.4\""));
    assert!(log.contains("CURRENT_RUN_MARKER"));
    assert!(!log.contains("PREVIOUS_RUN_MUST_NOT_BE_INCLUDED"));

    for secret in [
        "super-secret",
        "sk-test-123456789012345678",
        "hunter2",
        "another-secret",
        "report-secret",
        "D:\\private",
        "C:\\Users\\Alice",
    ] {
        assert!(!report.contains(secret), "report leaked {secret}");
        assert!(!log.contains(secret), "log leaked {secret}");
    }
}

#[test]
fn invalid_run_ids_are_rejected_before_creating_directories() {
    let temp = TempDir::new("diagnostics-invalid-run-id");
    let result = RunDiagnostics::start_with_run_id(
        &temp.path.join("logs"),
        &temp.path.join("reports"),
        "0.8.4",
        "../escape",
    );

    assert!(result.is_err());
    assert!(!temp.path.join("escape").exists());
}

#[test]
fn old_run_logs_are_bounded_but_user_generated_reports_are_preserved() {
    let temp = TempDir::new("diagnostics-retention");
    let logs_dir = temp.path.join("logs");
    let reports_dir = temp.path.join("reports");
    fs::create_dir_all(logs_dir.join("runs")).unwrap();
    fs::create_dir_all(&reports_dir).unwrap();
    for index in 0..22 {
        fs::create_dir_all(logs_dir.join("runs").join(format!("run-old-{index:02}"))).unwrap();
    }
    let user_report = reports_dir.join("keep-this-report.zip");
    fs::write(&user_report, b"user managed").unwrap();

    let diagnostics =
        RunDiagnostics::start_with_run_id(&logs_dir, &reports_dir, "0.8.4", "run-current").unwrap();

    let run_count = fs::read_dir(logs_dir.join("runs")).unwrap().count();
    assert_eq!(run_count, 20);
    assert!(diagnostics.backend_stdout_path().is_file());
    assert!(user_report.is_file());
}
