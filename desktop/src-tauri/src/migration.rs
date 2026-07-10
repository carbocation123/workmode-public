use std::fmt;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug)]
pub enum MigrationError {
    InvalidSource(PathBuf),
    DestinationNotEmpty(PathBuf),
    Io(io::Error),
}

impl fmt::Display for MigrationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidSource(path) => write!(
                formatter,
                "所选目录不是有效的 Workmode Public 便携版：{}",
                path.display()
            ),
            Self::DestinationNotEmpty(path) => write!(
                formatter,
                "新版本已经包含用户数据，为避免覆盖，已拒绝迁移：{}",
                path.display()
            ),
            Self::Io(error) => write!(formatter, "迁移失败：{error}"),
        }
    }
}

impl std::error::Error for MigrationError {}

impl From<io::Error> for MigrationError {
    fn from(value: io::Error) -> Self {
        Self::Io(value)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MigrationResult {
    pub copied_data: bool,
    pub copied_config: bool,
}

pub fn destination_has_user_data(destination_app_data: &Path) -> Result<bool, MigrationError> {
    Ok(tree_has_user_content(&destination_app_data.join("data"))?
        || destination_app_data.join("config").join(".env").exists())
}

pub fn migrate_legacy_portable(
    legacy_root: &Path,
    destination_app_data: &Path,
) -> Result<MigrationResult, MigrationError> {
    let legacy_data = if legacy_root.join("data").join("work").is_dir() {
        legacy_root.join("data")
    } else if legacy_root.file_name().is_some_and(|name| name == "data")
        && legacy_root.join("work").is_dir()
    {
        legacy_root.to_path_buf()
    } else {
        return Err(MigrationError::InvalidSource(legacy_root.to_path_buf()));
    };

    let destination_data = destination_app_data.join("data");
    let destination_env = destination_app_data.join("config").join(".env");
    if tree_has_user_content(&destination_data)? || destination_env.exists() {
        return Err(MigrationError::DestinationNotEmpty(
            destination_app_data.to_path_buf(),
        ));
    }

    fs::create_dir_all(destination_app_data)?;
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let stage =
        destination_app_data.join(format!(".migration-stage-{}-{nonce}", std::process::id()));
    if stage.exists() {
        fs::remove_dir_all(&stage)?;
    }

    let operation = (|| -> Result<MigrationResult, MigrationError> {
        copy_dir_recursive(&legacy_data, &stage.join("data"))?;
        let legacy_env = legacy_root.join("config").join(".env");
        let copied_config = legacy_env.is_file();
        if copied_config {
            fs::create_dir_all(stage.join("config"))?;
            fs::copy(&legacy_env, stage.join("config").join(".env"))?;
        }

        if destination_data.exists() {
            fs::remove_dir_all(&destination_data)?;
        }
        fs::rename(stage.join("data"), &destination_data)?;
        if copied_config {
            fs::create_dir_all(destination_app_data.join("config"))?;
            fs::rename(stage.join("config").join(".env"), &destination_env)?;
        }
        Ok(MigrationResult {
            copied_data: true,
            copied_config,
        })
    })();

    if stage.exists() {
        let _ = fs::remove_dir_all(&stage);
    }
    operation
}

fn tree_has_user_content(path: &Path) -> io::Result<bool> {
    if !path.exists() {
        return Ok(false);
    }
    for entry in fs::read_dir(path)? {
        let entry = entry?;
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            if tree_has_user_content(&entry.path())? {
                return Ok(true);
            }
        } else if entry.metadata()?.len() > 0 {
            return Ok(true);
        }
    }
    Ok(false)
}

fn copy_dir_recursive(source: &Path, destination: &Path) -> io::Result<()> {
    fs::create_dir_all(destination)?;
    for entry in fs::read_dir(source)? {
        let entry = entry?;
        let source_path = entry.path();
        let destination_path = destination.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir_recursive(&source_path, &destination_path)?;
        } else {
            fs::copy(&source_path, &destination_path)?;
        }
    }
    Ok(())
}
