use std::fs;
use std::io;
use std::path::PathBuf;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DesktopPaths {
    pub app_data_dir: PathBuf,
    pub data_dir: PathBuf,
    pub config_dir: PathBuf,
    pub env_file: PathBuf,
    pub logs_dir: PathBuf,
    pub reports_dir: PathBuf,
    pub resource_dir: PathBuf,
    pub backend_dir: PathBuf,
    pub python_exe: PathBuf,
    pub site_packages: PathBuf,
}

impl DesktopPaths {
    pub fn new(app_data_dir: PathBuf, resource_dir: PathBuf) -> Self {
        let config_dir = app_data_dir.join("config");
        Self {
            data_dir: app_data_dir.join("data"),
            env_file: config_dir.join(".env"),
            logs_dir: app_data_dir.join("logs"),
            reports_dir: app_data_dir.join("reports"),
            backend_dir: resource_dir.join("backend"),
            python_exe: resource_dir
                .join("runtime")
                .join("python-base")
                .join("pythonw.exe"),
            site_packages: resource_dir
                .join("runtime")
                .join("backend-venv")
                .join("Lib")
                .join("site-packages"),
            app_data_dir,
            config_dir,
            resource_dir,
        }
    }

    pub fn ensure_user_dirs(&self) -> io::Result<()> {
        fs::create_dir_all(&self.data_dir)?;
        fs::create_dir_all(&self.config_dir)?;
        fs::create_dir_all(&self.logs_dir)?;
        fs::create_dir_all(&self.reports_dir)?;
        Ok(())
    }

    pub fn validate_resources(&self) -> io::Result<()> {
        for required in [
            &self.python_exe,
            &self.site_packages,
            &self.backend_dir.join("app").join("main.py"),
        ] {
            if !required.exists() {
                return Err(io::Error::new(
                    io::ErrorKind::NotFound,
                    format!("desktop resource is missing: {}", required.display()),
                ));
            }
        }
        Ok(())
    }
}
