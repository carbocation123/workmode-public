use std::collections::BTreeMap;
use std::io;
use std::net::TcpListener;
use std::path::PathBuf;

use crate::paths::DesktopPaths;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BackendLaunchSpec {
    pub program: PathBuf,
    pub cwd: PathBuf,
    pub args: Vec<String>,
    pub env: BTreeMap<String, String>,
}

impl BackendLaunchSpec {
    pub fn new(paths: &DesktopPaths, port: u16, app_version: &str) -> Self {
        let mut env = BTreeMap::new();
        env.insert(
            "PYTHONPATH".to_string(),
            paths.site_packages.to_string_lossy().into_owned(),
        );
        env.insert(
            "WORKMODE_PUBLIC_DATA_DIR".to_string(),
            paths.data_dir.to_string_lossy().into_owned(),
        );
        env.insert(
            "WORKMODE_ENV_FILE".to_string(),
            paths.env_file.to_string_lossy().into_owned(),
        );
        env.insert("WORKMODE_APP_VERSION".to_string(), app_version.to_string());
        env.insert("WORKMODE_HOST".to_string(), "127.0.0.1".to_string());
        env.insert("WORKMODE_PORT".to_string(), port.to_string());
        env.insert(
            "WORKMODE_ALLOWED_ORIGINS".to_string(),
            "tauri://localhost,http://tauri.localhost,https://tauri.localhost".to_string(),
        );
        env.insert("PYTHONUTF8".to_string(), "1".to_string());
        env.insert("PYTHONDONTWRITEBYTECODE".to_string(), "1".to_string());

        Self {
            program: paths.python_exe.clone(),
            cwd: paths.backend_dir.clone(),
            args: vec![
                "-m".to_string(),
                "uvicorn".to_string(),
                "app.main:app".to_string(),
                "--host".to_string(),
                "127.0.0.1".to_string(),
                "--port".to_string(),
                port.to_string(),
            ],
            env,
        }
    }
}

pub fn select_free_port() -> io::Result<u16> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}
