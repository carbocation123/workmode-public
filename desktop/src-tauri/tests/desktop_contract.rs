use std::fs;
use std::net::TcpListener;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use workmode_public_lib::backend::{select_free_port, BackendLaunchSpec};
use workmode_public_lib::migration::{migrate_legacy_portable, MigrationError};
use workmode_public_lib::paths::DesktopPaths;

fn temp_dir(label: &str) -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("workmode-public-{label}-{nonce}"));
    fs::create_dir_all(&path).expect("create temp directory");
    path
}

#[test]
fn desktop_paths_keep_user_data_outside_install_resources() {
    let app_data = PathBuf::from(r"C:\Users\tester\AppData\Roaming\WorkmodePublic");
    let resources = PathBuf::from(r"C:\Program Files\Workmode Public\resources");

    let paths = DesktopPaths::new(app_data.clone(), resources.clone());

    assert_eq!(paths.data_dir, app_data.join("data"));
    assert_eq!(paths.env_file, app_data.join("config").join(".env"));
    assert_eq!(paths.logs_dir, app_data.join("logs"));
    assert_eq!(paths.reports_dir, app_data.join("reports"));
    assert_eq!(paths.backend_dir, resources.join("backend"));
    assert_eq!(
        paths.python_exe,
        resources
            .join("runtime")
            .join("python-base")
            .join("pythonw.exe")
    );
}

#[test]
fn backend_launch_spec_uses_dynamic_port_and_user_owned_paths() {
    let root = temp_dir("backend-spec");
    let app_data = root.join("app-data");
    let resources = root.join("resources");
    let paths = DesktopPaths::new(app_data.clone(), resources.clone());
    let spec = BackendLaunchSpec::new(&paths, 43123, "0.2.0");

    assert_eq!(spec.program, paths.python_exe);
    assert_eq!(spec.cwd, paths.backend_dir);
    assert_eq!(
        spec.args,
        vec![
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "43123",
            "--no-access-log"
        ]
    );
    assert_eq!(
        spec.env.get("WORKMODE_PUBLIC_DATA_DIR"),
        Some(&paths.data_dir.to_string_lossy().into_owned())
    );
    assert_eq!(
        spec.env.get("WORKMODE_ENV_FILE"),
        Some(&paths.env_file.to_string_lossy().into_owned())
    );
    assert_eq!(
        spec.env.get("WORKMODE_APP_VERSION"),
        Some(&"0.2.0".to_string())
    );
    assert_eq!(
        spec.env.get("PYTHONDONTWRITEBYTECODE"),
        Some(&"1".to_string())
    );
}

#[test]
fn selected_backend_port_can_be_bound_immediately() {
    let port = select_free_port().expect("select port");
    let listener = TcpListener::bind(("127.0.0.1", port)).expect("bind selected port");
    assert_eq!(listener.local_addr().expect("address").port(), port);
}

#[test]
fn updater_lifecycle_commands_are_registered_for_the_frontend() {
    let source = include_str!("../src/lib.rs");

    assert!(source.contains("fn desktop_prepare_update("));
    assert!(source.contains("fn desktop_recover_update("));
    assert!(source.contains("desktop_prepare_update,"));
    assert!(source.contains("desktop_recover_update"));
}

#[test]
fn legacy_migration_copies_data_and_config_without_touching_source() {
    let root = temp_dir("migration");
    let legacy = root.join("workmode-public-0.1.3-win-x64");
    let destination = root.join("new-app-data");
    fs::create_dir_all(legacy.join("data").join("work")).expect("legacy data");
    fs::create_dir_all(legacy.join("config")).expect("legacy config");
    fs::write(
        legacy.join("data").join("work").join("active.json"),
        "{\"slug\":\"demo\"}",
    )
    .expect("write data");
    fs::write(
        legacy.join("config").join(".env"),
        "WORKMODE_MODEL_NAME=demo\n",
    )
    .expect("write env");

    let result = migrate_legacy_portable(&legacy, &destination).expect("migration succeeds");

    assert!(result.copied_data);
    assert!(result.copied_config);
    assert_eq!(
        fs::read_to_string(destination.join("data").join("work").join("active.json"))
            .expect("new data"),
        "{\"slug\":\"demo\"}"
    );
    assert!(legacy
        .join("data")
        .join("work")
        .join("active.json")
        .exists());
    assert!(legacy.join("config").join(".env").exists());
}

#[test]
fn legacy_migration_refuses_to_merge_into_existing_user_data() {
    let root = temp_dir("migration-conflict");
    let legacy = root.join("legacy");
    let destination = root.join("new-app-data");
    fs::create_dir_all(legacy.join("data").join("work")).expect("legacy data");
    fs::create_dir_all(destination.join("data").join("work")).expect("existing data");
    fs::write(
        destination.join("data").join("work").join("existing.json"),
        "keep",
    )
    .expect("existing file");

    let error = migrate_legacy_portable(&legacy, &destination).expect_err("must refuse merge");

    assert!(matches!(error, MigrationError::DestinationNotEmpty(_)));
    assert_eq!(
        fs::read_to_string(destination.join("data").join("work").join("existing.json"))
            .expect("preserved"),
        "keep"
    );
}

#[test]
fn legacy_migration_allows_backend_created_empty_skeleton() {
    let root = temp_dir("migration-skeleton");
    let legacy = root.join("legacy");
    let destination = root.join("new-app-data");
    fs::create_dir_all(legacy.join("data").join("work")).expect("legacy data");
    fs::write(
        legacy.join("data").join("work").join("active.json"),
        "{\"slug\":\"demo\"}",
    )
    .expect("legacy active");
    fs::create_dir_all(destination.join("data").join("work").join("projects"))
        .expect("empty projects");
    fs::create_dir_all(destination.join("data").join("work").join("sessions"))
        .expect("empty sessions");
    fs::create_dir_all(destination.join("data").join("work").join("memory")).expect("empty memory");
    fs::write(
        destination
            .join("data")
            .join("work")
            .join("memory")
            .join("global.md"),
        "",
    )
    .expect("empty global memory");

    migrate_legacy_portable(&legacy, &destination).expect("empty skeleton is replaceable");

    assert!(destination
        .join("data")
        .join("work")
        .join("active.json")
        .exists());
}
