pub mod backend;
pub mod migration;
pub mod paths;

use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use backend::{select_free_port, BackendLaunchSpec};
use migration::{destination_has_user_data, migrate_legacy_portable};
use paths::DesktopPaths;
use serde::Serialize;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Manager, RunEvent, State};

struct DesktopRuntime {
    port: u16,
    paths: DesktopPaths,
    child: Mutex<Option<Child>>,
    migration_available: AtomicBool,
}

impl DesktopRuntime {
    fn start_backend(&self, app_version: &str) -> Result<(), String> {
        let mut guard = self
            .child
            .lock()
            .map_err(|_| "后端进程锁已损坏".to_string())?;
        if guard
            .as_mut()
            .is_some_and(|child| child.try_wait().ok().flatten().is_none())
        {
            return Ok(());
        }
        self.paths
            .ensure_user_dirs()
            .map_err(|error| error.to_string())?;
        self.paths
            .validate_resources()
            .map_err(|error| error.to_string())?;
        ensure_env_file(&self.paths).map_err(|error| error.to_string())?;

        let spec = BackendLaunchSpec::new(&self.paths, self.port, app_version);
        let stdout = open_log(&self.paths.logs_dir.join("backend.out.log"))
            .map_err(|error| error.to_string())?;
        let stderr = open_log(&self.paths.logs_dir.join("backend.err.log"))
            .map_err(|error| error.to_string())?;
        let mut command = Command::new(&spec.program);
        command
            .args(&spec.args)
            .current_dir(&spec.cwd)
            .envs(&spec.env)
            .stdin(Stdio::null())
            .stdout(Stdio::from(stdout))
            .stderr(Stdio::from(stderr));
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x0800_0000);
        }
        let child = command
            .spawn()
            .map_err(|error| format!("启动本地后端失败：{error}"))?;
        *guard = Some(child);
        Ok(())
    }

    fn stop_backend(&self) {
        let Ok(mut guard) = self.child.lock() else {
            return;
        };
        if let Some(mut child) = guard.take() {
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                let pid = child.id().to_string();
                let mut command = Command::new("taskkill");
                command
                    .args(["/PID", pid.as_str(), "/T", "/F"])
                    .creation_flags(0x0800_0000);
                let _ = command.status();
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopBootstrap {
    api_base: String,
    version: String,
    data_dir: String,
    env_file: String,
    migration_available: bool,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopMigrationResult {
    copied_data: bool,
    copied_config: bool,
    relaunch_required: bool,
}

#[tauri::command]
async fn desktop_bootstrap(
    app: tauri::AppHandle,
    runtime: State<'_, DesktopRuntime>,
) -> Result<DesktopBootstrap, String> {
    let port = runtime.port;
    tauri::async_runtime::spawn_blocking(move || {
        wait_for_backend_health(port, Duration::from_secs(30))
    })
    .await
    .map_err(|error| format!("等待本地后端失败：{error}"))??;
    Ok(DesktopBootstrap {
        api_base: format!("http://127.0.0.1:{port}/api"),
        version: app.package_info().version.to_string(),
        data_dir: runtime.paths.data_dir.to_string_lossy().into_owned(),
        env_file: runtime.paths.env_file.to_string_lossy().into_owned(),
        migration_available: runtime.migration_available.load(Ordering::SeqCst),
    })
}

#[tauri::command]
fn migrate_legacy(
    legacy_root: String,
    runtime: State<'_, DesktopRuntime>,
) -> Result<DesktopMigrationResult, String> {
    if !runtime.migration_available.load(Ordering::SeqCst) {
        return Err("当前用户目录已经包含数据，不能再覆盖导入旧版。".to_string());
    }
    runtime.stop_backend();
    match migrate_legacy_portable(Path::new(&legacy_root), &runtime.paths.app_data_dir) {
        Ok(result) => {
            runtime.migration_available.store(false, Ordering::SeqCst);
            Ok(DesktopMigrationResult {
                copied_data: result.copied_data,
                copied_config: result.copied_config,
                relaunch_required: true,
            })
        }
        Err(error) => {
            let _ = runtime.start_backend(env!("CARGO_PKG_VERSION"));
            Err(error.to_string())
        }
    }
}

#[tauri::command]
fn desktop_prepare_update(runtime: State<'_, DesktopRuntime>) -> Result<(), String> {
    runtime.stop_backend();
    Ok(())
}

#[tauri::command]
fn desktop_recover_update(
    app: tauri::AppHandle,
    runtime: State<'_, DesktopRuntime>,
) -> Result<(), String> {
    let version = app.package_info().version.to_string();
    runtime.start_backend(&version)
}

fn open_log(path: &Path) -> std::io::Result<File> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    OpenOptions::new().create(true).append(true).open(path)
}

fn ensure_env_file(paths: &DesktopPaths) -> std::io::Result<()> {
    if paths.env_file.exists() {
        return Ok(());
    }
    fs::create_dir_all(&paths.config_dir)?;
    let example = paths.resource_dir.join("config").join(".env.example");
    if example.exists() {
        fs::copy(example, &paths.env_file)?;
    } else {
        File::create(&paths.env_file)?;
    }
    Ok(())
}

fn wait_for_backend_health(port: u16, timeout: Duration) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    let mut last_error = String::new();
    while Instant::now() < deadline {
        match TcpStream::connect_timeout(
            &format!("127.0.0.1:{port}")
                .parse()
                .map_err(|error| format!("端口解析失败：{error}"))?,
            Duration::from_millis(500),
        ) {
            Ok(mut stream) => {
                let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
                let request = format!(
                    "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
                );
                if stream.write_all(request.as_bytes()).is_ok() {
                    let mut response = String::new();
                    if stream.read_to_string(&mut response).is_ok()
                        && response.contains("200 OK")
                        && response.contains("workmode-public")
                    {
                        return Ok(());
                    }
                }
                last_error = "健康检查返回异常".to_string();
            }
            Err(error) => last_error = error.to_string(),
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    Err(format!("本地后端未在 30 秒内就绪：{last_error}"))
}

fn app_data_root(app: &tauri::App) -> Result<PathBuf, Box<dyn std::error::Error>> {
    Ok(app.path().local_data_dir()?.join("WorkmodePublic"))
}

fn resource_root(app: &tauri::App) -> Result<PathBuf, Box<dyn std::error::Error>> {
    Ok(app.path().resource_dir()?)
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn setup_tray(app: &tauri::App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "显示 Workmode Public", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "停止并退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;
    let mut builder = TrayIconBuilder::new()
        .tooltip("Workmode Public")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => show_main_window(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            show_main_window(app);
        }))
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let app_data = app_data_root(app)?;
            let resources = resource_root(app)?;
            let paths = DesktopPaths::new(app_data, resources);
            let migration_available = !destination_has_user_data(&paths.app_data_dir)?;
            let runtime = DesktopRuntime {
                port: select_free_port()?,
                paths,
                child: Mutex::new(None),
                migration_available: AtomicBool::new(migration_available),
            };
            runtime.start_backend(app.package_info().version.to_string().as_str())?;
            app.manage(runtime);
            setup_tray(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                window.app_handle().exit(0);
            }
        })
        .invoke_handler(tauri::generate_handler![
            desktop_bootstrap,
            migrate_legacy,
            desktop_prepare_update,
            desktop_recover_update
        ]);

    let app = builder
        .build(tauri::generate_context!())
        .expect("failed to build Workmode Public desktop application");
    app.run(|app_handle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            if let Some(runtime) = app_handle.try_state::<DesktopRuntime>() {
                runtime.stop_backend();
            }
        }
    });
}
