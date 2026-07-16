use regex::Regex;
use serde_json::json;
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, ZipWriter};

const MAX_RUNS: usize = 20;
const MAX_LOG_BYTES_PER_FILE: u64 = 512 * 1024;
const MAX_REPORT_CHARS: usize = 64 * 1024;

#[derive(Debug)]
pub enum DiagnosticsError {
    InvalidRunId,
    Io(std::io::Error),
    Json(serde_json::Error),
    Zip(zip::result::ZipError),
}

impl fmt::Display for DiagnosticsError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidRunId => write!(formatter, "invalid diagnostic run id"),
            Self::Io(error) => write!(formatter, "diagnostic file error: {error}"),
            Self::Json(error) => write!(formatter, "diagnostic manifest error: {error}"),
            Self::Zip(error) => write!(formatter, "diagnostic archive error: {error}"),
        }
    }
}

impl std::error::Error for DiagnosticsError {}

impl From<std::io::Error> for DiagnosticsError {
    fn from(value: std::io::Error) -> Self {
        Self::Io(value)
    }
}

impl From<serde_json::Error> for DiagnosticsError {
    fn from(value: serde_json::Error) -> Self {
        Self::Json(value)
    }
}

impl From<zip::result::ZipError> for DiagnosticsError {
    fn from(value: zip::result::ZipError) -> Self {
        Self::Zip(value)
    }
}

#[derive(Clone, Debug)]
pub struct DiagnosticBundle {
    pub path: PathBuf,
    pub run_id: String,
}

#[derive(Clone, Debug)]
pub struct RunDiagnostics {
    logs_dir: PathBuf,
    reports_dir: PathBuf,
    run_dir: PathBuf,
    run_id: String,
    app_version: String,
    started_at_unix_ms: u128,
}

impl RunDiagnostics {
    pub fn start(
        logs_dir: &Path,
        reports_dir: &Path,
        app_version: &str,
    ) -> Result<Self, DiagnosticsError> {
        let run_id = format!("run-{}-{}", unix_millis(), std::process::id());
        Self::start_with_run_id(logs_dir, reports_dir, app_version, &run_id)
    }

    pub fn start_with_run_id(
        logs_dir: &Path,
        reports_dir: &Path,
        app_version: &str,
        run_id: &str,
    ) -> Result<Self, DiagnosticsError> {
        if !valid_run_id(run_id) {
            return Err(DiagnosticsError::InvalidRunId);
        }
        let runs_dir = logs_dir.join("runs");
        let run_dir = runs_dir.join(run_id);
        fs::create_dir_all(&runs_dir)?;
        fs::create_dir_all(reports_dir)?;
        fs::create_dir(&run_dir)?;

        let diagnostics = Self {
            logs_dir: logs_dir.to_path_buf(),
            reports_dir: reports_dir.to_path_buf(),
            run_dir,
            run_id: run_id.to_string(),
            app_version: app_version.to_string(),
            started_at_unix_ms: unix_millis(),
        };
        for path in [
            diagnostics.desktop_log_path(),
            diagnostics.frontend_log_path(),
            diagnostics.backend_stdout_path(),
            diagnostics.backend_stderr_path(),
        ] {
            File::create(path)?;
        }
        diagnostics.write_manifest("running")?;
        diagnostics.append_desktop_event("info", "run_started", "desktop run started")?;
        cleanup_old_runs(&runs_dir, &diagnostics.run_dir)?;
        Ok(diagnostics)
    }

    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    pub fn backend_stdout_path(&self) -> PathBuf {
        self.run_dir.join("backend.out.log")
    }

    pub fn backend_stderr_path(&self) -> PathBuf {
        self.run_dir.join("backend.err.log")
    }

    pub fn append_frontend_event(
        &self,
        level: &str,
        category: &str,
        message: &str,
    ) -> Result<(), DiagnosticsError> {
        self.append_event(&self.frontend_log_path(), level, category, message)
    }

    pub fn append_desktop_event(
        &self,
        level: &str,
        category: &str,
        message: &str,
    ) -> Result<(), DiagnosticsError> {
        self.append_event(&self.desktop_log_path(), level, category, message)
    }

    pub fn mark_finished(&self) -> Result<(), DiagnosticsError> {
        self.append_desktop_event("info", "run_finished", "desktop run finished")?;
        self.write_manifest("finished")
    }

    pub fn generate_report(&self, report: &str) -> Result<DiagnosticBundle, DiagnosticsError> {
        let created_at = unix_millis();
        let safe_report = self.sanitize(&truncate_chars(report, MAX_REPORT_CHARS));
        let current_log = self.collect_current_run_log()?;
        let manifest = serde_json::to_string_pretty(&json!({
            "schema": "workmode-public-diagnostic/v1",
            "version": self.app_version,
            "run_id": self.run_id,
            "started_at_unix_ms": self.started_at_unix_ms,
            "created_at_unix_ms": created_at,
            "status": "running",
            "contents": ["report.md", "manifest.json", "current-run.log"],
            "privacy": "Secrets and local paths are redacted; user content is not intentionally collected."
        }))?;

        let filename = format!(
            "Workmode-Public-Error-{}-{}-{created_at}.zip",
            safe_label(&self.app_version),
            self.run_id
        );
        let target = self.reports_dir.join(filename);
        let temporary = target.with_extension("zip.tmp");
        let operation = (|| -> Result<(), DiagnosticsError> {
            let file = OpenOptions::new()
                .create_new(true)
                .write(true)
                .open(&temporary)?;
            let mut archive = ZipWriter::new(file);
            let options = SimpleFileOptions::default()
                .compression_method(CompressionMethod::Stored)
                .unix_permissions(0o600);
            write_zip_entry(&mut archive, "report.md", &safe_report, options)?;
            write_zip_entry(&mut archive, "manifest.json", &manifest, options)?;
            write_zip_entry(&mut archive, "current-run.log", &current_log, options)?;
            archive.finish()?;
            fs::rename(&temporary, &target)?;
            Ok(())
        })();
        if operation.is_err() && temporary.exists() {
            let _ = fs::remove_file(&temporary);
        }
        operation?;
        self.append_desktop_event("info", "report_generated", "diagnostic report generated")?;
        Ok(DiagnosticBundle {
            path: target,
            run_id: self.run_id.clone(),
        })
    }

    fn desktop_log_path(&self) -> PathBuf {
        self.run_dir.join("desktop.log")
    }

    fn frontend_log_path(&self) -> PathBuf {
        self.run_dir.join("frontend.log")
    }

    fn manifest_path(&self) -> PathBuf {
        self.run_dir.join("manifest.json")
    }

    fn write_manifest(&self, status: &str) -> Result<(), DiagnosticsError> {
        let manifest = serde_json::to_vec_pretty(&json!({
            "schema": "workmode-public-run/v1",
            "version": self.app_version,
            "run_id": self.run_id,
            "started_at_unix_ms": self.started_at_unix_ms,
            "status": status
        }))?;
        fs::write(self.manifest_path(), manifest)?;
        Ok(())
    }

    fn append_event(
        &self,
        path: &Path,
        level: &str,
        category: &str,
        message: &str,
    ) -> Result<(), DiagnosticsError> {
        let mut file = OpenOptions::new().create(true).append(true).open(path)?;
        let safe_message = truncate_chars(&self.sanitize(message), 8 * 1024);
        writeln!(
            file,
            "[{}] {} {} {}",
            unix_millis(),
            safe_label(level),
            safe_label(category),
            safe_message.replace(['\r', '\n'], " ")
        )?;
        Ok(())
    }

    fn collect_current_run_log(&self) -> Result<String, DiagnosticsError> {
        let mut combined = String::new();
        for (label, path) in [
            ("desktop", self.desktop_log_path()),
            ("frontend", self.frontend_log_path()),
            ("backend stdout", self.backend_stdout_path()),
            ("backend stderr", self.backend_stderr_path()),
        ] {
            combined.push_str(&format!("## {label}\n"));
            let content = read_tail(&path, MAX_LOG_BYTES_PER_FILE)?;
            if content.trim().is_empty() {
                combined.push_str("(empty)\n\n");
            } else {
                combined.push_str(&self.sanitize(&content));
                if !combined.ends_with('\n') {
                    combined.push('\n');
                }
                combined.push('\n');
            }
        }
        Ok(combined)
    }

    fn sanitize(&self, value: &str) -> String {
        let mut sanitized = value.to_string();
        if let Some(app_data_dir) = self.logs_dir.parent() {
            sanitized = sanitized.replace(app_data_dir.to_string_lossy().as_ref(), "%APP_DATA%");
        }
        if let Some(profile) = std::env::var_os("USERPROFILE") {
            sanitized = sanitized.replace(
                PathBuf::from(profile).to_string_lossy().as_ref(),
                "%USER_HOME%",
            );
        }
        sanitized = secret_assignment_regex()
            .replace_all(&sanitized, "$1$2[REDACTED]")
            .into_owned();
        sanitized = secret_key_regex()
            .replace_all(&sanitized, "[REDACTED_SECRET]")
            .into_owned();
        sanitized = windows_path_regex()
            .replace_all(&sanitized, "%LOCAL_PATH%")
            .into_owned();
        sanitized = unc_path_regex()
            .replace_all(&sanitized, "%LOCAL_PATH%")
            .into_owned();
        sanitized
    }
}

fn unix_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

fn valid_run_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 80
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}

fn safe_label(value: &str) -> String {
    let label: String = value
        .chars()
        .filter(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.')
        })
        .take(80)
        .collect();
    if label.is_empty() {
        "unknown".to_string()
    } else {
        label
    }
}

fn truncate_chars(value: &str, limit: usize) -> String {
    value.chars().take(limit).collect()
}

fn secret_assignment_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(
            r"(?i)(authorization|x-workmode-token|api[_-]?key|token|password|secret)(\s*[:=]\s*)(?:bearer\s+)?[^\s&;,]+",
        )
        .expect("secret assignment regex")
    })
}

fn secret_key_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| Regex::new(r"(?i)\bsk-[a-z0-9_-]{12,}\b").expect("secret key regex"))
}

fn windows_path_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(r#"(?i)\b[A-Z]:[\\/][^\r\n\"'<>|?&]*"#).expect("windows path regex")
    })
}

fn unc_path_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| Regex::new(r#"\\\\[^\r\n\"'<>|?&]*"#).expect("UNC path regex"))
}

fn read_tail(path: &Path, max_bytes: u64) -> Result<String, DiagnosticsError> {
    let mut file = File::open(path)?;
    let length = file.metadata()?.len();
    if length > max_bytes {
        file.seek(SeekFrom::Start(length - max_bytes))?;
    }
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)?;
    let mut value = String::from_utf8_lossy(&bytes).into_owned();
    if length > max_bytes {
        value.insert_str(0, "[earlier log content omitted]\n");
    }
    Ok(value)
}

fn write_zip_entry(
    archive: &mut ZipWriter<File>,
    name: &str,
    content: &str,
    options: SimpleFileOptions,
) -> Result<(), DiagnosticsError> {
    archive.start_file(name, options)?;
    archive.write_all(content.as_bytes())?;
    Ok(())
}

fn cleanup_old_runs(runs_dir: &Path, current_run: &Path) -> Result<(), DiagnosticsError> {
    let mut run_dirs: Vec<PathBuf> = fs::read_dir(runs_dir)?
        .filter_map(Result::ok)
        .filter_map(|entry| {
            entry
                .file_type()
                .ok()
                .filter(|file_type| file_type.is_dir())
                .map(|_| entry.path())
        })
        .collect();
    run_dirs.sort();
    let mut excess = run_dirs.len().saturating_sub(MAX_RUNS);
    for path in run_dirs {
        if excess == 0 {
            break;
        }
        if path != current_run {
            fs::remove_dir_all(path)?;
            excess -= 1;
        }
    }
    Ok(())
}
